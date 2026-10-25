"""
Quick verification: What parameters does TrendPullbackV5 actually use?
"""

from src.strategies.portfolio_v5_6_leg import TrendPullbackV5

strat = TrendPullbackV5()

print("=" * 60)
print("TRENDPULLBACK V5 PARAMETER VERIFICATION")
print("=" * 60)
print(f"\nStrategy Name: {strat.name}")
print(f"Magic Number: {strat.magic}")
print(f"SL ATR Mult: {strat.sl_atr_mult}")
print(f"TP ATR Mult: {strat.tp_atr_mult}")
print(f"\nSession: {strat.session}")
print(f"Fast EMA: {strat.fast_ema_period}")
print(f"Slow EMA: {strat.slow_ema_period}")
print(f"Pullback EMA: {strat.pullback_ema}")
print("\n" + "=" * 60)
print("EXPECTED VALUES:")
print("=" * 60)
print("Name: TREND_PULLBACK_V5")
print("SL: 0.1")
print("TP: 2.0")
print("\n" + "=" * 60)
