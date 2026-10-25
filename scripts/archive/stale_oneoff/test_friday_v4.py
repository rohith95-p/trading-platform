"""Test portfolio_v4 for a single day (Friday, Sept 4)."""
from datetime import datetime, timezone
import numpy as np
from src.backtesting.data import load_bars
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.costs import SCENARIOS
from src.research.candidates import build_library
from scripts.phase3_worker import TightStopStrategy

def _ts(d): return int(datetime.strptime(d,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())
lib = {c.id: c for c in build_library()}
bars = load_bars("XAUUSDm", timeframes=("M15","M5","M1","D1"))

legs = [
    ("squeeze_ASIA", "XAU-062", (2.5,11.5), 2.0, 4.0),
    ("emastack_LONDON_tight", "XAU-005", (11.5,15.5), 0.75, 3.0),
    ("fvg_NY_tight", "XAU-092", (17.5,21.5), 0.5, 2.5),
    ("rangerejection_NY_tight", "XAU-049", (17.5,21.5), 0.75, 2.25),
]

all_trades = []
for name, cid, sess, sl, tp in legs:
    cfg = EngineConfig(symbol="XAUUSDm", starting_balance=105.74, sizing_mode="fixed",
        fixed_lots=0.01, dedup_per_candle=True, max_concurrent=1, max_same_direction=1,
        enable_pyramiding=False, enable_consolidation_exit=False, enable_trailing=False,
        history_bars=900, warmup_bars=950, daily_loss_limit_mode="off",
        tp_atr_mult=tp, sl_atr_mult_override=sl)
    strat = TightStopStrategy(name, hash(name) % 9000, lib[cid].rule, sess)
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic"], config=cfg)
    res = eng.run([strat], start_ts=_ts("2026-09-04"), end_ts=_ts("2026-09-05"))
    for t in res.trades:
        all_trades.append((t.entry_time, t.exit_time, name, t.net_pl))

all_trades.sort(key=lambda x: x[1])

START_BAL = 105.74
IST_OFFSET = 5.5 * 3600
balance = START_BAL
daily_pl = {}
daily_start_bal = {}
shutdown_days = set()
kept = []

for entry_ts, exit_ts, name, pl in all_trades:
    day = datetime.fromtimestamp(entry_ts + IST_OFFSET, tz=timezone.utc).date()
    if day not in daily_start_bal:
        daily_start_bal[day] = balance
    if day in shutdown_days:
        continue
    balance += pl
    daily_pl[day] = daily_pl.get(day, 0.0) + pl
    kept.append((entry_ts, name, pl, balance))
    if daily_pl[day] < -0.06 * daily_start_bal[day]:
        shutdown_days.add(day)

print(f"Results for Friday Sept 4:")
print(f"Total trades: {len(kept)}")
for t in kept:
    print(f"  {t[1]}: ${t[2]:.2f} (Balance: ${t[3]:.2f})")
print(f"Net Profit: ${sum(t[2] for t in kept):.2f}")
print(f"Final Balance: ${balance:.2f}")
