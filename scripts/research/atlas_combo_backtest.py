"""Backtest the actual deployed Atlas portfolio: Asian + Donchian + LondonMomentum.

Checks Atlas rule compliance (MaxDD, daily loss limits) across all splits.
Run: python -I scripts/research/atlas_combo_backtest.py
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

# Atlas limits (as percentages)
ATLAS_LIMITS = {
    "eval_max_dd_pct": 10.0,
    "funded_max_dd_pct": 6.0,
    "eval_daily_loss_pct": 5.0,
    "funded_daily_loss_pct": 3.0,
    "eval_profit_target_pct": 3.0,
}

from src.strategies.asian_breakout import AsianBreakoutV6
from src.strategies.momentum_strategies import DonchianTrendV6
from src.strategies.london_momentum import LondonMomentumV6

PORTFOLIO = [AsianBreakoutV6, DonchianTrendV6, LondonMomentumV6]


def analyze(strat_classes, bars_obj, start, end, balance):
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
    wr = d.get("win_rate", 0.0)          # already a percentage
    net = d.get("net_pl", 0.0)
    max_dd = d.get("max_drawdown_pct", 0.0)  # already a percentage

    # Daily P&L breakdown
    daily_pls = {}
    for t in sorted(res.trades, key=lambda t: t.exit_time):
        day = dt.datetime.fromtimestamp(t.exit_time, tz=dt.timezone.utc).date()
        daily_pls[day] = daily_pls.get(day, 0.0) + t.net_pl

    worst_daily_usd = min(daily_pls.values()) if daily_pls else 0.0
    worst_daily_pct = (worst_daily_usd / balance * 100) if balance else 0.0
    best_daily_usd = max(daily_pls.values()) if daily_pls else 0.0
    profit_days = sum(1 for v in daily_pls.values() if v > balance * 0.005)

    # Days to 3% target
    target_usd = balance * 0.03
    days_to_target = None
    cum = 0.0
    for i, (day, pl) in enumerate(sorted(daily_pls.items())):
        cum += pl
        if cum >= target_usd:
            days_to_target = i + 1
            break

    # Equity curve drawdown analysis (from the equity array)
    eq = np.array([e[1] for e in res.equity], dtype=float) if res.equity else np.array([balance])
    peak = np.maximum.accumulate(eq)
    dd_pct = (peak - eq) / peak * 100
    max_dd_equity = float(dd_pct.max()) if len(dd_pct) > 0 else 0.0

    # Count days exceeding daily loss thresholds
    days_over_3pct = sum(1 for v in daily_pls.values() if v < -balance * 0.03)
    days_over_5pct = sum(1 for v in daily_pls.values() if v < -balance * 0.05)

    return {
        "trades": n, "pf": pf, "wr": wr, "net": net,
        "max_dd_pct": max_dd, "max_dd_equity_pct": max_dd_equity,
        "worst_daily_pct": worst_daily_pct, "worst_daily_usd": worst_daily_usd,
        "best_daily_usd": best_daily_usd,
        "profit_days": profit_days, "days_to_target": days_to_target,
        "total_trading_days": len(daily_pls),
        "days_over_3pct_loss": days_over_3pct,
        "days_over_5pct_loss": days_over_5pct,
    }


print("=" * 90)
print("ATLAS 3-STRATEGY COMBO BACKTEST")
print("Portfolio: AsianBreakoutV6 + DonchianTrendV6 + LondonMomentumV6")
print(f"Balance: ${ATLAS_BALANCE:.0f} | Lot: 0.01 | Cost: realistic_ecn")
print("=" * 90)

print("\nLoading data (M15, M5, D1)...", flush=True)
bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "D1"))

all_results = {}
for split_name, start, end in SPLITS:
    print(f"\nRunning {split_name}...", flush=True)
    r = analyze(PORTFOLIO, bars, start, end, ATLAS_BALANCE)
    all_results[split_name] = r

    pf_s = f"{r['pf']:.2f}" if r['pf'] < 99 else "INF"
    dt_s = f"{r['days_to_target']}d" if r['days_to_target'] else "N/A"
    print(f"  Trades:       {r['trades']}")
    print(f"  Profit Factor:{pf_s:>8s}")
    print(f"  Win Rate:     {r['wr']:>7.1f}%")
    print(f"  Net P&L:      ${r['net']:>10.2f}")
    print(f"  Max DD:       {r['max_dd_pct']:>7.2f}% (summarize)")
    print(f"  Max DD (eq):  {r['max_dd_equity_pct']:>7.2f}% (equity curve)")
    print(f"  Worst Day:    {r['worst_daily_pct']:>7.2f}% (${r['worst_daily_usd']:.2f})")
    print(f"  Best Day:     ${r['best_daily_usd']:>8.2f}")
    print(f"  Profit Days:  {r['profit_days']} / {r['total_trading_days']} trading days")
    print(f"  Days to 3%:   {dt_s}")
    print(f"  Days > 3% loss: {r['days_over_3pct_loss']}")
    print(f"  Days > 5% loss: {r['days_over_5pct_loss']}")

# --- ATLAS RULE COMPLIANCE ---
print("\n" + "=" * 90)
print("ATLAS RULE COMPLIANCE CHECK")
print("=" * 90)

for phase, dd_limit, daily_limit in [
    ("EVALUATION (10% DD, 5% daily)", 10.0, 5.0),
    ("FUNDED (6% DD, 3% daily)", 6.0, 3.0),
]:
    print(f"\n--- {phase} ---")
    for split_name in ["DEV", "VALIDATE", "HOLDOUT"]:
        r = all_results[split_name]
        dd_ok = r["max_dd_pct"] < dd_limit
        dd_eq_ok = r["max_dd_equity_pct"] < dd_limit
        daily_ok = abs(r["worst_daily_pct"]) < daily_limit
        all_ok = dd_ok and dd_eq_ok and daily_ok

        dd_sym = "PASS" if dd_ok else "FAIL"
        dd_eq_sym = "PASS" if dd_eq_ok else "FAIL"
        daily_sym = "PASS" if daily_ok else "FAIL"
        overall = "PASS" if all_ok else "*** FAIL ***"

        print(f"  {split_name:10s}: {overall}")
        print(f"    MaxDD {r['max_dd_pct']:.2f}% vs {dd_limit}% limit: {dd_sym}")
        print(f"    MaxDD(eq) {r['max_dd_equity_pct']:.2f}% vs {dd_limit}% limit: {dd_eq_sym}")
        print(f"    WorstDay {abs(r['worst_daily_pct']):.2f}% vs {daily_limit}% limit: {daily_sym}")

print("\n" + "=" * 90)
print("VERDICT")
print("=" * 90)

holdout = all_results["HOLDOUT"]
validate = all_results["VALIDATE"]

eval_safe = (holdout["max_dd_pct"] < 10.0 and holdout["max_dd_equity_pct"] < 10.0
             and abs(holdout["worst_daily_pct"]) < 5.0)
funded_safe = (holdout["max_dd_pct"] < 6.0 and holdout["max_dd_equity_pct"] < 6.0
               and abs(holdout["worst_daily_pct"]) < 3.0)

print(f"  Holdout PF:           {holdout['pf']:.2f} ({'profitable' if holdout['pf'] > 1.0 else 'UNPROFITABLE'})")
print(f"  Evaluation phase:     {'SAFE' if eval_safe else 'UNSAFE - would breach limits'}")
print(f"  Funded phase:         {'SAFE' if funded_safe else 'UNSAFE - would breach limits'}")
if holdout["days_to_target"]:
    print(f"  Est. days to pass eval: {holdout['days_to_target']}")
else:
    print(f"  Est. days to pass eval: did not reach 3% target in holdout period")

print("\n" + "=" * 90)
