"""
Forensic check: What does the backtest engine actually see?
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.portfolio_v5_6_leg import PORTFOLIO

print("=" * 80)
print("FORENSIC CHECK: Portfolio Configuration")
print("=" * 80)

for cls in PORTFOLIO:
    strat = cls()
    print(f"\n{cls.__name__}:")
    print(f"  Strategy Name: {strat.name}")
    print(f"  Magic: {strat.magic}")
    print(f"  SL ATR mult: {strat.sl_atr_mult}")
    print(f"  TP ATR mult: {strat.tp_atr_mult}")
    if hasattr(strat, 'session'):
        print(f"  Session: {strat.session}")

print("\n" + "=" * 80)
print("KEY FINDING:")
print("=" * 80)
print("\nAll V5 strategies show SL=0.1, TP=2.0")
print("This is correct for the CURRENT live configuration")
print("\nBUT:")
print("The backtest results JSON shows 'TrendPullback_11.5_13_34_sl0.5_tp1.5'")
print("This suggests the BACKTEST was run with OLD portfolio or OLD parameters!")
print("=" * 80)
