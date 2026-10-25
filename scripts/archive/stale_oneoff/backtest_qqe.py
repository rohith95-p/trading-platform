import os
import sys
import numpy as np
import logging
import json
from datetime import datetime, timezone
from dataclasses import asdict

from src.backtesting.costs import SCENARIOS
from src.backtesting.data import load_bars
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.metrics import summarize
from src.strategies.base_strategy import BaseStrategy, Signal, mt5

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("backtest_qqe")

class QQEStrategy(BaseStrategy):
    name = "QQE_TEST"
    magic = 9999

    def __init__(self):
        self.rsi_period = 14
        self.sf = 5
        self.qqe_factor = 4.238
        self.wilders_period = self.rsi_period * 2 - 1

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Signal:
        if m15_rates is None or len(m15_rates) < 200:
            return None

        # Calculate on M15 closes. (Assuming we trade on M15 timeframe crosses)
        closes = m15_rates["close"]
        
        def safe_ema(arr, period):
            valid_idx = np.where(~np.isnan(arr))[0]
            if len(valid_idx) == 0:
                return np.full_like(arr, np.nan)
            first = valid_idx[0]
            valid_arr = arr[first:]
            if len(valid_arr) < period:
                return np.full_like(arr, np.nan)
            res = self.ema(valid_arr, period)
            out = np.full_like(arr, np.nan)
            out[first:] = res
            return out

        rsi = self.rsi(closes, self.rsi_period)
        rsi_ma = safe_ema(rsi, self.sf)
        
        atr_rsi = np.full_like(rsi_ma, np.nan)
        atr_rsi[1:] = np.abs(rsi_ma[:-1] - rsi_ma[1:])
        
        ma_atr_rsi = safe_ema(atr_rsi, self.wilders_period)
        dar = safe_ema(ma_atr_rsi, self.wilders_period) * self.qqe_factor
        
        n = len(closes)
        longband = np.zeros(n)
        shortband = np.zeros(n)
        trend = np.ones(n)
        
        # Calculate exactly for the last two bars to see if there's a cross
        # It's inefficient to calculate the whole series on every tick, 
        # but for a backtest engine that might call evaluate repeatedly, 
        # we can just calculate the whole array if needed.
        # However, to be fast in python, let's just do it vectorized where possible or full loop.
        # Since n is small (m15_rates is truncated by engine usually, wait engine passes what? 
        # In this engine, evaluate receives truncated rates (up to history_bars).
        
        for i in range(1, n):
            if np.isnan(rsi_ma[i]) or np.isnan(dar[i]):
                continue
            
            rs_index = rsi_ma[i]
            rs_index_prev = rsi_ma[i-1]
            delta_fast_atr_rsi = dar[i]
            
            newshortband = rs_index + delta_fast_atr_rsi
            newlongband = rs_index - delta_fast_atr_rsi
            
            # longband logic
            if rs_index_prev > longband[i-1] and rs_index > longband[i-1]:
                longband[i] = max(longband[i-1], newlongband)
            else:
                longband[i] = newlongband
                
            # shortband logic
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
                
        fast_atr_rsi_tl = np.where(trend == 1, longband, shortband)
        
        # Find QQExlong and QQExshort for the last bar
        # We only need the signal for the current close (index -2)
        # Because we only act on closed bars. But wait, `evaluate` runs after candle close, 
        # so `rates[-2]` is the last closed candle? 
        # Wait, in the ultra_core engine, `rates[-1]` is the current incomplete candle, 
        # `rates[-2]` is the latest fully closed candle. (As seen in EMAPullback)
        
        # We check the condition at -2
        idx = -2
        if np.isnan(fast_atr_rsi_tl[idx]) or np.isnan(rsi_ma[idx]):
            return None
            
        curr_fast = fast_atr_rsi_tl[idx]
        curr_rsi = rsi_ma[idx]
        prev_fast = fast_atr_rsi_tl[idx-1]
        prev_rsi = rsi_ma[idx-1]
        
        is_long_signal = (curr_fast < curr_rsi) and (prev_fast >= prev_rsi)
        is_short_signal = (curr_fast > curr_rsi) and (prev_fast <= prev_rsi)
        
        if is_long_signal:
            return Signal(
                direction=mt5.ORDER_TYPE_BUY,
                strategy_name=self.name,
                magic=self.magic,
                is_buy=True
            )
            
        if is_short_signal:
            return Signal(
                direction=mt5.ORDER_TYPE_SELL,
                strategy_name=self.name,
                magic=self.magic,
                is_buy=False
            )
            
        return None

def main():
    log.info("Loading bars for last 100 days...")
    bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1"))
    
    cfg = EngineConfig(
        symbol="XAUUSDm", 
        starting_balance=105.74,
        sizing_mode="fixed", 
        fixed_lots=0.01,
        max_concurrent=1, 
        max_same_direction=1,
        enable_trailing=False, 
        enable_pyramiding=False,
        daily_loss_limit_mode="off",
        enable_d1_bias_gate=False,
        history_bars=300,
        warmup_bars=350,
    )
    
    cost = SCENARIOS["realistic"]
    engine = BacktestEngine(bars=bars, cost=cost, config=cfg)
    
    log.info("Running QQE Strategy...")
    result = engine.run([QQEStrategy()])
    
    stats = summarize(result.trades, result.equity, cfg.starting_balance)
    
    print("\n--- RESULTS ---")
    s = stats
    print(f"  trades {s.trades:<6} win rate {s.win_rate:>6.2f}%")
    print(f"  net    ${s.net_pl:<10,.2f} PF {s.profit_factor:<7.3f}")
    print(f"  avg win ${s.avg_win:<8,.2f} avg loss ${s.avg_loss:<8,.2f}")
    print(f"  max DD ${s.max_drawdown:,.2f} ({s.max_drawdown_pct:.1f}%)")
    print(f"  balance ${s.start_balance:,.2f} -> ${s.end_balance:,.2f} ({s.return_pct:+.1f}%)")
    print(f"  duplicates {s.duplicate_trades} (${s.duplicate_pl:,.2f})")
    print(f"  exits: {dict(sorted(s.exit_reasons.items(), key=lambda kv: -kv[1]))}")

if __name__ == "__main__":
    main()
