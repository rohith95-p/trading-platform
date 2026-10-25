"""
Full Portfolio Backtest with Checkpoint Support
Tests ALL 6 strategies with different SL/TP configurations
"""

import sys
import json
import pickle
from pathlib import Path
from datetime import datetime
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import summarize, bootstrap_expectancy, monte_carlo_paths, drop_best_worst
from src.strategies.portfolio_v5_6_leg import (
    TrendPullbackV5,
    BBMeanReversionV5,
    NVMRPortfolioV5,
    FVGNYTightV5,
    PDHLRStrategyV5,
    NYLiquidityExpansionV5
)

# Configuration from command line
if len(sys.argv) != 3:
    print("Usage: python -m scripts.backtest_full_portfolio_checkpoints <sl_mult> <tp_mult>")
    print("Example: python -m scripts.backtest_full_portfolio_checkpoints 0.5 1.5")
    sys.exit(1)

SL_MULT = float(sys.argv[1])
TP_MULT = float(sys.argv[2])
CONFIG_NAME = f"portfolio_sl{SL_MULT}_tp{TP_MULT}"

# Setup paths
CHECKPOINT_DIR = Path("reports/backtest_checkpoints")
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_FILE = CHECKPOINT_DIR / f"checkpoint_{CONFIG_NAME}.pkl"
PROGRESS_FILE = CHECKPOINT_DIR / f"progress_{CONFIG_NAME}.json"
FINAL_REPORT = Path(f"reports/backtest_{CONFIG_NAME}.json")

print("=" * 80)
print(f"FULL 6-STRATEGY PORTFOLIO BACKTEST: SL={SL_MULT} TP={TP_MULT}")
print("=" * 80)
print(f"\nConfiguration: {CONFIG_NAME}")
print(f"Checkpoint: {CHECKPOINT_FILE}")
print(f"Progress: {PROGRESS_FILE}")
print(f"Final Report: {FINAL_REPORT}")

# Engine config
CFG = EngineConfig(
    symbol="XAUUSDm",
    starting_balance=100.0,
    sizing_mode="fixed",
    fixed_lots=0.01,
    max_concurrent=2,
    max_same_direction=2,
    enable_trailing=False,
    enable_pyramiding=False,
    enable_d1_bias_gate=True,
    direction_gate="d1_ema20",
    daily_loss_limit_mode="balance_pct",
    daily_loss_limit_pct=0.06,
    dedup_per_candle=True,
)
COST = SCENARIOS["realistic_ecn"]

# Save progress helper
def save_progress(stage, message, data=None):
    progress = {
        "config": CONFIG_NAME,
        "sl_mult": SL_MULT,
        "tp_mult": TP_MULT,
        "stage": stage,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "data": data or {}
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)
    print(f"[CHECKPOINT] {stage}: {message}")

# Stage 1: Load Data
save_progress("LOADING", "Loading XAUUSD historical data...")
print("\nLoading XAUUSD data (M15/M5/M1/D1)...")
try:
    bars = load_bars(symbol="XAUUSDm", timeframes=("M15", "M5", "M1", "D1"))
    data_info = {
        "m15_bars": len(bars.m15),
        "m1_bars": len(bars.m1) if bars.m1 is not None else 0,
        "d1_bars": len(bars.d1) if bars.d1 is not None else 0,
        "date_range_days": len(bars.d1) if bars.d1 is not None else 0
    }
    save_progress("LOADED", f"Data loaded: {data_info['d1_bars']} days", data_info)
    print(f"✅ Loaded {data_info['d1_bars']} days of data")
except Exception as e:
    save_progress("FAILED", f"Data loading failed: {str(e)}")
    raise

# Stage 2: Initialize ALL Strategies with custom SL/TP
save_progress("INITIALIZING", "Creating 6 strategy instances with custom SL/TP...")
try:
    strategies = []
    
    # Create instances and override SL/TP
    for StratClass in [TrendPullbackV5, BBMeanReversionV5, NVMRPortfolioV5, 
                        FVGNYTightV5, PDHLRStrategyV5, NYLiquidityExpansionV5]:
        strat = StratClass()
        # Override SL/TP for this test
        strat.sl_atr_mult = SL_MULT
        strat.tp_atr_mult = TP_MULT
        strategies.append(strat)
    
    strat_info = {
        "count": len(strategies),
        "names": [s.name for s in strategies],
        "sl_atr_mult": SL_MULT,
        "tp_atr_mult": TP_MULT
    }
    save_progress("INITIALIZED", f"Portfolio: {len(strategies)} strategies", strat_info)
    print(f"✅ Portfolio: {len(strategies)} strategies")
    for s in strategies:
        print(f"   - {s.name} (SL={s.sl_atr_mult}, TP={s.tp_atr_mult})")
except Exception as e:
    save_progress("FAILED", f"Strategy initialization failed: {str(e)}")
    raise

# Stage 3: Run Backtest
save_progress("BACKTESTING", "Running full portfolio backtest (60-180 seconds)...")
print("\nRunning backtest (this may take 2-3 minutes)...\n")
try:
    eng = BacktestEngine(bars=bars, cost=COST, config=CFG)
    result = eng.run(strategies)
    trades = result.trades
    
    if not trades:
        save_progress("FAILED", "No trades generated!")
        print("❌ No trades generated!")
        sys.exit(1)
    
    # Save raw trade data as checkpoint
    checkpoint_data = {
        "trades": [
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "is_buy": t.is_buy,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "lots": t.lots,
                "net_pl": t.net_pl,
                "gross_pl": t.gross_pl,
                "strategy": t.strategy,
                "exit_reason": t.exit_reason,
            }
            for t in trades
        ],
        "equity_curve": result.equity.tolist() if hasattr(result.equity, 'tolist') else list(result.equity),
        "starting_balance": CFG.starting_balance
    }
    
    with open(CHECKPOINT_FILE, "wb") as f:
        pickle.dump(checkpoint_data, f)
    
    backtest_info = {
        "total_trades": len(trades),
        "date_range": f"{datetime.utcfromtimestamp(trades[0].entry_time).date()} to {datetime.utcfromtimestamp(trades[-1].exit_time).date()}",
    }
    save_progress("BACKTEST_COMPLETE", f"Generated {len(trades)} trades", backtest_info)
    print(f"✅ Backtest complete: {len(trades)} trades")
    
except Exception as e:
    save_progress("FAILED", f"Backtest execution failed: {str(e)}")
    raise

# Stage 4: Calculate Metrics
save_progress("ANALYZING", "Calculating statistics...")
print("\nCalculating metrics...\n")
try:
    stats = summarize(trades, result.equity, CFG.starting_balance)
    
    core_metrics = {
        "trades": stats.trades,
        "wins": stats.wins,
        "losses": stats.losses,
        "win_rate": stats.win_rate,
        "profit_factor": stats.profit_factor,
        "net_pl": stats.net_pl,
        "gross_profit": stats.gross_profit,
        "gross_loss": stats.gross_loss,
        "expectancy": stats.expectancy,
        "avg_win": stats.avg_win,
        "avg_loss": stats.avg_loss,
        "payoff_ratio": stats.payoff_ratio,
        "max_drawdown": stats.max_drawdown,
        "max_drawdown_pct": stats.max_drawdown_pct,
        "return_pct": stats.return_pct,
        "end_balance": stats.end_balance,
        # === ELITE RISK METRICS (ALWAYS INCLUDED) ===
        "calmar_ratio": stats.calmar_ratio,
        "omega_ratio": stats.omega_ratio,
        "sortino_ratio": stats.sortino_ratio,
        "recovery_factor": stats.recovery_factor,
    }
    
    save_progress("METRICS_CALCULATED", "Core metrics computed", core_metrics)
    
    # Print summary
    print("=" * 80)
    print("PORTFOLIO BACKTEST RESULTS")
    print("=" * 80)
    print(f"\nConfiguration: Portfolio SL={SL_MULT} TP={TP_MULT}")
    print(f"Total Trades:      {stats.trades:,}")
    print(f"Win Rate:          {stats.win_rate:.2f}%")
    print(f"Profit Factor:     {stats.profit_factor:.3f}")
    print(f"Net P&L:           ${stats.net_pl:.2f}")
    print(f"Expectancy/trade:  ${stats.expectancy:.4f}")
    print(f"Avg Win:           ${stats.avg_win:.2f}")
    print(f"Avg Loss:          ${stats.avg_loss:.2f}")
    print(f"Payoff Ratio:      {stats.payoff_ratio:.2f}x")
    print(f"Max Drawdown:      {stats.max_drawdown_pct:.2f}%")
    print(f"Return:            {stats.return_pct:.2f}%")
    print(f"Ending Balance:    ${stats.end_balance:.2f}")
    
    # Per-strategy breakdown
    print(f"\n{'Strategy':<40} {'Trades':<8} {'PF':<8} {'Net P&L':<12}")
    print(f"{'-'*70}")
    for name, d in sorted(stats.by_strategy.items(), key=lambda x: x[1]['net_pl'], reverse=True):
        print(f"{name:<40} {d['trades']:<8} {d['profit_factor']:<8.3f} ${d['net_pl']:<11.2f}")
    
except Exception as e:
    save_progress("FAILED", f"Metrics calculation failed: {str(e)}")
    raise

# Stage 5: Bootstrap Analysis
save_progress("BOOTSTRAP", "Running bootstrap analysis (5000 resamples)...")
print("\nRunning bootstrap analysis...\n")
try:
    bs = bootstrap_expectancy(trades, n=5000)
    bootstrap_metrics = {
        "mean": bs.get("mean", 0),
        "p05": bs.get("p05", 0),
        "p50": bs.get("p50", 0),
        "p95": bs.get("p95", 0),
        "prob_negative": bs.get("prob_negative", 1.0)
    }
    save_progress("BOOTSTRAP_COMPLETE", "Bootstrap analysis done", bootstrap_metrics)
    
    print(f"Bootstrap 5th Percentile: ${bs.get('p05', 0):.4f}")
    print(f"Probability of Negative:  {bs.get('prob_negative', 1.0):.2%}")
    
except Exception as e:
    save_progress("WARNING", f"Bootstrap failed: {str(e)}")
    bootstrap_metrics = {}

# Stage 6: Monte Carlo
save_progress("MONTE_CARLO", "Running Monte Carlo simulation (5000 paths)...")
print("\nRunning Monte Carlo simulation...\n")
try:
    mc = monte_carlo_paths(trades, CFG.starting_balance, n=5000)
    mc_metrics = {
        "median_max_dd": mc.get("median_max_dd", 0),
        "p95_max_dd": mc.get("p95_max_dd", 0),
        "prob_50pct_drawdown": mc.get("prob_50pct_drawdown", 1.0),
        "prob_final_below_start": mc.get("prob_final_below_start", 1.0)
    }
    save_progress("MONTE_CARLO_COMPLETE", "Monte Carlo done", mc_metrics)
    
    print(f"Median Max DD:            ${mc.get('median_max_dd', 0):.2f}")
    print(f"P(50% drawdown):          {mc.get('prob_50pct_drawdown', 1.0):.2%}")
    
except Exception as e:
    save_progress("WARNING", f"Monte Carlo failed: {str(e)}")
    mc_metrics = {}

# Stage 7: Outlier Test
save_progress("OUTLIER_TEST", "Testing outlier dependency...")
try:
    dbw = drop_best_worst(trades)
    outlier_metrics = {
        "net_pl": dbw.get("net_pl", 0),
        "drop_best_1": dbw.get("drop_best_1", 0),
        "drop_best_3": dbw.get("drop_best_3", 0),
        "drop_best_5": dbw.get("drop_best_5", 0)
    }
    save_progress("OUTLIER_TEST_COMPLETE", "Outlier test done", outlier_metrics)
    
    print(f"\nDrop Best 3 Trades:       ${dbw.get('drop_best_3', 0):.2f}")
    
except Exception as e:
    save_progress("WARNING", f"Outlier test failed: {str(e)}")
    outlier_metrics = {}

# Stage 8: Final Report
save_progress("FINALIZING", "Generating final report...")
print("\n" + "=" * 80)
print("GENERATING FINAL REPORT")
print("=" * 80 + "\n")

final_report = {
    "generated_at": datetime.now().isoformat(),
    "configuration": {
        "name": CONFIG_NAME,
        "sl_atr_mult": SL_MULT,
        "tp_atr_mult": TP_MULT,
        "portfolio": "6-strategy full portfolio",
        "strategies": [s.name for s in strategies]
    },
    "data": data_info,
    "core_metrics": core_metrics,
    "bootstrap": bootstrap_metrics,
    "monte_carlo": mc_metrics,
    "outlier_test": outlier_metrics,
    "by_strategy": stats.by_strategy,
    "by_session": stats.by_session,
    "by_month": stats.by_month,
    "validation_gates": {
        "profit_factor_gt_1.3": stats.profit_factor > 1.3,
        "bootstrap_p05_positive": bootstrap_metrics.get("p05", -1) > 0,
        "prob_negative_lt_5pct": bootstrap_metrics.get("prob_negative", 1.0) < 0.05,
        "drop_best_3_positive": outlier_metrics.get("drop_best_3", -1) > 0,
        "mc_ruin_lt_1pct": mc_metrics.get("prob_50pct_drawdown", 1.0) < 0.01,
    }
}

# Calculate score
gates_passed = sum(1 for v in final_report["validation_gates"].values() if v)
total_gates = len(final_report["validation_gates"])
final_report["validation_score"] = f"{gates_passed}/{total_gates}"

# Save final report
with open(FINAL_REPORT, "w") as f:
    json.dump(final_report, f, indent=2)

save_progress("COMPLETE", f"Portfolio backtest complete! Score: {gates_passed}/{total_gates}", {
    "profit_factor": stats.profit_factor,
    "net_pl": stats.net_pl,
    "win_rate": stats.win_rate,
    "validation_score": final_report["validation_score"]
})

print(f"✅ Final report saved: {FINAL_REPORT}")
print(f"\nValidation Score: {gates_passed}/{total_gates} gates passed")
print("\n" + "=" * 80)
print("PORTFOLIO BACKTEST COMPLETE!")
print("=" * 80)

# Print validation gates
print("\nValidation Gates:")
for gate, passed in final_report["validation_gates"].items():
    icon = "✅" if passed else "❌"
    print(f"  [{icon}] {gate}")

print(f"\n{'='*80}\n")

sys.exit(0)
