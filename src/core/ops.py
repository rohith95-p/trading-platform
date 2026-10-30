"""ops.py -- operational safety helpers for the live demo bot (added 2026-10-18).

* HALT LATCH: a halt is stored in a file outside process memory (logs/HALT_LATCH.json). A crash or restart cannot clear it;
  only a deliberate operator action (`python -m scripts.halt clear --note ...`) does. main_loop refuses to
  start while it is set.
* MEASUREMENT-ONLY mode (env ULTRA_MEASURE_ONLY=1): the bot keeps scanning, logging and reconciling but sends NO orders.
* EXTERNAL HEARTBEAT: a status payload is POSTed (in a daemon thread, never blocking the loop) to ULTRA_HEARTBEAT_URL
  (healthchecks.io / Uptime Kuma / any HTTPS endpoint). The dead-man alert is configured at the external service: it fires
  when pings stop, so it still works if the PC sleeps, crashes or loses network.

Nothing here places or modifies an order.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HALT_FILE = os.path.join(_ROOT, "logs", "HALT_LATCH.json")
PUSH_MIN_INTERVAL_S = 30.0
PUSH_TIMEOUT_S = 4.0

BUILD: Dict[str, Any] = {"fingerprint": None}   # filled at startup by main_loop
_last_push = 0.0
_commit_cache: Optional[str] = None


# ---------------------------------------------------------------- halt latch
def set_halt(reason: str, source: str = "unknown", notify: bool = True,
             expires_utc: Optional[datetime] = None) -> None:
    """Latch a halt. Idempotent: an existing latch is never overwritten (first cause is kept).

    expires_utc: the latch clears itself at that instant (owner 2026-10-30: an Atlas stop caused only by the
    daily-loss limit resumes at the next Atlas day). Without it, only `halt clear` removes the latch.
    """
    try:
        if os.path.exists(HALT_FILE):
            return
        os.makedirs(os.path.dirname(HALT_FILE), exist_ok=True)
        rec = {"reason": str(reason), "source": source, "set_at_utc": datetime.now(timezone.utc).isoformat()}
        if expires_utc is not None:
            rec["expires_utc"] = expires_utc.astimezone(timezone.utc).isoformat()
        tmp = HALT_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f)
        os.replace(tmp, HALT_FILE)
        log.error(f"HALT LATCHED ({source}): {reason}. Clear with: python -m scripts.halt clear --note \"...\"")
        if notify:                                     # tell the owner (a halt used to be log-only: 2026-10-21)
            try:
                from src.core import alerts
                alerts.send("Bot halted: no new trades until you clear it", alerts.CRITICAL,
                            context={"why": reason, "by": source},
                            action='RDP in, check MT5, then run: venv\\Scripts\\python.exe -m scripts.halt '
                                   'clear --note "checked"')
            except Exception:
                pass
    except OSError as e:                               # never raise from a safety path
        log.error(f"could not write halt latch: {e}")


def halt_status() -> Optional[Dict[str, Any]]:
    """None if not halted. A corrupt latch file still counts as halted (fail closed)."""
    if not os.path.exists(HALT_FILE):
        return None
    try:
        with open(HALT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"reason": "latch file unreadable", "source": "corrupt"}
    except (OSError, ValueError):
        return {"reason": "latch file unreadable", "source": "corrupt"}
    exp = data.get("expires_utc")
    if exp:
        try:
            expired = datetime.now(timezone.utc) >= datetime.fromisoformat(exp)
        except (TypeError, ValueError):
            return data                                # unreadable expiry: stay halted (fail closed)
        if expired:
            try:
                _archive_latch(data, f"auto-expired at {exp}")
            except RuntimeError:
                return data
            log.warning(f"halt latch auto-expired ({data.get('reason')})")
            return None
    return data


def clear_halt(note: str) -> bool:
    """Deliberate operator action. A non-empty note is mandatory; the cleared latch is archived next to the file."""
    if not note or not note.strip():
        raise ValueError("clearing a halt requires a non-empty operator note")
    st = halt_status()
    if st is None:
        return False
    _archive_latch(st, note.strip())
    return True


def _archive_latch(st: Dict[str, Any], note: str) -> None:
    try:
        archive = HALT_FILE.replace(".json", f".cleared_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
        with open(archive, "w", encoding="utf-8") as f:
            json.dump({"cleared_latch": st, "operator_note": note,
                       "cleared_at_utc": datetime.now(timezone.utc).isoformat()}, f)
        os.remove(HALT_FILE)
    except OSError as e:
        raise RuntimeError(f"could not clear halt latch: {e}")


# ---------------------------------------------------------------- measurement-only
def measure_only() -> bool:
    return os.environ.get("ULTRA_MEASURE_ONLY", "").strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------- heartbeat
def git_commit() -> str:
    global _commit_cache
    if _commit_cache is None:
        try:
            _commit_cache = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_ROOT, capture_output=True,
                                           text=True, timeout=5).stdout.strip() or "unknown"
        except Exception:
            _commit_cache = "unknown"
    return _commit_cache


def rule_state(drawdown_shutdown: bool = False) -> str:
    if halt_status() is not None:
        return "HALT_LATCHED"
    if drawdown_shutdown:
        return "DAILY_SHUTDOWN"
    if measure_only():
        return "MEASURE_ONLY"
    return "NORMAL"


def build_status(*, account: str, scan_interval_s: Optional[float], quote_age_s: Optional[float],
                 open_positions: Optional[int], pending_orders: Optional[int], daily_pnl: Optional[float],
                 drawdown_shutdown: bool = False, extra: Optional[dict] = None) -> Dict[str, Any]:
    payload = {
        "bot": "ultra_core", "account": account, "commit": git_commit(), "config_fingerprint": BUILD.get("fingerprint"),
        "scan_interval_s": None if scan_interval_s is None else round(scan_interval_s, 1),
        "quote_age_s": None if quote_age_s is None else round(quote_age_s, 1),
        "open_positions": open_positions, "pending_orders": pending_orders,
        "daily_pnl": None if daily_pnl is None else round(daily_pnl, 2),
        "rule_state": rule_state(drawdown_shutdown), "measure_only": measure_only(),
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if extra:
        payload.update(extra)
    return payload


def _post(url: str, payload: dict) -> None:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=PUSH_TIMEOUT_S) as resp:
            if resp.status < 200 or resp.status >= 300:
                log.debug(f"heartbeat: unexpected status {resp.status}")
    except Exception as e:                              # a heartbeat failure must never stop trading
        log.debug(f"heartbeat push failed (non-fatal): {e}")


def push_status(payload: dict, *, force: bool = False) -> bool:
    """POST the payload in a daemon thread. Returns True if a push was started. Rate-limited to one per 30 s.
    Halt/shutdown states are reported to healthchecks-style endpoints on `<url>/fail` so they alert immediately."""
    global _last_push
    url = os.environ.get("ULTRA_HEARTBEAT_URL", "").strip()
    now = time.time()
    if not url or (not force and now - _last_push < PUSH_MIN_INTERVAL_S):
        return False
    _last_push = now
    if payload.get("rule_state") in ("HALT_LATCHED",) and "hc-ping.com" in url and not url.rstrip("/").endswith("/fail"):
        url = url.rstrip("/") + "/fail"
    threading.Thread(target=_post, args=(url, payload), daemon=True).start()
    return True
