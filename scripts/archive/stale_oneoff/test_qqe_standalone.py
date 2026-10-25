import numpy as np
from src.backtesting.data import load_bars
from src.strategies.base_strategy import BaseStrategy

def safe_ema(arr, period):
    valid_idx = np.where(~np.isnan(arr))[0]
    if len(valid_idx) == 0:
        return np.full_like(arr, np.nan)
    first = valid_idx[0]
    valid_arr = arr[first:]
    if len(valid_arr) < period:
        return np.full_like(arr, np.nan)
    res = BaseStrategy.ema(valid_arr, period)
    out = np.full_like(arr, np.nan)
    out[first:] = res
    return out

print("Loading data...")
bars = load_bars("XAUUSDm", timeframes=("M15",))
closes = bars.m15["close"]
print(f"Total M15 bars: {len(closes)}")

rsi_period = 14
sf = 5
qqe_factor = 4.238
wilders_period = rsi_period * 2 - 1

rsi = BaseStrategy.rsi(closes, rsi_period)
rsi_ma = safe_ema(rsi, sf)

atr_rsi = np.full_like(rsi_ma, np.nan)
atr_rsi[1:] = np.abs(rsi_ma[:-1] - rsi_ma[1:])

ma_atr_rsi = safe_ema(atr_rsi, wilders_period)
dar = safe_ema(ma_atr_rsi, wilders_period) * qqe_factor

n = len(closes)
longband = np.zeros(n)
shortband = np.zeros(n)
trend = np.ones(n)

for i in range(1, n):
    if np.isnan(rsi_ma[i]) or np.isnan(dar[i]):
        continue
    
    rs_index = rsi_ma[i]
    rs_index_prev = rsi_ma[i-1]
    delta = dar[i]
    
    newshortband = rs_index + delta
    newlongband = rs_index - delta
    
    if rs_index_prev > longband[i-1] and rs_index > longband[i-1]:
        longband[i] = max(longband[i-1], newlongband)
    else:
        longband[i] = newlongband
        
    if rs_index_prev < shortband[i-1] and rs_index < shortband[i-1]:
        shortband[i] = min(shortband[i-1], newshortband)
    else:
        shortband[i] = newshortband
        
    if trend[i-1] == -1:
        if rs_index > shortband[i-1]:
            trend[i] = 1
        else:
            trend[i] = -1
    else:
        if rs_index < longband[i-1]:
            trend[i] = -1
        else:
            trend[i] = 1

fast = np.where(trend == 1, longband, shortband)

long_signals = 0
short_signals = 0
for i in range(1, min(150, n)):
    if i > 70:
        print(f"i={i} rsi={rsi_ma[i]:.2f} dar={dar[i]:.2f} longband={longband[i]:.2f} shortband={shortband[i]:.2f}")

for i in range(1, n):
    if np.isnan(fast[i]) or np.isnan(rsi_ma[i]) or np.isnan(fast[i-1]) or np.isnan(rsi_ma[i-1]):
        continue
        
    curr_fast = fast[i]
    curr_rsi = rsi_ma[i]
    prev_fast = fast[i-1]
    prev_rsi = rsi_ma[i-1]
    
    if curr_rsi > curr_fast and prev_rsi <= prev_fast:
        long_signals += 1
        
    if curr_rsi < curr_fast and prev_rsi >= prev_fast:
        short_signals += 1

print(f"Found {long_signals} long signals and {short_signals} short signals.")
