"""London Momentum Continuation — trend continuation in London/NY overlap.

Logic: At 12:00 UTC (London/NY overlap start), check if the London morning
session (07:00-11:45) established a clear trend: EMA8 > EMA21 (or vice versa)
with the last 4 bars all closing in the trend direction. Enter with the trend.

This captures the overlap liquidity surge that accelerates existing London trends.
The overlap is the highest-volume period for gold trading.

Based on research:
- London/NY overlap is the most volatile gold window ($23/hr avg move)
- Trend continuation during overlap has better PF than reversal
- Sources: quantvps.com session analysis, MQL5 London breakout study
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class LondonMomentumV6(BaseStrategy):
    """London/NY overlap trend continuation.

    Entry: At 12:00 UTC, if London morning established a trend
           (EMA8 > EMA21 for up, vice versa) with last 4 bars aligned.
    SL: 2.5x ATR14, TP: 5.0x ATR14.
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True

    def __init__(self, sl_atr_mult: float = 2.5, tp_atr_mult: float = 5.0,
                 magic: int = 7316):
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "LONDON_MOMENTUM_V6"
        self._min_bars = 250

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        # Fire at 12:00 UTC = 43200s from midnight (overlap start)
        if bar_time % 86400 != 43200:
            return None

        times = m15_rates["time"].astype("int64")
        closes = m15_rates["close"].astype(float)
        opens = m15_rates["open"].astype(float)
        highs = m15_rates["high"].astype(float)
        lows = m15_rates["low"].astype(float)

        current_day = bar_time // 86400

        # London morning bars: 07:00-11:45 UTC
        london_mask = (times // 86400 == current_day) & \
                      (times % 86400 >= 25200) & (times % 86400 < 43200)
        if london_mask.sum() < 16:
            return None

        london_closes = closes[london_mask]

        # EMA8 and EMA21 on London morning closes
        ema8 = self.ema(london_closes, 8)
        ema21 = self.ema(london_closes, min(21, len(london_closes)))

        if not np.isfinite(ema8[-1]) or not np.isfinite(ema21[-1]):
            return None

        # ATR14
        atr_arr = self.atr(highs, lows, closes, 14)
        atr_val = float(atr_arr[-2])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return None

        # Check last 4 London bars alignment
        last4_closes = london_closes[-4:]
        last4_opens = opens[london_mask][-4:]
        if len(last4_closes) < 4:
            return None

        bars_up = int(np.sum(last4_closes > last4_opens))
        bars_down = int(np.sum(last4_closes < last4_opens))

        # Bullish: EMA8 > EMA21, >= 3 of last 4 bars up
        if ema8[-1] > ema21[-1] and bars_up >= 3:
            # Confirm trend strength: London range > 1.0x ATR
            london_range = float(highs[london_mask].max() - lows[london_mask].min())
            if london_range >= 1.0 * atr_val:
                return Signal(direction=mt5.ORDER_TYPE_BUY,
                              strategy_name=self.name, magic=self.magic, is_buy=True)

        # Bearish: EMA8 < EMA21, >= 3 of last 4 bars down
        if ema8[-1] < ema21[-1] and bars_down >= 3:
            london_range = float(highs[london_mask].max() - lows[london_mask].min())
            if london_range >= 1.0 * atr_val:
                return Signal(direction=mt5.ORDER_TYPE_SELL,
                              strategy_name=self.name, magic=self.magic, is_buy=False)

        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
