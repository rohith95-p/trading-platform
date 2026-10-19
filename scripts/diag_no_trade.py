"""One-shot 'why is there no trade' diagnostic. Read-only. Run: python scripts/diag_no_trade.py [HH:MM IST window start]"""
import os, sys, json, glob, datetime as dt, collections, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, ROOT)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
now = dt.datetime.now(IST); start_hm = sys.argv[1] if len(sys.argv) > 1 else "17:30"
start = now.replace(hour=int(start_hm[:2]), minute=int(start_hm[3:]), second=0, microsecond=0)
print(f"== diagnostic {now:%Y-%m-%d %H:%M} IST (window from {start_hm}) ==")

import MetaTrader5 as mt5
mt5.initialize()
a = mt5.account_info(); tk = mt5.symbol_info_tick("XAUUSDm"); s = mt5.symbol_info("XAUUSDm")
age = dt.datetime.now(dt.timezone.utc).timestamp() - tk.time
print(f"MT5: connected={mt5.terminal_info().connected} account={a.login} balance={a.balance} equity={a.equity} trade_allowed={a.trade_allowed}")
print(f"Feed: tick age {age:.0f}s, spread {s.spread} pts, trade_mode={s.trade_mode}")
print(f"Positions {len(mt5.positions_get() or [])}, pending {len(mt5.orders_get() or [])}")

from src.core import ops
h = ops.halt_status(); print("Halt latch:", h if h else "clear")
print("STOP file:", os.path.exists("STOP"))
rs = json.load(open("logs/risk_state.json")); print(f"Risk state: peak={rs['peak_equity']} halt_reason={rs['hard_halt_reason']!r} consecutive_losses={rs['consecutive_losses']}")
hb = os.path.getmtime("logs/heartbeat"); print(f"Bot heartbeat age: {dt.datetime.now().timestamp()-hb:.0f}s")

ev = collections.Counter(); last = {}
for line in open(glob.glob(f"logs/trades/{now:%Y-%m-%d}.jsonl")[0], encoding="utf-8", errors="ignore") if glob.glob(f"logs/trades/{now:%Y-%m-%d}.jsonl") else []:
    try: e = json.loads(line)
    except Exception: continue
    t = dt.datetime.strptime(e["ist"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    if t < start: continue
    key = (e.get("kind"), e.get("strategy", e.get("gate", "")), e.get("action", ""), (e.get("reason") or "")[:60])
    ev[key] += 1; last[key] = e["ist"][11:]
print("\nDecisions in window (kind, leg/gate, action, reason) -> count, last seen:")
for k, c in ev.most_common(15): print(f"  {c:4d}  {k}  last {last[k]}")
if not ev: print("  (none: no leg produced a signal in the window)")

errs = []
for line in open("logs/main_loop.log", encoding="utf-8", errors="ignore"):
    if line.startswith("2026-") and ("[ERROR]" in line or "Traceback" in line or "LIVENESS" in line or "Refusing" in line):
        try: t = dt.datetime.strptime(line[:22], "%Y-%m-%d %I:%M:%S %p").replace(tzinfo=IST)
        except Exception: continue
        if t >= start: errs.append(line.strip()[:200])
print(f"\nErrors/warnings of note in window: {len(errs)}"); [print("  ", x) for x in errs[-6:]]
n_scan = sum(1 for line in open("logs/main_loop.log", encoding="utf-8", errors="ignore") if "D1 GATE" in line and line.startswith(f"{now:%Y-%m-%d}") and dt.datetime.strptime(line[:22], "%Y-%m-%d %I:%M:%S %p").replace(tzinfo=IST) >= start)
print(f"Scans (D1 gate lines) in window: {n_scan} (expect about {int((now-start).total_seconds()/60)})")
