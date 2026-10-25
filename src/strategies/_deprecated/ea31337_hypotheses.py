"""Three pre-registered hypotheses inspired by EA31337 strategy names (SuperTrend, MA Breakout, Pinbar).

These are OUR plain-text definitions of the textbook ideas, not ports of EA31337 code, and are not in any PORTFOLIO.
All rules read only CLOSED bars (index -2 is the last closed bar; -1 is the forming bar) on M15 data.
Exits are the engine's fixed ATR14 stop/target (sl_atr_mult / tp_atr_mult).

Pre-registered rules
  SUPERTREND  : SuperTrend(ATR 10, multiplier 3.0). Signal only on the bar where the trend FLIPS (edge trigger);
                trade in the new direction.
  MA_BREAKOUT : EMA(20) +/- 1.0 x ATR14 band. BUY when the closed bar closes above the upper band and the previous
                closed bar did not; SELL symmetrically (volatility-expansion break out of the MA envelope).
  PINBAR      : rejection candle: wick >= 60% of the bar range and >= 2x the body, at a 20-bar extreme, confirmed by
                CCI(14) < -100 and RSI(14) < 35 (BUY, lower wick) or CCI > 100 and RSI > 65 (SELL, upper wick).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5


def _atr(h, l, c, n):
    return BaseStrategy.atr(h, l, c, n)


def supertrend_direction(h, l, c, period=10, mult=3.0):
    """Return array of +1/-1 trend direction (0 before warm-up), standard final-band SuperTrend."""
    n = len(c)
    a = _atr(h, l, c, period)
    hl2 = (h + l) / 2.0
    ub, lb = hl2 + mult * a, hl2 - mult * a
    fub, flb = ub.copy(), lb.copy()
    d = np.zeros(n, dtype=int)
    start = period
    if n <= start:
        return d
    d[start] = 1 if c[start] >= hl2[start] else -1
    for i in range(start + 1, n):
        fub[i] = ub[i] if (ub[i] < fub[i - 1] or c[i - 1] > fub[i - 1]) else fub[i - 1]
        flb[i] = lb[i] if (lb[i] > flb[i - 1] or c[i - 1] < flb[i - 1]) else flb[i - 1]
        if d[i - 1] == 1:
            d[i] = -1 if c[i] < flb[i] else 1
        else:
            d[i] = 1 if c[i] > fub[i] else -1
    return d


class _Base(BaseStrategy):
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    _min_bars = 120

    def __init__(self, sl_atr_mult: float, tp_atr_mult: float, magic: int):
        self.sl_atr_mult, self.tp_atr_mult, self.magic = sl_atr_mult, tp_atr_mult, magic

    def _sig(self, buy: bool) -> Signal:
        return Signal(direction=mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL, strategy_name=self.name,
                      magic=self.magic, is_buy=buy)

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass


class SuperTrendH(_Base):
    def __init__(self, sl_atr_mult=2.0, tp_atr_mult=4.0, magic=7301):
        super().__init__(sl_atr_mult, tp_atr_mult, magic)
        self.name = f"SUPERTREND_H_{sl_atr_mult}_{tp_atr_mult}"

    def evaluate(self, m15_rates, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None
        r = m15_rates[:-1]                                   # closed bars only
        h, l, c = (r[k].astype(float) for k in ("high", "low", "close"))
        d = supertrend_direction(h, l, c)
        if d[-1] != 0 and d[-2] != 0 and d[-1] != d[-2]:
            return self._sig(d[-1] > 0)
        return None


class MABreakoutH(_Base):
    def __init__(self, sl_atr_mult=2.0, tp_atr_mult=4.0, magic=7302):
        super().__init__(sl_atr_mult, tp_atr_mult, magic)
        self.name = f"MA_BREAKOUT_H_{sl_atr_mult}_{tp_atr_mult}"

    def evaluate(self, m15_rates, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None
        r = m15_rates[:-1]
        h, l, c = (r[k].astype(float) for k in ("high", "low", "close"))
        ma = BaseStrategy.ema(c, 20)
        a = _atr(h, l, c, 14)
        up, dn = ma + a, ma - a
        if np.isnan(up[-2]) or np.isnan(a[-1]):
            return None
        if c[-1] > up[-1] and not c[-2] > up[-2]:
            return self._sig(True)
        if c[-1] < dn[-1] and not c[-2] < dn[-2]:
            return self._sig(False)
        return None


class PinbarH(_Base):
    def __init__(self, sl_atr_mult=1.0, tp_atr_mult=1.5, magic=7303):
        super().__init__(sl_atr_mult, tp_atr_mult, magic)
        self.name = f"PINBAR_H_{sl_atr_mult}_{tp_atr_mult}"

    @staticmethod
    def _cci(h, l, c, n=14):
        tp = (h + l + c) / 3.0
        out = np.full(len(tp), np.nan)
        for i in range(n - 1, len(tp)):
            w = tp[i - n + 1:i + 1]
            md = np.mean(np.abs(w - w.mean()))
            out[i] = (tp[i] - w.mean()) / (0.015 * md) if md > 0 else 0.0
        return out

    def evaluate(self, m15_rates, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None
        r = m15_rates[:-1]
        o, h, l, c = (r[k].astype(float) for k in ("open", "high", "low", "close"))
        rng = h[-1] - l[-1]
        if rng <= 0:
            return None
        body = abs(c[-1] - o[-1])
        lower = min(o[-1], c[-1]) - l[-1]
        upper = h[-1] - max(o[-1], c[-1])
        cci = self._cci(h[-30:], l[-30:], c[-30:])[-1]
        rsi = BaseStrategy.rsi(c[-60:], 14)[-1]
        if np.isnan(cci) or np.isnan(rsi):
            return None
        if lower >= 0.6 * rng and lower >= 2 * max(body, 1e-9) and l[-1] <= l[-20:].min() and cci < -100 and rsi < 35:
            return self._sig(True)
        if upper >= 0.6 * rng and upper >= 2 * max(body, 1e-9) and h[-1] >= h[-20:].max() and cci > 100 and rsi > 65:
            return self._sig(False)
        return None
