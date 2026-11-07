"""Candidate entry signals for the 2026-11-07 entry search.

Pre-registered: research/registry/PREREG_EntrySearch_2026-11-07.md
Seven signals x three geometries = 21 candidates, all frozen in that document
before anything ran. Thresholds here are fixed and deliberately NOT swept:
sweeping them is the mechanism that produced the last false positive.

All signals are built from the M15 view, because the engine passes strategies
`evaluate(m15_view, m5_view)` and no daily view. Daily bars are therefore
aggregated from M15 by calendar day with `reduceat`, which is exact and fast.

Convention copied from the live legs: `m15_rates[-1]` is a FORMING bar, so the
last CLOSED bar is `[-2]` and every read here drops the forming bar first.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5

# The bar that OPENS at 12:45 UTC closes at 13:00 UTC, the declared entry
# instant. The live legs use the same construction (12:00 -> 12:15 entry).
SIGNAL_BAR_SEC = 45900

# Frozen in the pre-registration.
TSMOM_ATR_MULT = 6.0
MR_Z = 2.0
NRX_SHORT_DAYS = 3
NRX_LOOKBACK_DAYS = 20


def _daily(times: np.ndarray, highs: np.ndarray, lows: np.ndarray,
           closes: np.ndarray):
    """Daily high/low/close from M15 bars, complete prior days only.

    The current (partial) day is dropped, so every value returned is a settled
    daily bar. Grouping uses reduceat over day boundaries: the M15 times are
    ascending, so each day is one contiguous block.
    """
    day = times // 86400
    udays = np.unique(day)
    if len(udays) < 2:
        return None
    bnd = np.searchsorted(day, udays)
    dh = np.maximum.reduceat(highs, bnd)
    dl = np.minimum.reduceat(lows, bnd)
    ends = np.r_[bnd[1:], len(closes)] - 1
    dc = closes[ends]
    # drop the current, still-forming day
    return dh[:-1], dl[:-1], dc[:-1]


class _Candidate(BaseStrategy):
    """Shared plumbing: fire once a day at the declared instant, on closed bars."""

    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True          # the D1 EMA20 gate added no information (2026-11-07)
    lookback_days = 20
    code = "BASE"

    def __init__(self, sl_atr_mult: float, tp_atr_mult: float, magic: int):
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "%s_S%g_T%g" % (self.code, sl_atr_mult, tp_atr_mult)
        self._min_bars = self.lookback_days * 96 + 120

    # -- subclasses implement this ------------------------------------------
    def decide(self, dh, dl, dc, px, atr) -> Optional[bool]:
        """Return True for long, False for short, None for no trade."""
        raise NotImplementedError

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self._min_bars:
            return None

        # last CLOSED bar; [-1] is forming
        bar_time = int(m15_rates["time"][-2])
        if bar_time % 86400 != SIGNAL_BAR_SEC:
            return None

        times = m15_rates["time"].astype("int64")[:-1]
        highs = m15_rates["high"].astype(float)[:-1]
        lows = m15_rates["low"].astype(float)[:-1]
        closes = m15_rates["close"].astype(float)[:-1]

        atr_arr = self.atr(highs, lows, closes, 14)
        atr = float(atr_arr[-1])
        if not np.isfinite(atr) or atr <= 0:
            return None

        got = _daily(times, highs, lows, closes)
        if got is None:
            return None
        dh, dl, dc = got
        if len(dc) < self.lookback_days + 1:
            return None

        want = self.decide(dh, dl, dc, float(closes[-1]), atr)
        if want is None:
            return None
        return Signal(
            direction=mt5.ORDER_TYPE_BUY if want else mt5.ORDER_TYPE_SELL,
            strategy_name=self.name, magic=self.magic, is_buy=bool(want))

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass


# --------------------------------------------------------------------------
# S1-S3  time-series momentum: trade the direction of the N-day move
# --------------------------------------------------------------------------
class _TSMom(_Candidate):
    n_days = 10

    def decide(self, dh, dl, dc, px, atr):
        if len(dc) < self.n_days + 1:
            return None
        move = float(dc[-1] - dc[-1 - self.n_days])
        if abs(move) < TSMOM_ATR_MULT * atr:
            return None
        return move > 0


class TSMom10(_TSMom):
    code, n_days, lookback_days = "TSMOM10", 10, 12


class TSMom20(_TSMom):
    code, n_days, lookback_days = "TSMOM20", 20, 22


class TSMom40(_TSMom):
    code, n_days, lookback_days = "TSMOM40", 40, 42


# --------------------------------------------------------------------------
# S4-S5  Donchian channel breakout (published turtle lengths, not fitted)
# --------------------------------------------------------------------------
class _Donchian(_Candidate):
    n_days = 20

    def decide(self, dh, dl, dc, px, atr):
        hi = float(dh[-self.n_days:].max())
        lo = float(dl[-self.n_days:].min())
        if px > hi:
            return True
        if px < lo:
            return False
        return None


class Donchian20(_Donchian):
    code, n_days, lookback_days = "DONCH20", 20, 22


class Donchian55(_Donchian):
    code, n_days, lookback_days = "DONCH55", 55, 57


# --------------------------------------------------------------------------
# S6  narrow-range expansion: compression, then trade the break
# --------------------------------------------------------------------------
class NarrowRangeExpansion(_Candidate):
    code = "NRX"
    lookback_days = NRX_LOOKBACK_DAYS + 2

    def decide(self, dh, dl, dc, px, atr):
        k, n = NRX_SHORT_DAYS, NRX_LOOKBACK_DAYS
        if len(dh) < n + k:
            return None
        # rolling k-day range for each of the last n days
        rng = np.array([dh[-(i + k):len(dh) - i].max() - dl[-(i + k):len(dl) - i].min()
                        for i in range(n)], dtype=float)
        if not np.isfinite(rng).all() or rng[0] > rng.min():
            return None                      # the newest window must be the tightest
        hi = float(dh[-k:].max())
        lo = float(dl[-k:].min())
        if px > hi:
            return True
        if px < lo:
            return False
        return None


# --------------------------------------------------------------------------
# S7  multi-day mean reversion at a z-score extreme
# --------------------------------------------------------------------------
class MeanReversion20(_Candidate):
    code = "MR20"
    lookback_days = 22
    n_days = 20

    def decide(self, dh, dl, dc, px, atr):
        w = dc[-self.n_days:].astype(float)
        sd = float(w.std(ddof=1))
        if sd <= 0:
            return None
        z = (px - float(w.mean())) / sd
        if z >= MR_Z:
            return False                     # stretched up -> short
        if z <= -MR_Z:
            return True
        return None


# --------------------------------------------------------------------------
# The 21 candidates, frozen: 7 signals x 3 geometries
# --------------------------------------------------------------------------
SIGNALS = [TSMom10, TSMom20, TSMom40, Donchian20, Donchian55,
           NarrowRangeExpansion, MeanReversion20]

GEOMETRIES = [(6.0, 10.0), (8.0, 16.0), (12.0, 24.0)]


def candidates():
    """[(id, factory)] -- 21 of them, in a fixed, reproducible order."""
    out = []
    magic = 8000
    for cls in SIGNALS:
        for sl, tp in GEOMETRIES:
            magic += 1

            def make(cls=cls, sl=sl, tp=tp, magic=magic):
                return cls(sl_atr_mult=sl, tp_atr_mult=tp, magic=magic)

            out.append(("%s_S%g_T%g" % (cls.code, sl, tp), make))
    return out
