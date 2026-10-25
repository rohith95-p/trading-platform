"""
Massive Grid Search Strategy Classes
Implements multiple paradigms for high-frequency, high-win-rate scalping.
"""

from __future__ import annotations
from typing import Optional
import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5

def _atr(rates: np.ndarray, period: int = 14) -> np.ndarray:
    return BaseStrategy.atr(rates["high"], rates["low"], rates["close"], period)

def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    return BaseStrategy.ema(arr, period)

def _rsi(arr: np.ndarray, period: int = 14) -> np.ndarray:
    return BaseStrategy.rsi(arr, period)

def _ist_hour(rates: np.ndarray) -> np.ndarray:
    ts = rates["time"].astype("int64")
    return ((ts % 86400) + 19800) % 86400 / 3600.0


# 1. Trend Pullback Strategy (EMA Stack)
class TrendPullbackStrat(BaseStrategy):
    name = "TREND_PULLBACK"
    magic = 5000
    execute_immediately = True
    edge_trigger = True
    _min_bars = 100
    
    def __init__(self, session=(11.5, 21.5), fast_ema=13, slow_ema=34, pullback_ema=13, sl=0.5, tp=1.5):
        self.session = session
        self.fast_ema_period = fast_ema
        self.slow_ema_period = slow_ema
        self.pullback_ema = pullback_ema
        self.sl_atr_mult = sl
        self.tp_atr_mult = tp
        self.name = f"TrendPullback_{session[0]}_{fast_ema}_{slow_ema}_sl{sl}_tp{tp}"
        self.magic = 5000 + int(sl*100) + int(tp*10)

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars: return None
        
        cl = m15_rates["close"].astype(float)
        hi = m15_rates["high"].astype(float)
        lo = m15_rates["low"].astype(float)
        ist = _ist_hour(m15_rates)
        i = -2
        
        if not (self.session[0] <= ist[i] < self.session[1]): return None
        
        fast = _ema(cl, self.fast_ema_period)
        slow = _ema(cl, self.slow_ema_period)
        pb = _ema(cl, self.pullback_ema)
        
        # Bullish: fast > slow, price pulls back to PB, then bullish candle
        if fast[i-1] > slow[i-1] and fast[i] > slow[i]:
            if lo[i-1] <= pb[i-1] and cl[i] > cl[i-1] and cl[i] > pb[i]:
                return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name, magic=self.magic, is_buy=True)
                
        # Bearish: fast < slow, price pulls back to PB, then bearish candle
        if fast[i-1] < slow[i-1] and fast[i] < slow[i]:
            if hi[i-1] >= pb[i-1] and cl[i] < cl[i-1] and cl[i] < pb[i]:
                return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name, magic=self.magic, is_buy=False)
                
        return None

# 2. Bollinger Band Mean Reversion
class BBMeanReversionStrat(BaseStrategy):
    name = "BB_MR"
    magic = 6000
    execute_immediately = True
    edge_trigger = False
    _min_bars = 100
    
    def __init__(self, session=(17.5, 21.5), bb_period=20, bb_std=2.0, sl=0.4, tp=1.0):
        self.session = session
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.sl_atr_mult = sl
        self.tp_atr_mult = tp
        self.name = f"BBMR_{session[0]}_{bb_period}_{bb_std}_sl{sl}_tp{tp}"
        self.magic = 6000 + int(sl*100) + int(tp*10)

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars: return None
        
        cl = m15_rates["close"].astype(float)
        ist = _ist_hour(m15_rates)
        i = -2
        
        if not (self.session[0] <= ist[i] < self.session[1]): return None
        
        # Simple rolling BB
        slice_cl = cl[i-self.bb_period+1 : i+1]
        mean = slice_cl.mean()
        std = slice_cl.std()
        upper = mean + self.bb_std * std
        lower = mean - self.bb_std * std
        
        rsi = _rsi(cl, 14)[i]
        
        if cl[i] < lower and rsi < 35:
            return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name, magic=self.magic, is_buy=True)
        if cl[i] > upper and rsi > 65:
            return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name, magic=self.magic, is_buy=False)
            
        return None

# 3. Session Breakout Strategy
class SessionBreakoutStrat(BaseStrategy):
    name = "SESSION_BO"
    magic = 7000
    execute_immediately = True
    edge_trigger = True
    _min_bars = 150
    
    def __init__(self, range_start=5.5, range_end=11.5, trade_start=11.5, trade_end=13.5, sl=0.5, tp=1.5):
        self.range_start = range_start
        self.range_end = range_end
        self.trade_start = trade_start
        self.trade_end = trade_end
        self.sl_atr_mult = sl
        self.tp_atr_mult = tp
        self.name = f"Breakout_{range_start}_{trade_start}_sl{sl}_tp{tp}"
        self.magic = 7000 + int(sl*100) + int(tp*10)

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars: return None
        
        hi = m15_rates["high"].astype(float)
        lo = m15_rates["low"].astype(float)
        cl = m15_rates["close"].astype(float)
        ist = _ist_hour(m15_rates)
        i = -2
        
        if not (self.trade_start <= ist[i] < self.trade_end): return None
        
        # Find range
        range_mask = (ist >= self.range_start) & (ist < self.range_end)
        lookback = 100
        window_slice = slice(max(0, len(m15_rates) + i - lookback), len(m15_rates) + i)
        recent_range = range_mask[window_slice]
        
        if recent_range.sum() < 4: return None
        
        r_hi = hi[window_slice][recent_range].max()
        r_lo = lo[window_slice][recent_range].min()
        
        # Breakout
        if cl[i] > r_hi and cl[i-1] <= r_hi:
            return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name, magic=self.magic, is_buy=True)
        if cl[i] < r_lo and cl[i-1] >= r_lo:
            return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name, magic=self.magic, is_buy=False)
            
        return None
