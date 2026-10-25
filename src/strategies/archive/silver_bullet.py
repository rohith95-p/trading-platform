"""Silver Bullet — ICT 10am NY fair value gap entry.

Logic: During the 10:00-11:00 NY window (14:00-15:00 UTC), look for a
displacement move that creates a fair value gap (FVG). The FVG is a 3-bar
pattern where bar[i]'s high < bar[i+2]'s low (bullish) or bar[i]'s low >
bar[i+2]'s high (bearish). Enter when price returns to fill the gap.

This is the ICT Silver Bullet setup, documented as particularly effective
on gold during the NY AM session when institutional flow is highest.

Based on research:
- ICT Silver Bullet: 10:00-11:00 AM NY time window
- FVG (fair value gap) as entry mechanism
- Sources: chartinglens.com, innercircletrader.net, tradingstrategyguides.com
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class SilverBulletV6(BaseStrategy):
    """ICT Silver Bullet strategy for the 10-11am NY window.

    Entry: At 14:00-15:00 UTC, detect FVG + displacement, enter on gap fill.
    Filter: Displacement candle body >= 0.6x ATR14.
    SL: 2.0x ATR14, TP: 4.0x ATR14.
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True

    def __init__(self, displacement_atr: float = 0.6,
                 sl_atr_mult: float = 2.0, tp_atr_mult: float = 4.0,
                 magic: int = 7315):
        self.displacement_atr = displacement_atr
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "SILVER_BULLET_V6"
        self._min_bars = 250
        self._last_signal_day = None

    def _detect_fvg(self, highs, lows, closes, opens, idx):
        """Check for a 3-bar FVG pattern ending at idx.

        Bullish FVG: bar[idx-2].high < bar[idx].low (gap up)
        Bearish FVG: bar[idx-2].low > bar[idx].high (gap down)
        """
        if idx < 2:
            return None

        # Bullish FVG: gap between bar[-3] high and bar[-1] low
        if lows[idx] > highs[idx - 2]:
            gap_size = lows[idx] - highs[idx - 2]
            return ("bullish", gap_size, highs[idx - 2], lows[idx])

        # Bearish FVG: gap between bar[-3] low and bar[-1] high
        if highs[idx] < lows[idx - 2]:
            gap_size = lows[idx - 2] - highs[idx]
            return ("bearish", gap_size, highs[idx], lows[idx - 2])

        return None

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        utc_seconds = bar_time % 86400
        # Silver Bullet window: 14:00-15:00 UTC (10:00-11:00 NY EST)
        if utc_seconds < 50400 or utc_seconds >= 54000:
            return None

        current_day = bar_time // 86400
        if self._last_signal_day == current_day:
            return None

        highs = m15_rates["high"].astype(float)
        lows = m15_rates["low"].astype(float)
        closes = m15_rates["close"].astype(float)
        opens = m15_rates["open"].astype(float)

        # ATR14
        atr_arr = self.atr(highs, lows, closes, 14)
        atr_val = float(atr_arr[-2])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return None

        # Check for FVG in the last few bars
        idx = len(m15_rates) - 2  # last closed bar

        # Look at the 3-bar window ending at bar before last (to see if
        # current bar is filling a recently created FVG)
        for offset in range(0, 3):
            check_idx = idx - offset
            if check_idx < 3:
                continue

            fvg = self._detect_fvg(highs, lows, closes, opens, check_idx)
            if fvg is None:
                continue

            direction, gap_size, gap_low, gap_high = fvg

            # Displacement filter: the FVG-creating candle must have body >= threshold
            disp_body = abs(closes[check_idx] - opens[check_idx])
            if disp_body < self.displacement_atr * atr_val:
                continue

            bar_close = float(closes[-2])
            bar_open = float(opens[-2])

            if direction == "bullish":
                # Price has come back down toward the FVG (filling it)
                if bar_close > gap_low and bar_close > bar_open:
                    self._last_signal_day = current_day
                    return Signal(direction=mt5.ORDER_TYPE_BUY,
                                  strategy_name=self.name, magic=self.magic, is_buy=True)

            elif direction == "bearish":
                # Price has come back up toward the FVG (filling it)
                if bar_close < gap_high and bar_close < bar_open:
                    self._last_signal_day = current_day
                    return Signal(direction=mt5.ORDER_TYPE_SELL,
                                  strategy_name=self.name, magic=self.magic, is_buy=False)

        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
