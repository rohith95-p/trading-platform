"""Production momentum strategy for XAUUSD: Donchian 10-day breakout with EMA50 filter.

Backtested 2026-10-25 on DEV/VALIDATE/HOLDOUT (2022-08 to 2026-10):
  DEV:      n=33 PF=1.04 win=36% net=+$3   maxDD=25%
  VALIDATE: n=39 PF=1.45 win=41% net=+$63  maxDD=33%
  HOLDOUT:  n=36 PF=1.40 win=42% net=+$119 maxDD=30%

Pre-registered: research/registry/PREREG_MomentumPortfolio_2026-10-25.md
Sweep results: scripts/research/donchian_sweep_2026_10_25.py

Live mode: accepts D1 rates directly (passed by main_loop alongside M15).
Backtest mode: builds D1 bars from M15 internally (engine only passes M15).
Fires once per day at 00:30 UTC (6:00 IST), the first M15 bar inside the
IST trading window.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


def _build_d1_from_m15(m15: np.ndarray, min_days: int = 30):
    """Aggregate M15 bars into complete D1 bars (UTC midnight boundary)."""
    times = m15["time"].astype("int64")
    day_key = times // 86400

    keys, start_idx = np.unique(day_key, return_index=True)
    if len(keys) < min_days + 1:
        return None

    keys = keys[:-1]
    bounds = list(start_idx) + [len(m15)]

    n = len(keys)
    d_ts = np.empty(n, dtype="int64")
    d_open = np.empty(n)
    d_high = np.empty(n)
    d_low = np.empty(n)
    d_close = np.empty(n)

    for i in range(n):
        idx_from = bounds[i]
        idx_to = bounds[i + 1]
        seg = m15[idx_from:idx_to]
        d_ts[i] = int(keys[i]) * 86400
        d_open[i] = seg["open"][0]
        d_high[i] = seg["high"].max()
        d_low[i] = seg["low"].min()
        d_close[i] = seg["close"][-1]

    return d_ts, d_open, d_high, d_low, d_close


def _ema(arr, period):
    return BaseStrategy.ema(arr, period)


class DonchianTrendV6(BaseStrategy):
    """10-day Donchian breakout with EMA50 trend filter on XAUUSD.

    Entry: D1 close above 10-day high AND price > EMA50 -> BUY.
           D1 close below 10-day low AND price < EMA50 -> SELL.
    Edge trigger: only fires on a NEW breakout (previous day was not one).
    SL: 2.0x ATR14, TP: 4.0x ATR14.
    Evaluated once per day at 00:30 UTC (6:00 IST market open).
    """
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = False  # owner 2026-10-30: apply the daily trend gate live, as every validated backtest did

    def __init__(self, channel: int = 10, trend_ma: int = 50,
                 sl_atr_mult: float = 2.0, tp_atr_mult: float = 4.0,
                 magic: int = 7310):
        self.channel = channel
        self.trend_ma = trend_ma
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "DONCHIAN_TREND_V6"
        needed = max(channel, trend_ma) + 5
        self._min_bars = needed * 96 + 200
        self._min_d1 = max(channel, trend_ma) + 3
        self._d1_rates: Optional[np.ndarray] = None

    def set_d1_rates(self, d1_rates: np.ndarray) -> None:
        """Called by the live loop each scan with the latest D1 bars from MT5."""
        self._d1_rates = d1_rates

    def _get_d1(self, m15_rates: np.ndarray):
        """Use live D1 rates if available, else build from M15."""
        d = self._d1_rates
        if d is not None and len(d) and int(d["time"][-1]) >= int(m15_rates["time"][-1]) // 86400 * 86400:
            d = d[:-1]  # live feed includes today's forming bar; the strategy (and backtest) use completed days
        if d is not None and len(d) >= self._min_d1:
            return (d["time"].astype("int64"), d["open"].astype(float),
                    d["high"].astype(float), d["low"].astype(float),
                    d["close"].astype(float))
        return _build_d1_from_m15(m15_rates, self._min_d1)

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < 200:
            return None

        bar_time = int(m15_rates["time"][-2])
        if bar_time % 86400 != 1800:
            return None

        d1 = self._get_d1(m15_rates)
        if d1 is None:
            return None
        _, _, d_high, d_low, d_close = d1

        if len(d_close) < max(self.channel, self.trend_ma) + 2:
            return None

        prev_high = d_high[-1 - self.channel:-1].max()
        prev_low = d_low[-1 - self.channel:-1].min()

        p_high = d_high[-2 - self.channel:-2].max()
        p_low = d_low[-2 - self.channel:-2].min()

        ma = _ema(d_close, self.trend_ma)
        if np.isnan(ma[-1]):
            return None
        above_ma = d_close[-1] > ma[-1]

        if d_close[-1] > prev_high and not d_close[-2] > p_high:
            if not above_ma:
                return None
            return Signal(direction=mt5.ORDER_TYPE_BUY,
                          strategy_name=self.name, magic=self.magic, is_buy=True)
        if d_close[-1] < prev_low and not d_close[-2] < p_low:
            if above_ma:
                return None
            return Signal(direction=mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=False)
        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
