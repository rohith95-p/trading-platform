# Backtest vs. Live Execution Discrepancy Analysis

## Overview
During the Master Weekend Audit on August 28, 2026, a significant discrepancy was discovered between historical backtest results and actual live trading performance, specifically regarding the `EMA_PULLBACK` and `MORNING_MOMENTUM` strategies.

- **`EMA_PULLBACK` Backtest (30 Days):** -$111.81 (27.6% Win Rate)
- **`EMA_PULLBACK` Live (Aug 27):** +$24.06 (66.7% Win Rate)
- **`MORNING_MOMENTUM` Backtest (30 Days):** +$55.15 (38.7% Win Rate)
- **`MORNING_MOMENTUM` Live (5 Days):** +$103.07 (66.7% Win Rate)

## Root Causes of Discrepancy

### 1. The Backtest is Naive (No Trailing Stops)
The backtest scripts (e.g., `backtest_all.py`) implement a rigid and static `1.5x ATR` Stop Loss and `3.0x ATR` Take Profit. It simulates trades by simply waiting up to 20 candles to see which level is hit first.
**Live Execution Reality:** The actual `RiskAgent` employs an aggressive trailing stop system. It activates a trailing stop when profit reaches `0.7x ATR` and trails at a distance of `0.3x ATR`. This locks in profits early and prevents winning trades from turning into full `1.5x ATR` losses if the `3.0x ATR` target is never reached.

### 2. Bypassed SL Cooldown Logic
Many strategies (especially `EMA_PULLBACK`) rely heavily on state management, such as a 2-hour cooldown after a Stop Loss hit (`self._sl_hit_candle_idx`), to prevent machine-gunning trades during a choppy, non-trending session.
**Live Execution Reality:** The strategy's state is properly managed.
**Backtest Flaw:** The backtest script loops through candles but *never calls* `notify_sl_hit()` when a simulated trade hits a stop loss. Consequently, the backtest takes many chained losses during choppy markets that the live bot would have successfully filtered out.

### 3. Small Sample Size Variance
The live result for `EMA_PULLBACK` was heavily influenced by exactly 3 trades taken on August 27th—a day where Gold happened to be trending perfectly in alignment with the strategy's EMA structures. 

## Conclusion
The current automated backtesting framework severely under-reports the profitability of our strategies because it ignores complex execution management (trailing stops) and state-feedback (SL cooldowns). 

**Strategic Decision:** We will explicitly prioritize Live Execution data over naive backtest data. Strategies like `EMA_PULLBACK` that show live promise will be monitored in real-time to build statistical significance (target: 30+ trades) rather than being discarded due to flawed backtests.
