"""Detailed per-trade metrics for Atlas portfolio strategies."""
import sys, os, datetime as dt, dataclasses
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import summarize

ts = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())

HOLDOUT_START = ts(2025, 6, 1)
HOLDOUT_END = ts(2026, 10, 13)
HOLDOUT_MONTHS = (dt.date(2026, 10, 13) - dt.date(2025, 6, 1)).days / 30.44

ATLAS_BALANCE = 5000.0

from src.strategies.asian_breakout import AsianBreakoutV6
from src.strategies.momentum_strategies import DonchianTrendV6
from src.strategies.asian_range_filtered import AsianRangeFilteredV6

STRATS = {
    "AsianBreakout": AsianBreakoutV6,
    "DonchianTrend": DonchianTrendV6,
    "AsianRangeFiltered": AsianRangeFilteredV6,
}

print("Loading data...", flush=True)
bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "D1"))

def detailed_report(name, cls_list, bars, start, end, balance):
    strategies = [cls() for cls in cls_list]
    cfg = EngineConfig(
        sizing_mode="fixed", fixed_lots=0.01,
        starting_balance=balance, history_bars=7500,
        enable_d1_bias_gate=False, dedup_per_candle=True,
        max_concurrent=3, max_same_direction=2,
    )
    engine = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg)
    res = engine.run(strategies, start, end)
    trades = res.trades

    if not trades:
        print(f"\n--- {name}: 0 trades ---")
        return

    pls = [t.net_pl for t in trades]
    wins = [p for p in pls if p > 0]
    losses = [p for p in pls if p < 0]
    scratches = [p for p in pls if p == 0]

    total_trades = len(trades)
    win_count = len(wins)
    loss_count = len(losses)

    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    median_win = np.median(wins) if wins else 0
    median_loss = np.median(losses) if losses else 0
    best_trade = max(pls)
    worst_trade = min(pls)
    net = sum(pls)

    months = (dt.date(2026, 10, 13) - dt.date(2025, 6, 1)).days / 30.44
    trades_per_month = total_trades / months
    profit_per_month = net / months

    # Time to $150 (eval target)
    cum = 0
    days_to_150 = None
    first_date = dt.datetime.fromtimestamp(trades[0].exit_time, tz=dt.timezone.utc).date()
    for t in sorted(trades, key=lambda t: t.exit_time):
        cum += t.net_pl
        if cum >= 150 and days_to_150 is None:
            hit_date = dt.datetime.fromtimestamp(t.exit_time, tz=dt.timezone.utc).date()
            days_to_150 = (hit_date - first_date).days

    # Hold time per trade
    hold_times = []
    for t in trades:
        entry = getattr(t, 'entry_time', None) or getattr(t, 'open_time', None)
        exit_t = t.exit_time
        if entry and exit_t:
            hold_times.append((exit_t - entry) / 3600)  # hours

    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}")
    print(f"  Period:          {dt.date(2025, 6, 1)} to {dt.date(2026, 10, 13)} ({months:.1f} months)")
    print(f"  Total trades:    {total_trades}")
    print(f"  Trades/month:    {trades_per_month:.1f}")
    print(f"  Win rate:        {win_count}/{total_trades} = {win_count/total_trades*100:.1f}%")
    print(f"  Scratches:       {len(scratches)}")
    print(f"")
    print(f"  --- Per-Trade Economics ---")
    print(f"  Avg WIN:         ${avg_win:+.2f}")
    print(f"  Avg LOSS:        ${avg_loss:+.2f}")
    print(f"  Median WIN:      ${median_win:+.2f}")
    print(f"  Median LOSS:     ${median_loss:+.2f}")
    print(f"  Best trade:      ${best_trade:+.2f}")
    print(f"  Worst trade:     ${worst_trade:+.2f}")
    print(f"  Avg trade (all): ${net/total_trades:+.2f}")
    print(f"")
    print(f"  --- Totals ---")
    print(f"  Net profit:      ${net:+.2f}")
    print(f"  Profit/month:    ${profit_per_month:+.2f}")
    if days_to_150:
        print(f"  Days to $150:    {days_to_150} days")
    else:
        print(f"  Days to $150:    DID NOT HIT")
    print(f"  Gross wins:      ${sum(wins):+.2f}")
    print(f"  Gross losses:    ${sum(losses):+.2f}")
    if hold_times:
        print(f"")
        print(f"  --- Hold Time ---")
        print(f"  Avg hold:        {np.mean(hold_times):.1f} hours")
        print(f"  Median hold:     {np.median(hold_times):.1f} hours")
        print(f"  Min hold:        {min(hold_times):.1f} hours")
        print(f"  Max hold:        {max(hold_times):.1f} hours")

# Individual strategies
for name, cls in STRATS.items():
    detailed_report(name, [cls], bars, HOLDOUT_START, HOLDOUT_END, ATLAS_BALANCE)

# Combined portfolio
print("\n\n" + "#"*70)
print("  COMBINED PORTFOLIO (all 3)")
print("#"*70)
detailed_report("COMBINED (Donchian + AsianFiltered + AsianBreakout)",
                [DonchianTrendV6, AsianRangeFilteredV6, AsianBreakoutV6],
                bars, HOLDOUT_START, HOLDOUT_END, ATLAS_BALANCE)
