"""Portfolio-level risk layer for the multi-asset system.

PURE module: no MT5 import, no network, no file writes, no side effects at
import. It answers one question -- "may this order proposal be opened, given
what is already open and the state of the account?" -- and it answers it
FAIL CLOSED: a missing field, NaN, stale timestamp, unknown symbol, missing
price, or any exception inside the engine yields ``allow=False``.

Contract terms (contract size, base/quote currency, volume limits, spread
gate) are NOT duplicated here; they come from ``src.instruments.registry``.

Units
-----
* Every ``*_pct`` field in :class:`PortfolioLimits` is in PERCENT
  (``0.35`` means 0.35 %), measured against account EQUITY.
* ``*_x_equity`` fields are multiples of equity (``5.0`` = 5x).
* Stop-loss risk is in USD (account currency).
* Prices passed in ``AccountSnapshot.prices`` are the current mid/last price
  of each symbol, used for notional and for JPY -> USD conversion.

Risk math
---------
``risk_usd = distance * contract_size * lots`` when the quote currency is USD
(XAU: 100 oz, EUR/GBP: 100 000 units, BTC/ETH: 1 coin). For USDJPY the P&L is
in JPY and is converted at the current USDJPY price: ``pnl_usd = jpy / price``
(the exact conversion would use the price at the stop, so this is an
approximation of the order of distance/price, i.e. < 1 % for realistic stops).

Open positions contribute ``max(0, stop distance from ENTRY)`` -- a stop that
was trailed past entry contributes 0, never a negative number, so adding a
position can never reduce computed open risk.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from src.instruments.registry import (
    InstrumentMeta,
    UnknownInstrumentError,
    get_meta,
    value_per_price_per_lot,
)

ACCOUNT_CCY = "USD"
GROUP_NAMES = ("usd_short", "risk_on")
_EPS = 1e-9
_FUTURE_SKEW_SECONDS = 5.0     # tolerated clock skew before a timestamp counts as invalid


class RiskInputError(ValueError):
    """Bad/missing input. ``code`` becomes the prefix of the deny reason."""

    def __init__(self, code: str, msg: str):
        super().__init__(f"{code}: {msg}")
        self.code = code


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Position:
    symbol: str
    side: str                       # 'BUY' | 'SELL'
    lots: float
    entry: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    strategy: str = ""


@dataclass
class AccountSnapshot:
    equity: float
    balance: float
    free_margin: float
    margin_used: float
    timestamp_utc: Optional[datetime]
    price_ts: Dict[str, datetime] = field(default_factory=dict)   # symbol -> time of last price
    prices: Dict[str, float] = field(default_factory=dict)        # symbol -> current price
    spread_points: Dict[str, float] = field(default_factory=dict) # symbol -> current spread (points)


@dataclass
class OrderProposal:
    symbol: str
    side: str
    lots: float
    entry: float
    sl: Optional[float] = None
    strategy: str = ""


@dataclass
class PortfolioLimits:
    # --- risk budget (percent of equity) -------------------------------
    max_risk_per_trade_pct: float = 0.35
    max_open_risk_pct: float = 1.0            # open positions + proposal
    max_risk_per_instrument_pct: float = 0.5
    max_group_risk_pct: float = 0.7           # each correlated group
    # --- structure ------------------------------------------------------
    max_positions: int = 4
    # --- exposure (multiples of equity) --------------------------------
    max_net_usd_exposure_x_equity: float = 5.0
    max_gross_notional_x_equity: float = 10.0
    # --- margin ---------------------------------------------------------
    max_margin_utilisation_pct: float = 50.0
    leverage: Dict[str, float] = field(default_factory=lambda: {
        # XAUUSDm 200 verified on the broker (engine.py); the rest are ASSUMPTIONS.
        "XAUUSDm": 200.0, "EURUSDm": 200.0, "GBPUSDm": 200.0, "USDJPYm": 200.0,
        "BTCUSDm": 100.0, "ETHUSDm": 100.0,
    })
    # --- data freshness --------------------------------------------------
    stale_price_seconds: float = 120.0
    stale_account_seconds: float = 60.0
    # --- spread -----------------------------------------------------------
    # Override per symbol; otherwise the registry's spread_gate_points is used.
    # No override and no registry gate (e.g. ETHUSDm) => proposal is denied.
    max_spread_points: Dict[str, float] = field(default_factory=dict)
    # --- firm limits (pass-through, percent) and kill-switch fractions ---
    daily_loss_pct: float = 5.0               # firm daily-loss limit
    trailing_dd_pct: float = 10.0             # firm trailing-drawdown limit
    soft_fraction: float = 0.60               # SOFT_STOP at 60 % of a firm limit
    hard_fraction: float = 0.80               # HARD_FLATTEN at 80 % of a firm limit

    def validate(self) -> None:
        pos = ("max_risk_per_trade_pct", "max_open_risk_pct", "max_risk_per_instrument_pct",
               "max_group_risk_pct", "max_net_usd_exposure_x_equity",
               "max_gross_notional_x_equity", "max_margin_utilisation_pct",
               "stale_price_seconds", "stale_account_seconds", "daily_loss_pct",
               "trailing_dd_pct", "soft_fraction", "hard_fraction")
        for name in pos:
            v = getattr(self, name)
            if not _finite(v) or v <= 0:
                raise RiskInputError("INVALID_LIMITS", f"{name}={v!r} must be finite and > 0")
        if not isinstance(self.max_positions, int) or isinstance(self.max_positions, bool) \
                or self.max_positions < 1:
            raise RiskInputError("INVALID_LIMITS", f"max_positions={self.max_positions!r}")
        if self.soft_fraction > self.hard_fraction:
            raise RiskInputError("INVALID_LIMITS", "soft_fraction must be <= hard_fraction")


@dataclass
class Decision:
    allow: bool
    reasons: List[str] = field(default_factory=list)
    computed: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _norm_side(side: Any) -> str:
    s = side.strip().upper() if isinstance(side, str) else None
    if s not in ("BUY", "SELL"):
        raise RiskInputError("INVALID_SIDE", f"side={side!r} must be 'BUY' or 'SELL'")
    return s


def _meta(symbol: Any) -> InstrumentMeta:
    try:
        return get_meta(symbol)
    except UnknownInstrumentError as exc:
        raise RiskInputError("UNKNOWN_SYMBOL", str(symbol)) from exc


def _price(prices: Dict[str, float], symbol: str) -> float:
    p = prices.get(symbol) if isinstance(prices, dict) else None
    if not _finite(p) or p <= 0:
        raise RiskInputError("NO_PRICE", f"{symbol}: price missing or invalid ({p!r})")
    return float(p)


def _lots(lots: Any, symbol: str) -> float:
    if not _finite(lots) or lots <= 0:
        raise RiskInputError("INVALID_LOTS", f"{symbol}: lots={lots!r} must be finite and > 0")
    return float(lots)


def groups_for(meta: InstrumentMeta, side: str) -> List[str]:
    """Correlated risk groups a (symbol, side) belongs to.

    usd_short: long X/USD (EUR, GBP, XAU, BTC, ETH) or short USD/X (USDJPY).
    risk_on:   long gold or crypto.
    """
    side = _norm_side(side)
    out: List[str] = []
    if (side == "BUY" and meta.quote_currency == ACCOUNT_CCY) or \
            (side == "SELL" and meta.base_currency == ACCOUNT_CCY):
        out.append("usd_short")
    if side == "BUY" and meta.asset_class in ("gold", "crypto"):
        out.append("risk_on")
    return out


def sl_risk_usd(symbol: str, side: str, entry: float, sl: Optional[float], lots: float,
                price: float, *, strict: bool = True) -> float:
    """Stop-loss risk in USD.

    strict=True (order proposals): missing SL or SL on the wrong side of entry
    raises RiskInputError. strict=False (already-open positions): a missing SL
    still raises, but an SL on the profit side of entry (trailed) yields 0.
    """
    meta = _meta(symbol)
    side = _norm_side(side)
    lots = _lots(lots, symbol)
    if not _finite(entry) or entry <= 0:
        raise RiskInputError("INVALID_ENTRY", f"{symbol}: entry={entry!r}")
    if sl is None or not _finite(sl) or sl <= 0:
        raise RiskInputError("SL_MISSING", f"{symbol}: stop-loss missing or invalid ({sl!r})")
    dist = (entry - sl) if side == "BUY" else (sl - entry)
    if dist <= 0:
        if strict:
            raise RiskInputError(
                "SL_WRONG_SIDE",
                f"{symbol} {side}: sl={sl} is not on the loss side of entry={entry}")
        dist = 0.0
    try:
        vpp = value_per_price_per_lot(meta, price, ACCOUNT_CCY)
    except ValueError as exc:
        raise RiskInputError("NO_CONVERSION", str(exc)) from exc
    return dist * vpp * lots


def notional_usd(meta: InstrumentMeta, lots: float, price: float) -> float:
    """USD notional of one position (unsigned)."""
    if meta.quote_currency == ACCOUNT_CCY:
        return lots * meta.contract_size * price
    if meta.base_currency == ACCOUNT_CCY:
        return lots * meta.contract_size
    raise RiskInputError("NO_CONVERSION", f"{meta.symbol}: cross-currency not supported")


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------


def kill_switch_state(account: AccountSnapshot, peak_equity: float,
                      day_start_equity: float, limits: Optional[PortfolioLimits] = None) -> str:
    """'OK' | 'SOFT_STOP' | 'HARD_FLATTEN'.

    Trailing drawdown = (peak - equity) / peak; daily loss = (day_start - equity)
    / day_start (both in percent). A threshold is INCLUSIVE: reaching exactly
    soft_fraction x firm limit is SOFT_STOP, hard_fraction x limit is
    HARD_FLATTEN. HARD overrides SOFT; either metric can trigger.

    Invalid input (NaN/None/non-positive equity or reference) cannot be judged;
    it returns 'SOFT_STOP' (stop new entries, but do not blindly flatten on a
    data glitch).
    """
    try:
        lim = limits or PortfolioLimits()
        lim.validate()
        eq = account.equity
        if not (_finite(eq) and _finite(peak_equity) and _finite(day_start_equity)):
            return "SOFT_STOP"
        if eq <= 0 or peak_equity <= 0 or day_start_equity <= 0:
            return "SOFT_STOP"
        peak = max(peak_equity, eq)
        dd = (peak - eq) / peak * 100.0
        dl = (day_start_equity - eq) / day_start_equity * 100.0
        hard = (lim.trailing_dd_pct * lim.hard_fraction, lim.daily_loss_pct * lim.hard_fraction)
        soft = (lim.trailing_dd_pct * lim.soft_fraction, lim.daily_loss_pct * lim.soft_fraction)
        if dd >= hard[0] - _EPS or dl >= hard[1] - _EPS:
            return "HARD_FLATTEN"
        if dd >= soft[0] - _EPS or dl >= soft[1] - _EPS:
            return "SOFT_STOP"
        return "OK"
    except Exception:  # noqa: BLE001 - fail closed
        return "SOFT_STOP"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PortfolioRiskEngine:
    """Stateless portfolio risk gate. All methods are pure."""

    # -- aggregation -------------------------------------------------------

    def position_risk_usd(self, pos: Position, prices: Dict[str, float]) -> float:
        """Stop-loss risk of an OPEN position (>= 0; trailed-past-entry => 0)."""
        return sl_risk_usd(pos.symbol, pos.side, pos.entry, pos.sl, pos.lots,
                           _price(prices, pos.symbol), strict=False)

    def open_risk_usd(self, positions: Iterable[Position], prices: Dict[str, float]) -> float:
        """Sum of stop-loss risk of open positions. Monotone: adding a position
        never decreases it (each term is >= 0)."""
        return float(sum(self.position_risk_usd(p, prices) for p in positions))

    def exposure_report(self, positions: Iterable[Position],
                        prices: Dict[str, float]) -> Dict[str, Any]:
        """Aggregate exposure. Raises RiskInputError on unknown symbol/missing price.

        Each position becomes two signed USD-notional legs: long = +base, -quote;
        short = -base, +quote. Returns:
          per_currency_net_usd : {ccy: signed USD notional}
          net_usd_exposure     : signed net USD leg (= per_currency_net_usd['USD'])
          gross_notional       : sum of per-position USD notionals
          groups               : {group: {'notional_usd','risk_usd','positions'}}
          per_position         : list of dicts
        Group ``risk_usd`` uses stop-loss risk when the position has a valid SL
        (positions lacking one contribute 0 here; open-risk checks reject them).
        """
        per_ccy: Dict[str, float] = {}
        groups = {g: {"notional_usd": 0.0, "risk_usd": 0.0, "positions": 0} for g in GROUP_NAMES}
        rows: List[Dict[str, Any]] = []
        gross = 0.0
        for p in positions:
            meta = _meta(p.symbol)
            side = _norm_side(p.side)
            lots = _lots(p.lots, p.symbol)
            price = _price(prices, p.symbol)
            n = notional_usd(meta, lots, price)
            sgn = 1.0 if side == "BUY" else -1.0
            per_ccy[meta.base_currency] = per_ccy.get(meta.base_currency, 0.0) + sgn * n
            per_ccy[meta.quote_currency] = per_ccy.get(meta.quote_currency, 0.0) - sgn * n
            gross += n
            try:
                risk = sl_risk_usd(p.symbol, side, p.entry, p.sl, lots, price, strict=False)
            except RiskInputError:
                risk = 0.0
            gs = groups_for(meta, side)
            for g in gs:
                groups[g]["notional_usd"] += n
                groups[g]["risk_usd"] += risk
                groups[g]["positions"] += 1
            rows.append({"symbol": p.symbol, "side": side, "lots": lots, "price": price,
                         "notional_usd": n, "risk_usd": risk, "groups": gs})
        return {
            "per_currency_net_usd": per_ccy,
            "net_usd_exposure": per_ccy.get(ACCOUNT_CCY, 0.0),
            "gross_notional": gross,
            "groups": groups,
            "per_position": rows,
        }

    # -- the gate ----------------------------------------------------------

    def check(self, proposal: OrderProposal, positions: List[Position],
              account: AccountSnapshot, now: datetime,
              limits: Optional[PortfolioLimits] = None, *,
              peak_equity: Optional[float] = None,
              day_start_equity: Optional[float] = None) -> Decision:
        """Run EVERY check, return all failing reasons. allow iff none failed.

        If both ``peak_equity`` and ``day_start_equity`` are given, the kill
        switch is also evaluated and any state other than 'OK' denies entry.
        Any exception (in a check or around it) denies.
        """
        reasons: List[str] = []
        computed: Dict[str, Any] = {}
        try:
            return self._check(proposal, positions, account, now, limits,
                               peak_equity, day_start_equity, reasons, computed)
        except Exception as exc:  # noqa: BLE001 - fail closed
            reasons.append(f"ENGINE_ERROR: {type(exc).__name__}: {exc}")
            return Decision(False, reasons, computed)

    def _check(self, proposal, positions, account, now, limits, peak_equity, day_start_equity,
               reasons: List[str], computed: Dict[str, Any]) -> Decision:
        lim = limits if limits is not None else PortfolioLimits()
        st: Dict[str, Any] = {}
        completed: List[str] = []

        def run(name: str, fn: Callable[[], None]) -> None:
            try:
                fn()
            except RiskInputError as exc:
                reasons.append(str(exc))
            except Exception as exc:  # noqa: BLE001 - fail closed per check
                reasons.append(f"CHECK_ERROR[{name}]: {type(exc).__name__}: {exc}")
            completed.append(name)

        # ---- 1. limits + account + clock sanity ------------------------
        def c_inputs():
            lim.validate()
            if not isinstance(now, datetime) or now.tzinfo is None:
                raise RiskInputError("INVALID_INPUT", "now must be a timezone-aware datetime")
            if not isinstance(account, AccountSnapshot):
                raise RiskInputError("INVALID_INPUT", "account snapshot missing")
            bad = [n for n in ("equity", "balance", "free_margin", "margin_used")
                   if not _finite(getattr(account, n, None))]
            if bad:
                raise RiskInputError("INVALID_ACCOUNT",
                                     f"missing/NaN fields: {bad}")
            if account.equity <= 0:
                raise RiskInputError("INVALID_ACCOUNT", f"equity={account.equity} <= 0")
            if account.margin_used < 0:
                raise RiskInputError("INVALID_ACCOUNT", f"margin_used={account.margin_used} < 0")
            if not isinstance(positions, (list, tuple)):
                raise RiskInputError("INVALID_INPUT", "positions must be a list")
            st["inputs_ok"] = True
            computed["equity"] = account.equity

        run("inputs", c_inputs)
        ok_inputs = st.get("inputs_ok", False)

        def age_seconds(ts: Any, what: str) -> float:
            if not isinstance(ts, datetime) or ts.tzinfo is None:
                raise RiskInputError("INVALID_INPUT", f"{what}: timestamp missing or naive")
            return (now - ts.astimezone(timezone.utc)).total_seconds()

        # ---- 2. account freshness --------------------------------------
        def c_account_fresh():
            if not ok_inputs:
                return
            age = age_seconds(account.timestamp_utc, "account")
            computed["account_age_s"] = age
            if age < -_FUTURE_SKEW_SECONDS:
                raise RiskInputError("STALE_ACCOUNT", f"snapshot is {-age:.1f}s in the future")
            if age > lim.stale_account_seconds:
                raise RiskInputError(
                    "STALE_ACCOUNT", f"snapshot age {age:.1f}s > {lim.stale_account_seconds}s")

        run("account_fresh", c_account_fresh)

        # ---- 3. proposal basics (symbol/side/lots/volume/price/SL) ------
        def c_proposal():
            meta = _meta(proposal.symbol)
            side = _norm_side(proposal.side)
            lots = _lots(proposal.lots, proposal.symbol)
            st["meta"], st["side"], st["lots"] = meta, side, lots
            problems = []
            if lots < meta.volume_min - _EPS:
                problems.append(f"lots {lots} < volume_min {meta.volume_min}")
            if lots > meta.volume_max + _EPS:
                problems.append(f"lots {lots} > volume_max {meta.volume_max}")
            steps = lots / meta.volume_step
            if abs(steps - round(steps)) > 1e-6:
                problems.append(f"lots {lots} not a multiple of volume_step {meta.volume_step}")
            if problems:
                raise RiskInputError("INVALID_LOTS", f"{proposal.symbol}: " + "; ".join(problems))

        run("proposal", c_proposal)

        # price freshness is per symbol so every stale symbol is reported
        def c_price_fresh_all():
            if not ok_inputs:
                return
            symbols = {p.symbol for p in positions if isinstance(p.symbol, str)}
            if isinstance(proposal.symbol, str):
                symbols.add(proposal.symbol)
            for sym in sorted(symbols):
                try:
                    _price(account.prices, sym)
                    ts = account.price_ts.get(sym) if isinstance(account.price_ts, dict) else None
                    if ts is None:
                        raise RiskInputError("STALE_PRICE", f"{sym}: no price timestamp")
                    age = age_seconds(ts, f"price {sym}")
                    computed.setdefault("price_age_s", {})[sym] = age
                    if age < -_FUTURE_SKEW_SECONDS:
                        raise RiskInputError("STALE_PRICE",
                                             f"{sym}: timestamp {-age:.1f}s in future")
                    if age > lim.stale_price_seconds:
                        raise RiskInputError(
                            "STALE_PRICE", f"{sym}: age {age:.1f}s > {lim.stale_price_seconds}s")
                except RiskInputError as exc:
                    reasons.append(str(exc))

        run("price_fresh", c_price_fresh_all)

        # ---- 4. proposal stop-loss risk ---------------------------------
        def c_sl():
            if "meta" not in st:
                return
            price = _price(account.prices, proposal.symbol)
            st["price"] = price
            risk = sl_risk_usd(proposal.symbol, st["side"], proposal.entry, proposal.sl,
                               st["lots"], price, strict=True)
            st["prop_risk"] = risk
            computed["proposal_risk_usd"] = risk
            computed["proposal_risk_pct"] = risk / account.equity * 100.0

        if ok_inputs:
            run("proposal_sl", c_sl)
        else:
            completed.append("proposal_sl")

        # ---- 5. existing positions' risk ------------------------------------
        def c_positions():
            if not ok_inputs:
                return
            risks: List[float] = []
            bad = False
            for i, p in enumerate(positions):
                try:
                    if not isinstance(p, Position):
                        raise RiskInputError("INVALID_POSITION", f"#{i} is not a Position")
                    risks.append(sl_risk_usd(p.symbol, p.side, p.entry, p.sl, p.lots,
                                             _price(account.prices, p.symbol), strict=False))
                except RiskInputError as exc:
                    bad = True
                    reasons.append(f"INVALID_POSITION[{i}] {exc}")
            if not bad:
                st["pos_risks"] = risks
                st["open_risk"] = float(sum(risks))
                computed["open_risk_usd_existing"] = st["open_risk"]

        run("positions", c_positions)

        # ---- 6. per-trade cap ---------------------------------------------
        def c_per_trade():
            if "prop_risk" not in st:
                return
            pct = st["prop_risk"] / account.equity * 100.0
            computed["risk_per_trade_pct"] = pct
            if pct > lim.max_risk_per_trade_pct + _EPS:
                raise RiskInputError(
                    "RISK_PER_TRADE",
                    f"{pct:.4f}% > {lim.max_risk_per_trade_pct}% of equity")

        run("per_trade", c_per_trade)

        # ---- 7. total open risk -------------------------------------------
        def c_open_risk():
            if "prop_risk" not in st or "open_risk" not in st:
                return
            total = st["open_risk"] + st["prop_risk"]
            pct = total / account.equity * 100.0
            computed["open_risk_usd_total"] = total
            computed["open_risk_pct_total"] = pct
            if pct > lim.max_open_risk_pct + _EPS:
                raise RiskInputError(
                    "OPEN_RISK", f"{pct:.4f}% > {lim.max_open_risk_pct}% of equity "
                                 f"(existing {st['open_risk']:.2f} + new {st['prop_risk']:.2f} USD)")

        run("open_risk", c_open_risk)

        # ---- 8. position count --------------------------------------------
        def c_count():
            if not ok_inputs:
                return
            n = len(positions) + 1
            computed["positions_after"] = n
            if n > lim.max_positions:
                raise RiskInputError("MAX_POSITIONS", f"{n} > {lim.max_positions}")

        run("count", c_count)

        # ---- 9. per-instrument risk -----------------------------------------
        def c_instrument():
            if "prop_risk" not in st or "pos_risks" not in st:
                return
            same = sum(r for p, r in zip(positions, st["pos_risks"]) if p.symbol == proposal.symbol)
            total = same + st["prop_risk"]
            pct = total / account.equity * 100.0
            computed["instrument_risk_pct"] = pct
            if pct > lim.max_risk_per_instrument_pct + _EPS:
                raise RiskInputError(
                    "INSTRUMENT_RISK",
                    f"{proposal.symbol}: {pct:.4f}% > {lim.max_risk_per_instrument_pct}%")

        run("instrument", c_instrument)

        # ---- 10. correlated groups --------------------------------------------
        def c_groups():
            if "prop_risk" not in st or "pos_risks" not in st:
                return
            member = groups_for(st["meta"], st["side"])
            gr: Dict[str, float] = {}
            for g in GROUP_NAMES:
                existing = 0.0
                for p, r in zip(positions, st["pos_risks"]):
                    if g in groups_for(_meta(p.symbol), _norm_side(p.side)):
                        existing += r
                gr[g] = existing + (st["prop_risk"] if g in member else 0.0)
            computed["group_risk_pct"] = {g: v / account.equity * 100.0 for g, v in gr.items()}
            computed["proposal_groups"] = member
            fails = []
            for g in member:
                pct = gr[g] / account.equity * 100.0
                if pct > lim.max_group_risk_pct + _EPS:
                    fails.append(f"{g}: {pct:.4f}% > {lim.max_group_risk_pct}%")
            if fails:
                raise RiskInputError("GROUP_RISK", "; ".join(fails))

        run("groups", c_groups)

        # ---- 11. exposure (net USD, gross) ------------------------------------
        def c_exposure():
            if "meta" not in st or not ok_inputs:
                return
            prop_pos = Position(proposal.symbol, st["side"], st["lots"], proposal.entry,
                                proposal.sl, None, proposal.strategy)
            rep = self.exposure_report(list(positions) + [prop_pos], account.prices)
            eq = account.equity
            net_x = rep["net_usd_exposure"] / eq
            gross_x = rep["gross_notional"] / eq
            computed["net_usd_exposure"] = rep["net_usd_exposure"]
            computed["net_usd_exposure_x_equity"] = net_x
            computed["gross_notional"] = rep["gross_notional"]
            computed["gross_notional_x_equity"] = gross_x
            computed["per_currency_net_usd"] = rep["per_currency_net_usd"]
            fails = []
            if abs(net_x) > lim.max_net_usd_exposure_x_equity + _EPS:
                fails.append(f"NET_USD_EXPOSURE: |{net_x:.3f}|x > "
                             f"{lim.max_net_usd_exposure_x_equity}x equity")
            if gross_x > lim.max_gross_notional_x_equity + _EPS:
                fails.append(f"GROSS_NOTIONAL: {gross_x:.3f}x > "
                             f"{lim.max_gross_notional_x_equity}x equity")
            reasons.extend(fails)

        run("exposure", c_exposure)

        # ---- 12. margin ----------------------------------------------------------
        def c_margin():
            if "meta" not in st or "price" not in st or not ok_inputs:
                return
            lev = lim.leverage.get(proposal.symbol) if isinstance(lim.leverage, dict) else None
            if not _finite(lev) or lev <= 0:
                raise RiskInputError("MARGIN", f"{proposal.symbol}: leverage unknown")
            need = notional_usd(st["meta"], st["lots"], st["price"]) / lev
            after = account.margin_used + need
            util = after / account.equity * 100.0
            computed["margin_required"] = need
            computed["margin_utilisation_pct"] = util
            fails = []
            if util > lim.max_margin_utilisation_pct + _EPS:
                fails.append(f"{util:.2f}% > {lim.max_margin_utilisation_pct}% of equity")
            if need > account.free_margin + _EPS:
                fails.append(f"required {need:.2f} > free_margin {account.free_margin:.2f}")
            if fails:
                raise RiskInputError("MARGIN", "; ".join(fails))

        run("margin", c_margin)

        # ---- 13. spread --------------------------------------------------------------
        def c_spread():
            if "meta" not in st:
                return
            cap = lim.max_spread_points.get(proposal.symbol) \
                if isinstance(lim.max_spread_points, dict) else None
            if cap is None:
                cap = st["meta"].spread_gate_points
            if not _finite(cap) or cap <= 0:
                raise RiskInputError("SPREAD", f"{proposal.symbol}: no spread limit configured")
            sp = account.spread_points.get(proposal.symbol) \
                if isinstance(account.spread_points, dict) else None
            if not _finite(sp) or sp < 0:
                raise RiskInputError("SPREAD", f"{proposal.symbol}: current spread unknown")
            computed["spread_points"] = sp
            computed["spread_cap_points"] = cap
            if sp > cap + _EPS:
                raise RiskInputError("SPREAD", f"{proposal.symbol}: {sp} > {cap} points")

        run("spread", c_spread)

        # ---- 14. kill switch (optional) ------------------------------------------
        def c_kill():
            if peak_equity is None and day_start_equity is None:
                return
            state = kill_switch_state(account, peak_equity, day_start_equity, lim)  # type: ignore[arg-type]
            computed["kill_switch"] = state
            if state != "OK":
                raise RiskInputError("KILL_SWITCH", state)

        run("kill_switch", c_kill)

        expected = ["inputs", "account_fresh", "proposal", "price_fresh", "proposal_sl",
                    "positions", "per_trade", "open_risk", "count", "instrument", "groups",
                    "exposure", "margin", "spread", "kill_switch"]
        if completed != expected:
            reasons.append("INCOMPLETE_CHECKS: " +
                           ",".join(sorted(set(expected) - set(completed))))
        return Decision(allow=not reasons, reasons=reasons, computed=computed)
