"""NY Session Reversal — London high/low sweep reversal at NY open.

Logic: During the NY session (12:00-16:00 UTC), detect when price sweeps
the London session high or low (penetrates by >= 0.2x ATR) then closes
back inside the range on a strong displacement candle (body >= 0.5x ATR).
This is the classic "Judas swing" / liquidity sweep pattern.

Fires at most once per day when the sweep-and-reject pattern completes.

Based on research:
- ICT kill zone sweep pattern (accumulation-manipulation-distribution)
- NY London Sweep Reversal from deprecated ny_session_suite.py
- Gold is the most responsive instrument to kill-zone sweeps
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class NYSessionReversalV6(BaseStrategy):
    """NY session London-range sweep reversal.

    Entry: During 12:00-16:00 UTC, if price sweeps London high/low
           (penetration >= 0.2x ATR) and the closed bar rejects back inside
           with a displacement body >= 0.5x ATR.
    SL: 2.5x ATR14, TP: 4.5x ATR14.
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = False  # owner 2026-10-30: apply the daily trend gate live, as every validated backtest did

    def __init__(self, penetration_atr: float = 0.2, displacement_atr: float = 0.5,
                 sl_atr_mult: float = 2.5, tp_atr_mult: float = 4.5,
                 magic: int = 7313):
        self.penetration_atr = penetration_atr
        self.displacement_atr = displacement_atr
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "NY_SESSION_REVERSAL_V6"
        self._min_bars = 250
        self._last_signal_day = None

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        utc_seconds = bar_time % 86400
        # NY session: 12:00-16:00 UTC (43200-57600)
        if utc_seconds < 43200 or utc_seconds >= 57600:
            return None

        # One signal per UTC day
        current_day = bar_time // 86400
        if self._last_signal_day == current_day:
            return None

        times = m15_rates["time"].astype("int64")
        highs = m15_rates["high"].astype(float)
        lows = m15_rates["low"].astype(float)
        closes = m15_rates["close"].astype(float)
        opens = m15_rates["open"].astype(float)

        # ATR14
        atr_arr = self.atr(highs, lows, closes, 14)
        atr_val = float(atr_arr[-2])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return None

        # London session range: 07:00-11:45 UTC on same day
        london_mask = (times // 86400 == current_day) & \
                      (times % 86400 >= 25200) & (times % 86400 < 42300)
        if london_mask.sum() < 8:
            return None

        london_high = float(highs[london_mask].max())
        london_low = float(lows[london_mask].min())
        london_range = london_high - london_low
        if london_range < 3.0:
            return None

        bar_high = float(highs[-2])
        bar_low = float(lows[-2])
        bar_close = float(closes[-2])
        bar_open = float(opens[-2])
        body = abs(bar_close - bar_open)

        # Bear sweep (swept London high, closed back below) -> SELL
        if (bar_high > london_high + self.penetration_atr * atr_val and
                bar_close < london_high and
                bar_close < bar_open and
                body >= self.displacement_atr * atr_val):
            self._last_signal_day = current_day
            return Signal(direction=mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=False)

        # Bull sweep (swept London low, closed back above) -> BUY
        if (bar_low < london_low - self.penetration_atr * atr_val and
                bar_close > london_low and
                bar_close > bar_open and
                body >= self.displacement_atr * atr_val):
            self._last_signal_day = current_day
            return Signal(direction=mt5.ORDER_TYPE_BUY,
                          strategy_name=self.name, magic=self.magic, is_buy=True)

        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
