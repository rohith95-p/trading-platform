"""London open drive continuation (research candidate -- NOT in PORTFOLIO, not live).

RULE (evaluated only when the last CLOSED M15 bar [-2] is the 4th bar after the
London open, i.e. opens 13:15 IST = 07:45 UTC; this makes it one-per-day by
construction)
  1. The 4 M15 bars opening 12:30, 12:45, 13:00, 13:15 IST must all be present
     (consecutive timestamps; holidays/gaps -> no trade).
  2. drive = close(13:15 bar) - open(12:30 bar). ATR = ATR14 of the last bar
     closed BEFORE 12:30 IST (pre-open volatility, excludes the drive itself).
  3. BUY  if drive >= +1.0 x ATR and at least 3 of the 4 bars closed up
     (close > open); SELL mirror image (drive <= -1.0 x ATR, >= 3 bars down).
  4. Exits: sl 1.5 x ATR, tp 3.0 x ATR (engine-applied).
Needs >= 250 M15 bars. Causal: uses only bars <= index -2.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5
from src.strategies.new_common import closed, ist_sec, atr14


class LondonOpenDrive(BaseStrategy):
    execute_immediately = True
    edge_trigger = True
    session = (12.5, 13.5)          # IST

    DRIVE_START = 45000             # 12:30 IST in seconds
    LAST_BAR = 47700                # 13:15 IST (opening time of the 4th bar)

    def __init__(self, drive_atr: float = 1.0, sl_atr_mult: float = 1.5,
                 tp_atr_mult: float = 3.0, magic: int = 7202):
        self.drive_atr = drive_atr
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "NEW_LONDON_OPEN_DRIVE"
        self._min_bars = 250

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None
        c = closed(m15_rates)
        t = c["time"].astype("int64")
        if int(ist_sec(t[-1:])[0]) != self.LAST_BAR:
            return None
        if t[-1] - t[-4] != 3 * 900 or int(ist_sec(t[-4:-3])[0]) != self.DRIVE_START:
            return None
        if t[-4] - t[-5] > 3600:
            return None                      # no recent pre-open bar
        atr = atr14(c)
        a = float(atr[-5])                   # last bar closed before 12:30 IST
        if not np.isfinite(a) or a <= 0:
            return None
        o = c["open"][-4:].astype(float)
        cl = c["close"][-4:].astype(float)
        drive = cl[-1] - o[0]
        if drive >= self.drive_atr * a and int((cl > o).sum()) >= 3:
            return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name,
                          magic=self.magic, is_buy=True)
        if drive <= -self.drive_atr * a and int((cl < o).sum()) >= 3:
            return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name,
                          magic=self.magic, is_buy=False)
        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
