"""Enforceable encoding of the Atlas Funded 'Access' account rules.

Source of truth for the numbers is ``config/atlas_access.json`` (each rule carries
its source URL, retrieval date and a verification status). This module is pure
logic: no MetaTrader5, no network, no file I/O at import time.

Design principles
-----------------
* FAIL CLOSED. Any exception, NaN/inf, stale snapshot, naive timestamp, unknown
  phase or malformed input produces a *deny* (check_order) or a safe action
  (monitor). Nothing here ever raises out of check_order / monitor.
* SAFETY BUFFER. We never trade up to an official limit. New risk stops at
  ``safety_buffer`` (default 0.6 = 60%) of each limit, and positions are
  flattened at ``Thresholds.hard_fraction`` (80%) of each limit.
* UNVERIFIED RULES. ``load_rules`` refuses a rule that is needed for enforcement
  but is not ``verified-official`` unless the caller names it in
  ``allow_unverified``.

Unit conventions
----------------
* Fractions are decimals (0.10 == 10%) everywhere EXCEPT ``payout_eligibility``
  daily profits, which are in PERCENT units (0.5 == 0.5%) because that is how
  Atlas states the rule.
* All timestamps must be timezone-aware; they are converted to UTC.
* Drawdown / daily-loss / protector limits are expressed against the INITIAL
  balance. The daily-loss base is the conservative ``min(initial, reference)``
  (the exact Atlas computation is unverified; see config).
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "atlas_access.json"

VALID_STATUSES = ("verified-official", "conflict", "unverified")
VALID_PHASES = ("evaluation", "funded")
_EPS = 1e-9
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RulesError(ValueError):
    """Raised when the rules file is missing, malformed or not safe to use."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _finite(x: Any) -> bool:
    return (
        isinstance(x, (int, float))
        and not isinstance(x, bool)
        and math.isfinite(float(x))
    )


def _to_utc(ts: Any) -> datetime:
    """Return a tz-aware UTC datetime or raise ValueError (naive -> error)."""
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if not isinstance(ts, datetime):
        raise ValueError(f"not a datetime: {ts!r}")
    if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
        raise ValueError("naive datetime rejected (timezone-aware UTC required)")
    return ts.astimezone(timezone.utc)


def _scan_nonfinite(obj: Any, path: str = "$") -> None:
    if isinstance(obj, float) and not math.isfinite(obj):
        raise RulesError(f"non-finite number at {path}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _scan_nonfinite(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan_nonfinite(v, f"{path}[{i}]")


def _reject_constant(name: str) -> None:
    raise RulesError(f"non-finite JSON constant {name!r} is not allowed")


# --------------------------------------------------------------------------- #
# Rules loading / validation
# --------------------------------------------------------------------------- #
def _phase_fracs(v: Any, name: str, *, funded_none: bool = False) -> None:
    if not isinstance(v, dict) or set(v) != {"evaluation", "funded"}:
        raise RulesError(f"{name}: value must be {{evaluation, funded}}")
    for ph in VALID_PHASES:
        x = v[ph]
        if ph == "funded" and funded_none and x is None:
            continue
        if not _finite(x) or not (0 < x < 1):
            raise RulesError(f"{name}.{ph}: must be a finite fraction in (0,1), got {x!r}")


def _frac(v: Any, name: str, *, upper_inclusive: bool = False) -> None:
    ok = _finite(v) and (0 < v <= 1 if upper_inclusive else 0 < v < 1)
    if not ok:
        raise RulesError(f"{name}: must be a finite fraction, got {v!r}")


def _nonneg(v: Any, name: str) -> None:
    if not _finite(v) or v < 0:
        raise RulesError(f"{name}: must be a finite number >= 0, got {v!r}")


def _v_payout_days(v: Any, name: str) -> None:
    if not isinstance(v, dict):
        raise RulesError(f"{name}: value must be an object")
    d, p = v.get("days"), v.get("min_day_profit_pct")
    if not (isinstance(d, int) and not isinstance(d, bool) and d >= 1):
        raise RulesError(f"{name}.days must be int >= 1")
    if not _finite(p) or p <= 0:
        raise RulesError(f"{name}.min_day_profit_pct must be finite > 0 (percent units)")


def _v_protector(v: Any, name: str) -> None:
    if not isinstance(v, dict):
        raise RulesError(f"{name}: value must be an object")
    _frac(v.get("floating_loss_pct_of_initial"), f"{name}.floating_loss_pct_of_initial")
    _frac(v.get("reduced_split"), f"{name}.reduced_split", upper_inclusive=True)
    b = v.get("breach_on_strike")
    if not (isinstance(b, int) and not isinstance(b, bool) and b >= 1):
        raise RulesError(f"{name}.breach_on_strike must be int >= 1")


def _v_reset(v: Any, name: str) -> None:
    if v != "00:00":
        raise RulesError(f"{name}: engine only supports a 00:00 UTC reset, got {v!r}")


def _v_bool(v: Any, name: str) -> None:
    if not isinstance(v, bool):
        raise RulesError(f"{name}: must be a boolean")


def _v_nonempty_str(v: Any, name: str) -> None:
    if not isinstance(v, str) or not v.strip():
        raise RulesError(f"{name}: must be a non-empty string")


def _v_pos(v: Any, name: str) -> None:
    if not _finite(v) or v <= 0:
        raise RulesError(f"{name}: must be finite > 0")


# name -> value validator. Every name here is REQUIRED in the file.
_REQUIRED_VALIDATORS = {
    "profit_target_pct": lambda v, n: _phase_fracs(v, n, funded_none=True),
    "max_drawdown_pct": _phase_fracs,
    "daily_loss_pct": _phase_fracs,
    "daily_loss_reset_utc": _v_reset,
    "daily_loss_eod_computation": _v_nonempty_str,
    "payout_min_profit_days": _v_payout_days,
    "payout_consistency_best_day_max_share": lambda v, n: _frac(v, n, upper_inclusive=True),
    "atlas_protector": _v_protector,
    "news_window_minutes": _nonneg,
    "min_hold_seconds": _nonneg,
    "margin_usage_close_pct": lambda v, n: _frac(v, n, upper_inclusive=True),
    "inactivity_limit_days": _v_pos,
    "weekend_new_positions_allowed": _v_bool,
    "per_instrument_risk_max_share_of_daily_limit": lambda v, n: _frac(v, n, upper_inclusive=True),
    "ea_approval_required": _v_nonempty_str,
}


@dataclass(frozen=True)
class AtlasRules:
    """Validated rules. ``rules`` maps name -> full rule record."""

    rules: Mapping[str, Mapping[str, Any]]
    acknowledged: tuple = ()

    def value(self, name: str) -> Any:
        try:
            return self.rules[name]["value"]
        except KeyError as exc:
            raise RulesError(f"unknown rule {name!r}") from exc

    def status(self, name: str) -> str:
        return self.rules[name]["status"]

    def phase_value(self, name: str, phase: str) -> Any:
        if phase not in VALID_PHASES:
            raise RulesError(f"unknown phase {phase!r}")
        return self.value(name)[phase]


def load_rules(path: Union[str, Path, None] = None,
               allow_unverified: Optional[Iterable[str]] = None) -> AtlasRules:
    """Load and validate the Atlas rules JSON. Raises RulesError on any problem.

    A rule with ``needed_for_enforcement`` true whose status is not
    ``verified-official`` (i.e. 'unverified' or 'conflict') is refused unless its
    name is listed in ``allow_unverified``.
    """
    p = Path(path) if path is not None else DEFAULT_RULES_PATH
    try:
        raw = p.read_text(encoding="utf-8")
        doc = json.loads(raw, parse_constant=_reject_constant)
    except RulesError:
        raise
    except Exception as exc:  # noqa: BLE001 - fail closed with a clear error
        raise RulesError(f"cannot read/parse rules file {p}: {exc}") from exc

    if not isinstance(doc, dict) or not isinstance(doc.get("rules"), dict):
        raise RulesError("rules file must be an object with a 'rules' object")
    _scan_nonfinite(doc)
    rules = doc["rules"]

    allow = set(allow_unverified or ())
    unknown_allow = allow - set(rules)
    if unknown_allow:
        raise RulesError(f"allow_unverified names not in rules file: {sorted(unknown_allow)}")

    for name, rec in rules.items():
        if not isinstance(rec, dict):
            raise RulesError(f"{name}: rule record must be an object")
        for key in ("value", "source", "retrieved", "status", "needed_for_enforcement"):
            if key not in rec:
                raise RulesError(f"{name}: missing field {key!r}")
        if rec["status"] not in VALID_STATUSES:
            raise RulesError(f"{name}: invalid status {rec['status']!r}")
        if not isinstance(rec["source"], str) or not rec["source"].startswith("https://"):
            raise RulesError(f"{name}: source must be an https URL")
        ret = rec["retrieved"]
        if not isinstance(ret, str) or not _DATE_RE.match(ret):
            raise RulesError(f"{name}: retrieved must be YYYY-MM-DD")
        try:
            date.fromisoformat(ret)
        except ValueError as exc:
            raise RulesError(f"{name}: invalid retrieved date") from exc
        if not isinstance(rec["needed_for_enforcement"], bool):
            raise RulesError(f"{name}: needed_for_enforcement must be a boolean")

    missing = [n for n in _REQUIRED_VALIDATORS if n not in rules]
    if missing:
        raise RulesError(f"missing required rules: {missing}")

    for name, validator in _REQUIRED_VALIDATORS.items():
        validator(rules[name]["value"], name)

    refused = [
        n for n, rec in rules.items()
        if rec["needed_for_enforcement"]
        and rec["status"] != "verified-official"
        and n not in allow
    ]
    if refused:
        detail = ", ".join(f"{n} ({rules[n]['status']})" for n in refused)
        raise RulesError(
            "refusing to load: rules needed for enforcement are not verified-official: "
            f"{detail}. Resolve them or pass allow_unverified=[...] explicitly."
        )

    return AtlasRules(rules=rules, acknowledged=tuple(sorted(allow)))


# --------------------------------------------------------------------------- #
# Data containers
# --------------------------------------------------------------------------- #
@dataclass
class AtlasState:
    """Mutable per-account state the engine reads (and update_state maintains)."""

    initial_balance: float
    peak_equity: float
    day_ref_equity: float
    day_ref_date_utc: date
    phase: str = "evaluation"
    protector_strikes: int = 0
    last_trade_ts: Optional[datetime] = None
    # date -> that UTC day's profit in PERCENT of initial balance (payout cycle)
    cycle_day_profits: Dict[date, float] = field(default_factory=dict)
    day_high_equity: Optional[float] = None
    day_start_balance: Optional[float] = None

    @classmethod
    def new(cls, initial_balance: float, now_utc: datetime, phase: str = "evaluation",
            equity: Optional[float] = None) -> "AtlasState":
        eq = initial_balance if equity is None else equity
        now = _to_utc(now_utc)
        return cls(initial_balance=initial_balance, peak_equity=max(initial_balance, eq),
                   day_ref_equity=eq, day_ref_date_utc=now.date(), phase=phase,
                   day_high_equity=eq, day_start_balance=initial_balance)


@dataclass
class AccountInfo:
    balance: float
    equity: float
    margin: float
    free_margin: float
    ts_utc: Optional[datetime] = None
    floating_pnl: Optional[float] = None  # derived as equity - balance if None
    open_risk_by_symbol: Mapping[str, float] = field(default_factory=dict)  # USD at stop


@dataclass
class OrderRequest:
    symbol: str
    stop_risk_usd: float      # loss in USD if the stop is hit
    margin_required: float    # additional margin this order consumes
    volume: float = 0.0
    side: str = "buy"


@dataclass
class Decision:
    allow: bool
    reasons: List[str] = field(default_factory=list)
    computed: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorResult:
    action: str  # 'OK' | 'STOP_NEW' | 'FLATTEN'
    reasons: List[str] = field(default_factory=list)
    computed: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PayoutResult:
    eligible: bool
    reasons: List[str]
    qualifying_days: int
    best_day_share: Optional[float]
    delayed_by_consistency: bool = False


@dataclass(frozen=True)
class Thresholds:
    """Engine thresholds beyond the safety buffer (all stricter than Atlas)."""

    hard_fraction: float = 0.8          # flatten at 80% of drawdown/daily limits
    margin_order_cap: float = 0.50      # deny orders projecting margin usage >= 50%
    margin_flatten: float = 0.65        # flatten at >= 65% margin usage
    protector_soft_pct: float = 0.01    # STOP_NEW / deny at floating loss >= 1.0% initial
    protector_flatten_pct: float = 0.015  # flatten at floating loss >= 1.5% initial
    news_extra_pad_minutes: float = 2.0   # added to the +/-5 min official window
    max_snapshot_age_s: float = 30.0


# --------------------------------------------------------------------------- #
# Stand-alone helpers
# --------------------------------------------------------------------------- #
def min_hold_ok(open_ts: Any, close_ts: Any, min_seconds: float = 180.0) -> bool:
    """True if a trade was held at least ``min_seconds`` (3 minutes). Fail closed."""
    try:
        if isinstance(open_ts, (int, float)) and isinstance(close_ts, (int, float)):
            if not (_finite(open_ts) and _finite(close_ts)):
                return False
            held = float(close_ts) - float(open_ts)
        else:
            held = (_to_utc(close_ts) - _to_utc(open_ts)).total_seconds()
        return held >= min_seconds
    except Exception:  # noqa: BLE001
        return False


def evaluation_progress(balance: float, initial: float, target_pct: float = 0.03) -> Dict[str, Any]:
    """Evaluation target progress on the CLOSED balance (3% of start balance)."""
    if not (_finite(balance) and _finite(initial)) or initial <= 0:
        raise ValueError("balance/initial must be finite and initial > 0")
    profit_pct = (balance - initial) / initial
    return {
        "profit_pct": profit_pct,
        "target_pct": target_pct,
        "progress": profit_pct / target_pct,
        "target_reached": profit_pct >= target_pct - _EPS,
        "profit_usd": balance - initial,
        "target_usd": initial * target_pct,
    }


def payout_eligibility(day_profits_pct: Union[Mapping[Any, float], Sequence[float]],
                       cycle_profit: float, *, min_days: int = 3,
                       min_day_pct: float = 0.5, max_best_share: float = 0.40,
                       cycle_profit_usd: Optional[float] = None,
                       min_profit_usd: float = 100.0) -> PayoutResult:
    """Funded payout rules for one cycle.

    ``day_profits_pct``: daily profit per trading day in PERCENT units (0.5 == 0.5%).
    ``cycle_profit``: total cycle profit in the SAME units as the daily profits.
    ``cycle_profit_usd``: optional; if given, the $100 threshold is enforced.
    Needs >= ``min_days`` days with >= ``min_day_pct``; best day <= 40% of cycle profit
    (a consistency miss only DELAYS the payout, flagged via delayed_by_consistency).
    """
    reasons: List[str] = []
    try:
        vals = list(day_profits_pct.values()) if isinstance(day_profits_pct, Mapping) \
            else list(day_profits_pct)
        if not all(_finite(v) for v in vals) or not _finite(cycle_profit):
            return PayoutResult(False, ["invalid_input"], 0, None)
        qualifying = sum(1 for v in vals if v >= min_day_pct - _EPS)
        eligible = True
        if qualifying < min_days:
            eligible = False
            reasons.append(f"min_profit_days:{qualifying}<{min_days}")
        share: Optional[float] = None
        delayed = False
        if cycle_profit <= 0:
            eligible = False
            reasons.append("cycle_profit_not_positive")
        else:
            best = max(vals) if vals else 0.0
            share = best / cycle_profit
            if share > max_best_share + _EPS:
                eligible = False
                delayed = True
                reasons.append(f"consistency:best_day_share {share:.4f}>{max_best_share}")
        if cycle_profit_usd is not None:
            if not _finite(cycle_profit_usd) or cycle_profit_usd < min_profit_usd - _EPS:
                eligible = False
                reasons.append(f"below_min_profit_usd:{cycle_profit_usd}<{min_profit_usd}")
        return PayoutResult(eligible, reasons, qualifying, share, delayed)
    except Exception as exc:  # noqa: BLE001
        return PayoutResult(False, [f"internal_error:{exc!r}"], 0, None)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class AtlasRuleEngine:
    def __init__(self, rules: AtlasRules, safety_buffer: float = 0.6,
                 thresholds: Optional[Thresholds] = None):
        if not isinstance(rules, AtlasRules):
            raise TypeError("rules must be an AtlasRules (use load_rules)")
        th = thresholds or Thresholds()
        if not (_finite(safety_buffer) and 0 < safety_buffer <= th.hard_fraction):
            raise ValueError("safety_buffer must be in (0, hard_fraction]")
        if not (0 < th.hard_fraction < 1):
            raise ValueError("hard_fraction must be in (0,1)")
        margin_close = float(rules.value("margin_usage_close_pct"))
        protector = float(rules.value("atlas_protector")["floating_loss_pct_of_initial"])
        if not (th.margin_order_cap < th.margin_flatten < margin_close):
            raise ValueError("margin thresholds must satisfy order_cap < flatten < official close")
        if not (0 < th.protector_soft_pct < th.protector_flatten_pct < protector):
            raise ValueError("protector thresholds must be below the official protector limit")
        self.rules = rules
        self.safety_buffer = float(safety_buffer)
        self.th = th
        self._margin_close = margin_close
        self._protector = protector
        self._news_min = float(rules.value("news_window_minutes"))
        self._min_hold = float(rules.value("min_hold_seconds"))
        self._inst_share = float(rules.value("per_instrument_risk_max_share_of_daily_limit"))
        self._weekend_ok = bool(rules.value("weekend_new_positions_allowed"))

    # ----- limits ----------------------------------------------------------
    def _check_phase(self, phase: Any) -> str:
        if phase not in VALID_PHASES:
            raise ValueError(f"unknown phase {phase!r}")
        return phase

    def limits(self, phase: str) -> Dict[str, float]:
        phase = self._check_phase(phase)
        return {
            "max_drawdown_pct": float(self.rules.phase_value("max_drawdown_pct", phase)),
            "daily_loss_pct": float(self.rules.phase_value("daily_loss_pct", phase)),
        }

    def _validate_state(self, state: AtlasState) -> None:
        if not isinstance(state, AtlasState):
            raise ValueError("state must be AtlasState")
        self._check_phase(state.phase)
        for n in ("initial_balance", "peak_equity", "day_ref_equity"):
            if not _finite(getattr(state, n)):
                raise ValueError(f"state.{n} not finite")
        if state.initial_balance <= 0:
            raise ValueError("state.initial_balance must be > 0")
        if not isinstance(state.day_ref_date_utc, date):
            raise ValueError("state.day_ref_date_utc must be a date")
        if not isinstance(state.protector_strikes, int) or state.protector_strikes < 0:
            raise ValueError("state.protector_strikes invalid")

    def trailing_floor(self, state: AtlasState, phase: Optional[str] = None,
                       equity: Optional[float] = None) -> float:
        """Trailing max-drawdown floor. Rises with peak equity (incl. unrealized
        profit), never falls: peak is max(state.peak_equity, equity)."""
        phase = self._check_phase(phase if phase is not None else state.phase)
        peak = state.peak_equity
        if equity is not None:
            if not _finite(equity):
                raise ValueError("equity not finite")
            peak = max(peak, equity)
        dd = self.limits(phase)["max_drawdown_pct"]
        return peak - dd * state.initial_balance

    def daily_floor(self, state: AtlasState, phase: Optional[str] = None) -> float:
        """Daily-loss floor = ref - pct * min(initial, ref) (conservative; see config)."""
        phase = self._check_phase(phase if phase is not None else state.phase)
        pct = self.limits(phase)["daily_loss_pct"]
        ref = state.day_ref_equity
        return ref - pct * min(state.initial_balance, ref)

    def _daily_limit_usd(self, state: AtlasState, phase: str) -> float:
        pct = self.limits(phase)["daily_loss_pct"]
        return pct * min(state.initial_balance, state.day_ref_equity)

    def _loss_fractions(self, state: AtlasState, equity: float, phase: str) -> Dict[str, float]:
        lim = self.limits(phase)
        peak = max(state.peak_equity, equity)
        dd_usd = lim["max_drawdown_pct"] * state.initial_balance
        daily_usd = self._daily_limit_usd(state, phase)
        if dd_usd <= 0 or daily_usd <= 0:
            raise ValueError("non-positive loss limit")
        return {
            "trailing_used": (peak - equity) / dd_usd,
            "daily_used": (state.day_ref_equity - equity) / daily_usd,
            "trailing_floor": peak - dd_usd,
            "daily_floor": state.day_ref_equity - daily_usd,
            "daily_limit_usd": daily_usd,
            "dd_limit_usd": dd_usd,
        }

    # ----- state maintenance ----------------------------------------------
    def update_state_on_new_day(self, state: AtlasState, account: AccountInfo,
                                now_utc: datetime) -> bool:
        """Roll the daily reference at 00:00 UTC. Returns True if a new day began.

        New reference = previous day's highest equity/balance. The finished day's
        profit (percent of initial) is appended to ``cycle_day_profits``.
        """
        now = _to_utc(now_utc)
        today = now.date()
        if today < state.day_ref_date_utc:
            raise ValueError("clock went backwards across a UTC day boundary")
        if today == state.day_ref_date_utc:
            return False
        high = state.day_high_equity if state.day_high_equity is not None else state.day_ref_equity
        if not (_finite(account.balance) and _finite(account.equity)):
            raise ValueError("account data not finite")
        if state.day_start_balance is not None:
            state.cycle_day_profits[state.day_ref_date_utc] = (
                (account.balance - state.day_start_balance) / state.initial_balance * 100.0
            )
        state.day_ref_equity = max(high, account.balance)
        state.day_ref_date_utc = today
        state.day_high_equity = max(account.equity, account.balance)
        state.day_start_balance = account.balance
        return True

    def update_state(self, account: AccountInfo, state: AtlasState, now_utc: datetime) -> None:
        """Per-tick maintenance: day roll, peak equity (monotonic), day high."""
        self._validate_state(state)
        self.update_state_on_new_day(state, account, now_utc)
        eq = account.equity
        if not _finite(eq):
            raise ValueError("equity not finite")
        state.peak_equity = max(state.peak_equity, eq)
        state.day_high_equity = eq if state.day_high_equity is None else max(state.day_high_equity, eq)

    def record_protector_strike(self, state: AtlasState) -> str:
        """Register an Atlas Protector trigger. Returns 'REDUCED_SPLIT' or 'BREACH'."""
        state.protector_strikes += 1
        n = int(self.rules.value("atlas_protector")["breach_on_strike"])
        return "BREACH" if state.protector_strikes >= n else "REDUCED_SPLIT"

    # ----- coercion / validation of inputs --------------------------------
    def _coerce_account(self, a: Any) -> AccountInfo:
        if isinstance(a, Mapping):
            a = AccountInfo(**{k: a[k] for k in a if k in AccountInfo.__dataclass_fields__})
        if not isinstance(a, AccountInfo):
            raise ValueError("account must be AccountInfo or mapping")
        for n in ("balance", "equity", "margin", "free_margin"):
            if not _finite(getattr(a, n)):
                raise ValueError(f"account.{n} missing/NaN/inf")
        if a.margin < 0:
            raise ValueError("account.margin negative")
        if a.floating_pnl is not None and not _finite(a.floating_pnl):
            raise ValueError("account.floating_pnl NaN/inf")
        for sym, r in dict(a.open_risk_by_symbol or {}).items():
            if not _finite(r) or r < 0:
                raise ValueError(f"open_risk_by_symbol[{sym}] invalid")
        return a

    def _coerce_order(self, o: Any) -> OrderRequest:
        if isinstance(o, Mapping):
            o = OrderRequest(**{k: o[k] for k in o if k in OrderRequest.__dataclass_fields__})
        if not isinstance(o, OrderRequest):
            raise ValueError("order must be OrderRequest or mapping")
        if not isinstance(o.symbol, str) or not o.symbol:
            raise ValueError("order.symbol missing")
        for n in ("stop_risk_usd", "margin_required"):
            v = getattr(o, n)
            if not _finite(v) or v < 0:
                raise ValueError(f"order.{n} invalid (a stop-loss is mandatory)")
        return o

    def _check_fresh(self, a: AccountInfo, now: datetime) -> float:
        if a.ts_utc is None:
            raise ValueError("account snapshot has no timestamp")
        age = (now - _to_utc(a.ts_utc)).total_seconds()
        if age > self.th.max_snapshot_age_s or age < -5.0:
            raise ValueError(f"stale/invalid snapshot age {age:.1f}s")
        return age

    @staticmethod
    def _floating_loss(a: AccountInfo) -> float:
        pnl = a.floating_pnl if a.floating_pnl is not None else a.equity - a.balance
        return max(0.0, -pnl)

    # ----- news / weekend ---------------------------------------------------
    def _event_times(self, events: Optional[Iterable[Any]]) -> List[datetime]:
        out: List[datetime] = []
        for ev in events or ():
            if isinstance(ev, Mapping):
                impact = str(ev.get("impact", "high")).lower()
                if impact not in ("high", "red", "3"):
                    continue  # explicit lower impact is ignored; unspecified counts as high
                raw = next((ev[k] for k in ("time", "ts", "timestamp") if k in ev), None)
                if raw is None:
                    raise ValueError("news event without a time")
                out.append(_to_utc(raw))
            else:
                out.append(_to_utc(ev))
        return out

    def news_window_minutes(self) -> float:
        return self._news_min + self.th.news_extra_pad_minutes

    def in_news_window(self, now_utc: datetime, news_events: Optional[Iterable[Any]]) -> bool:
        """True if now is within +/-(5 + pad) minutes (edges inclusive). Fails closed."""
        try:
            now = _to_utc(now_utc)
            w = timedelta(minutes=self.news_window_minutes())
            return any(abs(now - t) <= w for t in self._event_times(news_events))
        except Exception:  # noqa: BLE001
            return True

    @staticmethod
    def is_weekend_utc(now_utc: datetime) -> bool:
        return _to_utc(now_utc).weekday() >= 5

    # ----- decisions --------------------------------------------------------
    def check_order(self, order: Any, account: Any, state: AtlasState, now_utc: datetime,
                    news_events: Optional[Iterable[Any]] = None) -> Decision:
        """Gate a NEW position. Never raises; any problem is a deny."""
        try:
            return self._check_order(order, account, state, now_utc, news_events)
        except Exception as exc:  # noqa: BLE001 - fail closed
            return Decision(False, [f"fail_closed:{type(exc).__name__}:{exc}"], {})

    def _check_order(self, order, account, state, now_utc, news_events) -> Decision:
        now = _to_utc(now_utc)
        self._validate_state(state)
        phase = state.phase
        acct = self._coerce_account(account)
        od = self._coerce_order(order)
        self._check_fresh(acct, now)
        reasons: List[str] = []
        c: Dict[str, Any] = {"phase": phase, "buffer": self.safety_buffer}

        if state.protector_strikes >= int(self.rules.value("atlas_protector")["breach_on_strike"]):
            reasons.append("protector_breach_state")

        # weekend (new positions only)
        if not self._weekend_ok and self.is_weekend_utc(now):
            reasons.append("weekend_entry")

        # news window
        if self.in_news_window(now, news_events):
            reasons.append("news_window")

        # projected equity if the stop is hit
        projected = acct.equity - od.stop_risk_usd
        f = self._loss_fractions(state, projected, phase)
        c.update(projected_equity=projected, **f)
        if f["trailing_used"] >= self.safety_buffer - _EPS:
            reasons.append(f"trailing_dd_buffer:{f['trailing_used']:.4f}>={self.safety_buffer}")
        if f["daily_used"] >= self.safety_buffer - _EPS:
            reasons.append(f"daily_loss_buffer:{f['daily_used']:.4f}>={self.safety_buffer}")
        if projected < f["trailing_floor"] - _EPS or projected < f["daily_floor"] - _EPS:
            reasons.append("projected_floor_breach")

        # margin projection
        new_margin = acct.margin + od.margin_required
        new_free = acct.free_margin - od.margin_required
        total = new_margin + new_free
        if total <= 0:
            reasons.append("margin_total_non_positive")
            usage = float("inf")
        else:
            usage = new_margin / total
        c["projected_margin_usage"] = usage
        if usage >= self.th.margin_order_cap - _EPS:
            reasons.append(f"margin_projection:{usage:.4f}>={self.th.margin_order_cap}")

        # per-instrument risk (existing + new on same symbol)
        existing = float(dict(acct.open_risk_by_symbol or {}).get(od.symbol, 0.0))
        inst_risk = existing + od.stop_risk_usd
        inst_cap = self._inst_share * f["daily_limit_usd"]
        c.update(instrument_risk=inst_risk, instrument_cap=inst_cap)
        if inst_risk > inst_cap + _EPS:
            reasons.append(f"instrument_risk:{inst_risk:.2f}>{inst_cap:.2f}")

        # Atlas Protector proximity
        fl = self._floating_loss(acct)
        soft = self.th.protector_soft_pct * state.initial_balance
        c.update(floating_loss=fl, protector_soft_usd=soft)
        if fl >= soft - _EPS:
            reasons.append(f"protector_buffer:floating_loss {fl:.2f}>={soft:.2f}")
        elif fl + od.stop_risk_usd >= self._protector * state.initial_balance - _EPS:
            # floating loss plus this order's stop would reach the OFFICIAL protector level
            reasons.append(f"protector_projection:{fl + od.stop_risk_usd:.2f}>="
                           f"{self._protector * state.initial_balance:.2f}")

        return Decision(not reasons, reasons, c)

    def monitor_detail(self, account: Any, state: AtlasState, now_utc: datetime) -> MonitorResult:
        try:
            return self._monitor(account, state, now_utc)
        except Exception as exc:  # noqa: BLE001
            return MonitorResult("FLATTEN", [f"fail_closed:{type(exc).__name__}:{exc}"], {})

    def monitor(self, account: Any, state: AtlasState, now_utc: datetime) -> str:
        """'OK' | 'STOP_NEW' | 'FLATTEN'. Internal errors -> 'FLATTEN'."""
        return self.monitor_detail(account, state, now_utc).action

    def _monitor(self, account, state, now_utc) -> MonitorResult:
        now = _to_utc(now_utc)
        self._validate_state(state)
        phase = state.phase
        # Stale / NaN / malformed account data -> STOP_NEW (we cannot size new
        # risk); a broken STATE or an unexpected exception -> FLATTEN (outer wrapper).
        try:
            acct = self._coerce_account(account)
            self._check_fresh(acct, now)
        except ValueError as exc:
            return MonitorResult("STOP_NEW", [f"bad_or_stale_data:{exc}"], {})
        f = self._loss_fractions(state, acct.equity, phase)
        total = acct.margin + acct.free_margin
        usage = acct.margin / total if total > 0 else (float("inf") if acct.margin > 0 else 0.0)
        fl = self._floating_loss(acct)
        c = dict(f, margin_usage=usage, floating_loss=fl, phase=phase)
        hard_r, soft_r = [], []
        hf, sb = self.th.hard_fraction, self.safety_buffer
        for key, label in (("trailing_used", "trailing_dd"), ("daily_used", "daily_loss")):
            if f[key] >= hf - _EPS:
                hard_r.append(f"{label}_hard:{f[key]:.4f}>={hf}")
            elif f[key] >= sb - _EPS:
                soft_r.append(f"{label}_soft:{f[key]:.4f}>={sb}")
        if usage >= self.th.margin_flatten - _EPS:
            hard_r.append(f"margin_hard:{usage:.4f}>={self.th.margin_flatten}")
        elif usage >= self.th.margin_order_cap - _EPS:
            soft_r.append(f"margin_soft:{usage:.4f}>={self.th.margin_order_cap}")
        hard_usd = self.th.protector_flatten_pct * state.initial_balance
        soft_usd = self.th.protector_soft_pct * state.initial_balance
        if fl >= hard_usd - _EPS:
            hard_r.append(f"protector_hard:{fl:.2f}>={hard_usd:.2f}")
        elif fl >= soft_usd - _EPS:
            soft_r.append(f"protector_soft:{fl:.2f}>={soft_usd:.2f}")
        if hard_r:
            return MonitorResult("FLATTEN", hard_r + soft_r, c)
        if soft_r:
            return MonitorResult("STOP_NEW", soft_r, c)
        return MonitorResult("OK", [], c)

    # ----- convenience wrappers around the module helpers -------------------
    def min_hold_ok(self, open_ts: Any, close_ts: Any) -> bool:
        return min_hold_ok(open_ts, close_ts, self._min_hold)

    def payout_eligibility(self, day_profits_pct, cycle_profit,
                           cycle_profit_usd: Optional[float] = None) -> PayoutResult:
        pd = self.rules.value("payout_min_profit_days")
        sched = self.rules.value("payout_schedule") if "payout_schedule" in self.rules.rules else {}
        return payout_eligibility(
            day_profits_pct, cycle_profit, min_days=pd["days"], min_day_pct=pd["min_day_profit_pct"],
            max_best_share=float(self.rules.value("payout_consistency_best_day_max_share")),
            cycle_profit_usd=cycle_profit_usd,
            min_profit_usd=float(sched.get("min_profit_usd", 100.0)),
        )

    def evaluation_progress(self, balance: float, initial: float) -> Dict[str, Any]:
        return evaluation_progress(balance, initial,
                                   float(self.rules.phase_value("profit_target_pct", "evaluation")))

    def inactivity_ok(self, state: AtlasState, now_utc: datetime) -> bool:
        """True while within the 30-day inactivity limit (fails closed)."""
        try:
            if state.last_trade_ts is None:
                return False
            days = (_to_utc(now_utc) - _to_utc(state.last_trade_ts)).total_seconds() / 86400.0
            return days < float(self.rules.value("inactivity_limit_days"))
        except Exception:  # noqa: BLE001
            return False
