"""London Open Drive — momentum continuation at London open.

Logic: Measure the first 4 M15 bars after London open (07:00-07:45 UTC).
If price drives strongly in one direction (>= 1.0x pre-open ATR14) with
at least 3 of 4 bars closing in the same direction, enter the continuation.

This captures the institutional flow that hits at London open and typically
carries through the morning session. Fires once per day at 08:00 UTC.

Based on research:
- MQL5 London breakout study (PF 1.38, 715 trades over 3.7yr)
- Deprecated new_london_open_drive.py (converted to UTC time)
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class LondonOpenDriveV6(BaseStrategy):
    """London open first-hour momentum drive.

    Entry: At 08:00 UTC bar close, if the 07:00-07:45 drive >= 1.0x ATR14
           with >= 3 of 4 bars closing in the drive direction.
    SL: 2.5x ATR14, TP: 4.0x ATR14.
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True

    def __init__(self, drive_atr: float = 1.0, min_bars_aligned: int = 3,
                 sl_atr_mult: float = 2.5, tp_atr_mult: float = 4.0,
                 magic: int = 7312):
        self.drive_atr = drive_atr
        self.min_bars_aligned = min_bars_aligned
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "LONDON_OPEN_DRIVE_V6"
        self._min_bars = 250

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        # Fire at 08:00 UTC = 28800s from midnight
        if bar_time % 86400 != 28800:
            return None

        times = m15_rates["time"].astype("int64")
        # The 4 London open bars: 07:00, 07:15, 07:30, 07:45 UTC
        target_times = [bar_time - 3600, bar_time - 2700, bar_time - 1800, bar_time - 900]

        indices = []
        for tt in target_times:
            matches = np.where(times == tt)[0]
            if len(matches) == 0:
                return None
            indices.append(matches[-1])

        opens = m15_rates["open"][indices].astype(float)
        closes = m15_rates["close"][indices].astype(float)
        highs = m15_rates["high"][indices].astype(float)
        lows = m15_rates["low"][indices].astype(float)

        drive = closes[-1] - opens[0]

        # ATR14 from the bar just before the drive (pre-open volatility)
        pre_open_idx = indices[0] - 1
        if pre_open_idx < 14:
            return None
        atr_arr = self.atr(
            m15_rates["high"][:pre_open_idx + 1].astype(float),
            m15_rates["low"][:pre_open_idx + 1].astype(float),
            m15_rates["close"][:pre_open_idx + 1].astype(float),
            14)
        atr_val = float(atr_arr[-1])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return None

        bars_up = int(np.sum(closes > opens))
        bars_down = int(np.sum(closes < opens))

        if drive >= self.drive_atr * atr_val and bars_up >= self.min_bars_aligned:
            return Signal(direction=mt5.ORDER_TYPE_BUY,
                          strategy_name=self.name, magic=self.magic, is_buy=True)
        if drive <= -self.drive_atr * atr_val and bars_down >= self.min_bars_aligned:
            return Signal(direction=mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=False)
        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
