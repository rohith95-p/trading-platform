"""
TrendlineEMA8Scalp — Instagram "one repeatable entry" strategy.

Setup (from screenshot):
  - Trendline retrace: price pulls back toward a rising/falling trendline
    (approximated here as the 34 EMA acting as the dynamic trendline)
  - 8 EMA crossover: the fast 8 EMA must be above/below the 21 EMA (trend stack)
  - Candlestick signal: the signal candle closes back above the 8 EMA (after touch)
    for longs, or below for shorts

Short version (BEARISH gate day):
  - 8 EMA < 21 EMA  (downtrend stack)
  - Price pulls up INTO the 8 EMA from below (retrace)
  - Signal candle closes BACK BELOW the 8 EMA (rejection)
  → SHORT

Long version (BULLISH gate day):
  - 8 EMA > 21 EMA  (uptrend stack)
  - Price pulls down INTO the 8 EMA from above (retrace)
  - Signal candle closes BACK ABOVE the 8 EMA (rejection bounce)
  → BUY

Session: 11:30-21:30 IST (London + NY, matching the live EMASTACK window)
SL/TP: set by engine via sl_atr_mult / tp_atr_mult
"""

from __future__ import annotations
from typing import Optional
import numpy as np
import MetaTrader5 as _mt5
from typing import Any
from src.strategies.base_strategy import BaseStrategy, Signal

mt5: Any = _mt5


def _ist_hour(rates: np.ndarray) -> np.ndarray:
    ts = rates["time"].astype("int64")
    return ((ts % 86400) + 19800) % 86400 / 3600.0


class TrendlineEMA8Scalp(BaseStrategy):
    """
    Trendline retrace + 8 EMA crossover scalp.
    Parameters tuned to mirror the Instagram setup on XAUUSD M15.
    """
    name = "TRENDLINE_EMA8_SCALP"
    magic = 9001
    execute_immediately = True
    edge_trigger = True
    _min_bars = 60

    def __init__(
        self,
        fast_ema: int = 8,
        trend_ema: int = 21,
        trendline_ema: int = 34,  # dynamic trendline proxy
        session: tuple = (11.5, 21.5),
        sl_atr_mult: float = 0.75,
        tp_atr_mult: float = 2.0,
    ):
        self.fast_ema = fast_ema
        self.trend_ema = trend_ema
        self.trendline_ema = trendline_ema
        self.session = session
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        cl = m15_rates["close"].astype(float)
        hi = m15_rates["high"].astype(float)
        lo = m15_rates["low"].astype(float)
        ist = _ist_hour(m15_rates)
        i = -2  # last CLOSED candle (no lookahead)

        # Session gate
        if not (self.session[0] <= ist[i] < self.session[1]):
            return None

        ema8  = self.ema(cl, self.fast_ema)
        ema21 = self.ema(cl, self.trend_ema)
        ema34 = self.ema(cl, self.trendline_ema)

        if np.isnan(ema8[i]) or np.isnan(ema21[i]) or np.isnan(ema34[i]):
            return None

        # ----------------------------------------------------------------
        # SHORT setup (bearish EMA stack — matches current BEARISH gate)
        # ----------------------------------------------------------------
        # 1. Trend: 8 EMA < 21 EMA (downtrend)
        # 2. Retrace: prior candle's HIGH touched or crossed the 8 EMA from below
        #    (meaning price came up to test the 8 EMA — the "retrace to trendline")
        # 3. Signal candle: closes back BELOW the 8 EMA (rejection)
        # ----------------------------------------------------------------
        if ema8[i] < ema21[i]:  # downtrend stack
            prior_high_touched_ema8 = hi[i - 1] >= ema8[i - 1]  # retrace to EMA8
            candle_rejected         = cl[i] < ema8[i]            # close below EMA8
            # Candle body is bearish (close < open) — the "candlestick signal"
            bearish_candle          = cl[i] < m15_rates["open"][i - 1]  # prev candle opened higher

            if prior_high_touched_ema8 and candle_rejected:
                return Signal(
                    direction=mt5.ORDER_TYPE_SELL,
                    strategy_name=self.name,
                    magic=self.magic,
                    is_buy=False,
                )

        # ----------------------------------------------------------------
        # LONG setup (bullish EMA stack)
        # ----------------------------------------------------------------
        # 1. Trend: 8 EMA > 21 EMA (uptrend)
        # 2. Retrace: prior candle's LOW touched or crossed the 8 EMA from above
        # 3. Signal candle: closes back ABOVE the 8 EMA (bounce)
        # ----------------------------------------------------------------
        if ema8[i] > ema21[i]:  # uptrend stack
            prior_low_touched_ema8 = lo[i - 1] <= ema8[i - 1]   # retrace to EMA8
            candle_bounced         = cl[i] > ema8[i]             # close above EMA8

            if prior_low_touched_ema8 and candle_bounced:
                return Signal(
                    direction=mt5.ORDER_TYPE_BUY,
                    strategy_name=self.name,
                    magic=self.magic,
                    is_buy=True,
                )

        return None
