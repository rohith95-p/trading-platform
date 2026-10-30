"""resilience.py -- keep-alive and safety helpers for main_loop.

None of this changes trading behaviour. It exists so the bot cannot:
  - run as two instances at once (lockfile)
  - keep trading after the operator says stop (STOP file kill switch)
  - die silently with no trace (heartbeat file)
  - start against the wrong account / a read-only connection (startup check)
  - spin forever on a dropped MT5 connection (reconnect)
  - re-fire a signal on the candle it was restarted during (state persistence)

Added rohith-2, 2026-09-03. See docs/research/REAL_MONEY_READINESS.md part IV.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

log = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOGS = os.path.join(_ROOT, "logs")

LOCK_FILE = os.path.join(_LOGS, "main_loop.lock")
STOP_FILE = os.path.join(_ROOT, "STOP")
HEARTBEAT_FILE = os.path.join(_LOGS, "heartbeat")
STATUS_FILE = os.path.join(_LOGS, "status.json")   # main_loop -> watchdog: account snapshot for the hourly pulse
STATE_FILE = os.path.join(_LOGS, "loop_state.json")

# Expected account identity -- refuse to start against anything else.
EXPECTED_LOGIN = int(os.environ.get("MT5_LOGIN", 198874999))
BALANCE_RANGE = (20.0, 10000.0)  # wide: catches wrong-account, not normal swings


# ---------------------------------------------------------------------------
# Single-instance lock
# ---------------------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (OSError, Exception):
        return False


def acquire_lock() -> bool:
    """True if we now hold the lock. False if another live instance has it."""
    os.makedirs(_LOGS, exist_ok=True)
    if os.path.exists(LOCK_FILE):
        try:
            old = int(open(LOCK_FILE).read().strip())
        except (ValueError, OSError):
            old = -1
        if _pid_alive(old):
            log.error(f"LOCK: main_loop PID {old} is already running. Refusing to start.")
            return False
        log.warning(f"LOCK: stale lock (PID {old} dead) -- taking over.")
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_lock() -> None:
    try:
        if os.path.exists(LOCK_FILE) and open(LOCK_FILE).read().strip() == str(os.getpid()):
            os.remove(LOCK_FILE)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

def kill_switch_active() -> bool:
    return os.path.exists(STOP_FILE)


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

def heartbeat() -> None:
    try:
        with open(HEARTBEAT_FILE, "w") as f:
            f.write(datetime.now(IST).isoformat())
    except OSError:
        pass


def write_status(snapshot: dict) -> None:
    """Atomically publish main_loop's latest account snapshot (read by the watchdog)."""
    try:
        tmp = STATUS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({**snapshot, "ts": time.time()}, f)
        os.replace(tmp, STATUS_FILE)
    except OSError:
        pass


def read_status() -> dict | None:
    try:
        with open(STATUS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Loop-state persistence (so a restart mid-candle can't re-fire)
# ---------------------------------------------------------------------------

def save_state(last_fired_candle: dict, drawdown_shutdown: bool,
               shutdown_date: Any, executed_dedup_keys: Optional[list] = None) -> None:
    try:
        data: dict[str, Any] = {
            "last_fired_candle": last_fired_candle,
            "drawdown_shutdown": drawdown_shutdown,
            "shutdown_date": str(shutdown_date) if shutdown_date else None,
            "saved_at": datetime.now(IST).isoformat(),
        }
        if executed_dedup_keys is not None:
            data["executed_dedup_keys"] = executed_dedup_keys
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except OSError:
        pass


def load_state() -> dict[str, Any]:
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
        if isinstance(data, dict):
            log.info(f"STATE: restored from {data.get('saved_at')}")
            return data
        return {}
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# Startup safety check
# ---------------------------------------------------------------------------

def startup_safety_check(mt5: Any, symbol: str) -> bool:
    """All must pass or the bot refuses to start."""
    ok = True
    info = mt5.account_info()
    if info is None:
        log.error("SAFETY: account_info() is None.")
        return False

    if EXPECTED_LOGIN and info.login != EXPECTED_LOGIN:
        log.error(f"SAFETY: connected to account {info.login}, expected {EXPECTED_LOGIN}.")
        ok = False
    if not getattr(info, "trade_allowed", True):
        log.error("SAFETY: trade_allowed=False -- investor password or AutoTrading off.")
        ok = False
    if not (BALANCE_RANGE[0] <= info.balance <= BALANCE_RANGE[1]):
        log.error(f"SAFETY: balance ${info.balance} outside expected {BALANCE_RANGE}.")
        ok = False

    si = mt5.symbol_info(symbol)
    if si is None:
        log.error(f"SAFETY: symbol {symbol} not found on this server.")
        ok = False
    elif not si.visible and not mt5.symbol_select(symbol, True):
        log.error(f"SAFETY: could not add {symbol} to Market Watch.")
        ok = False

    if ok:
        log.info(f"SAFETY: OK -- account {info.login}, balance ${info.balance:.2f}, {symbol} tradeable.")
    return ok


def check_connection_and_freshness(mt5: Any, rates: Any = None) -> tuple[bool, str]:
    """Check both MT5 terminal connection and rate feed freshness.
    Returns (is_healthy, reason_str).
    """
    try:
        t_info = mt5.terminal_info()
        if t_info is None:
            return False, "MT5 terminal_info() is None (terminal not responding)"
        if not getattr(t_info, "connected", False):
            return False, "MT5 terminal is disconnected from broker (connected=False)"
    except Exception as e:
        return False, f"MT5 terminal_info check exception: {e}"

    if rates is not None and len(rates) > 0:
        try:
            last_bar_time = int(rates["time"][-1])
            age_sec = time.time() - last_bar_time
            # During active market hours (weekday), if last bar is older than 25 minutes, it's stale
            if age_sec > 25 * 60:
                return False, f"MT5 candle feed is STALE: last candle is {age_sec / 60:.1f} minutes old"
        except Exception as e:
            return False, f"Rates freshness check exception: {e}"

    return True, "OK"


# ---------------------------------------------------------------------------
# MT5 reconnect
# ---------------------------------------------------------------------------

def note_fetch_result(mt5: Any, got_data: bool, fail_count: int, reason: str = "") -> int:
    """Track consecutive failed data fetches; reconnect after 3.

    Returns the updated fail count (0 once data flows again).
    """
    if got_data:
        return 0
    fail_count += 1
    if fail_count == 3 or (fail_count > 3 and fail_count % 3 == 0):
        msg = f"MT5: {fail_count} consecutive empty/stale fetches ({reason or 'no data'}) -- attempting reconnect."
        log.warning(msg)
        try:
            from src.core import alerts
            alerts.send(f"MT5 connection lost: reconnecting (try {fail_count // 3})", alerts.WARN,
                        context={"why": reason or "no data"},
                        action="Nothing yet: the bot retries by itself and restarts after 8 min.")
        except Exception:
            pass
        try:
            mt5.shutdown()
        except Exception:
            pass
        time.sleep(2)
        if mt5.initialize():
            log.info("MT5: reconnected.")
            return 0
        log.error("MT5: reconnect attempt failed -- will retry.")
    return fail_count


# ---------------------------------------------------------------------------
# External heartbeat push (Phase 3.4 of PRODUCTION_READINESS_PLAN.md)
# ---------------------------------------------------------------------------

def push_heartbeat_external() -> None:
    """Push a GET ping to an external uptime monitor (e.g. healthchecks.io).

    Configure via: ULTRA_HEARTBEAT_URL=https://hc-ping.com/<uuid>
    Without the env var this is a silent no-op. Failures are logged at DEBUG
    level and never propagate -- a heartbeat failure must not stop trading.

    Call from main_loop.py on every scan alongside resilience.heartbeat().
    """
    url = os.environ.get("ULTRA_HEARTBEAT_URL")
    if not url:
        return
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=8) as resp:
            if resp.status < 200 or resp.status >= 300:
                log.debug(f"External heartbeat: unexpected status {resp.status}")
    except Exception as e:
        log.debug(f"External heartbeat push failed (non-fatal): {e}")

