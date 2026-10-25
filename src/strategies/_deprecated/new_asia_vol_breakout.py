"""Asia range + volatility-expansion breakout (research candidate -- NOT in PORTFOLIO, not live).

RULE (all on the last CLOSED M15 bar, index -2; first-break-per-day is derived
statelessly from the bars passed in, so no persistent state is needed)
  1. Asia range = high/low of the M15 bars opening 02:30 <= IST < 11:30 on the
     same IST calendar day as the signal bar. At least `min_range_bars` (16)
     such bars must exist and the day's range must not be truncated by the
     start of the supplied history.
  2. Break bars = bars opening 11:30 <= IST < 23:30 that close beyond the range
     (close > range high -> BUY, close < range low -> SELL).
  3. Vol filter: ATR14 at the break bar > median of the last 100 ATR14 values
     (ending at that bar).
  4. A "qualifying break" = break bar that also passes the vol filter. Only the
     FIRST qualifying break of the IST day fires (edge trigger): the signal bar
     must be that first one; later breaks the same day are ignored.
  5. Wider exits intended: sl 1.5 x ATR, tp 3.0 x ATR (engine-applied).
Needs >= 250 M15 bars. Causal: uses only bars <= index -2.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5
from src.strategies.new_common import closed, ist_sec, ist_day, atr14


class AsiaVolBreakout(BaseStrategy):
    execute_immediately = True
    edge_trigger = True
    session = (11.5, 23.5)          # IST hours in which a break may fire

    RANGE_START = 9000              # 02:30 IST in seconds
    RANGE_END = 41400               # 11:30 IST
    BREAK_END = 84600               # 23:30 IST

    def __init__(self, sl_atr_mult: float = 1.5, tp_atr_mult: float = 3.0,
                 magic: int = 7201, min_range_bars: int = 16, med_len: int = 100):
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "NEW_ASIA_VOL_BREAKOUT"
        self.min_range_bars = min_range_bars
        self.med_len = med_len
        self._min_bars = 250

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None
        c = closed(m15_rates)
        n = len(c)
        t = c["time"].astype("int64")
        sec = ist_sec(t)
        if not (self.RANGE_END <= sec[-1] < self.BREAK_END):
            return None
        day = ist_day(t)
        in_day = np.flatnonzero(day == day[-1])
        rng = in_day[(sec[in_day] >= self.RANGE_START) & (sec[in_day] < self.RANGE_END)]
        if len(rng) < self.min_range_bars:
            return None
        if rng[0] == 0 and sec[0] > self.RANGE_START + 2 * 900:
            return None                      # history starts inside the range window
        hi = float(c["high"][rng].max())
        lo = float(c["low"][rng].min())

        atr = atr14(c)
        cl = c["close"].astype(float)
        brk = in_day[(sec[in_day] >= self.RANGE_END) & (sec[in_day] < self.BREAK_END)]
        for i in brk:
            if i < 13 + self.med_len - 1:
                continue
            up = cl[i] > hi
            dn = cl[i] < lo
            if not (up or dn):
                continue
            a = atr[i - self.med_len + 1:i + 1]
            if np.isnan(a).any() or not atr[i] > np.median(a):
                continue
            if i != n - 1:
                return None                  # first qualifying break was earlier
            return Signal(direction=mt5.ORDER_TYPE_BUY if up else mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=bool(up))
        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
