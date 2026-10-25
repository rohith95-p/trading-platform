"""Pullback-to-EMA Trend Entry — enter on pullback to moving average in trend.

Logic: When a clear trend is established (EMA21 > EMA50, price above both),
wait for a pullback that touches or crosses EMA21, then enter when the next
bar closes back in the trend direction.

This is one of the most robust patterns in trend-following literature.
GitHub backtest reference: PF 1.64, Sharpe 0.89, MaxDD 5.81% on gold.

Session-filtered to London+NY (07:00-20:00 UTC) for trend clarity.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


class PullbackTrendV6(BaseStrategy):
    """EMA pullback trend entry during London/NY sessions.

    Entry: Price pulls back to touch EMA21 in a trending market
           (EMA21 vs EMA50 aligned), then closes back in trend direction.
    Trend: EMA21 > EMA50 = uptrend, EMA21 < EMA50 = downtrend.
    Pullback: bar low touches EMA21 (up) or bar high touches EMA21 (down).
    Confirmation: closing bar's close is in trend direction.
    SL: 2.0x ATR14, TP: 4.0x ATR14.
    Once per day.
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True

    def __init__(self, ema_fast: int = 21, ema_slow: int = 50,
                 sl_atr_mult: float = 2.0, tp_atr_mult: float = 4.0,
                 magic: int = 7322):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "PULLBACK_TREND_V6"
        self._min_bars = 250
        self._last_signal_day = None

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        bar_time = int(m15_rates["time"][-2])
        utc_seconds = bar_time % 86400
        if utc_seconds < 25200 or utc_seconds >= 72000:
            return None

        current_day = bar_time // 86400
        if self._last_signal_day == current_day:
            return None

        closes = m15_rates["close"].astype(float)
        highs = m15_rates["high"].astype(float)
        lows = m15_rates["low"].astype(float)
        opens = m15_rates["open"].astype(float)

        atr_arr = self.atr(highs, lows, closes, 14)
        atr_val = float(atr_arr[-2])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return None

        ema_f = self.ema(closes, self.ema_fast)
        ema_s = self.ema(closes, self.ema_slow)

        idx = len(closes) - 2
        ef = float(ema_f[idx])
        es = float(ema_s[idx])
        if not np.isfinite(ef) or not np.isfinite(es):
            return None

        bar_close = float(closes[idx])
        bar_open = float(opens[idx])
        bar_low = float(lows[idx])
        bar_high = float(highs[idx])

        # Uptrend: EMA21 > EMA50, price above EMA50
        if ef > es and bar_close > es:
            # Pullback: bar low touched or crossed EMA21
            if bar_low <= ef * 1.001:
                # Confirmation: closed above EMA21 (bounced)
                if bar_close > ef and bar_close > bar_open:
                    self._last_signal_day = current_day
                    return Signal(direction=mt5.ORDER_TYPE_BUY,
                                  strategy_name=self.name, magic=self.magic,
                                  is_buy=True)

        # Downtrend: EMA21 < EMA50, price below EMA50
        if ef < es and bar_close < es:
            if bar_high >= ef * 0.999:
                if bar_close < ef and bar_close < bar_open:
                    self._last_signal_day = current_day
                    return Signal(direction=mt5.ORDER_TYPE_SELL,
                                  strategy_name=self.name, magic=self.magic,
                                  is_buy=False)

        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
