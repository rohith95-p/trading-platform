"""Asian Range London Breakout for XAUUSD — Atlas-optimized intraday strategy.

Logic: Mark the Asian session (00:00-06:00 UTC) high/low, enter at London
open (07:00 UTC bar close) if price breaks out. The structural stop is tight
(range width) and London momentum carries the move.

This is the #1 strategy prop firm gold traders use for evaluations because:
- Fires daily (good trade frequency for payout eligibility)
- Structurally tight stops from the range width
- London session provides follow-through momentum

SL/TP use ATR-based stops via the engine's standard mechanism.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class AsianBreakoutV6(BaseStrategy):
    """Asian range breakout at London open on XAUUSD.

    Entry: At 07:00 UTC bar close, if price > Asian high -> BUY,
           if price < Asian low -> SELL.
    Filter: Asian range must be >= $3 (skip dead sessions).
    SL: 3.0x ATR14, TP: 5.0x ATR14.
    Fires once per day at 07:15 UTC (when the 07:00 bar closes).
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True

    def __init__(self, sl_atr_mult: float = 3.0, tp_atr_mult: float = 5.0,
                 min_range: float = 5.0, magic: int = 7311):
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.min_range = min_range
        self.magic = magic
        self.name = "ASIAN_BREAKOUT_V6"
        self._min_bars = 96 * 2 + 100

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        # Fire at 07:00 UTC = 25200s from midnight (London open)
        if bar_time % 86400 != 25200:
            return None

        times = m15_rates["time"].astype("int64")
        current_day = bar_time // 86400

        # Asian session: 00:00-05:45 UTC of the same day (24 M15 bars)
        asian_mask = (times // 86400 == current_day) & (times % 86400 < 21600)

        if asian_mask.sum() < 10:
            return None

        asia_high = float(m15_rates["high"][asian_mask].max())
        asia_low = float(m15_rates["low"][asian_mask].min())
        range_width = asia_high - asia_low

        if range_width < self.min_range:
            return None

        close_price = float(m15_rates["close"][-2])

        if close_price > asia_high:
            return Signal(direction=mt5.ORDER_TYPE_BUY,
                          strategy_name=self.name, magic=self.magic, is_buy=True)
        if close_price < asia_low:
            return Signal(direction=mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=False)
        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
