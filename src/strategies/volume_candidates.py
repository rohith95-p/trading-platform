"""Volume-conditioned entry signals -- the only unused information we own.

Pre-registered: research/registry/PREREG_VolumeSearch_2026-11-09.md
Design: research/registry/DESIGN_NextSearch_2026-11-09.md

Every one of the ~209 trials this project has run predicted direction from PRICE
alone. `tick_volume` has been sitting in the bars untouched. Measured on 113,465
M15 bars (2022-2026):

    volume -> next-bar RANGE          +0.695
    volume -> |next-bar return|       +0.518
    volume -> SIGNED next return      -0.002

So volume forecasts magnitude strongly and direction not at all. The hypothesis
these four signals test is the only one that measurement leaves open: that
direction becomes predictable from volume regime **interacting with** price
structure, which an unconditional correlation cannot see.

Stated prior: low.

Two data facts that shape the implementation:

* **Volume scale is not comparable across eras.** Median tick_volume is 14 in
  2004-2008 and 1,452 in 2022-2026. Any absolute threshold is meaningless over 18
  years, so every signal here uses a ROLLING PERCENTILE of recent volume.
* `tick_volume` is a tick count, not traded size. It is a participation proxy.

Convention copied from the live legs: `m15_rates[-1]` is a FORMING bar, so the
last CLOSED bar is `[-2]` and every read here drops the forming bar first.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.strategies.base_strategy import BaseStrategy, Signal, mt5

# Frozen in the pre-registration. Not swept.
VOL_LOOKBACK = 500          # ~5 trading days of M15 bars for the percentile
BREAK_BARS = 40             # ~10 hours of structure
HIGH_VOL = 0.80
LOW_VOL = 0.20
SPIKE_VOL = 0.95
REJECT_FRAC = 0.20          # close inside the bottom/top fifth of its own range
VWAP_BARS = 96              # one trading day
VWAP_Z = 1.5


class _VolCandidate(BaseStrategy):
    """Shared plumbing: volume percentile, ATR, and the closed-bar convention."""

    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True        # the D1 EMA20 gate was shown to add nothing
    code = "BASE"
    min_bars = VOL_LOOKBACK + 120

    def __init__(self, sl_atr_mult: float, tp_atr_mult: float, magic: int):
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.magic = magic
        self.name = "%s_S%g_T%g" % (self.code, sl_atr_mult, tp_atr_mult)

    def decide(self, o, h, l, c, vol, volpct, atr) -> Optional[bool]:
        """True = long, False = short, None = no trade. Arrays end at the last
        CLOSED bar; `volpct` is that bar's volume percentile in [0, 1]."""
        raise NotImplementedError

    def evaluate(self, m15_rates: np.ndarray, m5_rates=None) -> Optional[Signal]:
        if m15_rates is None or len(m15_rates) < self.min_bars:
            return None
        if "tick_volume" not in m15_rates.dtype.names:
            return None

        # Only the tail is ever read -- the deepest lookback is VOL_LOOKBACK.
        # Slicing first matters: computing ATR over a 7,500-bar view on every
        # call made the smoke test unrunnable (8 candidates x 70k bars x 7,500
        # = ~4e9 operations). TAIL keeps each evaluation O(600).
        tail = -(VOL_LOOKBACK + 60) - 1
        o = m15_rates["open"].astype(float)[tail:-1]
        h = m15_rates["high"].astype(float)[tail:-1]
        l = m15_rates["low"].astype(float)[tail:-1]
        c = m15_rates["close"].astype(float)[tail:-1]
        vol = m15_rates["tick_volume"].astype(float)[tail:-1]
        if len(c) < VOL_LOOKBACK:
            return None

        win = vol[-VOL_LOOKBACK:]
        nz = win[win > 0]
        if len(nz) < VOL_LOOKBACK // 2 or vol[-1] <= 0:
            return None                      # era with no usable volume
        volpct = float((nz <= vol[-1]).mean())

        atr_arr = self.atr(h[-60:], l[-60:], c[-60:], 14)
        atr = float(atr_arr[-1])
        if not np.isfinite(atr) or atr <= 0:
            return None

        want = self.decide(o, h, l, c, vol, volpct, atr)
        if want is None:
            return None
        return Signal(
            direction=mt5.ORDER_TYPE_BUY if want else mt5.ORDER_TYPE_SELL,
            strategy_name=self.name, magic=self.magic, is_buy=bool(want))

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass


class VolBreakout(_VolCandidate):
    """Structure break WITH participation.

    A break on heavy volume is real buying or selling; a break on thin volume is
    a fakeout. This is the folk belief, tested.
    """
    code = "VOLBREAK"

    def decide(self, o, h, l, c, vol, volpct, atr):
        if volpct < HIGH_VOL:
            return None
        hi = float(h[-BREAK_BARS - 1:-1].max())
        lo = float(l[-BREAK_BARS - 1:-1].min())
        if c[-1] > hi:
            return True
        if c[-1] < lo:
            return False
        return None


class VolDivergence(_VolCandidate):
    """Structure break WITHOUT participation -- trade against it.

    A new extreme nobody showed up for is exhaustion rather than trend. The exact
    inverse of VolBreakout on the same structure, which is deliberate: if one has
    an edge the other should lose, and if both land at chance the volume regime
    carries no directional information at all.
    """
    code = "VOLDIVERG"

    def decide(self, o, h, l, c, vol, volpct, atr):
        if volpct > LOW_VOL:
            return None
        hi = float(h[-BREAK_BARS - 1:-1].max())
        lo = float(l[-BREAK_BARS - 1:-1].min())
        if c[-1] > hi:
            return False                     # unconfirmed high -> fade it
        if c[-1] < lo:
            return True
        return None


class VolSpikeRejection(_VolCandidate):
    """A volume spike that closes badly for whoever pushed it.

    Heavy volume with the close pinned at one end of the bar's range is the one
    pattern where volume and direction are jointly observable within a single
    bar: somebody committed size and immediately lost the level.
    """
    code = "VOLSPIKE"

    def decide(self, o, h, l, c, vol, volpct, atr):
        if volpct < SPIKE_VOL:
            return None
        rng = float(h[-1] - l[-1])
        if rng <= 0:
            return None
        cp = float((c[-1] - l[-1]) / rng)     # 0 = closed on the low, 1 = high
        if cp <= REJECT_FRAC:
            return False
        if cp >= 1.0 - REJECT_FRAC:
            return True
        return None


class VwapReversion(_VolCandidate):
    """Distance from the volume-weighted average price, not the simple mean.

    VWAP is the one reference price that uses volume rather than only price, so
    this is the mean-reversion family's genuinely volume-based variant. (Simple
    20-day mean reversion was tested on 2026-11-07 and returned PF 0.55-0.62.)
    """
    code = "VWAPREV"

    def decide(self, o, h, l, c, vol, volpct, atr):
        cw = c[-VWAP_BARS:]
        vw = vol[-VWAP_BARS:]
        tot = float(vw.sum())
        if tot <= 0 or len(cw) < VWAP_BARS:
            return None
        vwap = float((cw * vw).sum() / tot)
        sd = float(cw.std(ddof=1))
        if sd <= 0:
            return None
        z = (float(c[-1]) - vwap) / sd
        if z >= VWAP_Z:
            return False                      # stretched above VWAP -> short
        if z <= -VWAP_Z:
            return True
        return None


SIGNALS = [VolBreakout, VolDivergence, VolSpikeRejection, VwapReversion]

# Per DESIGN_NextSearch: average win must be >= $25 so the $0.51 round trip is
# ~2% of a winner rather than 3.94%. Two geometries only -- the 1/e trial cap
# matters more than coverage.
GEOMETRIES = [(6.0, 10.0), (8.0, 14.0)]


def candidates():
    """[(id, factory)] -- 8 of them, in a fixed, reproducible order."""
    out = []
    magic = 8100
    for cls in SIGNALS:
        for sl, tp in GEOMETRIES:
            magic += 1

            def make(cls=cls, sl=sl, tp=tp, magic=magic):
                return cls(sl_atr_mult=sl, tp_atr_mult=tp, magic=magic)

            out.append(("%s_S%g_T%g" % (cls.code, sl, tp), make))
    return out
