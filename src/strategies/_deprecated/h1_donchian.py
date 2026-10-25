"""H1 Donchian breakout (research candidate -- NOT in PORTFOLIO, not live).

Entry: an H1 bar closes beyond the highest high / lowest low of the previous
`channel` H1 bars. Evaluated once per hour, on the last M15 bar of that H1 bar,
so it fires at most once per H1 bar. H1 bars are built from M15 (broker H1 bars
are aligned to the hour).

Exits are the engine's fixed ATR stop/target (the production exit model), set per
instance; the original Donchian opposite-channel exit is approximated by a wide
target. Needs ~`channel`+2 complete H1 bars = ~410 M15 bars, more than the live
loop's 250-bar fetch, so running it live would require raising that window.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class H1Donchian(BaseStrategy):
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)

    def __init__(self, channel: int = 100, sl_atr_mult: float = 4.0,
                 tp_atr_mult: float = 12.0, magic: int = 7100):
        self.channel = channel
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = f"H1_DONCHIAN_{channel}"
        self._min_bars = (channel + 3) * 4 + 120  # slack for weekend gaps

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None
        t = int(m15_rates["time"][-2])
        if t % 3600 != 2700:          # only the last M15 bar of an hour
            return None

        # Complete H1 bars by hour key (weekends/holidays simply have no bars).
        seg = m15_rates[-2 - self._min_bars + 1:-1]      # closed M15 bars only
        hour = seg["time"].astype("int64") // 3600
        keys, start = np.unique(hour, return_index=True)
        if len(keys) < self.channel + 2:
            return None
        bounds = list(start) + [len(seg)]
        hi = np.array([seg["high"][bounds[k]:bounds[k + 1]].max() for k in range(len(keys))], float)
        lo = np.array([seg["low"][bounds[k]:bounds[k + 1]].min() for k in range(len(keys))], float)
        cl = np.array([seg["close"][bounds[k + 1] - 1] for k in range(len(keys))], float)
        prev_hi = hi[-1 - self.channel:-1].max()
        prev_lo = lo[-1 - self.channel:-1].min()
        # edge trigger: the previous H1 close must not already have been a breakout
        p_hi = hi[-2 - self.channel:-2].max()
        p_lo = lo[-2 - self.channel:-2].min()
        if cl[-1] > prev_hi and not cl[-2] > p_hi:
            return Signal(direction=mt5.ORDER_TYPE_BUY, strategy_name=self.name,
                          magic=self.magic, is_buy=True)
        if cl[-1] < prev_lo and not cl[-2] < p_lo:
            return Signal(direction=mt5.ORDER_TYPE_SELL, strategy_name=self.name,
                          magic=self.magic, is_buy=False)
        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
