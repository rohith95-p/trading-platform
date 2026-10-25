import MetaTrader5 as _mt5
from typing import Any
mt5: Any = _mt5
from datetime import datetime, timezone, timedelta
import logging

from src.core.data_fetcher import DataFetcher
from src.strategies.archive.morning_momentum import MorningMomentum
from src.strategies.archive.ema_pullback import EMAPullback
from src.strategies.archive.asian_sweep import AsianSweep
from src.strategies.supertrend_ema import SupertrendEMA

IST = timezone(timedelta(hours=5, minutes=30))

if not mt5.initialize():
    print("MT5 init failed")
    exit(1)

fetcher = DataFetcher("XAUUSDm")
m15_rates = fetcher.get_m15_rates(100)
m5_rates = fetcher.get_m5_rates(100)

if m15_rates is None or m5_rates is None:
    print("Failed to fetch rates")
    mt5.shutdown()
    exit(1)

strategies = [MorningMomentum(), EMAPullback(), AsianSweep(), SupertrendEMA()]

# We want to check the last 4-5 M15 candles (approx 1 hour)
# The evaluate function checks the candle at index -2.
# So we slice the arrays up to a specific index to simulate past evaluate calls.

print("Checking the last 1.5 hours for missed entries...")
for offset in range(6, 0, -1):
    sim_m15 = m15_rates[:-offset+1] if offset > 1 else m15_rates
    sim_m5 = m5_rates # approximate
    
    candle_time = datetime.fromtimestamp(int(sim_m15[-2]["time"]), tz=timezone.utc).astimezone(IST)
    print(f"\nEvaluating completed candle at: {candle_time.strftime('%Y-%m-%d %I:%M %p IST')}")
    
    found_signal = False
    for strat in strategies:
        sig = strat.evaluate(sim_m15, sim_m5)
        if sig:
            print(f"  --> {strat.name} triggered a {sig.direction_str} signal!")
            found_signal = True
            
    if not found_signal:
        print("  No signals.")

mt5.shutdown()
