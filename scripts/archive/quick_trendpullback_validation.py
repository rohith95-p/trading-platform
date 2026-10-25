"""
Quick TrendPullback validation: Compare 0.5/1.5 vs 0.1/2.0 on recent data
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import summarize
from src.strategies.grid_strategies import TrendPullbackStrat

# Config
CFG = EngineConfig(
    symbol="XAUUSDm",
    starting_balance=100.0,
    sizing_mode="fixed",
    fixed_lots=0.01,
    max_concurrent=1,
    max_same_direction=1,
    enable_trailing=False,
    enable_pyramiding=False,
    enable_d1_bias_gate=True,
    direction_gate="d1_ema20",
    daily_loss_limit_mode="balance_pct",
    daily_loss_limit_pct=0.06,
    dedup_per_candle=True,
)
COST = SCENARIOS["realistic_ecn"]

print("=" * 80)
print("FORENSIC COMPARISON: TrendPullback 0.5/1.5 vs 0.1/2.0")
print("=" * 80)

# Load data
print("\nLoading XAUUSD data (M15 + D1 only for speed)...")
bars = load_bars(symbol="XAUUSDm", timeframes=("M15", "D1"))

print(f"Data range: {len(bars.d1)} days (~{len(bars.d1)/365:.1f} years)")

results = {}

for label, sl, tp in [
    ("OLD (0.5/1.5)", 0.5, 1.5),
    ("NEW (0.1/2.0)", 0.1, 2.0),
]:
    print(f"\n{'='*80}")
    print(f"Testing: {label}")
    print(f"{'='*80}")
    
    strat = TrendPullbackStrat(session=(11.5, 21.5), fast_ema=13, slow_ema=34, pullback_ema=13, sl=sl, tp=tp)
    
    eng = BacktestEngine(bars=bars, cost=COST, config=CFG)
    result = eng.run([strat])
    trades = result.trades
    
    if not trades:
        print(f"❌ No trades generated for {label}!")
        continue
    
    stats = summarize(trades, result.equity, CFG.starting_balance)
    
    print(f"\nTrades: {stats.trades}")
    print(f"Win Rate: {stats.win_rate:.1f}%")
    print(f"Profit Factor: {stats.profit_factor:.3f}")
    print(f"Net P&L: ${stats.net_pl:.2f}")
    print(f"Avg Win: ${stats.avg_win:.2f}")
    print(f"Avg Loss: ${stats.avg_loss:.2f}")
    print(f"Payoff Ratio: {stats.payoff_ratio:.2f}x")
    print(f"Max Drawdown: {stats.max_drawdown_pct:.1f}%")
    print(f"Expectancy: ${stats.expectancy:.4f}")
    
    results[label] = {
        "trades": stats.trades,
        "win_rate": stats.win_rate,
        "profit_factor": stats.profit_factor,
        "net_pl": stats.net_pl,
        "avg_win": stats.avg_win,
        "avg_loss": stats.avg_loss,
        "payoff_ratio": stats.payoff_ratio,
        "max_dd_pct": stats.max_drawdown_pct,
        "expectancy": stats.expectancy,
    }

print(f"\n{'='*80}")
print("COMPARISON SUMMARY")
print(f"{'='*80}\n")

print(f"{'Metric':<25} {'OLD (0.5/1.5)':<20} {'NEW (0.1/2.0)':<20} {'Change':<15}")
print(f"{'-'*80}")

old = results.get("OLD (0.5/1.5)", {})
new = results.get("NEW (0.1/2.0)", {})

for metric in ["trades", "win_rate", "profit_factor", "net_pl", "avg_win", "avg_loss", "payoff_ratio", "max_dd_pct", "expectancy"]:
    old_val = old.get(metric, 0)
    new_val = new.get(metric, 0)
    
    if old_val != 0:
        change_pct = ((new_val - old_val) / abs(old_val)) * 100
        change_str = f"{change_pct:+.1f}%"
    else:
        change_str = "N/A"
    
    print(f"{metric:<25} {old_val:>18.3f}  {new_val:>18.3f}  {change_str:>13}")

print(f"\n{'='*80}")
print("FORENSIC VERDICT")
print(f"{'='*80}\n")

if new.get("profit_factor", 0) < old.get("profit_factor", 0):
    print("⚠️ NEW configuration (0.1/2.0) has LOWER Profit Factor than OLD (0.5/1.5)")
    print("⚠️ This explains why live performance doesn't match the backtest report!")
    print("\nThe 'excellent backtest' you saw was for 0.5/1.5, NOT 0.1/2.0!")
else:
    print("✅ NEW configuration (0.1/2.0) is equal or better than OLD (0.5/1.5)")

# Save results
out = Path("reports/trendpullback_config_comparison.json")
with open(out, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*80}")
print(f"Results saved: {out}")
print(f"{'='*80}\n")
