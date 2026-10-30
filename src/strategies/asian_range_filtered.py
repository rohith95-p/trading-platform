"""Asian Range Filtered Breakout — improved London breakout with range filter and BE stop.

Based on MQL5 blog backtest (3.7yr real ticks, PF 1.37, 715 trades):
- Asian range 00:00-06:00 UTC, breakout at 07:00 UTC
- Range filter: skip if range < 0.3% or > 1.6% of price (avoids dead/wild days)
- TP at 2.5R, breakeven stop at 1.5R (simulated via tighter SL/TP ratio)
- EOD exit: positions must close by 21:00 UTC (enforced by engine max_hold)

Key improvement over basic AsianBreakoutV6: the range filter eliminates
low-quality setups that cause most of the drawdown.

Source: https://www.mql5.com/en/blogs/post/777540
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class AsianRangeFilteredV6(BaseStrategy):
    """Filtered Asian range breakout with percentage-based range gate.

    Entry: At 07:00 UTC, if price > Asian high -> BUY, < Asian low -> SELL.
    Filters: range must be 0.3%-1.6% of price AND >= $3 (absolute floor).
    SL: 2.0x ATR14 (tighter than basic version), TP: 3.5x ATR14.
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = False  # owner 2026-10-30: apply the daily trend gate live, as every validated backtest did

    def __init__(self, sl_atr_mult: float = 2.0, tp_atr_mult: float = 3.5,
                 min_range_pct: float = 0.003, max_range_pct: float = 0.016,
                 min_range_abs: float = 3.0, magic: int = 7320):
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.min_range_pct = min_range_pct
        self.max_range_pct = max_range_pct
        self.min_range_abs = min_range_abs
        self.magic = magic
        self.name = "ASIAN_RANGE_FILTERED_V6"
        self._min_bars = 250

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        if bar_time % 86400 != 25200:
            return None

        times = m15_rates["time"].astype("int64")
        current_day = bar_time // 86400

        asian_mask = (times // 86400 == current_day) & (times % 86400 < 21600)
        if asian_mask.sum() < 10:
            return None

        highs = m15_rates["high"].astype(float)
        lows = m15_rates["low"].astype(float)
        closes = m15_rates["close"].astype(float)

        asia_high = float(highs[asian_mask].max())
        asia_low = float(lows[asian_mask].min())
        range_width = asia_high - asia_low
        mid_price = (asia_high + asia_low) / 2.0

        if range_width < self.min_range_abs:
            return None

        range_pct = range_width / mid_price
        if range_pct < self.min_range_pct or range_pct > self.max_range_pct:
            return None

        close_price = float(closes[-2])

        if close_price > asia_high:
            return Signal(direction=mt5.ORDER_TYPE_BUY,
                          strategy_name=self.name, magic=self.magic, is_buy=True)
        if close_price < asia_low:
            return Signal(direction=mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=False)
        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
