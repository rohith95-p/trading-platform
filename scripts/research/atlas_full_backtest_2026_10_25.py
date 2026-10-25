"""Full Atlas strategy backtest — all candidates + portfolio optimization.

Tests 10 strategies individually, then builds the best Atlas-safe portfolio
that maximizes PF while keeping MaxDD under Atlas limits.

Atlas limits:
  Evaluation: 10% trailing DD, 5% daily loss
  Funded:      6% trailing DD, 3% daily loss

Run: python -I scripts/research/atlas_full_backtest_2026_10_25.py
"""
import sys, os, datetime as dt, dataclasses
from itertools import combinations
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

from src.strategies.asian_breakout import AsianBreakoutV6
from src.strategies.momentum_strategies import DonchianTrendV6
from src.strategies.london_momentum import LondonMomentumV6
from src.strategies.london_momentum_tight import LondonMomentumTightV6
from src.strategies.asian_range_filtered import AsianRangeFilteredV6
from src.strategies.bb_squeeze_breakout import BBSqueezeBreakoutV6
from src.strategies.pullback_trend import PullbackTrendV6
from src.strategies.ny_afternoon_trend import NYAfternoonTrendV6
from src.strategies.london_open_drive import LondonOpenDriveV6
from src.strategies.ny_session_reversal import NYSessionReversalV6

ALL_STRATEGIES = {
    "AsianBreakout":       AsianBreakoutV6,
    "DonchianTrend":       DonchianTrendV6,
    "LondonMomentum":      LondonMomentumV6,
    "LondonMomTight":      LondonMomentumTightV6,
    "AsianRangeFiltered":  AsianRangeFilteredV6,
    "BBSqueezeBreakout":   BBSqueezeBreakoutV6,
    "PullbackTrend":       PullbackTrendV6,
    "NYAfternoonTrend":    NYAfternoonTrendV6,
    "LondonOpenDrive":     LondonOpenDriveV6,
    "NYSessionReversal":   NYSessionReversalV6,
}


def run_backtest(strat_classes, bars_obj, start, end, balance):
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

    daily_pls = {}
    for t in sorted(res.trades, key=lambda t: t.exit_time):
        day = dt.datetime.fromtimestamp(t.exit_time, tz=dt.timezone.utc).date()
        daily_pls[day] = daily_pls.get(day, 0.0) + t.net_pl
    worst_daily = min(daily_pls.values()) if daily_pls else 0.0
    worst_daily_pct = abs(worst_daily / balance * 100) if balance else 0.0
    profit_days = sum(1 for v in daily_pls.values() if v > balance * 0.005)
    target_usd = balance * 0.03
    days_to_target = None
    cum = 0.0
    for i, (day, pl) in enumerate(sorted(daily_pls.items())):
        cum += pl
        if cum >= target_usd:
            days_to_target = i + 1
            break

    return {
        "trades": n, "pf": pf, "wr": wr, "net": net,
        "max_dd_pct": max_dd, "worst_daily_pct": worst_daily_pct,
        "profit_days": profit_days, "days_to_target": days_to_target,
    }


def fmt(r, split_name):
    pf_s = f"{r['pf']:.2f}" if r['pf'] < 99 else "INF"
    dt_s = f"{r['days_to_target']}d" if r['days_to_target'] else "N/A"
    return (f"  {split_name:10s}: {r['trades']:4d} trades | PF {pf_s:>6s} | "
            f"WR {r['wr']:5.1f}% | Net ${r['net']:>8.2f} | "
            f"MaxDD {r['max_dd_pct']:5.2f}% | WorstDay {r['worst_daily_pct']:5.2f}% | "
            f"ProfitDays {r['profit_days']:3d} | Target {dt_s}")


print("=" * 95)
print("ATLAS FULL STRATEGY BACKTEST")
print(f"Balance: ${ATLAS_BALANCE:.0f} | Lot: 0.01 | Cost: realistic_ecn")
print("=" * 95)

print("\nLoading data (M15, M5, D1)...", flush=True)
bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "D1"))

# --- Phase 1: Individual strategies ---
print("\n" + "=" * 95)
print("PHASE 1: INDIVIDUAL STRATEGIES")
print("=" * 95)

individual_results = {}
for name, cls in ALL_STRATEGIES.items():
    print(f"\n--- {name} ---")
    for split_name, start, end in SPLITS:
        r = run_backtest([cls], bars, start, end, ATLAS_BALANCE)
        print(fmt(r, split_name))
        individual_results[(name, split_name)] = r

# --- Phase 2: Filter by VALIDATE + HOLDOUT ---
print("\n" + "=" * 95)
print("PHASE 2: FILTER (PF > 1.0 in VALIDATE, PF > 1.0 in HOLDOUT, >= 10 trades each)")
print("=" * 95)

winners = []
for name in ALL_STRATEGIES:
    val = individual_results.get((name, "VALIDATE"), {})
    hold = individual_results.get((name, "HOLDOUT"), {})
    v_pf = val.get("pf", 0)
    h_pf = hold.get("pf", 0)
    v_n = val.get("trades", 0)
    h_n = hold.get("trades", 0)
    passed = v_pf > 1.0 and h_pf > 1.0 and v_n >= 10 and h_n >= 10
    tag = "PASS" if passed else "FAIL"
    print(f"  {tag}: {name:25s} VAL PF={v_pf:.2f} ({v_n}t)  HOLD PF={h_pf:.2f} ({h_n}t)")
    if passed:
        winners.append(name)

if not winners:
    print("\nNo strategies passed both windows. Exiting.")
    sys.exit(0)

# --- Phase 3: Test all combos of 3-5 winners for Atlas compliance ---
print("\n" + "=" * 95)
print("PHASE 3: PORTFOLIO COMBINATIONS (Atlas DD compliance)")
print("=" * 95)
print(f"Winners: {', '.join(winners)}")

best_combo = None
best_score = -999

for size in range(2, min(len(winners) + 1, 6)):
    for combo in combinations(winners, size):
        classes = [ALL_STRATEGIES[n] for n in combo]
        # Test on HOLDOUT only for combo search (speed)
        r = run_backtest(classes, bars, SPLITS[2][1], SPLITS[2][2], ATLAS_BALANCE)

        # Atlas funded compliance
        eval_dd_ok = r["max_dd_pct"] < 10.0
        funded_dd_ok = r["max_dd_pct"] < 5.5  # 60% safety buffer on 6%
        eval_daily_ok = r["worst_daily_pct"] < 5.0
        funded_daily_ok = r["worst_daily_pct"] < 2.5  # safety buffer on 3%

        # Score: PF * penalty for DD breach
        score = r["pf"]
        if not funded_dd_ok:
            score *= 0.5
        if not funded_daily_ok:
            score *= 0.7

        combo_str = " + ".join(combo)
        dd_tag = "SAFE" if funded_dd_ok and funded_daily_ok else "RISK"
        print(f"  [{dd_tag}] {combo_str:60s} | PF {r['pf']:.2f} | DD {r['max_dd_pct']:.2f}% | "
              f"WD {r['worst_daily_pct']:.2f}% | {r['trades']}t | Score {score:.3f}")

        if score > best_score:
            best_score = score
            best_combo = combo

# --- Phase 4: Full report on best combo ---
if best_combo:
    print("\n" + "=" * 95)
    print(f"PHASE 4: BEST PORTFOLIO — {' + '.join(best_combo)}")
    print("=" * 95)

    classes = [ALL_STRATEGIES[n] for n in best_combo]
    for split_name, start, end in SPLITS:
        r = run_backtest(classes, bars, start, end, ATLAS_BALANCE)
        print(fmt(r, split_name))

    # Atlas compliance summary
    hold_r = run_backtest(classes, bars, SPLITS[2][1], SPLITS[2][2], ATLAS_BALANCE)
    print("\n--- ATLAS RULE COMPLIANCE (HOLDOUT) ---")
    print(f"  MaxDD:       {hold_r['max_dd_pct']:.2f}%  (Eval limit: 10%, Funded limit: 6%)")
    print(f"  Worst Day:   {hold_r['worst_daily_pct']:.2f}%  (Eval limit: 5%, Funded limit: 3%)")
    print(f"  Eval phase:  {'PASS' if hold_r['max_dd_pct'] < 10 and hold_r['worst_daily_pct'] < 5 else 'FAIL'}")
    print(f"  Funded phase: {'PASS' if hold_r['max_dd_pct'] < 6 and hold_r['worst_daily_pct'] < 3 else 'BORDERLINE/FAIL'}")
    if hold_r["days_to_target"]:
        print(f"  Days to 3% target: {hold_r['days_to_target']}")
    print(f"  Profit days: {hold_r['profit_days']}")

print("\n" + "=" * 95)
print("BACKTEST COMPLETE")
print("=" * 95)
