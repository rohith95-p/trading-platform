"""Backtest XAUUSD with SL=0.1 ATR / TP=2.0 ATR configuration.

Checkpoints at each stage to preserve partial results on failure.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.metrics import (
    summarize,
    bootstrap_expectancy,
    monte_carlo_paths,
    drop_best_worst,
)
from src.strategies.portfolio_v4 import FVGNYTight, FVGNYSweepOrVoid

# Configuration
SL_ATR = 0.1
TP_ATR = 2.0
CHECKPOINT_PATH = "c:\\projects\\ultra_core\\reports\\backtest_comparison\\checkpoint_sl01_tp20.json"
RESULT_PATH = "c:\\projects\\ultra_core\\reports\\backtest_comparison\\result_sl01_tp20.json"


def write_checkpoint(stage: str, **kwargs) -> None:
    """Write checkpoint file with current stage and optional data."""
    checkpoint = {
        "stage": stage,
        "sl_atr": SL_ATR,
        "tp_atr": TP_ATR,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "bars_loaded": kwargs.get("bars_loaded"),
        "trades_count": kwargs.get("trades_count"),
        "partial_stats": kwargs.get("partial_stats"),
    }
    
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2)
    print(f"[CHECKPOINT] {stage}")


def main():
    print("=" * 70)
    print("XAUUSD Backtest: SL=0.1 ATR / TP=2.0 ATR")
    print("=" * 70)
    
    # Stage 1: Load data
    write_checkpoint("LOADING")
    print("\n[1/9] Loading bars...")
    bars = load_bars('XAUUSDm')
    write_checkpoint("LOADED", bars_loaded=len(bars.m15))
    print(f"  ✓ Loaded {len(bars.m15)} M15 bars")
    print(f"  Data hash: {bars.hash_key()}")
    
    # Stage 2: Build strategies
    write_checkpoint("INITIALIZING")
    print("\n[2/9] Building strategies...")
    
    # Create strategy instances with overridden sl_atr_mult and tp_atr_mult
    class FVGNYTight_SL01_TP20(FVGNYTight):
        sl_atr_mult = SL_ATR
        tp_atr_mult = TP_ATR
    
    class FVGNYSweepOrVoid_SL01_TP20(FVGNYSweepOrVoid):
        sl_atr_mult = SL_ATR
        tp_atr_mult = TP_ATR
    
    # Instantiate the strategies
    strategies = [FVGNYTight_SL01_TP20(), FVGNYSweepOrVoid_SL01_TP20()]
    print(f"  ✓ Built {len(strategies)} strategies:")
    for s in strategies:
        print(f"    - {s.name} (SL={s.sl_atr_mult}, TP={s.tp_atr_mult})")
    
    # Stage 3: Configure engine
    print("\n[3/9] Configuring engine...")
    config = EngineConfig(
        symbol='XAUUSDm',
        starting_balance=105.74,
        sizing_mode='fixed',
        dedup_per_candle=True,
        enable_trailing=False,
        enable_pyramiding=False,
        enable_consolidation_exit=False,
        daily_loss_limit_mode='off',
        enable_d1_bias_gate=False,  # Disable direction gating to allow all signals
    )
    print(f"  ✓ Config: starting_balance=${config.starting_balance}, sizing_mode={config.sizing_mode}")
    print(f"  ✓ D1 bias gate disabled, dedup enabled")
    
    # Stage 4: Create engine
    cost = SCENARIOS['realistic']
    engine = BacktestEngine(bars, cost, config)
    write_checkpoint("INITIALIZED")
    print(f"  ✓ Engine initialized with cost model: realistic")
    
    # Stage 5: Run backtest
    write_checkpoint("BACKTESTING")
    print("\n[4/9] Running backtest...")
    result = engine.run(strategies)
    write_checkpoint("BACKTEST_COMPLETE", trades_count=len(result.trades))
    print(f"  ✓ Backtest complete: {len(result.trades)} trades")
    
    # Stage 6: Compute summary stats
    write_checkpoint("ANALYZING")
    print("\n[5/9] Computing statistics...")
    stats = summarize(result.trades, result.equity, config.starting_balance)
    
    # Save partial stats for checkpoint
    partial_stats = {
        "trades": stats.trades,
        "win_rate": stats.win_rate,
        "profit_factor": stats.profit_factor,
        "net_pl": stats.net_pl,
        "expectancy": stats.expectancy,
        "max_drawdown_pct": stats.max_drawdown_pct,
        "return_pct": stats.return_pct,
    }
    write_checkpoint("METRICS_CALCULATED", partial_stats=partial_stats)
    
    print(f"  ✓ Trades: {stats.trades}, Win Rate: {stats.win_rate}%")
    print(f"  ✓ Profit Factor: {stats.profit_factor}, Net P&L: ${stats.net_pl}")
    print(f"  ✓ Expectancy: ${stats.expectancy}, Max DD: {stats.max_drawdown_pct}%")
    
    # Stage 7: Bootstrap confidence intervals
    write_checkpoint("BOOTSTRAP")
    print("\n[6/9] Computing bootstrap confidence intervals...")
    bootstrap_result = bootstrap_expectancy(result.trades) if result.trades else {}
    print(f"  ✓ Bootstrap complete")
    if bootstrap_result:
        print(f"    90% CI: [${bootstrap_result.get('p05', 0):.4f}, ${bootstrap_result.get('p95', 0):.4f}]")
    
    # Stage 8: Monte Carlo simulation
    write_checkpoint("MONTE_CARLO")
    print("\n[7/9] Running Monte Carlo simulation...")
    mc_result = monte_carlo_paths(result.trades, config.starting_balance) if result.trades else {}
    print(f"  ✓ Monte Carlo complete")
    if mc_result:
        print(f"    P95 Max DD: ${mc_result.get('p95_max_dd', 0):.2f}")
        print(f"    P(50% DD): {mc_result.get('prob_50pct_drawdown', 0):.1%}")
    
    # Stage 9: Outlier analysis
    print("\n[8/9] Analyzing outlier dependence...")
    outlier_result = drop_best_worst(result.trades) if result.trades else {}
    print(f"  ✓ Outlier analysis complete")
    if outlier_result:
        print(f"    Drop best 3: ${outlier_result.get('drop_best_3', 0):.2f}")
    
    # Stage 10: Write final report
    write_checkpoint("COMPLETE")
    print("\n[9/9] Writing final report...")
    
    report = {
        "config": {
            "sl_atr": SL_ATR,
            "tp_atr": TP_ATR,
            "strategies": [s.name for s in strategies],
        },
        "stats": stats.to_dict(),
        "confidence": {
            "bootstrap_expectancy": bootstrap_result,
            "monte_carlo": mc_result,
            "outlier_dependence": outlier_result,
        },
        "data_hash": bars.hash_key(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    
    print(f"  ✓ Report written to: {RESULT_PATH}")
    
    # Final summary
    print("\n" + "=" * 70)
    print("BACKTEST COMPLETE")
    print("=" * 70)
    print(f"Configuration: SL={SL_ATR} ATR, TP={TP_ATR} ATR")
    print(f"Strategies: {', '.join([s.name for s in strategies])}")
    print(f"\nResults:")
    print(f"  Trades:           {stats.trades}")
    print(f"  Win Rate:         {stats.win_rate}%")
    print(f"  Profit Factor:    {stats.profit_factor}")
    print(f"  Net P&L:          ${stats.net_pl}")
    print(f"  Expectancy:       ${stats.expectancy}")
    print(f"  Max Drawdown:     {stats.max_drawdown_pct}%")
    print(f"  Return:           {stats.return_pct}%")
    
    if bootstrap_result:
        print(f"\nConfidence:")
        print(f"  Bootstrap 90% CI: [${bootstrap_result.get('p05', 0):.4f}, ${bootstrap_result.get('p95', 0):.4f}]")
        print(f"  P(negative):      {bootstrap_result.get('prob_negative', 0):.1%}")
    
    print(f"\nFiles:")
    print(f"  Checkpoint:  {CHECKPOINT_PATH}")
    print(f"  Result:      {RESULT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()
