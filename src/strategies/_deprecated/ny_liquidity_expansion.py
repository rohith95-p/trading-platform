"""Research-only NY liquidity sweep and expansion strategy.

The setup is intentionally narrow:

* trade only during the NY session;
* use the completed previous day's high/low and the completed pre-NY range;
* require a sweep and a closed-bar reclaim;
* emit at most one signal per IST day;
* never read the current forming bar.

This class is not imported by ``main_loop``. It must earn promotion through the
existing validation process.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


IST_OFFSET_SECONDS = 5.5 * 60 * 60
NY_START = 17.5
NY_END = 21.5


def _ist_day_and_hour(timestamp: int) -> Tuple[str, float]:
    shifted = int(timestamp) + int(IST_OFFSET_SECONDS)
    day = datetime.fromtimestamp(shifted, tz=timezone.utc).date().isoformat()
    hour = (shifted % 86400) / 3600.0
    return day, hour


class NYLiquidityExpansion(BaseStrategy):
    """Closed-bar NY sweep/reclaim with fixed ATR exit geometry."""

    name = "NY_LIQUIDITY_EXPANSION"
    magic = 3041
    session = (NY_START, NY_END)
    sl_atr_mult = 1.0
    tp_atr_mult = 2.5
    _min_bars = 120

    def __init__(self) -> None:
        self._last_signal_day: Optional[str] = None

    @staticmethod
    def _previous_day_levels(
        times: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        current_day: str,
    ) -> Optional[Tuple[float, float]]:
        days = np.array([_ist_day_and_hour(int(t))[0] for t in times])
        prior = days < current_day
        if not np.any(prior):
            return None
        prior_days = days[prior]
        previous_day = prior_days[-1]
        mask = prior & (days == previous_day)
        return float(np.max(highs[mask])), float(np.min(lows[mask]))

    @staticmethod
    def _pre_ny_levels(
        times: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        current_day: str,
    ) -> Optional[Tuple[float, float]]:
        hours = np.array([_ist_day_and_hour(int(t))[1] for t in times])
        days = np.array([_ist_day_and_hour(int(t))[0] for t in times])
        mask = (days == current_day) & (hours >= 6.0) & (hours < NY_START)
        if not np.any(mask):
            return None
        return float(np.max(highs[mask])), float(np.min(lows[mask]))

    def evaluate(
        self,
        rates: np.ndarray,
        m5_rates: Optional[np.ndarray] = None,
    ) -> Optional[Signal]:
        if rates is None or len(rates) < self._min_bars:
            return None

        # The final row is the forming bar in live and in the engine. Only the
        # closed row immediately before it may create a signal.
        closed = -2
        prior = -3
        day, hour = _ist_day_and_hour(int(rates["time"][closed]))
        if not (NY_START <= hour < NY_END) or self._last_signal_day == day:
            return None

        highs = rates["high"].astype(float)
        lows = rates["low"].astype(float)
        opens = rates["open"].astype(float)
        closes = rates["close"].astype(float)
        prev_levels = self._previous_day_levels(
            rates["time"][:closed], highs[:closed], lows[:closed], day
        )
        pre_ny = self._pre_ny_levels(
            rates["time"][:closed], highs[:closed], lows[:closed], day
        )
        if prev_levels is None or pre_ny is None:
            return None

        prev_high, prev_low = prev_levels
        range_high, range_low = pre_ny
        body = abs(closes[closed] - opens[closed])
        bar_range = max(highs[closed] - lows[closed], 1e-9)
        confirmation = body >= 0.25 * bar_range

        # Requiring the prior closed bar not to have already reclaimed the
        # level avoids treating a persistent state as a fresh event.
        long_sweep = (
            (
                (lows[closed] < prev_low and closes[closed] > prev_low)
                or (lows[closed] < range_low and closes[closed] > range_low)
            )
            and closes[closed] > opens[closed]
            and confirmation
            and closes[prior] >= min(prev_low, range_low)
        )
        short_sweep = (
            (
                (highs[closed] > prev_high and closes[closed] < prev_high)
                or (highs[closed] > range_high and closes[closed] < range_high)
            )
            and closes[closed] < opens[closed]
            and confirmation
            and closes[prior] <= max(prev_high, range_high)
        )

        if long_sweep:
            self._last_signal_day = day
            return Signal(
                direction=mt5.ORDER_TYPE_BUY,
                strategy_name=self.name,
                magic=self.magic,
                is_buy=True,
            )
        if short_sweep:
            self._last_signal_day = day
            return Signal(
                direction=mt5.ORDER_TYPE_SELL,
                strategy_name=self.name,
                magic=self.magic,
                is_buy=False,
            )
        return None
