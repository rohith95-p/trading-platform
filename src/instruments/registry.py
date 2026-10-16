"""Explicit instrument registry for the backtesting stack.

Why this exists
---------------
`CostModel` and `EngineConfig` grew up around one symbol (Exness `XAUUSDm`), and
their defaults (swap -515.5 points, 260-point fixed spread, margin =
contract*price*lots/leverage, Mon-Fri trading window) are gold facts. Applied to
EURUSD, USDJPY or BTC they are silently wrong. This module holds the contract
terms for every symbol the stack is allowed to simulate, one explicit entry
each, and refuses to guess for anything else.

Provenance
----------
Numeric values were read from MT5 `symbol_info` on the Exness demo account on
2026-10-16 (the `source` / `retrieved` fields). Anything that was NOT read from
the terminal is listed in `InstrumentMeta.unverified` so it is visible, never
implicit. `swap_long/short` are broker values in POINTS per 1.0 lot per night
and their *units* depend on `symbol_info.swap_mode` (1 = points on Exness
metals/FX; crypto may be in a different mode). `swap_mode` per symbol is still
to be confirmed -- every entry lists "swap_units" in `unverified` for that reason.

Nothing here talks to a terminal; it is plain data so tests need no MT5.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from src.backtesting.costs import CostModel

log = logging.getLogger(__name__)

_SOURCE = "MT5 symbol_info, Exness demo"
_RETRIEVED = "2026-10-16"
_SWAP_UNITS = ("points per 1.0 lot per night, signed (negative = account pays); "
               "unit is a broker value, confirm per symbol via symbol_info.swap_mode")


class UnknownInstrumentError(ValueError):
    """Raised for any symbol that has no registry entry. Never falls back."""


@dataclass(frozen=True)
class InstrumentMeta:
    symbol: str
    asset_class: str                 # "gold" | "forex" | "crypto"
    base_currency: str
    quote_currency: str
    digits: int
    contract_size: float
    volume_min: float
    volume_step: float
    volume_max: float
    swap_long_points: Optional[float]        # None = not yet read from the broker
    swap_short_points: Optional[float]       # None = not yet read from the broker
    typical_spread_points: Optional[float]   # None = not yet read from the broker
    session: str
    weekend_trading: bool
    swap_units: str = _SWAP_UNITS
    commission_per_lot_roundtrip: float = 0.0        # Exness Standard is spread-only
    ecn_commission_per_lot_roundtrip: float = 3.50   # used by the realistic_ecn scenario
    spread_gate_points: Optional[float] = None       # entry gate; None = leave engine default
    source: str = _SOURCE
    retrieved: str = _RETRIEVED
    unverified: Tuple[str, ...] = ()                 # field names NOT confirmed from the broker

    @property
    def point(self) -> float:
        return 10.0 ** (-self.digits)

    @property
    def tick_size(self) -> float:
        # Exness tick_size == point on every symbol in this registry.
        return self.point

    def is_verified(self, field_name: str) -> bool:
        return field_name not in self.unverified


# ---------------------------------------------------------------------------
# Entries. Values are the 2026-10-16 broker readings.
# ---------------------------------------------------------------------------

_FX_SESSION = "Sun 22:00 UTC to Fri 22:00 UTC; closed over the weekend (gap risk)"
_CRYPTO_SESSION = "24/7 including weekends (brief broker maintenance possible)"

_ENTRIES = (
    InstrumentMeta(
        symbol="XAUUSDm", asset_class="gold", base_currency="XAU", quote_currency="USD",
        digits=3, contract_size=100.0, volume_min=0.01, volume_step=0.01, volume_max=200.0,
        swap_long_points=-500.0, swap_short_points=0.0, typical_spread_points=240.0,
        session="Mon-Fri ~23h/day, daily break near 00:00 UTC; closed Sat/Sun (gap risk)",
        weekend_trading=False, spread_gate_points=350.0,
        unverified=("swap_units",),
    ),
    InstrumentMeta(
        symbol="EURUSDm", asset_class="forex", base_currency="EUR", quote_currency="USD",
        digits=5, contract_size=100000.0, volume_min=0.01, volume_step=0.01, volume_max=200.0,
        swap_long_points=-5.5, swap_short_points=0.0, typical_spread_points=8.0,
        session=_FX_SESSION, weekend_trading=False, spread_gate_points=40.0,
        unverified=("swap_units", "spread_gate_points"),
    ),
    InstrumentMeta(
        symbol="GBPUSDm", asset_class="forex", base_currency="GBP", quote_currency="USD",
        digits=5, contract_size=100000.0, volume_min=0.01, volume_step=0.01, volume_max=200.0,
        swap_long_points=-2.0, swap_short_points=-0.7, typical_spread_points=10.0,
        session=_FX_SESSION, weekend_trading=False, spread_gate_points=50.0,
        unverified=("swap_units", "spread_gate_points", "volume_min", "volume_step",
                    "volume_max"),
    ),
    InstrumentMeta(
        symbol="USDJPYm", asset_class="forex", base_currency="USD", quote_currency="JPY",
        digits=3, contract_size=100000.0, volume_min=0.01, volume_step=0.01, volume_max=300.0,
        swap_long_points=0.0, swap_short_points=-13.9, typical_spread_points=10.0,
        session=_FX_SESSION, weekend_trading=False, spread_gate_points=50.0,
        unverified=("swap_units", "spread_gate_points", "volume_min", "volume_step"),
    ),
    InstrumentMeta(
        symbol="BTCUSDm", asset_class="crypto", base_currency="BTC", quote_currency="USD",
        digits=2, contract_size=1.0, volume_min=0.01, volume_step=0.01, volume_max=200.0,
        swap_long_points=-1910.2, swap_short_points=0.0, typical_spread_points=640.0,
        session=_CRYPTO_SESSION, weekend_trading=True, spread_gate_points=3200.0,
        unverified=("swap_units", "spread_gate_points"),
    ),
    InstrumentMeta(
        symbol="ETHUSDm", asset_class="crypto", base_currency="ETH", quote_currency="USD",
        digits=2, contract_size=1.0, volume_min=0.1, volume_step=0.01, volume_max=2000.0,
        swap_long_points=-57.1,
        swap_short_points=None,            # not read from the broker yet
        typical_spread_points=None,        # not read from the broker yet
        session=_CRYPTO_SESSION, weekend_trading=True,
        unverified=("swap_units", "swap_short_points", "typical_spread_points",
                    "spread_gate_points", "digits", "contract_size"),
    ),
)

REGISTRY: Dict[str, InstrumentMeta] = {m.symbol: m for m in _ENTRIES}


def find_meta(symbol: str) -> Optional[InstrumentMeta]:
    """Registry lookup that returns None for unknown symbols (engine-side use)."""
    return REGISTRY.get(symbol)


def get_meta(symbol: str) -> InstrumentMeta:
    """Registry lookup. Exact symbol match; unknown symbols raise, never default."""
    meta = REGISTRY.get(symbol) if isinstance(symbol, str) else None
    if meta is None:
        raise UnknownInstrumentError(
            f"Unknown instrument {symbol!r}: no registry entry. Known symbols: "
            f"{sorted(REGISTRY)}. Add an explicit InstrumentMeta in "
            f"src/instruments/registry.py (verify it with MT5 symbol_info first); "
            f"gold values are never used as a fallback."
        )
    return meta


# ---------------------------------------------------------------------------
# Cost model
# ---------------------------------------------------------------------------

# Slippage is expressed in POINTS and scaled to the instrument as a fraction of
# its typical spread. 1/12 and 1/4 reproduce the legacy gold scenarios exactly
# (240-point spread -> 20 / 60 points).
_SLIP_SPREAD_FRACTION = {
    "observed": 0.0,
    "observed_no_swap": 0.0,
    "frictionless": 0.0,
    "realistic": 1.0 / 12.0,
    "realistic_ecn": 1.0 / 12.0,
    "stressed": 0.25,
}
_SCENARIO_NAMES = tuple(_SLIP_SPREAD_FRACTION)


def cost_model_for(symbol: str, scenario: str = "realistic", *,
                   commission_per_lot_roundtrip: Optional[float] = None,
                   fixed_spread_points: Optional[float] = None,
                   unknown_swap: str = "pessimistic") -> CostModel:
    """CostModel with this instrument's swap, spread fallback and slippage.

    scenario: observed | observed_no_swap | realistic | realistic_ecn | stressed |
        frictionless (same names as `costs.SCENARIOS`).
    commission_per_lot_roundtrip: overrides the scenario/registry commission.
    fixed_spread_points: overrides the registry's typical spread (used as the
        fallback when a bar reports zero spread). Required if the registry has
        none for this symbol and the scenario needs one.
    unknown_swap: how to treat a swap side the registry has no broker value for.
        "pessimistic" mirrors the known side as a cost (-abs), "zero" uses 0,
        "error" raises.
    """
    meta = get_meta(symbol)
    if scenario not in _SCENARIO_NAMES:
        raise ValueError(f"Unknown scenario {scenario!r}; expected one of {_SCENARIO_NAMES}")
    if unknown_swap not in ("pessimistic", "zero", "error"):
        raise ValueError("unknown_swap must be 'pessimistic', 'zero' or 'error'")

    spread_pts = (fixed_spread_points if fixed_spread_points is not None
                  else meta.typical_spread_points)
    frictionless = scenario == "frictionless"
    if spread_pts is None and not frictionless:
        raise ValueError(
            f"{symbol}: typical_spread_points is not known (unverified in the registry). "
            f"Pass fixed_spread_points=... or fill it in after reading symbol_info.spread.")

    sl, ss = meta.swap_long_points, meta.swap_short_points
    if sl is None or ss is None:
        known = sl if sl is not None else ss
        if unknown_swap == "error" or known is None:
            raise ValueError(f"{symbol}: swap value(s) unknown; cannot build a swap model")
        fill = -abs(known) if unknown_swap == "pessimistic" else 0.0
        log.warning("%s: swap_%s unknown; using %.1f (%s)", symbol,
                    "short" if ss is None else "long", fill, unknown_swap)
        sl = fill if sl is None else sl
        ss = fill if ss is None else ss

    slip = 0.0 if frictionless else _SLIP_SPREAD_FRACTION[scenario] * float(spread_pts)

    if commission_per_lot_roundtrip is not None:
        comm = float(commission_per_lot_roundtrip)
    elif scenario == "realistic_ecn":
        comm = meta.ecn_commission_per_lot_roundtrip
    else:
        comm = meta.commission_per_lot_roundtrip

    return CostModel(
        spread_source="fixed" if frictionless else "bar",
        fixed_spread_points=0.0 if frictionless else float(spread_pts),
        spread_multiplier=2.0 if scenario == "stressed" else 1.0,
        slippage_points=slip,
        commission_per_lot_roundtrip=0.0 if frictionless else comm,
        swap_long_points=float(sl),
        swap_short_points=float(ss),
        enable_swap=scenario not in ("frictionless", "observed_no_swap"),
        calibrated_for=symbol,
    )


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------


def value_per_price_per_lot(meta: InstrumentMeta, price: Optional[float] = None,
                            account_currency: str = "USD") -> float:
    """Account currency per 1.0 price unit per 1.0 lot.

    * quote == account (XAUUSD, EURUSD, BTCUSD ...): exactly `contract_size`.
    * base == account (USDJPY): `contract_size / price` -- needs the price.
    * any other cross: unsupported (needs a third conversion rate).
    """
    if meta.quote_currency == account_currency:
        return meta.contract_size
    if meta.base_currency == account_currency:
        if not price or price <= 0:
            raise ValueError(f"{meta.symbol}: quote currency is {meta.quote_currency}; "
                             f"a positive price is required to convert to {account_currency}")
        return meta.contract_size / price
    raise ValueError(f"{meta.symbol}: cross-currency conversion "
                     f"{meta.quote_currency}->{account_currency} is not supported")


def risk_lots(balance: float, risk_pct: float, stop_distance_price: float,
              meta: InstrumentMeta, price: Optional[float] = None,
              account_currency: str = "USD",
              value_per_price: Optional[float] = None) -> Tuple[float, float, bool]:
    """Size a position so a stop-out loses ~`risk_pct` of `balance`.

    Args:
        risk_pct: fraction (0.005 = 0.5%).
        stop_distance_price: entry-to-stop distance in PRICE units (0.0020 for
            20 pips on EURUSD, 500.0 for a $500 stop on BTC).
        price: current price; only needed when the quote currency is not the
            account currency (USDJPY).
        value_per_price: explicit account-currency P&L per price unit per lot
            (e.g. SymbolSpec.value_per_price_unit_per_lot = tick_value /
            tick_size); overrides the contract-size derivation.

    Returns (lots, actual_risk_pct, ok). Lots round DOWN to the volume step so
    rounding never pushes risk over budget. If even the minimum lot risks more
    than the budget, the minimum lot is returned with ok=False so the caller can
    skip the trade. Non-positive inputs return (0.0, 0.0, False).
    """
    if balance <= 0 or risk_pct <= 0 or stop_distance_price <= 0:
        return 0.0, 0.0, False
    vpp = (value_per_price if value_per_price is not None
           else value_per_price_per_lot(meta, price, account_currency))
    risk_per_lot = stop_distance_price * vpp
    budget = balance * risk_pct
    raw = budget / risk_per_lot

    step = meta.volume_step
    lots = round(math.floor(raw / step + 1e-9) * step, 8)
    ok = True
    if lots < meta.volume_min:
        lots = meta.volume_min
        ok = lots * risk_per_lot <= budget * (1 + 1e-9)
    if lots > meta.volume_max:
        lots = meta.volume_max
    actual = lots * risk_per_lot / balance
    if actual > risk_pct * (1 + 1e-9):
        ok = False
    return lots, actual, ok
