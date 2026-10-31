"""Backtest the three momentum strategy candidates on DEV/VALIDATE/HOLDOUT splits.

Pre-registered: research/registry/PREREG_MomentumPortfolio_2026-10-25.md
Run: python -I scripts/research/momentum_portfolio_2026_10_25.py
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
from src.strategies.momentum_strategies import (
    D1EMACrossover,
    DonchianBreakout20,
    TSMOMGold,
)

ts = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())

SPLITS = [
    ("DEV",      ts(2022, 8, 1),  ts(2024, 2, 1)),
    ("VALIDATE", ts(2024, 2, 1),  ts(2025, 6, 1)),
    ("HOLDOUT",  ts(2025, 6, 1),  ts(2026, 10, 13)),
]

STRATEGY_FACTORIES = [
    ("D1_EMA_21_50",    lambda: D1EMACrossover(21, 50, sl_atr_mult=2.0, tp_atr_mult=4.0)),
    ("DONCHIAN_D1_20",  lambda: DonchianBreakout20(20, sl_atr_mult=2.0, tp_atr_mult=6.0)),
    ("TSMOM_63D",       lambda: TSMOMGold(63, sl_atr_mult=1.5, tp_atr_mult=3.0)),
]

print("Loading data...", flush=True)
bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1"))
# DEV/TEST here ran on M15 candles, not M1 sub-bars: exits are ambiguous and the
# numbers read high (M1 A/B: PF 0.93 vs 1.38). Kept as a record of what was run on
# 2026-10-25; m1_policy="coarse" is now required to opt into it. Do not compare these
# DEV/TEST figures with M1 results.
coarse = dataclasses.replace(bars, m1=None)

results = {}

for strat_name, factory in STRATEGY_FACTORIES:
    print(f"\n{'='*70}")
    print(f"Strategy: {strat_name}")
    print(f"{'='*70}")
    for split_name, start, end in SPLITS:
        strat = factory()
        b = bars if split_name == "HOLDOUT" else coarse
        cfg = EngineConfig(
        m1_policy="coarse",
            sizing_mode="fixed",
            fixed_lots=0.01,
            starting_balance=105.74,
            history_bars=7500,
            enable_d1_bias_gate=False,
            dedup_per_candle=True,
            max_concurrent=2,
            max_same_direction=2,
        )
        engine = BacktestEngine(bars=b, cost=SCENARIOS["realistic_ecn"], config=cfg)
        res = engine.run([strat], start, end)
        d = summarize(res.trades, res.equity, 105.74).to_dict()

        bal = np.array([105.74] + [t.balance_after for t in res.trades])
        peak = np.maximum.accumulate(bal)
        max_dd = (peak - bal).max()
        dd_pct = max_dd / peak[np.argmax(peak - bal)] * 100 if len(peak) > 0 and peak.max() > 0 else 0
        losses = [-t.net_pl for t in res.trades if t.net_pl < 0]

        key = (strat_name, split_name)
        results[key] = d

        pf = d.get("profit_factor", 0)
        n_trades = d.get("trades", 0)
        win_rate = d.get("win_rate", 0)
        net = d.get("net_pl", 0)

        passed = True
        if split_name == "DEV" and pf < 1.2:
            passed = False
        elif split_name == "VALIDATE" and pf < 1.1:
            passed = False
        elif split_name == "HOLDOUT" and pf < 1.0:
            passed = False
        if dd_pct > 35:
            passed = False
        if n_trades < 10:
            passed = False

        status = "PASS" if passed else "FAIL"

        print(f"  {split_name:10s} n={n_trades:4d} win={win_rate:5.1f}% PF={pf:.3f} "
              f"net=${net:8.2f} end=${bal[-1]:8.2f} maxDD=${max_dd:7.2f} ({dd_pct:4.1f}%) "
              f"avgLoss=${np.mean(losses) if losses else 0:.2f} [{status}]", flush=True)

# Portfolio combo: run all three together
print(f"\n{'='*70}")
print("PORTFOLIO: All three momentum strategies combined")
print(f"{'='*70}")
for split_name, start, end in SPLITS:
    strats = [f() for _, f in STRATEGY_FACTORIES]
    b = bars if split_name == "HOLDOUT" else coarse
    cfg = EngineConfig(m1_policy="coarse", 
        sizing_mode="fixed",
        fixed_lots=0.01,
        starting_balance=105.74,
        history_bars=7500,
        enable_d1_bias_gate=False,
        dedup_per_candle=True,
        max_concurrent=2,
        max_same_direction=2,
    )
    engine = BacktestEngine(bars=b, cost=SCENARIOS["realistic_ecn"], config=cfg)
    res = engine.run(strats, start, end)
    d = summarize(res.trades, res.equity, 105.74).to_dict()

    bal = np.array([105.74] + [t.balance_after for t in res.trades])
    peak = np.maximum.accumulate(bal)
    max_dd = (peak - bal).max()
    dd_pct = max_dd / peak[np.argmax(peak - bal)] * 100 if len(peak) > 0 and peak.max() > 0 else 0

    pf = d.get("profit_factor", 0)
    n_trades = d.get("trades", 0)
    win_rate = d.get("win_rate", 0)
    net = d.get("net_pl", 0)

    # per-strategy breakdown
    by_strat = {}
    for t in res.trades:
        by_strat.setdefault(t.strategy, []).append(t)

    print(f"  {split_name:10s} n={n_trades:4d} win={win_rate:5.1f}% PF={pf:.3f} "
          f"net=${net:8.2f} end=${bal[-1]:8.2f} maxDD=${max_dd:7.2f} ({dd_pct:4.1f}%)", flush=True)
    for sn, trades in sorted(by_strat.items()):
        gross = sum(t.gross_pl for t in trades)
        cost = sum(t.commission + abs(t.swap) for t in trades)
        net_s = sum(t.net_pl for t in trades)
        wins = sum(1 for t in trades if t.net_pl > 0)
        wr = wins / len(trades) * 100 if trades else 0
        print(f"    {sn:25s} n={len(trades):3d} win={wr:5.1f}% net=${net_s:8.2f}", flush=True)

print("\nDone.", flush=True)
