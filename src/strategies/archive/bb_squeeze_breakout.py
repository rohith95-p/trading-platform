"""Bollinger Squeeze Breakout — volatility compression into expansion.

Logic: When Bollinger Band width contracts below a threshold (squeeze),
wait for the expansion breakout. Enter in the direction of the breakout
candle that closes outside the bands after a squeeze of at least N bars.

Session-filtered to Asian-to-London transition (04:00-09:00 UTC) where
gold often compresses during Asian lull then expands at London open.

The squeeze-breakout pattern is well-documented in volatility literature.
Key: the squeeze must be genuine compression (not just low ATR) and the
breakout candle must show conviction (body > 0.4x ATR).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class BBSqueezeBreakoutV6(BaseStrategy):
    """Bollinger Band squeeze breakout during Asian-London transition.

    Entry: After >= 4 bars of BB squeeze (width < 1.5x ATR),
           breakout candle closes outside BB with body >= 0.4x ATR.
    Window: 04:00-09:00 UTC (pre-London compression → London expansion).
    SL: 1.5x ATR14, TP: 3.0x ATR14.
    Once per day.
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True

    def __init__(self, bb_period: int = 20, bb_std: float = 2.0,
                 squeeze_atr_mult: float = 1.5, min_squeeze_bars: int = 4,
                 body_atr_mult: float = 0.4,
                 sl_atr_mult: float = 1.5, tp_atr_mult: float = 3.0,
                 magic: int = 7321):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.squeeze_atr_mult = squeeze_atr_mult
        self.min_squeeze_bars = min_squeeze_bars
        self.body_atr_mult = body_atr_mult
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "BB_SQUEEZE_BREAKOUT_V6"
        self._min_bars = 250
        self._last_signal_day = None

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        utc_seconds = bar_time % 86400
        if utc_seconds < 14400 or utc_seconds >= 32400:
            return None

        current_day = bar_time // 86400
        if self._last_signal_day == current_day:
            return None

        highs = m15_rates["high"].astype(float)
        lows = m15_rates["low"].astype(float)
        closes = m15_rates["close"].astype(float)
        opens = m15_rates["open"].astype(float)

        atr_arr = self.atr(highs, lows, closes, 14)
        atr_val = float(atr_arr[-2])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return None

        idx = len(closes) - 2
        if idx < self.bb_period + self.min_squeeze_bars:
            return None

        bb_window = closes[idx - self.bb_period + 1: idx + 1]
        bb_mean = float(np.mean(bb_window))
        bb_std_val = float(np.std(bb_window, ddof=1))
        if bb_std_val <= 0:
            return None

        upper_band = bb_mean + self.bb_std * bb_std_val
        lower_band = bb_mean - self.bb_std * bb_std_val
        bb_width = upper_band - lower_band

        squeeze_threshold = self.squeeze_atr_mult * atr_val

        squeeze_count = 0
        for lookback in range(1, self.min_squeeze_bars + 5):
            prev_idx = idx - lookback
            if prev_idx < self.bb_period:
                break
            prev_window = closes[prev_idx - self.bb_period + 1: prev_idx + 1]
            prev_mean = float(np.mean(prev_window))
            prev_std = float(np.std(prev_window, ddof=1))
            if prev_std <= 0:
                break
            prev_width = 2 * self.bb_std * prev_std
            if prev_width < squeeze_threshold:
                squeeze_count += 1
            else:
                break

        if squeeze_count < self.min_squeeze_bars:
            return None

        bar_close = float(closes[-2])
        bar_open = float(opens[-2])
        body = abs(bar_close - bar_open)

        if body < self.body_atr_mult * atr_val:
            return None

        if bar_close > upper_band and bar_close > bar_open:
            self._last_signal_day = current_day
            return Signal(direction=mt5.ORDER_TYPE_BUY,
                          strategy_name=self.name, magic=self.magic, is_buy=True)

        if bar_close < lower_band and bar_close < bar_open:
            self._last_signal_day = current_day
            return Signal(direction=mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=False)

        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
