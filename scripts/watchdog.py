"""watchdog.py -- restart main_loop if it dies.

Run this in a second terminal (or a Windows Task Scheduler task set to run at
logon). It checks every 30s that main_loop is alive via its lockfile PID and its
heartbeat file. If the process is gone OR the heartbeat is stale > 5 min, it
relaunches main_loop.

    python -m scripts.watchdog

Also (2026-10-30): stands down while the halt latch is set (one message, no
restart loop), and sends a silent hourly pulse built from logs/status.json,
which main_loop rewrites every scan -- so a missing pulse means trouble.
"""

import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core import resilience  # noqa: E402
from src.core import alerts  # noqa: E402
from src.core import trade_log  # noqa: E402
from src.core import ops  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
CHECK_EVERY = 30
HEARTBEAT_MAX_AGE = 300  # seconds
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(ROOT, "venv", "Scripts", "python.exe")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable
# Owner 2026-10-30: "turn off protector". ULTRA_PROTECT_PROFIT=0 (in .env.local,
# loaded by the alerts import) stops the watchdog starting protect_profit.py and
# kills one already running; trades then exit only at their SL/TP.
PROTECT_PROFIT_ON = os.getenv("ULTRA_PROTECT_PROFIT", "1") != "0"
PULSE_EVERY_H = int(os.getenv("ULTRA_PULSE_EVERY_H", "1"))   # 0 = no hourly pulse
STATUS_MAX_AGE = 600  # seconds; an older logs/status.json means main_loop is not scanning


def _now():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def _alert(msg: str, severity: str = alerts.WARN, action: str | None = None, **details):
    """Notification channel. Sends via Telegram/webhook if configured, and records to logs/alerts.log."""
    alerts.send(msg, severity=severity, context=details, action=action)


def _get_last_error_from_log(max_lines: int = 25) -> str:
    """Read recent error / traceback lines from logs/main_loop.log."""
    log_path = os.path.join(ROOT, "logs", "main_loop.log")
    if not os.path.exists(log_path):
        return "No main_loop.log found."
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        tail = [line.strip() for line in lines[-max_lines:] if line.strip()]
        error_lines = [l for l in tail if "ERROR" in l or "Traceback" in l or "Exception" in l]
        if error_lines:
            return "\n".join(tail[-10:])
        return "\n".join(tail[-5:]) if tail else "Log empty."
    except Exception as e:
        return f"Could not read log: {e}"


def handle_main_loop_crash(consecutive_restarts: int, wait_seconds: int = 5) -> int:
    """Handle main_loop crash: log traceback, alert, record in trade log, and restart.
    Fires high-priority alert and exits non-zero if restart fails after 3 attempts.
    """
    consecutive_restarts += 1
    traceback_snippet = _get_last_error_from_log()
    log_msg = (
        f"CRASH DETECTED: main_loop is down. Restart attempt #{consecutive_restarts}/3.\n"
        f"Last log snippet:\n{traceback_snippet}"
    )
    print(f"[{_now()}] {log_msg}")

    if consecutive_restarts >= 3:
        fatal_msg = (
            f"FATAL: main_loop restart failed after {consecutive_restarts} attempts! "
            f"Watchdog terminating non-zero.\nTraceback snippet:\n{traceback_snippet}"
        )
        _alert("Bot is down: 3 restarts failed, watchdog gave up", severity=alerts.CRITICAL,
               action="RDP into the VPS, check MT5 is open and logged in, then run start_ultra_core.bat.")
        trade_log.lifecycle("watchdog_fatal_exit", attempts=consecutive_restarts, error=traceback_snippet)
        sys.exit(1)

    last = [l for l in traceback_snippet.splitlines() if "ERROR" in l or "Traceback" in l or "Exception" in l]
    _alert(f"Bot stopped: restarting it (attempt {consecutive_restarts}/3)",
           severity=alerts.INFO if consecutive_restarts == 1 else alerts.WARN,
           action=None if consecutive_restarts == 1 else "Nothing yet. If a third one comes, RDP in.",
           last_error=re.sub(r"^\S+ \S+ \S+ \S+ IST ", "", last[-1])[:80] if last else "none logged")
    trade_log.lifecycle("watchdog_restart", attempt=consecutive_restarts, error=traceback_snippet)

    time.sleep(wait_seconds)

    if os.path.exists(resilience.LOCK_FILE):
        try:
            old_pid = int(open(resilience.LOCK_FILE).read().strip())
            if not resilience._pid_alive(old_pid):
                os.remove(resilience.LOCK_FILE)
        except Exception:
            pass

    _start_loop()
    return consecutive_restarts


def _protect_profit_alive() -> bool:
    """Check if protect_profit.py is running without relying on deprecated wmic."""
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline = " ".join(proc.info.get('cmdline') or [])
                if "protect_profit" in cmdline:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False
    except Exception:
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | Select-Object -ExpandProperty CommandLine"],
                capture_output=True, text=True, timeout=10)
            return "protect_profit" in (out.stdout or "")
        except Exception:
            return True  # can't tell -> don't cry wolf


def _stop_protect_profit() -> None:
    """Kill any running protect_profit.py (used when ULTRA_PROTECT_PROFIT=0)."""
    try:
        import psutil
        for proc in psutil.process_iter(['cmdline']):
            try:
                if "protect_profit" in " ".join(proc.info.get('cmdline') or []):
                    print(f"[{_now()}] protector switched off -- stopping protect_profit.py (PID {proc.pid})")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        print(f"[{_now()}] could not stop protect_profit.py: {e}")


def _money(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}${abs(x):,.2f}"


def build_pulse(status: dict | None, hb_age: float | None, halt: dict | None, now_ist: datetime) -> alerts.Alert:
    """The hourly 'is it alive' message, from main_loop's status.json snapshot."""
    when = now_ist.strftime("%H:%M")
    if halt and halt.get("expires_utc"):
        return alerts.Alert(f"Bot paused · {when}", (f"Why: {halt.get('reason', '?')}",
                                                     f"Resumes by itself at {_ist_time(halt['expires_utc'])}"),
                            alerts.INFO, icon="⏸")
    if halt:
        return alerts.Alert(f"Bot halted · {when}", (f"Why: {halt.get('reason', '?')}",),
                            alerts.INFO, icon="⛔",
                            action='Clear it on the VPS: venv\\Scripts\\python.exe -m scripts.halt clear --note "checked"')
    fresh = status is not None and time.time() - float(status.get("ts", 0)) < STATUS_MAX_AGE
    if not fresh or hb_age is None or hb_age > HEARTBEAT_MAX_AGE:
        return alerts.Alert(f"Bot not responding · {when}",
                            ("No scan in the last few minutes. The watchdog is restarting it.",),
                            alerts.WARN, action="If the next pulse says the same, RDP in and check MT5.")
    s = status
    n = int(s.get("open", 0))
    lines = [f"Balance ${s['balance']:,.2f} · Equity ${s['equity']:,.2f}",
             f"Today {_money(s.get('today', 0.0))} · {n} open trade{'' if n == 1 else 's'}"
             + (f" ({_money(s.get('floating', 0.0))})" if n else "")]
    if "trailing_floor" in s and "daily_floor" in s:
        lines.append(f"Atlas room: {_money(s['equity'] - s['trailing_floor'])} total · "
                     f"{_money(s['equity'] - s['daily_floor'])} today")
    return alerts.Alert(f"All good · {when}", tuple(lines), alerts.INFO, icon="💚")


def _ist_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(IST).strftime("%a %H:%M IST")
    except (TypeError, ValueError):
        return iso


def _pulse_due(now_ist: datetime, sent: set) -> bool:
    """Once per PULSE_EVERY_H hours, at the top of the hour, Mon-Fri IST."""
    if PULSE_EVERY_H <= 0 or now_ist.weekday() >= 5 or now_ist.hour % PULSE_EVERY_H or now_ist.minute >= 10:
        return False
    key = now_ist.strftime("%Y-%m-%d %H")
    if key in sent:
        return False
    sent.add(key)
    return True


def _heartbeat_age() -> float | None:
    try:
        return time.time() - os.path.getmtime(resilience.HEARTBEAT_FILE)
    except OSError:
        return None


def _loop_alive() -> bool:
    if not os.path.exists(resilience.LOCK_FILE):
        return False
    try:
        pid = int(open(resilience.LOCK_FILE).read().strip())
    except (ValueError, OSError):
        return False
    if not resilience._pid_alive(pid):
        return False
    # process is alive -- is it actually working?
    try:
        age = time.time() - os.path.getmtime(resilience.HEARTBEAT_FILE)
        if age > HEARTBEAT_MAX_AGE:
            print(f"[{_now()}] heartbeat stale ({age:.0f}s) though PID {pid} is alive "
                  f"-- HUNG. force-killing {pid}.")
            _force_kill(pid)
            return False
    except OSError:
        return False
    return True


def _force_kill(pid):
    """Kill a hung process so acquire_lock() won't refuse the restart."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True)
        else:
            os.kill(pid, 9)
        time.sleep(2)
    except Exception as e:
        print(f"[{_now()}] force-kill failed: {e}")


def _start_loop():
    print(f"[{_now()}] starting main_loop ...")
    log_path = os.path.join(ROOT, "logs", "main_loop.log")
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    if os.path.exists(resilience.LOCK_FILE):
        try:
            old_pid = int(open(resilience.LOCK_FILE).read().strip())
            if not resilience._pid_alive(old_pid):
                os.remove(resilience.LOCK_FILE)
        except Exception:
            pass
    with open(log_path, "a", encoding="utf-8") as logf:
        subprocess.Popen([PYTHON, "-X", "utf8", "-u", "-m", "src.core.main_loop"],
                         cwd=ROOT, env=env, stdout=logf, stderr=subprocess.STDOUT)


def main():
    print(f"[{_now()}] watchdog started (check every {CHECK_EVERY}s)")
    if not alerts.configured():
        print(f"[{_now()}] NOTE: no alert channel configured "
              f"(set ULTRA_ALERT_TELEGRAM_TOKEN/_CHAT or ULTRA_ALERT_WEBHOOK). "
              f"Alerts will still be written to logs/alerts.log.")
    _alert("Bot started", alerts.INFO, profit_protector="on" if PROTECT_PROFIT_ON else "off",
           trading_hours="24h" if os.getenv("ULTRA_TRADE_24H", "0") == "1" else "06:00-21:30 IST")
    if not os.path.exists(resilience.STOP_FILE) and ops.halt_status() is None and not _loop_alive():
        _start_loop()
        time.sleep(CHECK_EVERY)
    consecutive_restarts = 0
    last_restart = 0.0
    pp_warned = False
    pp_seen = False          # protect_profit has been seen running at least once
    halt_told = False
    pulses: set = set()
    while True:
        now_ist = datetime.now(IST)
        halt = ops.halt_status()
        if _pulse_due(now_ist, pulses):
            alerts.notify(build_pulse(resilience.read_status(), _heartbeat_age(), halt, now_ist))

        if os.path.exists(resilience.STOP_FILE):
            print(f"[{_now()}] STOP file present -- watchdog standing down (not restarting).")
            time.sleep(CHECK_EVERY)
            continue

        # A latched halt: main_loop refuses to start, so restarting it would only loop. Say so once, then wait.
        if halt is not None:
            if not halt_told and not _loop_alive() and halt.get("expires_utc"):
                _alert(f"Bot paused until {_ist_time(halt['expires_utc'])}", alerts.INFO, why=halt.get("reason", "?"))
                halt_told = True
            if not halt_told and not _loop_alive():
                # whoever set it within the last 10 min already sent the loud message; this is the record
                try:
                    age = (datetime.now(timezone.utc) - datetime.fromisoformat(halt["set_at_utc"])).total_seconds()
                except (KeyError, TypeError, ValueError):
                    age = float("inf")
                _alert("Bot halted: waiting for you to clear it", alerts.INFO if age < 600 else alerts.CRITICAL,
                       action='RDP in, check MT5, then run: venv\\Scripts\\python.exe -m scripts.halt clear '
                              '--note "checked". The bot restarts by itself within a minute.',
                       why=halt.get("reason", "?"))
                halt_told = True
            time.sleep(CHECK_EVERY)
            continue
        if halt_told:
            _alert("Halt cleared: bot restarting", alerts.INFO)
            halt_told = False
            consecutive_restarts = 0
            if not _loop_alive():
                _start_loop()
                time.sleep(CHECK_EVERY)
                continue

        # Watch the other safety layer too, not just main_loop.
        if not PROTECT_PROFIT_ON:
            if _protect_profit_alive():
                _stop_protect_profit()
        elif not _protect_profit_alive():
            if pp_seen and not pp_warned:   # first start after boot is routine; only a death is news
                _alert("Profit protector stopped: restarting it", alerts.WARN)
                pp_warned = True
                
            # Actually restart protect_profit.py safely (avoid fork bomb if it crashes immediately)
            now = time.time()
            if 'last_pp_restart' not in locals() or now - last_pp_restart > 300:
                print(f"[{_now()}] starting protect_profit.py ...")
                pp_log_path = os.path.join(ROOT, "logs", "protect_profit.log")
                env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
                with open(pp_log_path, "a", encoding="utf-8") as logf:
                    subprocess.Popen([PYTHON, "-X", "utf8", "-u", "scripts/protect_profit.py"],
                                     cwd=ROOT, env=env, stdout=logf, stderr=subprocess.STDOUT)
                last_pp_restart = now
                time.sleep(2)  # Give it a moment to start
        else:
            pp_warned, pp_seen = False, True

        if not _loop_alive():
            now = time.time()
            if now - last_restart > 300:
                consecutive_restarts = 0
            last_restart = now
            consecutive_restarts = handle_main_loop_crash(consecutive_restarts, wait_seconds=5)
        else:
            if time.time() - last_restart > 300 and consecutive_restarts > 0:
                consecutive_restarts = 0
        time.sleep(CHECK_EVERY)


if __name__ == "__main__":
    main()
