"""Backtest 5 new London/NY session strategies + existing 2 Atlas strategies.

Tests each strategy individually and all promising combinations on
DEV/VALIDATE/HOLDOUT splits with Atlas-relevant metrics.

Run: python -I scripts/research/london_ny_backtest_2026_10_25.py
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

ATLAS_BALANCE = 5000.0

# --- Strategy imports ---
from src.strategies.asian_breakout import AsianBreakoutV6
from src.strategies.momentum_strategies import DonchianTrendV6
from src.strategies.london_open_drive import LondonOpenDriveV6
from src.strategies.ny_session_reversal import NYSessionReversalV6
from src.strategies.london_close_reversal import LondonCloseReversalV6
from src.strategies.silver_bullet import SilverBulletV6
from src.strategies.london_momentum import LondonMomentumV6

ALL_STRATEGIES = {
    "AsianBreakout":      [AsianBreakoutV6],
    "DonchianTrend":      [DonchianTrendV6],
    "LondonOpenDrive":    [LondonOpenDriveV6],
    "NYSessionReversal":  [NYSessionReversalV6],
    "LondonCloseReversal":[LondonCloseReversalV6],
    "SilverBullet":       [SilverBulletV6],
    "LondonMomentum":     [LondonMomentumV6],
}


def run_and_report(strat_classes, label, bars_obj, start, end, balance):
    strategies = [cls() for cls in strat_classes]
    cfg = EngineConfig(
        sizing_mode="fixed", fixed_lots=0.01,
        starting_balance=balance,
        history_bars=7500,
        enable_d1_bias_gate=False, dedup_per_candle=True,
        max_concurrent=3, max_same_direction=2,
    )
    engine = BacktestEngine(bars=bars_obj, cost=SCENARIOS["realistic_ecn"], config=cfg)
    res = engine.run(strategies, start, end)

    d = summarize(res.trades, res.equity, balance).to_dict()
    n = d.get("trades", 0)
    pf = d.get("profit_factor", 0.0)
    wr = d.get("win_rate", 0.0)
    net = d.get("net_pl", 0.0)
    max_dd = d.get("max_drawdown_pct", 0.0)

    # Atlas-specific: worst daily loss, days to 3% target
    daily_pls = {}
    bal = balance
    for t in sorted(res.trades, key=lambda t: t.exit_time):
        day = dt.datetime.fromtimestamp(t.exit_time, tz=dt.timezone.utc).date()
        daily_pls[day] = daily_pls.get(day, 0.0) + t.net_pl
        bal += t.net_pl
    worst_daily = min(daily_pls.values()) if daily_pls else 0.0
    worst_daily_pct = (worst_daily / balance * 100) if balance else 0.0
    profit_days = sum(1 for v in daily_pls.values() if v > balance * 0.005)  # 0.5% days
    target_usd = balance * 0.03
    days_to_target = None
    cum = 0.0
    for i, (day, pl) in enumerate(sorted(daily_pls.items())):
        cum += pl
        if cum >= target_usd:
            days_to_target = i + 1
            break

    return {
        "label": label, "trades": n, "pf": pf, "wr": wr, "net": net,
        "max_dd_pct": max_dd, "worst_daily_pct": worst_daily_pct,
        "profit_days": profit_days, "days_to_target": days_to_target,
    }


print("=" * 90)
print("LONDON/NY SESSION STRATEGY BACKTEST")
print(f"Balance: ${ATLAS_BALANCE:.0f} | Lot: 0.01 | Cost: realistic_ecn")
print("=" * 90)

print("\nLoading data (M15, M5, D1 — skipping M1 for speed)...", flush=True)
bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "D1"))
coarse = bars

# --- Phase 1: Individual strategy backtests ---
print("\n" + "=" * 90)
print("PHASE 1: INDIVIDUAL STRATEGIES")
print("=" * 90)

results = []
for name, classes in ALL_STRATEGIES.items():
    print(f"\n--- {name} ---")
    for split_name, start, end in SPLITS:
        r = run_and_report(classes, f"{name}/{split_name}", coarse, start, end, ATLAS_BALANCE)
        pf_s = f"{r['pf']:.2f}" if r['pf'] < 99 else "INF"
        dt_s = f"{r['days_to_target']}d" if r['days_to_target'] else "N/A"
        print(f"  {split_name:10s}: {r['trades']:4d} trades | PF {pf_s:>6s} | "
              f"WR {r['wr']:5.1f}% | Net ${r['net']:>8.2f} | "
              f"MaxDD {r['max_dd_pct']:5.1f}% | WorstDay {r['worst_daily_pct']:>6.2f}% | "
              f"ProfitDays {r['profit_days']:3d} | Target {dt_s}")
        results.append(r)

# --- Phase 2: Identify winners (PF > 1.0 in VALIDATE) ---
print("\n" + "=" * 90)
print("PHASE 2: WINNERS (PF > 1.0 in VALIDATE period)")
print("=" * 90)

winners = []
for name, classes in ALL_STRATEGIES.items():
    val_r = run_and_report(classes, f"{name}/VALIDATE", coarse,
                           SPLITS[1][1], SPLITS[1][2], ATLAS_BALANCE)
    if val_r["pf"] > 1.0 and val_r["trades"] >= 10:
        winners.append((name, classes, val_r))
        print(f"  PASS: {name} (PF {val_r['pf']:.2f}, {val_r['trades']} trades)")
    else:
        print(f"  FAIL: {name} (PF {val_r['pf']:.2f}, {val_r['trades']} trades)")

# --- Phase 3: Combined portfolio of winners ---
if winners:
    print("\n" + "=" * 90)
    print("PHASE 3: COMBINED PORTFOLIO OF WINNERS")
    print("=" * 90)

    combined_classes = []
    for name, classes, _ in winners:
        combined_classes.extend(classes)

    combo_name = " + ".join(n for n, _, _ in winners)
    print(f"\nPortfolio: {combo_name}")
    for split_name, start, end in SPLITS:
        r = run_and_report(combined_classes, f"COMBINED/{split_name}",
                           coarse, start, end, ATLAS_BALANCE)
        pf_s = f"{r['pf']:.2f}" if r['pf'] < 99 else "INF"
        dt_s = f"{r['days_to_target']}d" if r['days_to_target'] else "N/A"
        print(f"  {split_name:10s}: {r['trades']:4d} trades | PF {pf_s:>6s} | "
              f"WR {r['wr']:5.1f}% | Net ${r['net']:>8.2f} | "
              f"MaxDD {r['max_dd_pct']:5.1f}% | WorstDay {r['worst_daily_pct']:>6.2f}% | "
              f"ProfitDays {r['profit_days']:3d} | Target {dt_s}")

    # Also test: all 7 strategies together
    print(f"\nAll 7 strategies combined:")
    all_classes = []
    for classes in ALL_STRATEGIES.values():
        all_classes.extend(classes)
    for split_name, start, end in SPLITS:
        r = run_and_report(all_classes, f"ALL7/{split_name}",
                           coarse, start, end, ATLAS_BALANCE)
        pf_s = f"{r['pf']:.2f}" if r['pf'] < 99 else "INF"
        dt_s = f"{r['days_to_target']}d" if r['days_to_target'] else "N/A"
        print(f"  {split_name:10s}: {r['trades']:4d} trades | PF {pf_s:>6s} | "
              f"WR {r['wr']:5.1f}% | Net ${r['net']:>8.2f} | "
              f"MaxDD {r['max_dd_pct']:5.1f}% | WorstDay {r['worst_daily_pct']:>6.2f}% | "
              f"ProfitDays {r['profit_days']:3d} | Target {dt_s}")

print("\n" + "=" * 90)
print("BACKTEST COMPLETE")
print("=" * 90)
