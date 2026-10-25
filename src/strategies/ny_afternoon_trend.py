"""NY Afternoon Trend Continuation — late-day momentum push.

Logic: At 16:00 UTC (noon NY), if the day has established a clear trend
(strong directional move from London open), enter with the trend for
the final push. The NY afternoon often sees trend acceleration as
European traders close and US-only flow takes over.

This fills the 16:00-20:00 UTC gap in our portfolio and captures
the well-documented "NY afternoon continuation" pattern.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class NYAfternoonTrendV6(BaseStrategy):
    """NY afternoon trend continuation.

    Entry: At 16:00 UTC, if intraday move from 07:00 is >= 1.5x ATR14
           and last 3 of 4 M15 bars aligned with the move direction.
    SL: 1.5x ATR14, TP: 3.0x ATR14.
    Once per day.
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True

    def __init__(self, min_move_atr: float = 1.5,
                 sl_atr_mult: float = 1.5, tp_atr_mult: float = 3.0,
                 magic: int = 7323):
        self.min_move_atr = min_move_atr
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "NY_AFTERNOON_TREND_V6"
        self._min_bars = 250

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        # Fire at 16:00 UTC = 57600s from midnight
        if bar_time % 86400 != 57600:
            return None

        times = m15_rates["time"].astype("int64")
        highs = m15_rates["high"].astype(float)
        lows = m15_rates["low"].astype(float)
        closes = m15_rates["close"].astype(float)
        opens = m15_rates["open"].astype(float)

        current_day = bar_time // 86400

        atr_arr = self.atr(highs, lows, closes, 14)
        atr_val = float(atr_arr[-2])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return None

        # Get the London open price (07:00 UTC bar open)
        london_open_mask = (times // 86400 == current_day) & \
                           (times % 86400 == 25200)
        if london_open_mask.sum() == 0:
            return None
        london_open_idx = np.where(london_open_mask)[0][0]
        london_open_price = float(opens[london_open_idx])

        current_close = float(closes[-2])
        intraday_move = current_close - london_open_price

        if abs(intraday_move) < self.min_move_atr * atr_val:
            return None

        # Check last 4 bars alignment
        last4_closes = closes[-5:-1]
        last4_opens = opens[-5:-1]
        if len(last4_closes) < 4:
            return None

        bars_up = int(np.sum(last4_closes > last4_opens))
        bars_down = int(np.sum(last4_closes < last4_opens))

        if intraday_move > 0 and bars_up >= 3:
            return Signal(direction=mt5.ORDER_TYPE_BUY,
                          strategy_name=self.name, magic=self.magic, is_buy=True)

        if intraday_move < 0 and bars_down >= 3:
            return Signal(direction=mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=False)

        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
