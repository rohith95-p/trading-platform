"""Part II of REAL_MONEY_READINESS.md, as code instead of prose.

Everything here was specified in that document and never built: the
balance-based sizing ladder (II.2), the cascading daily/weekly/monthly/peak
loss caps (II.3), the consecutive-loss circuit breakers (II.4), profit
ring-fence milestones (II.5), and the margin-utilisation cap (II.6). Until
now the only risk control that actually existed in code was a single 6%
same-day breaker, which `SYSTEM_FAULTS.md` correctly called "a 1-2 loss cap."

IMPORTANT -- deliberately OFF by default. `ENFORCE = False` means importing
this module changes nothing about live behaviour. The ladder below is
materially TIGHTER than the currently-validated live config (one position at
balances under $200, versus the three concurrent the live config runs), so
switching it on changes what the strategy does and therefore invalidates the
recorded backtest. Flip ENFORCE on only after the laddered config has been
backtested and registered via `validation_ledger.record(...)`, exactly like
any other config change -- see src/core/validation_ledger.py.

State (peak equity, week/month anchors, loss streaks, active pauses) persists
to logs/risk_state.json so a restart cannot silently reset a breaker.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PATH = os.path.join(_ROOT, "logs", "risk_state.json")

# Master switch. See module docstring -- do not flip without re-validating.
# 2026-10-09 audit fix: Risk controls must be enforced, not bypassable.
# The laddered config has now been incorporated into the core logic.
ENFORCE = True

# --- II.2 sizing ladder ----------------------------------------------------
# (upper_balance_exclusive, lots_per_order, max_total_volume, max_positions)
SIZING_LADDER: Tuple[Tuple[float, float, float, int], ...] = (
    (200.0,   0.01, 0.01, 1),
    (400.0,   0.01, 0.02, 2),
    (800.0,   0.01, 0.03, 3),
    (float("inf"), 0.02, 0.06, 3),
)

# --- II.3 cascading loss caps ---------------------------------------------
DAILY_LIMIT_PCT_EARLY = 0.03      # below EARLY_PHASE_BALANCE
DAILY_LIMIT_PCT_NORMAL = 0.06
EARLY_PHASE_BALANCE = 400.0
DAILY_MAX_LOSING_TRADES_EARLY = 2
WEEKLY_LIMIT_PCT = 0.15           # from Monday's opening balance
MONTHLY_LIMIT_PCT = 0.25          # from month-start balance
PEAK_DRAWDOWN_KILL_PCT = 0.30     # from all-time peak equity -> hard kill

# Owner decision 2026-10-21: on a DEMO account used only to collect data, the monthly-loss and peak-drawdown HARD halts are
# switched off (the daily cap, weekly cap, streak breakers, margin, spread and news rules all stay). The relaxation is
# deliberately narrow: it applies only (a) inside the live bot loop (main_loop sets LIVE_CONTEXT, so backtests and the
# research engine, which also call evaluate(), are untouched), and (b) while MT5 positively reports a DEMO account. A real or
# unknown account type (or any error reading it) leaves the hard halts fully active.
DEMO_RELAX_HARD_HALTS = True
LIVE_CONTEXT = False
_RELAX_LOGGED: dict = {}


def _account_is_demo() -> bool:
    try:
        import MetaTrader5 as mt5
        info = mt5.account_info()
        return info is not None and info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
    except Exception:
        return False                   # fail closed: unknown account type keeps the halts on


def hard_halts_relaxed() -> bool:
    return bool(DEMO_RELAX_HARD_HALTS and LIVE_CONTEXT and _account_is_demo())


def _note_relaxed(kind: str, text: str) -> None:
    if _RELAX_LOGGED.get(kind, 0.0) < datetime.now().timestamp() - 3600:
        _RELAX_LOGGED[kind] = datetime.now().timestamp()
        log.warning(f"HARD HALT RELAXED (demo account, owner decision 2026-10-21): {text} -- trading continues.")

# --- II.4 circuit breakers -------------------------------------------------
CONSEC_LOSSES_PAUSE = 3           # -> pause new entries
CONSEC_LOSS_PAUSE_HOURS = 4
CONSEC_LOSSES_STOP_DAY = 5        # -> done for the day

# --- II.6 margin -----------------------------------------------------------
MAX_MARGIN_UTILISATION = 0.20

# --- II.5 profit ring-fence milestones ------------------------------------
RING_FENCE_MILESTONES = (150.0, 200.0, 300.0, 500.0)
RING_FENCE_STEP_ABOVE = 250.0
RING_FENCE_FRACTION = 0.30


@dataclass
class RiskState:
    peak_equity: float = 0.0
    week_anchor_date: str = ""          # ISO date of the week's Monday (IST)
    week_start_balance: float = 0.0
    month_anchor: str = ""              # "YYYY-MM" (IST)
    month_start_balance: float = 0.0
    day_anchor_date: str = ""           # ISO date (IST)
    day_start_balance: float = 0.0
    day_losing_trades: int = 0
    consecutive_losses: int = 0
    pause_until_ts: float = 0.0
    day_stopped_date: str = ""
    hard_halt_reason: str = ""          # weekly/monthly/peak kill -> manual reset
    milestones_hit: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class RiskDecision:
    allow_new_entries: bool
    reason: str = ""
    lots: float = 0.01
    max_total_volume: float = 0.03
    max_positions: int = 3


def load_state() -> RiskState:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return RiskState(**json.load(f))
    except (OSError, ValueError, TypeError):
        return RiskState()


def save_state(state: RiskState) -> None:
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)
    except OSError as e:
        log.warning(f"Could not persist risk state: {e}")


# ---------------------------------------------------------------------------
# II.2 -- sizing
# ---------------------------------------------------------------------------

def sizing_for_balance(balance: float) -> Tuple[float, float, int]:
    """(lots_per_order, max_total_volume, max_positions) for this balance."""
    for upper, lots, max_vol, max_pos in SIZING_LADDER:
        if balance < upper:
            return lots, max_vol, max_pos
    return SIZING_LADDER[-1][1:]


# ---------------------------------------------------------------------------
# II.6 -- margin
# ---------------------------------------------------------------------------

def margin_ok(equity: float, margin_used: float) -> Tuple[bool, str]:
    if equity <= 0:
        return False, "equity <= 0"
    util = margin_used / equity
    if util > MAX_MARGIN_UTILISATION:
        return False, f"margin utilisation {util:.1%} > {MAX_MARGIN_UTILISATION:.0%} cap"
    return True, ""


# ---------------------------------------------------------------------------
# Period anchors -- roll day/week/month, track peak
# ---------------------------------------------------------------------------

def _roll_anchors(state: RiskState, balance: float, now: datetime) -> RiskState:
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    month_key = f"{today.year:04d}-{today.month:02d}"

    if state.day_anchor_date != today.isoformat():
        state.day_anchor_date = today.isoformat()
        state.day_start_balance = balance
        state.day_losing_trades = 0
        if state.day_stopped_date and state.day_stopped_date != today.isoformat():
            state.day_stopped_date = ""
    if state.week_anchor_date != monday.isoformat():
        state.week_anchor_date = monday.isoformat()
        state.week_start_balance = balance
    if state.month_anchor != month_key:
        state.month_anchor = month_key
        state.month_start_balance = balance
    state.peak_equity = max(state.peak_equity, balance)
    return state


# ---------------------------------------------------------------------------
# The full gate -- II.3 + II.4 together
# ---------------------------------------------------------------------------

def evaluate(balance: float, equity: float, margin_used: float = 0.0,
             now: Optional[datetime] = None,
             state: Optional[RiskState] = None) -> Tuple[RiskDecision, RiskState]:
    """Single entry point: may we open a new position right now, and at what size?

    Returns (decision, state). Caller persists state via save_state().
    Evaluates even when ENFORCE is False, so the decision can be logged in
    shadow mode and compared against live behaviour before being switched on.
    """
    now = now or datetime.now(IST)
    state = state or load_state()
    state = _roll_anchors(state, balance, now)

    lots, max_vol, max_pos = sizing_for_balance(balance)
    


    d = RiskDecision(True, "", lots, max_vol, max_pos)

    # Hard halts first -- these require a human to clear (except on a demo account in the live loop; see top of file).
    relaxed = hard_halts_relaxed()
    if state.hard_halt_reason and not relaxed:
        return RiskDecision(False, f"HARD HALT: {state.hard_halt_reason}", lots, max_vol, max_pos), state

    peak_dd = (state.peak_equity - equity) / state.peak_equity if state.peak_equity > 0 else 0.0
    if peak_dd >= PEAK_DRAWDOWN_KILL_PCT:
        if relaxed:
            _note_relaxed("peak", f"peak drawdown {peak_dd:.1%} >= {PEAK_DRAWDOWN_KILL_PCT:.0%}")
        else:
            state.hard_halt_reason = (f"peak drawdown {peak_dd:.1%} >= {PEAK_DRAWDOWN_KILL_PCT:.0%} "
                                      f"(peak ${state.peak_equity:.2f} -> ${equity:.2f}); post-mortem required")
            return RiskDecision(False, f"HARD HALT: {state.hard_halt_reason}", lots, max_vol, max_pos), state

    if state.month_start_balance > 0:
        m_dd = (state.month_start_balance - equity) / state.month_start_balance
        if m_dd >= MONTHLY_LIMIT_PCT:
            if relaxed:
                _note_relaxed("monthly", f"monthly loss {m_dd:.1%} >= {MONTHLY_LIMIT_PCT:.0%}")
            else:
                state.hard_halt_reason = (f"monthly loss {m_dd:.1%} >= {MONTHLY_LIMIT_PCT:.0%}; "
                                          f"re-run Part I before resuming")
                return RiskDecision(False, f"HARD HALT: {state.hard_halt_reason}", lots, max_vol, max_pos), state

    if state.week_start_balance > 0:
        w_dd = (state.week_start_balance - equity) / state.week_start_balance
        if w_dd >= WEEKLY_LIMIT_PCT:
            return RiskDecision(False, f"WEEK HALTED: down {w_dd:.1%} from Monday "
                                       f"(cap {WEEKLY_LIMIT_PCT:.0%}); review before resuming",
                                lots, max_vol, max_pos), state

    # Daily
    if state.day_stopped_date == now.date().isoformat():
        return RiskDecision(False, "day stopped by circuit breaker", lots, max_vol, max_pos), state

    daily_cap = DAILY_LIMIT_PCT_EARLY if balance < EARLY_PHASE_BALANCE else DAILY_LIMIT_PCT_NORMAL
    if state.day_start_balance > 0:
        d_dd = (state.day_start_balance - equity) / state.day_start_balance
        if d_dd >= daily_cap:
            return RiskDecision(False, f"daily loss {d_dd:.1%} >= {daily_cap:.0%} cap",
                                lots, max_vol, max_pos), state

    if (balance < EARLY_PHASE_BALANCE
            and state.day_losing_trades >= DAILY_MAX_LOSING_TRADES_EARLY):
        return RiskDecision(False, f"{state.day_losing_trades} losing trades today "
                                   f"(early-phase cap {DAILY_MAX_LOSING_TRADES_EARLY})",
                            lots, max_vol, max_pos), state

    # II.4 consecutive-loss pause
    if state.pause_until_ts > now.timestamp():
        mins = (state.pause_until_ts - now.timestamp()) / 60
        return RiskDecision(False, f"loss-streak pause active, {mins:.0f} min remaining",
                            lots, max_vol, max_pos), state

    # II.6 margin
    ok, why = margin_ok(equity, margin_used)
    if not ok:
        return RiskDecision(False, why, lots, max_vol, max_pos), state

    return d, state


def record_trade_result(pl: float, now: Optional[datetime] = None,
                        state: Optional[RiskState] = None) -> RiskState:
    """Call on every closed trade so the streak breakers actually see results."""
    now = now or datetime.now(IST)
    state = state or load_state()
    if pl < 0:
        state.consecutive_losses += 1
        state.day_losing_trades += 1
        if state.consecutive_losses >= CONSEC_LOSSES_STOP_DAY:
            state.day_stopped_date = now.date().isoformat()
            msg = f"CIRCUIT BREAKER: {state.consecutive_losses} consecutive losses -- stopped for the day."
            log.warning(msg)
            from src.core import alerts
            alerts.send(f"🛑 CIRCUIT BREAKER TRIPPED 🛑\n{msg}", severity=alerts.CRITICAL)
        elif state.consecutive_losses >= CONSEC_LOSSES_PAUSE:
            state.pause_until_ts = (now + timedelta(hours=CONSEC_LOSS_PAUSE_HOURS)).timestamp()
            msg = (f"CIRCUIT BREAKER: {state.consecutive_losses} consecutive losses -- "
                   f"pausing new entries {CONSEC_LOSS_PAUSE_HOURS}h.")
            log.warning(msg)
            from src.core import alerts
            alerts.send(f"⚠️ CIRCUIT BREAKER ⚠️\n{msg}", severity=alerts.WARN)
    else:
        state.consecutive_losses = 0
    return state


# ---------------------------------------------------------------------------
# II.5 -- profit ring-fencing (advisory: flags the milestone, human moves funds)
# ---------------------------------------------------------------------------

def ring_fence_due(balance: float, state: Optional[RiskState] = None) -> Tuple[Optional[float], RiskState]:
    """Returns (amount_to_ring_fence, state) when a milestone is newly crossed."""
    state = state or load_state()
    hit = list(state.milestones_hit)
    targets = list(RING_FENCE_MILESTONES)
    if balance > RING_FENCE_MILESTONES[-1]:
        n = int((balance - RING_FENCE_MILESTONES[-1]) // RING_FENCE_STEP_ABOVE)
        targets += [RING_FENCE_MILESTONES[-1] + RING_FENCE_STEP_ABOVE * (i + 1) for i in range(n)]
    due = [t for t in targets if balance >= t and t not in hit]
    if not due:
        return None, state
    milestone = max(due)
    state.milestones_hit = hit + due
    return round((balance - milestone) * RING_FENCE_FRACTION + milestone * 0.0, 2) or None, state
