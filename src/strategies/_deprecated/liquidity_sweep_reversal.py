"""Liquidity-sweep reversal -- the failed-breakout / stop-run fade.

THESIS (economic, written before the numbers)
---------------------------------------------
Stop-loss orders and breakout entries cluster just beyond an obvious swing
extreme -- the high/low of the last N bars, a confirmed pivot, or a clustered
band of old pivots. A bar that spikes *through* that level and then closes
back *inside* the prior range has run that liquidity without genuine
order-flow follow-through: a stop hunt, not a breakout. The reversal trades
the return move back into the range.

This is the same family as `_c_range_rejection` (XAU-049) and the
20-year-audit "Failed breakout reversal", but made precise: the level must be
a real liquidity reference, the penetration must be a true overshoot, and the
close must reject it. The liquidity-context work (HYP-059) showed a preceding
sweep is a genuine footprint of forced flow -- this strategy makes the sweep
the trigger instead of a filter.

FAILURE MODE
------------
On a 24h instrument most "sweeps" are ordinary noise wicks and the level
carries no information; the fade then just pays spread on every bar that pokes
a recent high. 22 years of ~sub-50% M15 follow-through
(INTRADAY_MARKET_STUDY_22YR.md) says that is the base rate to beat.

All detection is on the last CLOSED bar (index -2 of the engine's view). The
engine executes on the next bar's open and computes SL/TP as ATR multiples
from `self.sl_atr_mult` / `self.tp_atr_mult`, exactly as the live legs do.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5
from src.research.market_study import atr as _atr, adx as _adx, ema as _ema

# level types
LEVEL_ROLLING = "rolling"     # high/low of the last `lookback` closed bars
LEVEL_PIVOT = "pivot"         # last confirmed swing pivot (length = lookback//2)
LEVEL_CLUSTER = "cluster"     # clustered band of >=3 pivots within an ATR margin

# confirmation
CONFIRM_IMMEDIATE = "immediate"   # sweep bar itself closes back inside
CONFIRM_NEXT = "next"             # the bar after the sweep also closes inside
CONFIRM_DISPLACE = "displace"     # the bar after is a strong opposite bar
CONFIRM_CHOCH = "choch"           # a structure CHoCH prints within `choch_within` bars

# regime gate
REGIME_NONE = "none"
REGIME_RANGE = "range"            # ADX(14) below a threshold -- fades work in chop
REGIME_COUNTER = "counter"        # sweep is counter to the M15 EMA200 slope


class LiquiditySweepReversal(BaseStrategy):
    execute_immediately = True
    edge_trigger = False
    _min_bars = 250

    def __init__(self, *, level: str = LEVEL_ROLLING, lookback: int = 20,
                 penetration_atr: float = 0.10, close_reject_atr: float = 0.0,
                 confirm: str = CONFIRM_IMMEDIATE, regime: str = REGIME_NONE,
                 adx_max: float = 22.0, session: tuple = (17.5, 21.5),
                 choch_within: int = 4, choch_len: int = 10,
                 sl_atr_mult: float = 1.0, tp_atr_mult: float = 2.0,
                 name: str = "LIQ_SWEEP_REV", magic: int = 90101):
        self.level = level
        self.lookback = int(lookback)
        self.penetration_atr = float(penetration_atr)
        self.close_reject_atr = float(close_reject_atr)
        self.confirm = confirm
        self.regime = regime
        self.adx_max = float(adx_max)
        self.session = session
        self.choch_within = int(choch_within)
        self.choch_len = int(choch_len)
        self.sl_atr_mult = float(sl_atr_mult)
        self.tp_atr_mult = float(tp_atr_mult)
        self.name = name
        self.magic = int(magic)

    # -- helpers -----------------------------------------------------------
    def _in_session(self, ts: int) -> bool:
        hr = (int(ts) + 19800) % 86400 / 3600.0
        a, b = self.session
        return (a <= hr < b) if b > a else (hr >= a or hr < b)

    def _ref_level(self, h, l, i, want_high: bool) -> Optional[float]:
        """The liquidity level that bar `i` is tested against -- built only from
        bars strictly before `i`."""
        lb = self.lookback
        if self.level == LEVEL_ROLLING:
            seg = h[i - lb:i] if want_high else l[i - lb:i]
            return float(seg.max()) if want_high else float(seg.min())
        # pivot / cluster: confirmed swing points, right-offset by `plen`
        plen = max(2, lb // 2)
        piv = []
        src = h if want_high else l
        for p in range(i - 3 * plen, i - plen):
            if p - plen < 0:
                continue
            w = src[p - plen:p + plen + 1]
            if want_high and src[p] == w.max() and (w == src[p]).sum() == 1:
                piv.append(src[p])
            if (not want_high) and src[p] == w.min() and (w == src[p]).sum() == 1:
                piv.append(src[p])
        if not piv:
            return None
        if self.level == LEVEL_PIVOT:
            return float(piv[-1])
        # cluster: need >=3 pivots within a band; use the extreme of that band
        piv = np.array(piv)
        anchor = piv[-1]
        band = 0.5 * abs(np.nanmedian(np.diff(np.sort(piv)))) if len(piv) > 2 else 0.0
        near = piv[np.abs(piv - anchor) <= max(band, 1e-9)]
        if len(near) < 3:
            return None
        return float(near.max()) if want_high else float(near.min())

    # -- signal ----------------------------------------------------------
    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        r = m15_rates
        if r is None or len(r) < self._min_bars:
            return None
        h, l, c = r["high"].astype(float), r["low"].astype(float), r["close"].astype(float)
        atr = _atr(r, 14)
        a = atr[-2]
        if not np.isfinite(a) or a <= 0:
            return None

        # index of the bar the sweep must occur on
        sw = -2 if self.confirm == CONFIRM_IMMEDIATE else -3
        if not self._in_session(int(r["time"][sw])):
            return None

        pen = self.penetration_atr * a
        rej = self.close_reject_atr * a

        for want_high, is_buy in ((True, False), (False, True)):
            lvl = self._ref_level(h, l, len(c) + sw, want_high)
            if lvl is None:
                continue
            if want_high:
                swept = h[sw] > lvl + pen and c[sw] < lvl - rej
            else:
                swept = l[sw] < lvl - pen and c[sw] > lvl + rej
            if not swept:
                continue

            # confirmation on the bar after the sweep (index -2 when sw == -3)
            if self.confirm == CONFIRM_NEXT:
                if want_high and not (c[-2] < lvl):
                    continue
                if (not want_high) and not (c[-2] > lvl):
                    continue
            elif self.confirm == CONFIRM_DISPLACE:
                rng = h[-2] - l[-2]
                if rng < a:
                    continue
                pos = (c[-2] - l[-2]) / rng if rng > 0 else 0.5
                if want_high and pos > 0.35:
                    continue
                if (not want_high) and pos < 0.65:
                    continue
            elif self.confirm == CONFIRM_CHOCH:
                from src.research.structure import compute as _sc
                ev = _sc(r[-3 * self.choch_len - 60:], self.choch_len)["event"]
                recent = ev[-self.choch_within:]
                # a swept HIGH needs a bearish CHoCH (-2); a swept LOW a bullish one (+2)
                if want_high and not (recent == -2).any():
                    continue
                if (not want_high) and not (recent == 2).any():
                    continue

            # regime gate
            if self.regime == REGIME_RANGE:
                adx = _adx(r, 14)[-2]
                if not np.isfinite(adx) or adx > self.adx_max:
                    continue
            elif self.regime == REGIME_COUNTER:
                e200 = _ema(c, 200)[-2]
                if not np.isfinite(e200):
                    continue
                # a swept HIGH is a better fade when price is below its slow mean
                if want_high and c[-2] > e200:
                    continue
                if (not want_high) and c[-2] < e200:
                    continue

            return Signal(direction=mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
                          strategy_name=self.name, magic=self.magic, is_buy=is_buy)
        return None

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass
