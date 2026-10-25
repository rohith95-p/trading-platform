"""Daily-open momentum with EMA trend filter (research candidate -- NOT in PORTFOLIO, not live).

RULE (all on the last CLOSED M15 bar, index -2; once-per-day derived statelessly)
  1. Day open = open of the first M15 bar of the current UTC day (00:00 UTC);
     that bar must open within the first 2 hours of the UTC day and be present
     in the supplied history (otherwise no trade).
  2. BUY  when close - day_open > 0.8 x ATR14  AND  EMA50 > EMA200 (on closes);
     SELL when day_open - close > 0.8 x ATR14 AND  EMA50 < EMA200.
  3. Only the FIRST bar of the UTC day satisfying (2) fires (either side);
     the signal bar must be that bar. Signals only for bars opening
     05:30 <= IST < 23:30.
  4. Exits: sl 1.5 x ATR, tp 3.0 x ATR (engine-applied).
Needs >= 400 M15 bars (EMA200 warm-up) -- more than the live loop 250-bar
fetch, so live use would require raising that window. Causal: bars <= index -2.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5
from src.strategies.new_common import closed, ist_sec, utc_day, atr14, ema


class DailyOpenMomentum(BaseStrategy):
    execute_immediately = True
    edge_trigger = True
    session = (5.5, 23.5)           # IST

    def __init__(self, move_atr: float = 0.8, sl_atr_mult: float = 1.5,
                 tp_atr_mult: float = 3.0, magic: int = 7203):
        self.move_atr = move_atr
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "NEW_DAILY_OPEN_MOMENTUM"
        self._min_bars = 400

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None
        c = closed(m15_rates)
        n = len(c)
        t = c["time"].astype("int64")
        sec = ist_sec(t)
        if not (19800 <= sec[-1] < 84600):
            return None
        day = utc_day(t)
        idx = np.flatnonzero(day == day[-1])
        first = idx[0]
        if first == 0 or t[first] - day[-1] * 86400 > 7200:
            return None                      # day open missing / history truncated
        day_open = float(c["open"][first])
        cl = c["close"].astype(float)
        atr = atr14(c)
        e50 = ema(cl, 50)
        e200 = ema(cl, 200)
        d = cl[idx] - day_open
        a = atr[idx]
        long_ = (d > self.move_atr * a) & (e50[idx] > e200[idx])
        short_ = (-d > self.move_atr * a) & (e50[idx] < e200[idx])
        hit = np.flatnonzero(long_ | short_)       # NaN comparisons are False
        if len(hit) == 0 or idx[hit[0]] != n - 1:
            return None
        buy = bool(long_[hit[0]])
        return Signal(direction=mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL,
                      strategy_name=self.name, magic=self.magic, is_buy=buy)

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
