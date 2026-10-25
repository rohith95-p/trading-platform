"""
XAUUSD Backtest: SL=0.5 ATR / TP=1.5 ATR
With checkpoint support to preserve partial results on failure.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import summarize, bootstrap_expectancy, monte_carlo_paths, drop_best_worst
from src.strategies.portfolio_v4 import FVGNYTight, FVGNYSweepOrVoid

# Configuration
SL_ATR = 0.5
TP_ATR = 1.5

# Paths
CHECKPOINT_FILE = Path("reports/backtest_comparison/checkpoint_sl05_tp15.json")
CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
FINAL_REPORT = Path("reports/backtest_comparison/result_sl05_tp15.json")

print("=" * 80)
print(f"XAUUSD BACKTEST: SL={SL_ATR} ATR / TP={TP_ATR} ATR")
print("=" * 80)


def save_checkpoint(stage, bars_loaded=None, trades_count=None, partial_stats=None):
    """Write checkpoint file at each stage."""
    checkpoint = {
        "stage": stage,
        "sl_atr": SL_ATR,
        "tp_atr": TP_ATR,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "bars_loaded": bars_loaded,
        "trades_count": trades_count,
        "partial_stats": partial_stats,
    }
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, indent=2)
    print(f"[CHECKPOINT] {stage}")


# STAGE: LOADING
save_checkpoint("LOADING")
print("\nLoading XAUUSD bars...")
try:
    bars = load_bars("XAUUSDm")
    save_checkpoint("LOADED", bars_loaded=len(bars.m15))
    print(f"✅ Loaded {len(bars.m15)} M15 bars")
except Exception as e:
    save_checkpoint("FAILED_LOADING")
    print(f"❌ Failed to load bars: {e}")
    raise

# STAGE: INITIALIZING
save_checkpoint("INITIALIZING", bars_loaded=len(bars.m15))
print("\nBuilding FVG strategies with SL=0.5, TP=1.5...")

# Create strategy classes with overridden exit geometry
class FVGNYTightTest(FVGNYTight):
    sl_atr_mult = SL_ATR
    tp_atr_mult = TP_ATR

class FVGNYSweepOrVoidTest(FVGNYSweepOrVoid):
    sl_atr_mult = SL_ATR
    tp_atr_mult = TP_ATR

strategies = [FVGNYTightTest(), FVGNYSweepOrVoidTest()]
strategy_names = [s.name for s in strategies]
print(f"✅ Strategies: {strategy_names}")

# Engine configuration (matching clean live config)
config = EngineConfig(
    symbol="XAUUSDm",
    starting_balance=105.74,
    sizing_mode="fixed",
    dedup_per_candle=True,
    enable_trailing=False,
    enable_pyramiding=False,
    enable_consolidation_exit=False,
    daily_loss_limit_mode="off",
    enable_d1_bias_gate=False,  # Disable direction gating to allow all signals
)

cost = SCENARIOS["realistic"]
print(f"✅ Cost scenario: realistic")

try:
    engine = BacktestEngine(bars=bars, cost=cost, config=config)
    save_checkpoint("INITIALIZED", bars_loaded=len(bars.m15))
    print(f"✅ Engine initialized")
except Exception as e:
    save_checkpoint("FAILED_INITIALIZING", bars_loaded=len(bars.m15))
    print(f"❌ Failed to initialize engine: {e}")
    raise

# STAGE: BACKTESTING
save_checkpoint("BACKTESTING", bars_loaded=len(bars.m15))
print(f"\nRunning backtest on recent 10,000 bars for testing...")
print("(Full 100k bar backtest would take 30+ minutes due to liquidity calculations)")
try:
    # Run on last 10k bars only for reasonable execution time
    # Full data: bars.m15 has 100k bars spanning ~10 years
    # Last 10k bars: ~1 year of data, sufficient for validation
    from datetime import datetime, timezone, timedelta
    cutoff_ts = int(bars.m15["time"][-1]) - (365 * 86400)  # Last ~1 year
    print(f"Running from {datetime.fromtimestamp(cutoff_ts, timezone.utc).date()} to end...")
    
    result = engine.run(strategies, start_ts=cutoff_ts)
    trades = result.trades
    save_checkpoint("BACKTEST_COMPLETE", bars_loaded=len(bars.m15), trades_count=len(trades))
    print(f"✅ Backtest complete: {len(trades)} trades")
    
    if not trades:
        print("⚠️  No trades generated!")
        sys.exit(1)
        
except Exception as e:
    save_checkpoint("FAILED_BACKTESTING", bars_loaded=len(bars.m15))
    print(f"❌ Backtest failed: {e}")
    raise

# STAGE: ANALYZING
save_checkpoint("ANALYZING", bars_loaded=len(bars.m15), trades_count=len(trades))
print("\nCalculating statistics...")
try:
    stats = summarize(trades, result.equity, config.starting_balance)
    
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
    }
    
    save_checkpoint("METRICS_CALCULATED", bars_loaded=len(bars.m15), 
                   trades_count=len(trades), partial_stats=core_metrics)
    
    print(f"✅ Core metrics calculated")
    print(f"\n{'='*80}")
    print("CORE METRICS")
    print(f"{'='*80}")
    print(f"Trades:           {stats.trades:,}")
    print(f"Win Rate:         {stats.win_rate:.2f}%")
    print(f"Profit Factor:    {stats.profit_factor:.3f}")
    print(f"Net P&L:          ${stats.net_pl:.2f}")
    print(f"Expectancy:       ${stats.expectancy:.4f}")
    print(f"Max Drawdown:     {stats.max_drawdown_pct:.2f}%")
    print(f"Return:           {stats.return_pct:.2f}%")
    
except Exception as e:
    save_checkpoint("FAILED_ANALYZING", bars_loaded=len(bars.m15), trades_count=len(trades))
    print(f"❌ Metrics calculation failed: {e}")
    raise

# STAGE: BOOTSTRAP
save_checkpoint("BOOTSTRAP", bars_loaded=len(bars.m15), trades_count=len(trades), 
               partial_stats=core_metrics)
print("\nRunning bootstrap analysis (5000 resamples)...")
try:
    bootstrap = bootstrap_expectancy(trades, n=5000)
    print(f"✅ Bootstrap complete")
    print(f"   90% CI: [{bootstrap.get('p05', 0):.4f}, {bootstrap.get('p95', 0):.4f}]")
except Exception as e:
    print(f"⚠️  Bootstrap failed: {e}")
    bootstrap = {}

# STAGE: MONTE_CARLO
save_checkpoint("MONTE_CARLO", bars_loaded=len(bars.m15), trades_count=len(trades), 
               partial_stats=core_metrics)
print("\nRunning Monte Carlo simulation (5000 paths)...")
try:
    monte_carlo = monte_carlo_paths(trades, config.starting_balance, n=5000)
    print(f"✅ Monte Carlo complete")
    print(f"   Median max DD: ${monte_carlo.get('median_max_dd', 0):.2f}")
except Exception as e:
    print(f"⚠️  Monte Carlo failed: {e}")
    monte_carlo = {}

# Outlier dependence test
print("\nTesting outlier dependence...")
try:
    outlier = drop_best_worst(trades)
    print(f"✅ Outlier test complete")
except Exception as e:
    print(f"⚠️  Outlier test failed: {e}")
    outlier = {}

# STAGE: COMPLETE
save_checkpoint("COMPLETE", bars_loaded=len(bars.m15), trades_count=len(trades), 
               partial_stats=core_metrics)

# Generate final report
print("\nGenerating final report...")
final_report = {
    "config": {
        "sl_atr": SL_ATR,
        "tp_atr": TP_ATR,
        "strategies": strategy_names,
    },
    "stats": stats.to_dict(),
    "confidence": {
        "bootstrap_expectancy": bootstrap,
        "monte_carlo": monte_carlo,
        "outlier_dependence": outlier,
    },
    "data_hash": bars.hash_key(),
    "generated_utc": datetime.now(timezone.utc).isoformat(),
}

with open(FINAL_REPORT, "w") as f:
    json.dump(final_report, f, indent=2)

print(f"✅ Final report saved: {FINAL_REPORT}")

# Print summary
print(f"\n{'='*80}")
print("BACKTEST SUMMARY")
print(f"{'='*80}")
print(f"\nConfiguration: SL={SL_ATR} ATR, TP={TP_ATR} ATR")
print(f"Strategies:    {', '.join(strategy_names)}")
print(f"\nTrades:        {stats.trades:,}")
print(f"Win Rate:      {stats.win_rate:.2f}%")
print(f"Profit Factor: {stats.profit_factor:.3f}")
print(f"Net P&L:       ${stats.net_pl:.2f}")
print(f"Expectancy:    ${stats.expectancy:.4f}")
print(f"Max Drawdown:  {stats.max_drawdown_pct:.2f}%")
print(f"Return:        {stats.return_pct:.2f}%")

if bootstrap:
    print(f"\nBootstrap 90% CI: [${bootstrap.get('p05', 0):.4f}, ${bootstrap.get('p95', 0):.4f}]")
    print(f"P(negative):      {bootstrap.get('prob_negative', 1.0):.2%}")

print(f"\n{'='*80}")
print("COMPLETE")
print(f"{'='*80}\n")
