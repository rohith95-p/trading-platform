"""Transaction cost and fill modelling.

Prior backtests in this project applied no spread, no slippage and no
commission. On XAUUSDm the measured spread runs ~260 points ($0.26) against a
typical 1.5xATR stop of ~$16, so a round trip consumes roughly 1.6% of risk --
and against the live trailing stop, which banks about +0.4xATR ($4.2), it eats
closer to 6% of the average winner. That is not a rounding error.

MT5 bars carry a per-bar `spread` field in points, so historical spread is
observed rather than assumed. Slippage is not observable from bars and is
modelled explicitly with a stated assumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class CostModel:
    """Converts mid/bar prices into executable bid and ask.

    Attributes:
        spread_source: "bar" uses each bar's recorded spread field; "fixed" uses
            `fixed_spread_points` throughout. "bar" is the default because it is
            the only one grounded in observation.
        fixed_spread_points: Spread used when `spread_source == "fixed"`, and the
            fallback when a bar reports a nonsensical zero spread.
        spread_multiplier: Stress-test knob. 1.0 is the observed market; 2.0 asks
            what happens if every spread doubles.
        slippage_points: Adverse price movement applied to every market order and
            every stop-out, in points. Stop orders slip; limit orders do not.
        commission_per_lot_roundtrip: Account currency charged per 1.0 lot for a
            full round trip. Exness Standard is spread-only, so this defaults to
            zero, but it is here so a commission account can be modelled.
        swap_long_points / swap_short_points: Overnight financing in points per
            1.0 lot per night, signed as the broker reports it (negative = the
            account pays). Verified live on XAUUSDm 2026-09-01: long -515.5,
            short 0.0, swap_mode 1. That asymmetry is real money -- at 0.01 lot a
            long pays ~$0.52 a night while a short pays nothing -- and no prior
            backtest in this repo modelled it at all.
        enable_swap: Off switch, so the size of the swap assumption can itself be
            measured by running the same config with and without it.
        rollover_hour_utc: Server rollover instant. The Exness server runs
            UTC+0.00 (verified), so nights are counted across 00:00 UTC.
        triple_swap_weekday: Weekday (Mon=0) on which brokers book three nights
            to cover the weekend. None disables it; it is off by default because
            it was not verified on this account.
    """

    spread_source: str = "bar"
    fixed_spread_points: float = 260.0
    spread_multiplier: float = 1.0
    slippage_points: float = 0.0
    commission_per_lot_roundtrip: float = 0.0

    # -- overnight financing --------------------------------------------
    swap_long_points: float = -515.5
    swap_short_points: float = 0.0
    enable_swap: bool = True
    rollover_hour_utc: float = 0.0
    triple_swap_weekday: Optional[int] = None

    def spread_price(self, point: float, bar_spread_points: Optional[float]) -> float:
        """Spread for one bar, in price units."""
        if self.spread_source == "bar" and bar_spread_points:
            pts = float(bar_spread_points)
        else:
            pts = self.fixed_spread_points
        return pts * point * self.spread_multiplier

    def ask(self, mid: float, point: float, bar_spread_points: Optional[float]) -> float:
        """Bars are bid-based on MT5, so ask = bid + spread."""
        return mid + self.spread_price(point, bar_spread_points)

    def bid(self, mid: float, point: float, bar_spread_points: Optional[float]) -> float:
        return mid

    def slip(self, point: float) -> float:
        return self.slippage_points * point

    def commission(self, lots: float) -> float:
        return self.commission_per_lot_roundtrip * lots

    # -- overnight financing ------------------------------------------------

    def nights_held(self, entry_ts: int, exit_ts: int) -> int:
        """Number of broker rollovers crossed between two epoch seconds.

        A position opened at 23:00 and closed at 01:00 crosses one rollover and
        is charged one night; one opened and closed inside the same server day
        is charged nothing, which is what the broker actually does.
        """
        if exit_ts <= entry_ts:
            return 0
        off = self.rollover_hour_utc * 3600.0
        return int((exit_ts - off) // 86400 - (entry_ts - off) // 86400)

    def _swap_units(self, entry_ts: int, exit_ts: int) -> float:
        """Nights charged, including the triple-swap day if one is configured."""
        n = self.nights_held(entry_ts, exit_ts)
        if n <= 0 or self.triple_swap_weekday is None:
            return float(n)
        off = self.rollover_hour_utc * 3600.0
        first_day = int((entry_ts - off) // 86400) + 1
        extra = 0
        for d in range(first_day, first_day + n):
            # epoch day 0 (1970-01-01) was a Thursday -> weekday = (d + 3) % 7
            if (d + 3) % 7 == self.triple_swap_weekday:
                extra += 2
        return float(n + extra)

    def swap(self, lots: float, is_buy: bool, entry_ts: int, exit_ts: int,
             point: float, value_per_price_unit_per_lot: float) -> float:
        """Account-currency swap for one position. Negative means the account pays.

        Points are converted the same way P&L is: points -> price units -> account
        currency. At 0.01 lot on XAUUSDm this yields -515.5 * 0.001 * 100 * 0.01
        = -$0.5155 per night for a long, and exactly zero for a short.
        """
        if not self.enable_swap:
            return 0.0
        units = self._swap_units(entry_ts, exit_ts)
        if units <= 0:
            return 0.0
        pts = self.swap_long_points if is_buy else self.swap_short_points
        return pts * point * value_per_price_unit_per_lot * lots * units


# ---------------------------------------------------------------------------
# Named scenarios used by the sensitivity sweeps
# ---------------------------------------------------------------------------

SCENARIOS = {
    # What the broker actually charged, per bar.
    "observed": CostModel(spread_source="bar", slippage_points=0.0),
    # Observed spread plus a modest, always-adverse slip on market and stop fills.
    # NOTE: Exness Standard is spread-only (zero commission), but ECN accounts
    # typically charge $3.50-7.00 per roundtrip. Use "realistic_ecn" for that.
    "realistic": CostModel(spread_source="bar", slippage_points=20.0),
    # Realistic costs for ECN accounts (commission + spread + slippage)
    "realistic_ecn": CostModel(
        spread_source="bar", 
        slippage_points=20.0,
        commission_per_lot_roundtrip=3.50  # $3.50 per 1.0 lot roundtrip
    ),
    # Stress: spreads double and slippage triples. Roughly a news print.
    "stressed": CostModel(spread_source="bar", spread_multiplier=2.0, slippage_points=60.0),
    # The assumption every previous backtest in this repo made, kept only so the
    # size of that assumption can be measured.
    "frictionless": CostModel(spread_source="fixed", fixed_spread_points=0.0,
                              enable_swap=False),
    # Observed spread with swap switched off, so the cost of the swap assumption
    # can be isolated against "observed" rather than argued about.
    "observed_no_swap": CostModel(spread_source="bar", slippage_points=0.0,
                                  enable_swap=False),
}


def spread_stats(rates: np.ndarray, point: float) -> dict:
    """Descriptive spread stats for a manifest or report."""
    s = rates["spread"].astype(float)
    return {
        "mean_points": float(s.mean()),
        "p50_points": float(np.percentile(s, 50)),
        "p90_points": float(np.percentile(s, 90)),
        "p99_points": float(np.percentile(s, 99)),
        "max_points": float(s.max()),
        "mean_price": float(s.mean() * point),
        "p99_price": float(np.percentile(s, 99) * point),
    }
