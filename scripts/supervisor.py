"""supervisor.py -- keeps the live demo bot running (2026-10-18).

Replaces reliance on the 05:55 scheduled task alone. Run it at boot/logon (see scripts/install_supervisor_task.ps1).

* Starts `python -m src.core.main_loop` and restarts it after a CRASH with exponential backoff.
* Does NOT restart while the halt latch (logs/HALT_LATCH.json) or the STOP file exists; it keeps checking and alerts once.
* Starts the bot in MEASUREMENT-ONLY mode (no orders) unless you pass --trade.
* Captures the bot's output into a rotating log (logs/main_loop.log, 5 MB x 5) so a crash always leaves a traceback.
* Kills and restarts a bot whose heartbeat file is stale (> 5 min) -- a hung process.
* Detects sleep/resume (a >120 s gap in its own loop), logs it, and re-checks the bot.
* Publishes its own status to ULTRA_SUPERVISOR_HEARTBEAT_URL (optional, external dead-man check).

    python -m scripts.supervisor            # measurement-only (default)
    python -m scripts.supervisor --trade    # allow the bot to send orders
"""
import argparse
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.core import ops, resilience  # noqa: E402

CHECK_EVERY_S = 5
HEARTBEAT_MAX_AGE_S = 300
RESUME_GAP_S = 120
MAX_CRASHES_IN_WINDOW = 5
CRASH_WINDOW_S = 600


def backoff_seconds(consecutive_crashes: int) -> float:
    """5, 10, 20, 40, 80, 160, 300 (cap)."""
    return float(min(300, 5 * 2 ** max(0, min(consecutive_crashes - 1, 6))))


def decide_start(halt: Optional[dict], stop_file: bool, recent_crashes: List[float], now: float) -> Tuple[bool, str]:
    """Pure decision: may the supervisor (re)start the bot right now?"""
    if halt is not None:
        return False, f"halt latch set ({halt.get('source')}: {halt.get('reason')})"
    if stop_file:
        return False, "STOP file present"
    recent = [t for t in recent_crashes if now - t <= CRASH_WINDOW_S]
    if len(recent) >= MAX_CRASHES_IN_WINDOW:
        return False, f"crash loop: {len(recent)} crashes in {CRASH_WINDOW_S}s (waiting)"
    return True, "ok"


def heartbeat_stale(path: str, now: float, max_age: float = HEARTBEAT_MAX_AGE_S) -> bool:
    try:
        return now - os.path.getmtime(path) > max_age
    except OSError:
        return False        # no heartbeat file yet (bot still starting)


def _alert(msg: str, severity: str = "WARN") -> None:
    try:
        from src.core import alerts
        alerts.send(msg, severity=severity, context={"source": "supervisor"})
    except Exception:
        pass


def _make_logger() -> logging.Logger:
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    lg = logging.getLogger("bot_output")
    lg.setLevel(logging.INFO)
    lg.propagate = False
    if not lg.handlers:
        h = logging.handlers.RotatingFileHandler(os.path.join(ROOT, "logs", "main_loop.log"), maxBytes=5_000_000,
                                                 backupCount=5, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(message)s"))
        lg.addHandler(h)
    return lg


def _pump(stream, lg):
    for line in iter(stream.readline, ""):
        lg.info(line.rstrip("\n"))


def _start_child(trade: bool, lg) -> subprocess.Popen:
    py = os.path.join(ROOT, "venv", "Scripts", "python.exe")
    if not os.path.exists(py):
        py = sys.executable
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               ULTRA_MEASURE_ONLY="0" if trade else "1")
    p = subprocess.Popen([py, "-X", "utf8", "-u", "-m", "src.core.main_loop"], cwd=ROOT, env=env, text=True,
                         encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    threading.Thread(target=_pump, args=(p.stdout, lg), daemon=True).start()
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trade", action="store_true", help="allow the bot to send orders (default: measurement-only)")
    a = ap.parse_args(argv)
    lg = _make_logger()
    mode = "TRADE" if a.trade else "MEASUREMENT-ONLY"
    child: Optional[subprocess.Popen] = None
    crashes: List[float] = []
    consecutive = 0
    next_start = 0.0
    last_tick = time.time()
    warned_block = ""
    last_hb = 0.0
    print(f"supervisor started ({mode} mode)", flush=True)
    _alert(f"supervisor started ({mode} mode)", "INFO")
    while True:
        now = time.time()
        if now - last_tick > RESUME_GAP_S:
            msg = f"resume detected: supervisor loop paused {now - last_tick:.0f}s (sleep/hibernate?) -- re-checking the bot"
            print(msg, flush=True)
            lg.info(msg)
            _alert(msg, "WARN")
        last_tick = now
        if child is not None and child.poll() is None and heartbeat_stale(resilience.HEARTBEAT_FILE, now):
            _alert("bot heartbeat stale > 5 min while process alive (hung) -- killing and restarting", "WARN")
            child.kill()
            child.wait(timeout=10)
        if child is not None and child.poll() is not None:
            code = child.returncode
            child = None
            if ops.halt_status() is None and not os.path.exists(resilience.STOP_FILE):
                crashes.append(now)
                consecutive += 1
                next_start = now + backoff_seconds(consecutive)
                _alert(f"bot exited (code {code}); restart in {backoff_seconds(consecutive):.0f}s", "WARN")
        ok, why = decide_start(ops.halt_status(), os.path.exists(resilience.STOP_FILE), crashes, now)
        if child is None:
            if ok and now >= next_start:
                child = _start_child(a.trade, lg)
                warned_block = ""
                print(f"bot started pid={child.pid}", flush=True)
            elif not ok and why != warned_block:
                warned_block = why
                print(f"not starting: {why}", flush=True)
                _alert(f"supervisor NOT starting the bot: {why}", "CRITICAL" if "crash loop" in why else "WARN")
        elif consecutive and crashes and now - crashes[-1] > 300:
            consecutive = 0                       # stable for 5 min -> reset backoff
        if now - last_hb >= 30:
            last_hb = now
            url = os.environ.get("ULTRA_SUPERVISOR_HEARTBEAT_URL", "").strip()
            if url:
                payload = {"supervisor": "ultra_core", "bot_running": child is not None and child.poll() is None,
                           "mode": "trade" if a.trade else "measure_only", "halt": ops.halt_status() is not None,
                           "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                threading.Thread(target=ops._post, args=(url, payload), daemon=True).start()
        time.sleep(CHECK_EVERY_S)


if __name__ == "__main__":
    raise SystemExit(main())
