"""watchdog.py -- restart main_loop if it dies.

Run this in a second terminal (or a Windows Task Scheduler task set to run at
logon). It checks every 30s that main_loop is alive via its lockfile PID and its
heartbeat file. If the process is gone OR the heartbeat is stale > 5 min, it
relaunches main_loop.

    python -m scripts.watchdog

NOTE: no alerting is wired up yet (no notification channel configured). This
only restarts + logs. Wire a Telegram/push call into `_alert()` when ready.
See docs/research/REAL_MONEY_READINESS.md part IV.1.
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

IST = timezone(timedelta(hours=5, minutes=30))
CHECK_EVERY = 30
HEARTBEAT_MAX_AGE = 300  # seconds
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.path.join(ROOT, "venv", "Scripts", "python.exe")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable


def _now():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def _alert(msg: str, severity: str = alerts.WARN, **details):
    """Notification channel. Sends via Telegram/webhook if configured, and records to logs/alerts.log."""
    alerts.send(msg, severity=severity, context={**details, "source": "watchdog"})


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
        _alert(f"FATAL: trading loop failed {consecutive_restarts} restarts -- watchdog stopped",
               severity=alerts.CRITICAL, action="restart manually (start_ultra_core.bat)")
        trade_log.lifecycle("watchdog_fatal_exit", attempts=consecutive_restarts, error=traceback_snippet)
        sys.exit(1)

    last = [l for l in traceback_snippet.splitlines() if "ERROR" in l or "Traceback" in l or "Exception" in l]
    _alert(f"Trading loop crashed (attempt #{consecutive_restarts}/3)", severity=alerts.WARN,
           action=f"restart in {wait_seconds}s",
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
    _alert("watchdog started", alerts.INFO)
    if not os.path.exists(resilience.STOP_FILE) and not _loop_alive():
        _start_loop()
        time.sleep(CHECK_EVERY)
    consecutive_restarts = 0
    last_restart = 0.0
    pp_warned = False
    while True:
        if os.path.exists(resilience.STOP_FILE):
            print(f"[{_now()}] STOP file present -- watchdog standing down (not restarting).")
            time.sleep(CHECK_EVERY)
            continue

        # Watch the other safety layer too, not just main_loop.
        if not _protect_profit_alive():
            if not pp_warned:
                _alert("protect_profit.py is NOT running -- ATTEMPTING RESTART.", alerts.WARN)
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
            pp_warned = False

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
