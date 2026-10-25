"""
Quick EMA200 vs EMA20 D1 gate comparison
Uses existing backtest infrastructure
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import MetaTrader5 as mt5
import numpy as np

# Simple EMA calculation
def calc_ema(closes, period):
    ema = np.full_like(closes, np.nan, dtype=float)
    if len(closes) >= period:
        multiplier = 2.0 / (period + 1.0)
        ema[period - 1] = np.mean(closes[:period])
        for i in range(period, len(closes)):
            ema[i] = (closes[i] - ema[i - 1]) * multiplier + ema[i - 1]
    return ema


def main():
    # Initialize MT5
    if not mt5.initialize():
        print("MT5 initialization failed")
        return
    
    # Get D1 data
    rates = mt5.copy_rates_from_pos("XAUUSDm", mt5.TIMEFRAME_D1, 0, 500)
    
    if rates is None or len(rates) == 0:
        print("Failed to get D1 rates")
        mt5.shutdown()
        return
    
    closes = rates['close']
    
    # Calculate both EMAs
    ema20 = calc_ema(closes, 20)
    ema200 = calc_ema(closes, 200)
    
    # Current status (D1[-2] is completed daily bar)
    current_price = closes[-2]
    ema20_val = ema20[-2]
    ema200_val = ema200[-2]
    
    bias_ema20 = "BULLISH" if current_price > ema20_val else "BEARISH"
    bias_ema200 = "BULLISH" if current_price > ema200_val else "BEARISH"
    
    print("\n" + "="*70)
    print("D1 GATE COMPARISON - CURRENT STATUS")
    print("="*70)
    print(f"\nCurrent D1[-2] Close: ${current_price:.2f}")
    print(f"\nEMA20:  ${ema20_val:.2f}  ->  Bias: {bias_ema20}")
    print(f"EMA200: ${ema200_val:.2f}  ->  Bias: {bias_ema200}")
    
    if bias_ema20 != bias_ema200:
        print(f"\n⚠️  DIVERGENCE DETECTED!")
        print(f"   EMA20 says: {bias_ema20}")
        print(f"   EMA200 says: {bias_ema200}")
        
        if bias_ema200 == "BULLISH":
            print(f"\n✓ EMA200 would ALLOW BUY trades (vs EMA20 blocking)")
        else:
            print(f"\n✓ EMA20 would ALLOW SELL trades (vs EMA200 blocking)")
    else:
        print(f"\n✓ AGREEMENT: Both EMAs show {bias_ema20} bias")
    
    # Historical analysis - last 60 days
    print(f"\n" + "="*70)
    print("HISTORICAL ANALYSIS - Last 60 Trading Days")
    print("="*70)
    
    lookback = 60
    ema20_bullish = 0
    ema200_bullish = 0
    agreement = 0
    
    for i in range(-lookback, -1):
        idx = i - 1  # Use completed bars
        if not np.isnan(ema20[idx]) and not np.isnan(ema200[idx]):
            b20 = closes[idx] > ema20[idx]
            b200 = closes[idx] > ema200[idx]
            
            if b20:
                ema20_bullish += 1
            if b200:
                ema200_bullish += 1
            if b20 == b200:
                agreement += 1
    
    ema20_bearish = lookback - ema20_bullish
    ema200_bearish = lookback - ema200_bullish
    
    print(f"\nEMA20 Bias Distribution:")
    print(f"  BULLISH: {ema20_bullish} days ({ema20_bullish/lookback*100:.1f}%)")
    print(f"  BEARISH: {ema20_bearish} days ({ema20_bearish/lookback*100:.1f}%)")
    
    print(f"\nEMA200 Bias Distribution:")
    print(f"  BULLISH: {ema200_bullish} days ({ema200_bullish/lookback*100:.1f}%)")
    print(f"  BEARISH: {ema200_bearish} days ({ema200_bearish/lookback*100:.1f}%)")
    
    print(f"\nAgreement Rate: {agreement}/{lookback} days ({agreement/lookback*100:.1f}%)")
    print(f"Divergence Rate: {lookback-agreement}/{lookback} days ({(lookback-agreement)/lookback*100:.1f}%)")
    
    # Trading implications
    print(f"\n" + "="*70)
    print("TRADING IMPLICATIONS")
    print("="*70)
    
    if ema200_bullish > ema20_bullish:
        diff = ema200_bullish - ema20_bullish
        print(f"\n📊 EMA200 is MORE BULLISH")
        print(f"   Would allow BUY trades {diff} more days ({diff/lookback*100:.1f}%)")
        print(f"   = More trading opportunities, but potentially lower quality")
    elif ema20_bullish > ema200_bullish:
        diff = ema20_bullish - ema200_bullish
        print(f"\n📊 EMA20 is MORE BULLISH")
        print(f"   Would allow BUY trades {diff} more days ({diff/lookback*100:.1f}%)")
    else:
        print(f"\n📊 Both EMAs equally bullish over 60 days")
    
    # Recommendation
    print(f"\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    
    if current_price > ema200_val and bias_ema20 == "BEARISH":
        gap_pct = ((current_price - ema20_val) / ema20_val) * 100
        print(f"\n✅ SWITCH TO EMA200 RECOMMENDED")
        print(f"\n   Current situation:")
        print(f"   - Price above EMA200 (long-term BULLISH)")
        print(f"   - Price below EMA20 (short-term BEARISH)")
        print(f"   - Gap: {abs(gap_pct):.2f}% below EMA20")
        print(f"\n   EMA200 would allow BUY trades TODAY")
        print(f"   EMA20 is blocking them")
        print(f"\n   Your 200 EMA Filtered Parabolic SAR indicator agrees with EMA200")
    elif current_price < ema200_val and bias_ema20 == "BULLISH":
        print(f"\n⚠️  CAUTION: EMA20 allowing BUYs in long-term downtrend")
        print(f"   EMA200 would be more conservative")
    else:
        print(f"\n✓ KEEP EMA20")
        print(f"   Both EMAs currently agree: {bias_ema20}")
        print(f"   No immediate benefit to switching")
    
    mt5.shutdown()


if __name__ == "__main__":
    main()
