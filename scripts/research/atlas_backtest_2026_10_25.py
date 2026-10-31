"""Backtest Atlas portfolio under funded-account constraints.

Tests AsianBreakoutV6 + DonchianTrendV6 on DEV/VALIDATE/HOLDOUT splits
with Atlas-relevant metrics: max trailing DD, daily loss, profit target pace.

Run: python -I scripts/research/atlas_backtest_2026_10_25.py
"""
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

SPLITS = [
    ("DEV",      ts(2022, 8, 1),  ts(2024, 2, 1)),
    ("VALIDATE", ts(2024, 2, 1),  ts(2025, 6, 1)),
    ("HOLDOUT",  ts(2025, 6, 1),  ts(2026, 10, 13)),
]

# Atlas account simulation: $5000 starting balance (smallest Atlas account)
ATLAS_BALANCE = 5000.0

print("=" * 80)
print("ATLAS PORTFOLIO BACKTEST")
print("Strategies: AsianBreakoutV6 (7311) + DonchianTrendV6 (7310)")
print("Balance: $%.0f | Risk: 0.5%% per trade | Atlas DD limit: 10%%" % ATLAS_BALANCE)
print("=" * 80)

print("\nLoading data...", flush=True)
bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1"))
# DEV/TEST here ran on M15 candles, not M1 sub-bars: exits are ambiguous and the
# numbers read high (M1 A/B: PF 0.93 vs 1.38). Kept as a record of what was run on
# 2026-10-25; m1_policy="coarse" is now required to opt into it. Do not compare these
# DEV/TEST figures with M1 results.
coarse = dataclasses.replace(bars, m1=None)

# --- Test each strategy individually and combined ---
from src.strategies.asian_breakout import AsianBreakoutV6
from src.strategies.momentum_strategies import DonchianTrendV6


def run_and_report(strat_classes, label, bars_obj, start, end, balance):
    strategies = [cls() for cls in strat_classes]
    cfg = EngineConfig(
        m1_policy="coarse",
        sizing_mode="fixed", fixed_lots=0.01,
        starting_balance=balance,
        history_bars=7500,
        enable_d1_bias_gate=False, dedup_per_candle=True,
        max_concurrent=2, max_same_direction=2,
    )
    engine = BacktestEngine(bars=bars_obj, cost=SCENARIOS["realistic_ecn"], config=cfg)
    res = engine.run(strategies, start, end)

    d = summarize(res.trades, res.equity, balance).to_dict()
    n = d.get("trades", 0)
    pf = d.get("profit_factor", 0)
    wr = d.get("win_rate", 0)
    net = d.get("net_pl", 0)

    # Trailing DD calculation (Atlas uses equity-based trailing)
    bal = np.array([balance] + [t.balance_after for t in res.trades])
    peak = np.maximum.accumulate(bal)
    dd_abs = (peak - bal)
    max_dd = dd_abs.max()
    dd_pct = max_dd / balance * 100 if balance > 0 else 0

    # Daily P&L for daily loss check
    daily_pls = {}
    for t in res.trades:
        day = t.exit_time // 86400
        daily_pls[day] = daily_pls.get(day, 0) + t.net_pl
    worst_day = min(daily_pls.values()) if daily_pls else 0
    worst_day_pct = worst_day / balance * 100 if balance > 0 else 0

    # Profitable days >= 0.5% (Atlas payout eligibility)
    profit_days = sum(1 for pl in daily_pls.values() if pl >= balance * 0.005)

    # Best day share (Atlas consistency: best day < 40% of total)
    total_profit = sum(pl for pl in daily_pls.values() if pl > 0)
    best_day = max(daily_pls.values()) if daily_pls else 0
    best_day_share = best_day / total_profit * 100 if total_profit > 0 else 0

    # Days to 3% target
    target = balance * 0.03
    running = 0
    days_to_target = None
    sorted_days = sorted(daily_pls.keys())
    for i, day in enumerate(sorted_days):
        running += daily_pls[day]
        if running >= target:
            days_to_target = i + 1
            break

    return {
        "n": n, "pf": pf, "wr": wr, "net": net,
        "max_dd_pct": dd_pct, "worst_day_pct": worst_day_pct,
        "profit_days": profit_days, "best_day_share": best_day_share,
        "days_to_target": days_to_target, "total_days": len(daily_pls),
    }


configs = [
    ("AsianBreakout ONLY", [AsianBreakoutV6]),
    ("DonchianTrend ONLY", [DonchianTrendV6]),
    ("ATLAS COMBINED",     [AsianBreakoutV6, DonchianTrendV6]),
]

for config_name, strat_classes in configs:
    print("\n" + "-" * 80)
    print(">>> %s" % config_name)
    print("-" * 80)
    for split_name, start, end in SPLITS:
        b = bars if split_name == "HOLDOUT" else coarse
        r = run_and_report(strat_classes, config_name, b, start, end, ATLAS_BALANCE)
        atlas_dd_ok = "PASS" if r["max_dd_pct"] < 10 else "FAIL"
        atlas_daily_ok = "PASS" if r["worst_day_pct"] > -5 else "FAIL"
        target_str = "%dd" % r["days_to_target"] if r["days_to_target"] else "NOT HIT"

        print("  %-10s n=%3d PF=%.2f wr=%.0f%% net=$%+.0f | "
              "DD=%.1f%%[%s] DailyLoss=%.1f%%[%s] | "
              "ProfitDays=%d BestDay=%.0f%% Target=%s"
              % (split_name, r["n"], r["pf"], r["wr"], r["net"],
                 r["max_dd_pct"], atlas_dd_ok, r["worst_day_pct"], atlas_daily_ok,
                 r["profit_days"], r["best_day_share"], target_str))

print("\n" + "=" * 80)
print("ATLAS CONSTRAINTS REFERENCE:")
print("  Evaluation: 3%% profit target, 10%% trailing DD, 5%% daily loss")
print("  Funded:     no target, 6%% trailing DD, 3%% daily loss")
print("  Payout:     3+ days with >=0.5%% profit, best day <40%% of total")
print("=" * 80)
print("\nDone.", flush=True)
