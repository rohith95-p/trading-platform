"""London Close Reversal — mean reversion around the London PM fix.

Logic: At 15:00 UTC (London PM fix time), if the London session has been
strongly trending (range > 1.5x ATR and close near an extreme), fade the
move. The fix often marks the session extreme as institutional hedging
flows absorb directional momentum.

Fires once per day at 15:15 UTC (when the 15:00 bar closes).

Based on research:
- London PM gold fix causes reversals as institutional flows absorb momentum
- Gold fixing at 3pm London time is the daily benchmark
- Sources: Wikipedia gold fixing, QuantVPS session analysis
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class LondonCloseReversalV6(BaseStrategy):
    """London close / PM fix mean reversion.

    Entry: At 15:00 UTC bar close, if London session range > 1.5x ATR14
           and price is near the session extreme (within top/bottom 20%),
           fade the move.
    SL: 2.0x ATR14, TP: 3.5x ATR14.
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True

    def __init__(self, min_range_atr: float = 1.5, extreme_pct: float = 0.20,
                 sl_atr_mult: float = 2.0, tp_atr_mult: float = 3.5,
                 magic: int = 7314):
        self.min_range_atr = min_range_atr
        self.extreme_pct = extreme_pct
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "LONDON_CLOSE_REVERSAL_V6"
        self._min_bars = 250

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        # Fire at 15:00 UTC = 54000s from midnight (London PM fix)
        if bar_time % 86400 != 54000:
            return None

        times = m15_rates["time"].astype("int64")
        highs = m15_rates["high"].astype(float)
        lows = m15_rates["low"].astype(float)
        closes = m15_rates["close"].astype(float)

        current_day = bar_time // 86400

        # ATR14
        atr_arr = self.atr(highs, lows, closes, 14)
        atr_val = float(atr_arr[-2])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return None

        # London session: 07:00-14:45 UTC (up to this bar)
        london_mask = (times // 86400 == current_day) & \
                      (times % 86400 >= 25200) & (times % 86400 <= 54000)
        if london_mask.sum() < 16:
            return None

        session_high = float(highs[london_mask].max())
        session_low = float(lows[london_mask].min())
        session_range = session_high - session_low

        if session_range < self.min_range_atr * atr_val:
            return None

        close_price = float(closes[-2])
        range_position = (close_price - session_low) / session_range

        # Near the top (>80%) -> SELL (fade the up-move)
        if range_position > (1.0 - self.extreme_pct):
            return Signal(direction=mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=False)

        # Near the bottom (<20%) -> BUY (fade the down-move)
        if range_position < self.extreme_pct:
            return Signal(direction=mt5.ORDER_TYPE_BUY,
                          strategy_name=self.name, magic=self.magic, is_buy=True)

        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
