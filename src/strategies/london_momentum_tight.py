"""London Momentum Tight — tighter stops for funded-phase Atlas compliance.

Same logic as LondonMomentumV6 but with 2.0x ATR SL (vs 2.5x) and
4.0x ATR TP (vs 5.0x). This reduces per-trade risk to stay under
Atlas's 6% trailing DD limit in funded phase.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class LondonMomentumTightV6(BaseStrategy):
    """London/NY overlap trend continuation with tighter risk.

    Same entry logic as LondonMomentumV6 but tighter stops.
    SL: 2.0x ATR14 (was 2.5), TP: 4.0x ATR14 (was 5.0).
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = False  # owner 2026-10-30: apply the daily trend gate live, as every validated backtest did

    def __init__(self, sl_atr_mult: float = 2.0, tp_atr_mult: float = 4.0,
                 magic: int = 7324):
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "LONDON_MOMENTUM_TIGHT_V6"
        self._min_bars = 250

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        if bar_time % 86400 != 43200:
            return None

        times = m15_rates["time"].astype("int64")
        closes = m15_rates["close"].astype(float)
        opens = m15_rates["open"].astype(float)
        highs = m15_rates["high"].astype(float)
        lows = m15_rates["low"].astype(float)

        current_day = bar_time // 86400

        london_mask = (times // 86400 == current_day) & \
                      (times % 86400 >= 25200) & (times % 86400 < 43200)
        if london_mask.sum() < 16:
            return None

        london_closes = closes[london_mask]
        ema8 = self.ema(london_closes, 8)
        ema21 = self.ema(london_closes, min(21, len(london_closes)))

        if not np.isfinite(ema8[-1]) or not np.isfinite(ema21[-1]):
            return None

        atr_arr = self.atr(highs, lows, closes, 14)
        atr_val = float(atr_arr[-2])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return None

        last4_closes = london_closes[-4:]
        last4_opens = opens[london_mask][-4:]
        if len(last4_closes) < 4:
            return None

        bars_up = int(np.sum(last4_closes > last4_opens))
        bars_down = int(np.sum(last4_closes < last4_opens))

        if ema8[-1] > ema21[-1] and bars_up >= 3:
            london_range = float(highs[london_mask].max() - lows[london_mask].min())
            if london_range >= 1.0 * atr_val:
                return Signal(direction=mt5.ORDER_TYPE_BUY,
                              strategy_name=self.name, magic=self.magic, is_buy=True)

        if ema8[-1] < ema21[-1] and bars_down >= 3:
            london_range = float(highs[london_mask].max() - lows[london_mask].min())
            if london_range >= 1.0 * atr_val:
                return Signal(direction=mt5.ORDER_TYPE_SELL,
                              strategy_name=self.name, magic=self.magic, is_buy=False)

        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
