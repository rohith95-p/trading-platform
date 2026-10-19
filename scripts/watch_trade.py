"""Read-only watcher: exit on first position/closed trade, halt latch, stale heartbeat, new ERROR, or deadline (IST HH:MM)."""
import os, sys, time, datetime as dt, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, ROOT)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
deadline_hm = sys.argv[1] if len(sys.argv) > 1 else "20:30"
import MetaTrader5 as mt5
from src.core import ops
mt5.initialize()
t0 = dt.datetime.now(IST); base_deals = len(mt5.history_deals_get(t0 - dt.timedelta(hours=1), t0 + dt.timedelta(days=1)) or [])
log_pos = os.path.getsize("logs/main_loop.log")
reason = None
while True:
    now = dt.datetime.now(IST)
    if now.strftime("%H:%M") >= deadline_hm: reason = f"deadline {deadline_hm} reached, no trade"; break
    ps = mt5.positions_get() or []
    if ps: reason = f"POSITION OPENED: {[(p.ticket, p.magic, 'SELL' if p.type else 'BUY', p.volume, p.price_open, p.sl, p.tp) for p in ps]}"; break
    nd = len(mt5.history_deals_get(t0 - dt.timedelta(hours=1), now + dt.timedelta(days=1)) or [])
    if nd != base_deals: reason = "NEW DEAL in history (a trade opened and closed)"; break
    if ops.halt_status(): reason = f"HALT LATCH SET: {ops.halt_status()}"; break
    if time.time() - os.path.getmtime("logs/heartbeat") > 180: reason = "BOT HEARTBEAT STALE > 3 min"; break
    sz = os.path.getsize("logs/main_loop.log")
    if sz > log_pos:
        with open("logs/main_loop.log", encoding="utf-8", errors="ignore") as f:
            f.seek(log_pos); new = f.read()
        log_pos = sz
        bad = [l for l in new.splitlines() if "[ERROR]" in l or "Traceback" in l or "BLOCKED" in l or "LIVENESS CHECK FAILED" in l]
        if bad: reason = "NEW LOG ISSUE: " + " | ".join(x[:180] for x in bad[:3]); break
    time.sleep(20)
print(f"WATCH ENDED {dt.datetime.now(IST):%H:%M:%S} IST -> {reason}", flush=True)
print(subprocess.run([sys.executable, "-X", "utf8", "scripts/diag_no_trade.py", "17:30"], capture_output=True, text=True).stdout, flush=True)
