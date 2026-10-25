"""
Check actual broker spread and execution quality for XAUUSD
"""
import MetaTrader5 as mt5
import time
from datetime import datetime
import statistics

print("="*80)
print("BROKER EXECUTION QUALITY CHECK")
print("="*80)

# Initialize MT5
if not mt5.initialize():
    print("❌ MT5 not connected!")
    exit(1)

# Get account info
info = mt5.account_info()
print(f"\nBroker: {info.company}")
print(f"Server: {info.server}")
print(f"Account: {info.login}")

# Find XAUUSD symbol (might be XAUUSDm or XAUUSD)
symbols_to_check = ['XAUUSD', 'XAUUSDm', 'XAUUSD247m']
xauusd_symbol = None

for sym in symbols_to_check:
    if mt5.symbol_select(sym, True):
        xauusd_symbol = sym
        print(f"\n✅ Found symbol: {xauusd_symbol}")
        break

if not xauusd_symbol:
    print("\n❌ XAUUSD not found! Available gold symbols:")
    all_symbols = mt5.symbols_get()
    gold_symbols = [s.name for s in all_symbols if 'XAU' in s.name or 'GOLD' in s.name.upper()]
    for s in gold_symbols:
        print(f"  - {s}")
    mt5.shutdown()
    exit(1)

# Get symbol info
symbol_info = mt5.symbol_info(xauusd_symbol)

print("\n" + "="*80)
print("SYMBOL SPECIFICATIONS")
print("="*80)

print(f"\nSymbol: {xauusd_symbol}")
print(f"Description: {symbol_info.description}")
print(f"Currency Base: {symbol_info.currency_base}")
print(f"Currency Profit: {symbol_info.currency_profit}")
print(f"Digits: {symbol_info.digits}")
print(f"Point: {symbol_info.point}")
print(f"Trade Mode: {symbol_info.trade_mode}")

print(f"\nLot Specifications:")
print(f"  Min Lot: {symbol_info.volume_min}")
print(f"  Max Lot: {symbol_info.volume_max}")
print(f"  Lot Step: {symbol_info.volume_step}")

print(f"\nStops & Levels:")
try:
    print(f"  Stops Level: {symbol_info.trade_stops_level} points")
    print(f"  Freeze Level: {symbol_info.trade_freeze_level} points")
except AttributeError:
    print(f"  Stops Level: N/A")
    print(f"  Freeze Level: N/A")

# Calculate actual pip value for XAUUSD
# For XAUUSD, 1 pip = 0.01 movement
# With 0.01 lots, 1 pip = $0.01
pip_value = 0.01  # For 0.01 lots

print("\n" + "="*80)
print("LIVE SPREAD MONITORING (30 samples over 60 seconds)")
print("="*80)

spreads = []
ask_prices = []
bid_prices = []

print("\nSampling spread every 2 seconds...")
print(f"{'Time':<12} {'Bid':<12} {'Ask':<12} {'Spread (pts)':<15} {'Spread (pips)':<15} {'Cost ($)'}")
print("-" * 85)

for i in range(30):
    tick = mt5.symbol_info_tick(xauusd_symbol)
    if tick:
        spread_points = tick.ask - tick.bid
        spread_pips = spread_points / symbol_info.point / 10  # Convert to pips
        spread_cost = spread_pips * pip_value  # Cost for 0.01 lots
        
        spreads.append(spread_pips)
        ask_prices.append(tick.ask)
        bid_prices.append(tick.bid)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{timestamp:<12} {tick.bid:<12.2f} {tick.ask:<12.2f} {spread_points:<15.5f} {spread_pips:<15.2f} ${spread_cost:.4f}")
    
    time.sleep(2)

print("\n" + "="*80)
print("SPREAD STATISTICS")
print("="*80)

avg_spread = statistics.mean(spreads)
min_spread = min(spreads)
max_spread = max(spreads)
median_spread = statistics.median(spreads)
stdev_spread = statistics.stdev(spreads) if len(spreads) > 1 else 0

print(f"\nSpread (in pips):")
print(f"  Average: {avg_spread:.2f} pips")
print(f"  Minimum: {min_spread:.2f} pips")
print(f"  Maximum: {max_spread:.2f} pips")
print(f"  Median:  {median_spread:.2f} pips")
print(f"  Std Dev: {stdev_spread:.2f} pips")

print(f"\nCost per Trade (0.01 lots):")
print(f"  Average: ${avg_spread * pip_value:.4f}")
print(f"  Minimum: ${min_spread * pip_value:.4f}")
print(f"  Maximum: ${max_spread * pip_value:.4f}")

print("\n" + "="*80)
print("SPREAD ASSESSMENT")
print("="*80)

if avg_spread < 1.5:
    print(f"\n✅ EXCELLENT: Average spread {avg_spread:.2f} pips (ECN-like)")
    print("   Your 0.1 ATR SL (~1 pip) will work perfectly!")
    spread_rating = "EXCELLENT"
elif avg_spread < 2.5:
    print(f"\n✅ GOOD: Average spread {avg_spread:.2f} pips (Standard account)")
    print("   Your 0.1 ATR SL will work, but costs slightly higher")
    spread_rating = "GOOD"
elif avg_spread < 3.5:
    print(f"\n⚠️  ACCEPTABLE: Average spread {avg_spread:.2f} pips")
    print("   Your 0.1 ATR SL will work but at higher cost")
    print("   Consider ECN broker for better results")
    spread_rating = "ACCEPTABLE"
else:
    print(f"\n❌ POOR: Average spread {avg_spread:.2f} pips (too wide!)")
    print("   Your 0.1 ATR SL may not work well")
    print("   STRONGLY recommend switching to ECN broker")
    spread_rating = "POOR"

print("\n" + "="*80)
print("EXECUTION QUALITY ESTIMATE")
print("="*80)

# Calculate price volatility (as proxy for slippage risk)
price_changes = [abs(ask_prices[i] - ask_prices[i-1]) for i in range(1, len(ask_prices))]
avg_price_change = statistics.mean(price_changes)
max_price_change = max(price_changes)

print(f"\nPrice Movement During Test:")
print(f"  Avg Change per 2 sec: {avg_price_change:.2f} points")
print(f"  Max Change per 2 sec: {max_price_change:.2f} points")

# Estimate slippage
# If price changes by X points per 2 seconds, slippage on execution is typically 0.1-0.3 of that
estimated_slippage = avg_price_change * 0.2
slippage_pips = estimated_slippage / symbol_info.point / 10

print(f"\nEstimated Slippage (on execution):")
print(f"  Points: {estimated_slippage:.2f}")
print(f"  Pips: {slippage_pips:.2f}")
print(f"  Cost (0.01 lots): ${slippage_pips * pip_value:.4f}")

print("\n" + "="*80)
print("TOTAL EXECUTION COST (per trade)")
print("="*80)

total_cost_per_trade = (avg_spread + slippage_pips * 2) * pip_value  # *2 for entry+exit
print(f"\nSpread cost: ${avg_spread * pip_value:.4f}")
print(f"Slippage cost (entry+exit): ${slippage_pips * 2 * pip_value:.4f}")
print(f"TOTAL: ${total_cost_per_trade:.4f} per 0.01 lot trade")

print("\n" + "="*80)
print("IMPACT ON YOUR STRATEGY")
print("="*80)

# Expected values from backtest
expected_avg_loss = 0.52
expected_expectancy = 1.01

# Adjusted with actual broker costs
actual_avg_loss = expected_avg_loss + total_cost_per_trade
actual_expectancy = expected_expectancy - total_cost_per_trade

print(f"\nBacktest (ideal conditions):")
print(f"  Avg Loss: ${expected_avg_loss:.2f}")
print(f"  Expectancy: ${expected_expectancy:.4f}")

print(f"\nWith YOUR broker (actual):")
print(f"  Avg Loss: ${actual_avg_loss:.2f}")
print(f"  Expectancy: ${actual_expectancy:.4f}")
print(f"  Impact: {(actual_expectancy / expected_expectancy - 1) * 100:+.1f}%")

if actual_expectancy > 0.50:
    print(f"\n✅ SYSTEM STILL PROFITABLE")
    print(f"   Expectancy ${actual_expectancy:.4f} is healthy (>$0.50)")
elif actual_expectancy > 0.20:
    print(f"\n⚠️  SYSTEM MARGINALLY PROFITABLE")
    print(f"   Expectancy ${actual_expectancy:.4f} is low but positive")
    print(f"   Results will be slower than backtest")
else:
    print(f"\n❌ SYSTEM MAY NOT BE PROFITABLE")
    print(f"   Expectancy ${actual_expectancy:.4f} is too low")
    print(f"   RECOMMEND: Switch to ECN broker or use wider SL")

print("\n" + "="*80)
print("FINAL VERDICT")
print("="*80)

print(f"\nSpread Rating: {spread_rating}")
print(f"Average Spread: {avg_spread:.2f} pips")
print(f"Estimated Slippage: {slippage_pips:.2f} pips")
print(f"Total Cost per Trade: ${total_cost_per_trade:.4f}")
print(f"Adjusted Expectancy: ${actual_expectancy:.4f}")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

if spread_rating == "EXCELLENT" and actual_expectancy > 0.80:
    print("\n✅ YOUR BROKER IS GREAT!")
    print("   - Spread is tight (ECN-like)")
    print("   - System will work as backtested")
    print("   - Expected $10/day is achievable")
    print("\n>>> START TRADING MONDAY! 🚀")
    
elif spread_rating in ["GOOD", "ACCEPTABLE"] and actual_expectancy > 0.50:
    print("\n✅ YOUR BROKER IS WORKABLE")
    print("   - Spread is acceptable for standard account")
    print("   - System will work but at 80-90% efficiency")
    print("   - Expected $8-10/day is achievable")
    print("\n>>> START TRADING MONDAY (but monitor costs)")
    
elif actual_expectancy > 0.20:
    print("\n⚠️  YOUR BROKER IS MARGINAL")
    print("   - Spread/slippage is eating into profits")
    print("   - System might still work but slowly")
    print("   - Expected $5-7/day (50% less than target)")
    print("\n>>> OPTION 1: Try for 2 weeks, then switch if needed")
    print(">>> OPTION 2: Switch to ECN broker now (IC Markets, Pepperstone)")
    
else:
    print("\n❌ YOUR BROKER IS TOO EXPENSIVE")
    print("   - Spread/slippage kills the edge")
    print("   - System unlikely to be profitable")
    print(f"   - Expected daily: ${actual_expectancy * 5.21:.2f} (not $10)")
    print("\n>>> RECOMMENDATION: Switch to ECN broker immediately")
    print(">>> Or use wider SL/TP (0.5/1.5 instead of 0.1/2.0)")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)

mt5.shutdown()
