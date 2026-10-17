"""Execution-realistic simulator for the Ultra Core live loop.

The engine's job is to reproduce what `src/core/main_loop.py` would have done,
bar for bar, using the same strategy and risk modules the live bot imports. It
does not re-implement entry rules, stop maths, sizing or trailing -- it calls
them.

Three things it models that the previous backtests did not:

1. **The live scan cadence.** `main_loop` sleeps 60s and re-reads the same closed
   M15 candle for fifteen minutes. With `dedup=False` (the behaviour at HEAD)
   the engine re-fires that unchanged signal exactly as production does, which
   is what produced the duplicate live fills 57-61 seconds apart.

2. **The live history window.** `main_loop` hands strategies exactly 250 M15
   bars, so `ema200` is read about a quarter of the way through its warm-up. The
   engine slices the same 250-bar window rather than passing full history, so
   the simulated indicator equals the live indicator. `history_bars` can be
   raised to measure what that truncation costs.

3. **Intrabar order.** Stop-versus-target on the same bar is resolved by walking
   M1 sub-bars, not by assuming. Where M1 is unavailable the trade is flagged
   `intrabar_ambiguous` and resolved stop-first, so ambiguity is counted instead
   of hidden.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from src.backtesting.costs import CostModel
from src.backtesting.data import BarSet, SymbolSpec
from src.core import risk_rules as _rr
from src.core.sizing_ladder import SizingLadder as _SizingLadder
from src.research.market_study import atr as _flat_atr
import src.core.market_hours as market_hours

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1


def _tod_atr_expanding_state(m15: np.ndarray, bucket_minutes: int, period: int,
                              min_samples: int) -> Dict[str, Any]:
    """Point-in-time-safe precompute for the `use_time_of_day_atr` flag.

    2026-09-25 audit finding, fixed here: `time_of_day_atr()` in
    market_study.py is an intentional whole-sample diagnostic (its own
    docstring: "nothing calls it yet"). This engine used to call it once on
    `self.m15` -- the *entire* backtest window -- at the start of run() and
    reuse that single lookup table for every decision point, so a trade in
    month 1 had its stop scaled partly by month 24's volatility. That is
    leakage: any result produced with this flag on could not be reproduced
    live.

    This precomputes, per hour-of-day bucket, an *expanding* running mean of
    ATR ordered by time, plus an expanding overall mean, so a query "as of
    timestamp T" only ever averages bars with time <= T.
    """
    flat = _flat_atr(m15, period)
    times = m15["time"].astype(np.int64)
    n_buckets = 1440 // bucket_minutes

    minute_of_day = np.array([
        (lambda d: d.hour * 60 + d.minute)(
            datetime.fromtimestamp(int(t), tz=timezone.utc).astimezone(IST)
        )
        for t in times
    ])
    bucket = (minute_of_day // bucket_minutes).astype(np.int64)
    valid = ~np.isnan(flat)
    safe = np.where(valid, flat, 0.0)

    cum_sum = np.cumsum(safe)
    cum_cnt = np.cumsum(valid.astype(np.int64))
    with np.errstate(invalid="ignore", divide="ignore"):
        overall_expanding = np.where(cum_cnt > 0, cum_sum / np.maximum(cum_cnt, 1), np.nan)

    per_bucket_times: List[np.ndarray] = []
    per_bucket_mean: List[np.ndarray] = []
    for b in range(n_buckets):
        idx = np.where(bucket == b)[0]
        if len(idx) == 0:
            per_bucket_times.append(np.array([], dtype=np.int64))
            per_bucket_mean.append(np.array([], dtype=float))
            continue
        vb = valid[idx]
        fb = np.where(vb, flat[idx], 0.0)
        cs = np.cumsum(fb)
        cc = np.cumsum(vb.astype(np.int64))
        with np.errstate(invalid="ignore", divide="ignore"):
            mean_b = np.where(cc >= min_samples, cs / np.maximum(cc, 1), np.nan)
        per_bucket_times.append(times[idx])
        per_bucket_mean.append(mean_b)

    return {
        "times": times,
        "overall_expanding": overall_expanding,
        "bucket_minutes": bucket_minutes,
        "per_bucket_times": per_bucket_times,
        "per_bucket_mean": per_bucket_mean,
    }


def _tod_atr_ratio_as_of(state: Dict[str, Any], ist_bucket: int, as_of_ts: int) -> float:
    """Ratio for one bucket using only data with time <= as_of_ts. 1.0 if unknown."""
    times = state["times"]
    idx = int(np.searchsorted(times, as_of_ts, side="right")) - 1
    if idx < 0:
        return 1.0
    overall = state["overall_expanding"][idx]
    if not (overall == overall) or overall == 0:
        return 1.0

    bt = state["per_bucket_times"][ist_bucket]
    bm = state["per_bucket_mean"][ist_bucket]
    if len(bt) == 0:
        return 1.0
    bidx = int(np.searchsorted(bt, as_of_ts, side="right")) - 1
    if bidx < 0:
        return 1.0
    bucket_mean = bm[bidx]
    if not (bucket_mean == bucket_mean):
        return 1.0
    return float(bucket_mean / overall)


# ---------------------------------------------------------------------------
# MT5 stub -- lets the real RiskManager run without a terminal
# ---------------------------------------------------------------------------


class _Mt5Stub:
    """Minimal stand-in for the MetaTrader5 module.

    `RiskManager` reads `account_info().balance` for sizing and `symbol_info()`
    for contract terms. Feeding it a stub is what allows the engine to call the
    production sizing code instead of copying its formula.
    """

    ORDER_TYPE_BUY = ORDER_TYPE_BUY
    ORDER_TYPE_SELL = ORDER_TYPE_SELL

    def __init__(self, spec: SymbolSpec):
        self._spec = spec
        self.balance = 0.0

    def account_info(self):
        return SimpleNamespace(balance=self.balance, equity=self.balance)

    def symbol_info(self, symbol: str):
        s = self._spec
        return SimpleNamespace(
            volume_min=s.volume_min,
            volume_max=s.volume_max,
            volume_step=s.volume_step,
            trade_tick_size=s.trade_tick_size,
            trade_tick_value=s.trade_tick_value,
            digits=s.digits,
            point=s.point,
            spread=0,
        )


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass
class Position:
    ticket: int
    strategy: str
    magic: int
    is_buy: bool
    lots: float
    entry_price: float
    entry_time: int
    sl: float
    tp: float
    atr_at_entry: float
    session: str
    is_pyramid: bool = False
    initial_sl: float = 0.0
    trail_active: bool = False
    mfe_price: float = 0.0
    mae_price: float = 0.0
    minutes_open: int = 0
    minutes_to_mfe: int = 0
    price_current: float = 0.0
    intrabar_ambiguous: bool = False
    duplicate_of: Optional[int] = None
    # live-parity bookkeeping (unused unless the matching EngineConfig flag is on)
    scan_ts: int = 0        # M1-bar stamp of the scan that opened this position
    delay_sec: int = 0      # entry_delay_sec in force when it opened
    hit_frac: float = 0.5   # where in its exit minute the stop/target was crossed (0..1)

    @property
    def type(self) -> int:
        """Named to match the MT5 position object RiskManager expects."""
        return ORDER_TYPE_BUY if self.is_buy else ORDER_TYPE_SELL

    @property
    def price_open(self) -> float:
        """Alias so the production RiskManager can read this like an MT5 position."""
        return self.entry_price


@dataclass
class Trade:
    ticket: int
    strategy: str
    is_buy: bool
    lots: float
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    sl: float
    tp: float
    initial_sl: float
    atr_at_entry: float
    session: str
    exit_reason: str
    gross_pl: float
    commission: float
    net_pl: float
    r_multiple: float
    mae_price: float
    mfe_price: float
    mae_r: float
    mfe_r: float
    minutes_open: int
    minutes_to_mfe: int
    is_pyramid: bool
    duplicate_of: Optional[int]
    intrabar_ambiguous: bool
    balance_after: float
    # Overnight financing. Defaulted so anything that built a Trade before swap
    # existed keeps working; the engine always populates them.
    swap: float = 0.0
    nights_held: int = 0


@dataclass
class EngineConfig:
    """Every switch that changes results is recorded here and hashed into the run
    manifest, so a number can always be traced back to the assumptions behind it."""

    symbol: str = "XAUUSDm"
    starting_balance: float = 105.74
    risk_pct: float = 0.02

    # Live-loop fidelity
    history_bars: int = 250          # M15 bars main_loop hands strategies
    m5_history_bars: int = 100
    d1_history_bars: int = 50
    loop_interval_sec: int = 60
    resignal_interval_sec: int = 300  # strategies re-evaluated on M5 boundaries

    # Behaviour switches (defaults reproduce the VALIDATED live config -- see
    # main_loop.py ENABLE_TRAILING / ENABLE_PYRAMIDING and the A/B test at
    # lines 82-96 proving both are net-negative at PF 0.592 / -$93.59).
    # P0-3 fix: dedup_per_candle default set to True so the backtest engine
    # reproduces live deduplication (at most one order per strategy per candle).
    dedup_per_candle: bool = True
    max_concurrent: int = 2           # live validated with 2 concurrent positions
    max_same_direction: int = 2
    enable_pyramiding: bool = False   # net-negative; see main_loop.py ENABLE_PYRAMIDING
    enable_consolidation_exit: bool = True
    enable_trailing: bool = False     # net-negative; see main_loop.py ENABLE_TRAILING
    close_only_trail: bool = False  # Ignore wicks, check trailing stop only at candle close
    enable_d1_bias_gate: bool = True
    # Direction gate variant (rohith-2 research). "d1_ema20" reproduces HEAD.
    #   "d1_ema20"     : daily close vs D1 EMA20 (current live)
    #   "d1_ema10"     : faster daily
    #   "structure"    : BigBeluga M15 structure trend (src/research/structure.py)
    #   "both"         : d1_ema20 AND M15 structure must agree
    #   "d1_proximity" : d1_ema20, BUT allow both directions when the D1 close is
    #                    within gate_prox_atr * D1_ATR14 of the EMA20 (transition
    #                    zone -- the "macro might be flipping" case)
    #   "h4_structure" : structure trend on H4 bars (needs H4 data)
    #   "d1_choch"     : d1_ema20, BUT allow a counter-daily trade if an H4
    #                    structure flip (CHoCH) fired in that direction within
    #                    the last choch_lookback_h4 H4 bars
    # Only consulted when enable_d1_bias_gate is True.
    direction_gate: str = "d1_ema20"
    d1_ema_period: int = 20
    structure_len: int = 10
    gate_prox_atr: float = 0.5
    choch_lookback_h4: int = 3
    # Breakeven exit: once a position's favourable excursion reaches
    # be_trigger_atr * entry-ATR, move its stop ONCE to entry + be_offset_atr*ATR
    # (a losing near-miss then exits ~flat instead of at the full stop). 0 = off.
    be_trigger_atr: float = 0.0
    be_offset_atr: float = 0.1
    # Equity-curve pause: stop OPENING new trades when balance falls more than
    # equity_pause_dd below its running peak; resume when it recovers to within
    # equity_resume_dd of the peak. Open positions keep their stops. 0 = off.
    # A "the strategy has stopped working, stand down" rule that needs no
    # external data. Tested rohith-2 iter 4 against the 4-year regime swings.
    equity_pause_dd: float = 0.0
    equity_resume_dd: float = 0.0
    spread_gate_points: float = 350.0
    spread_gate_blocks_management: bool = True   # HIGH-7: the bug at HEAD
    lot_cap: Optional[float] = None              # the lost 0.01 guard
    daily_loss_limit_mode: str = "balance_pct"   # matches live RiskManager: DAILY_LOSS_LIMIT_PCT fraction of balance
    daily_loss_limit_pct: float = 0.06
    load_macro_rules: bool = False               # markdown-driven bias, off for reproducibility

    # Coarse-mode realism: test a new position against its own entry bar.
    walk_entry_bar_coarse: bool = True

    warmup_bars: int = 260
    min_tradeable_balance: float = 5.0
    # Margin. Verified live: leverage 200 on XAUUSDm, contract 100 oz, so one
    # 0.01-lot position at $4,428 locks (100 * 4428 * 0.01) / 200 = $22.14. On a
    # $105.74 account that is a hard cap of four concurrent positions before
    # margin is exhausted -- a binding constraint no prior backtest enforced.
    leverage: float = 200.0
    enforce_margin: bool = True
    margin_call_level_pct: float = 100.0  # free margin must stay >= 0 at entry
    # "live" runs production sizing (compounding, and at 15% it self-destructs).
    # "fixed" holds lots constant so a strategy's edge can be measured without
    # the sizing spiral swamping it. Edge and survivability are separate questions.
    sizing_mode: str = "live"
    # Exit-geometry overrides, applied to the RiskManager module for the run.
    # None keeps the production constant. These are the parameters Phase 13
    # exit research varies; they are recorded in the manifest like everything else.
    tp_atr_mult: Optional[float] = None
    # Structural take-profit (2026-09-09, owner request -- "snap TP to the swing
    # level instead of a fixed ATR distance"). When True, at entry the TP is
    # pulled IN to just before the nearest CONFIRMED BigBeluga swing pivot in
    # the trade's direction (structure.compute on the same backward-looking
    # m15_view -- confirmation is already lag-shifted, no lookahead). Bounds:
    # the structural TP is only used when its distance is in
    # [structural_tp_min_atr * ATR, static ATR TP distance) -- i.e. it can only
    # ever bring the target closer, never reach further through open air. If no
    # pivot sits between entry and the ATR target, TP is unchanged. SL is never
    # touched, so this isolates the TP variable.
    structural_tp: bool = False
    structural_tp_len: int = 10
    structural_tp_buffer_atr: float = 0.1
    structural_tp_min_atr: float = 1.0
    trail_activation_atr: Optional[float] = None
    trail_distance_atr: Optional[float] = None
    sl_atr_mult_override: Optional[float] = None
    fixed_lots: float = 0.01
    # Phase 2 found flat ATR14 mis-sizes stops by 1.05x-1.95x depending on
    # session, worst in LATE/POSTNY -- exactly where Phase 1 said the account
    # could afford the tightest stops. Opt-in: when True, the stop distance is
    # the flat ATR rescaled by that hour-bucket's historical ratio to the
    # overall mean, instead of the raw flat ATR14. src/core/risk_manager.py
    # itself is untouched; this only patches the engine's own RiskManager
    # instance for the duration of one backtest run.
    use_time_of_day_atr: bool = False
    tod_atr_bucket_minutes: int = 60

    # ------------------------------------------------------------------
    # LIVE-PARITY switches (2026-10-17). Every flag below defaults OFF so the
    # results of every existing backtest, and tests/test_engine_gold_regression.py,
    # are unchanged. Each models one piece of what the live demo bot
    # (src/core/main_loop.py + scripts/protect_profit.py) actually did that the
    # engine did not. `live_parity=True` (or EngineConfig.live_parity_preset())
    # switches all of them on at once; see each flag's comment for its source.
    # ------------------------------------------------------------------
    live_parity: bool = False

    # main_loop._execute_signal ordering: live applies Highlander FIRST and only
    # then the execution gates (market hours, strategy spread cap, concurrency,
    # risk_rules, ladder veto), and marks the candle fired whether or not the
    # order went through (main_loop.py ~L544-557: `last_fired_candle[...] =
    # signal_candle` after _execute_signal, which returns None on any block).
    # The legacy engine pre-filters on caps and retries every minute.
    live_exec_order: bool = False

    # (1) src/core/risk_rules.py semantics, ENFORCE=True: early-phase (<$400)
    # daily cap 3% of day-start equity + max 2 losing trades/day, 3 straight
    # losses -> 4h pause, 5 -> stop the day, weekly 15%, monthly 25%, peak-DD
    # 30% hard halt. Uses the module's own evaluate()/_roll_anchors() on the
    # engine's simulated balance/equity/time; record_trade_result() is
    # re-implemented (its alerts.send side effect must not fire from a backtest).
    risk_rules_enforce: bool = False
    # Epoch seconds. 0 = block from the start. >0 = the state machine always
    # runs (shadow mode, as live did while risk_rules.ENFORCE was False) but only
    # BLOCKS entries at/after this instant. The live bot ran ENFORCE=False until
    # the 2026-10-12 05:55 IST restart (commit 6a27858, 2026-10-11).
    risk_rules_enforce_from_ts: int = 0

    # (2) main_loop.py L448-451: no strategy evaluation while
    # RiskManager.get_session_name(now_ist) == "LONDON_NY_OVERLAP" (15:30-17:30
    # IST); open positions are still managed.
    skip_overlap_session: bool = False

    # (3) main_loop._execute_signal L759-765: a strategy carrying
    # `max_spread_pts` (the FVG leg: 250) is blocked at entry when the current
    # spread exceeds it.
    enforce_strategy_max_spread: bool = False

    # (4) ExecutionHandler.send_order: SizingLadder.get_sizing(balance) sets the
    # lot size (ignoring the caller's) and PreTradeVeto layers 1-4 apply
    # (balance floor $50, ENFORCE'd weekly/monthly/pause breakers, ladder
    # concurrency <$100: 1, $100-800: 2/3, exposure caps), then the legacy
    # MAX_CONCURRENT_POSITIONS / MAX_SAME_DIRECTION_POSITIONS checks.
    sizing_ladder_caps: bool = False
    # The ladder table the live bot actually carried changed over time (commit
    # d9c219e, 2026-10-13 22:47 IST, made $100-200 two positions instead of one;
    # live picked it up at the 2026-10-14 22:24 restart). None = the table in
    # src/core/sizing_ladder.py as it is now. Otherwise a list of
    # (effective_from_epoch, ((threshold, lots, max_concurrent, max_exposure), ...)).
    sizing_ladder_schedule: Optional[List[Tuple[int, Tuple[Tuple[float, float, int, float], ...]]]] = None

    # (5) main_loop.py L408-439: D1 EMA20 bias from the LAST CLOSED daily bar,
    # then overridden by the FORMING daily bar if |close-open| >= mult * median
    # |diff| of the last 15 D1 closes (forming bar included). The forming bar is
    # rebuilt from M1 data up to the decision minute, per scan.
    # NOTE: the live code said 2.0 until commit 20335dd (2026-10-16 16:10 IST)
    # and 1.0 since; the bot traded 2026-10-05..15 on 2.0.
    d1_intraday_override: bool = False
    d1_intraday_override_mult: float = 1.0

    # (6) scripts/protect_profit.py (separate process, polls every 20s): closes
    # a GREEN position (profit >= MIN_GREEN) on (a) giveback: peak >= GIVEBACK_PEAK
    # and profit <= GIVEBACK_FLOOR, or (b) a clean M15 reversal checked once per
    # new M15 bar (clean_reversal_against), then blocks that leg from re-entering
    # for COOLDOWN_MIN minutes (main_loop._leg_in_cooldown). Constants mirror
    # protect_profit.py L32-35 (a unit test pins them to the script).
    protect_profit: bool = False
    protect_giveback_peak: float = 6.0
    protect_giveback_floor: float = 1.0
    protect_min_green: float = 0.5
    protect_cooldown_min: int = 45

    # (7) Entry timing. Live scans every 60s (~20s past the minute at start,
    # then drifting), so an entry fills 0-60s after the M15 close at the
    # then-current ask/bid. `entry_delay_sec` fills at the price interpolated
    # `entry_delay_sec` seconds into the first M1 bar after the close. 0 = legacy
    # (fill at that bar's open). Must be in [0, 60).
    entry_delay_sec: int = 0

    # main_loop.py L340-345 Gate 1b: no new entries within +-NEWS_BLACKOUT_MINUTES
    # of a tier-1 event (src/core/news_filter.py); management continues.
    news_blackout: bool = False

    # main_loop._record_closed_trades only learns of a close when the position
    # was seen open on a previous loop: a position that opens and closes inside
    # one 60s scan interval never reaches risk_rules.record_trade_result (seen on
    # 2026-10-12: the 18:15:39 FVG entry stopped out at 18:16:13 and the
    # day_losing_trades counter stayed 0). Midpoint rule on 1-min bars.
    streak_blind_spot: bool = False

    # Downtime / retirement windows: {strategy_name or "*": [(start_ts, end_ts)]}.
    # Inside a window that strategy is not evaluated ("*" = the whole bot is down:
    # no evaluation, no entries, no management, no protect_profit; the special key
    # "@protect_profit" = only the profit-protection watcher is not running).
    # Broker-side SL/TP keep working. Epoch seconds, [start, end).
    disabled_windows: Optional[Dict[str, List[Tuple[int, int]]]] = None

    # Record one row per signal decision in BacktestResult.diagnostics["decisions"]
    # (for reconciliation reports). Not a behaviour switch.
    record_decisions: bool = False

    def __post_init__(self) -> None:
        if self.live_parity:
            for f in _PARITY_FLAGS:
                setattr(self, f, True)
            # live main_loop calls _manage_open_positions on the spread-gate branch
            self.spread_gate_blocks_management = False
            # live sizing is the ladder's fixed 0.01 (ladder flag also sets lots)
            self.sizing_mode = "fixed"
            self.fixed_lots = 0.01
            self.entry_delay_sec = LIVE_SCAN_PHASE_SEC

    @classmethod
    def live_parity_preset(cls, **overrides: Any) -> "EngineConfig":
        """All live-parity flags on, then `overrides` applied on top."""
        cfg = cls(live_parity=True)
        for k, v in overrides.items():
            if not hasattr(cfg, k):
                raise TypeError(f"unknown EngineConfig field {k!r}")
            setattr(cfg, k, v)
        return cfg

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


# Flags that `live_parity=True` switches on.
_PARITY_FLAGS = (
    "live_exec_order", "risk_rules_enforce", "skip_overlap_session",
    "enforce_strategy_max_spread", "sizing_ladder_caps", "d1_intraday_override",
    "protect_profit", "news_blackout", "streak_blind_spot",
)

# Calibrated from broker history (scripts/validation/reconcile_live_parity.py):
# median seconds between an M15 close and the live fill on trades that filled on
# the first scan after the close. Reported by the reconcile script on every run.
LIVE_SCAN_PHASE_SEC = 30


@dataclass
class BacktestResult:
    trades: List[Trade]
    equity: List[Tuple[int, float]]
    config: Dict[str, Any]
    data_hash: str
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class BacktestEngine:
    def __init__(self, bars: BarSet, cost: CostModel, config: EngineConfig):
        self.bars = bars
        self.cost = cost
        self.cfg = config
        self.spec = bars.spec

        self.m15 = bars.m15
        self.m5 = bars.m5
        self.m1 = bars.m1
        self.d1 = bars.d1
        self.h4 = getattr(bars, "h4", None)

        self._m15_t = self.m15["time"].astype(np.int64)
        self._m5_t = self.m5["time"].astype(np.int64) if self.m5 is not None else None
        self._m1_t = self.m1["time"].astype(np.int64) if self.m1 is not None else None
        self._d1_t = self.d1["time"].astype(np.int64) if self.d1 is not None else None
        self._h4_t = self.h4["time"].astype(np.int64) if self.h4 is not None else None

        self.stub = _Mt5Stub(self.spec)
        self.balance = config.starting_balance
        self.stub.balance = self.balance

        self._ticket = 1
        self.positions: List[Position] = []
        self.trades: List[Trade] = []
        self.equity: List[Tuple[int, float]] = []
        self.diag: Dict[str, Any] = {
            "signals_generated": 0,
            "signals_deduped": 0,
            "entries_blocked_caps": 0,
            "entries_blocked_spread": 0,
            "entries_blocked_d1_bias": 0,
            "duplicate_entries": 0,
            "pyramid_entries": 0,
            "ambiguous_bars": 0,
            "management_skipped_spread": 0,
            "daily_shutdowns": 0,
            "bars_without_m1": 0,
            "entries_blocked_insufficient_equity": 0,
            "entries_blocked_margin": 0,
            "same_candle_refires": 0,
            "swap_nights_charged": 0,
            "swap_paid": 0.0,
        }
        # live-parity state (inert unless the matching EngineConfig flag is on)
        if config.entry_delay_sec < 0 or config.entry_delay_sec >= 60:
            raise ValueError("entry_delay_sec must be in [0, 60)")
        self.rr_state = _rr.RiskState()
        self.cooldown_until: Dict[str, int] = {}
        self.decisions: List[Dict[str, Any]] = []
        self._down_windows: Dict[str, List[Tuple[int, int]]] = {
            k: sorted(v) for k, v in (config.disabled_windows or {}).items()
        }

    def seed_risk_state(self, **fields: Any) -> None:
        """Pre-load risk_rules.RiskState (e.g. peak equity / week & month anchors
        carried in from before the replay window)."""
        for k, v in fields.items():
            if not hasattr(self.rr_state, k):
                raise TypeError(f"unknown RiskState field {k!r}")
            setattr(self.rr_state, k, v)

    # -- live-parity helpers -----------------------------------------------

    def _is_down(self, name: str, ts: int) -> bool:
        """True when `name` (or the whole bot, key "*") is disabled at `ts`."""
        if not self._down_windows:
            return False
        for key in ("*", name):
            for a, b in self._down_windows.get(key, ()):
                if a <= ts < b:
                    return True
        return False

    def _decide(self, ts: int, name: str, is_buy: bool, outcome: str) -> None:
        if self.cfg.record_decisions:
            self.decisions.append({"ts": int(ts), "strategy": name,
                                   "dir": "BUY" if is_buy else "SELL", "outcome": outcome})

    def _forming_d1(self, ts: int) -> Optional[Tuple[float, float, float, float]]:
        """(open, high, low, close) of the still-forming daily bar at `ts`, built
        from M1 (M15 when M1 is missing). Broker day = UTC midnight (verified:
        Exness server runs UTC+0). Close is the bar open at `ts`, i.e. the price
        the live bot would read from copy_rates_from_pos(D1)[-1] at that scan."""
        day0 = ts - (ts % 86400)
        for arr, times, step in ((self.m1, self._m1_t, 60), (self.m15, self._m15_t, 900)):
            if arr is None or times is None:
                continue
            lo = int(np.searchsorted(times, day0, side="left"))
            # only bars that have fully closed by `ts` (no look-ahead)
            hi = int(np.searchsorted(times, ts - step, side="right"))
            if hi <= lo:
                continue
            seg = arr[lo:hi]
            last_close = float(seg["close"][-1])
            return (float(seg["open"][0]), float(seg["high"].max()),
                    float(seg["low"].min()), last_close)
        return None

    def _live_d1_bias(self, d1_view: np.ndarray, ts: int) -> Optional[str]:
        """Re-implementation of main_loop.py L387-439 on the engine's D1 view.

        Bias = last CLOSED bar ([-2]) vs EMA20 at [-2]; then the forming bar
        ([-1], rebuilt from M1 as of `ts`) overrides it when its |close-open| is
        >= mult * median(|diff(closes[-15:])|) and points the other way.
        """
        if d1_view is None or len(d1_view) < 21:
            return None
        closes = np.array(d1_view["close"], dtype=float)
        opens = np.array(d1_view["open"], dtype=float)
        forming = self._forming_d1(ts)
        if forming is not None:
            opens[-1], closes[-1] = forming[0], forming[3]
        ema = _ema(closes, 20)
        if np.isnan(ema[-2]):
            return None
        bias = "BULLISH" if closes[-2] > ema[-2] else "BEARISH"
        if len(closes) >= 15:
            arr = np.abs(np.diff(closes[-15:]))
            atr = float(np.median(arr)) if len(arr) else 0.0
            move = closes[-1] - opens[-1]
            if atr > 0 and abs(move) / atr >= self.cfg.d1_intraday_override_mult:
                intraday = "BULLISH" if move > 0 else "BEARISH"
                if intraday != bias:
                    self.diag["d1_intraday_overrides"] = self.diag.get("d1_intraday_overrides", 0) + 1
                    bias = intraday
        return bias

    # -- helpers ---------------------------------------------------------

    def _next_ticket(self) -> int:
        t = self._ticket
        self._ticket += 1
        return t

    def _value_per_price(self, lots: float) -> float:
        return self.spec.value_per_price_unit_per_lot * lots

    # -- margin ----------------------------------------------------------

    def margin_required(self, lots: float, price: float) -> float:
        """Initial margin for `lots` at `price`, in account currency.

        Forex-style margin: notional / leverage. On XAUUSDm the notional of one
        lot is 100 oz * price, so 0.01 lot at $4,428 needs $22.14 at 1:200.
        """
        lev = self.cfg.leverage
        if not lev or lev <= 0:
            return 0.0
        return self.spec.contract_size * price * lots / lev

    def used_margin(self) -> float:
        """Margin locked by open positions, booked at each position's open price."""
        return sum(self.margin_required(p.lots, p.entry_price) for p in self.positions)

    def floating_pl(self) -> float:
        return sum(
            (p.price_current - p.entry_price) * (1.0 if p.is_buy else -1.0)
            * self._value_per_price(p.lots)
            for p in self.positions
        )

    def free_margin(self) -> float:
        """Equity minus locked margin. Equity includes floating P&L, as MT5 does."""
        return (self.balance + self.floating_pl()) - self.used_margin()

    def _margin_allows(self, lots: float, price: float) -> bool:
        if not self.cfg.enforce_margin:
            return True
        return self.free_margin() >= self.margin_required(lots, price)

    def _forming_bar(self, arr: np.ndarray, last_closed_idx: int, next_time: int) -> np.ndarray:
        """Build the partially-formed bar the live bot sees at index [-1].

        At the instant a bar closes, the next bar has zero elapsed time, so its
        OHLC all sit at the previous close. Passing the real, fully-formed next
        bar here would leak the future into every strategy that reads [-1].
        """
        b = arr[last_closed_idx].copy()
        c = float(arr[last_closed_idx]["close"])
        b["time"] = next_time
        b["open"] = b["high"] = b["low"] = b["close"] = c
        b["tick_volume"] = 0
        if "real_volume" in b.dtype.names:
            b["real_volume"] = 0
        return b

    def _view(self, arr: np.ndarray, times: np.ndarray, cutoff: int, count: int,
              step_sec: int) -> Optional[np.ndarray]:
        """Bars visible at `cutoff` (a bar-close timestamp), shaped like a live fetch.

        Returns `count` bars where [-1] is the freshly-opened forming bar and
        [-2] is the last closed bar -- exactly the layout `copy_rates_from_pos`
        gives the live loop.
        """
        # last bar whose close time is <= cutoff
        idx = int(np.searchsorted(times, cutoff - step_sec, side="right")) - 1
        if idx < 0:
            return None
        start = idx - (count - 2)
        if start < 0:
            return None
        closed = arr[start: idx + 1]
        forming = self._forming_bar(arr, idx, cutoff)
        return np.concatenate([closed, np.array([forming], dtype=arr.dtype)])

    def _m1_slice(self, start_ts: int, end_ts: int) -> Optional[np.ndarray]:
        if self.m1 is None or self._m1_t is None:
            return None
        lo = int(np.searchsorted(self._m1_t, start_ts, side="left"))
        hi = int(np.searchsorted(self._m1_t, end_ts, side="left"))
        if hi <= lo:
            return None
        return self.m1[lo:hi]

    # -- risk plumbing ---------------------------------------------------

    def _make_risk_manager(self):
        """Instantiate the production RiskManager against the stub terminal."""
        import src.core.risk_manager as rm_mod

        rm_mod.mt5 = self.stub  # type: ignore[assignment]

        # Exit geometry lives in module-level constants, so a sweep has to set
        # them here. Restored by the caller is unnecessary -- each run builds its
        # own engine -- but the values are echoed into the manifest.
        if self.cfg.tp_atr_mult is not None:
            rm_mod.TP_ATR_MULTIPLIER = self.cfg.tp_atr_mult
        if self.cfg.trail_activation_atr is not None:
            rm_mod.TRAIL_ACTIVATION_ATR = self.cfg.trail_activation_atr
        if self.cfg.trail_distance_atr is not None:
            rm_mod.TRAIL_DISTANCE_ATR = self.cfg.trail_distance_atr

        rm = rm_mod.RiskManager(self.cfg.symbol)
        if not self.cfg.load_macro_rules:
            rm._strict_short_stops = False

        if self.cfg.use_time_of_day_atr:
            bucket_minutes = self.cfg.tod_atr_bucket_minutes
            tod_state = _tod_atr_expanding_state(
                self.m15, bucket_minutes=bucket_minutes, period=14, min_samples=20
            )
            flat_get_latest_atr = rm.get_latest_atr

            def _tod_get_latest_atr(m15_rates, period: int = 14):
                flat = flat_get_latest_atr(m15_rates, period)
                if flat is None:
                    return None
                # [-1] is the synthesized forming bar (see _forming_bar/_view);
                # its timestamp gives the current hour-of-day bucket. The ATR
                # value itself came from the last *closed* bar at [-2], so the
                # ratio must be looked up as of that bar's time, not the whole
                # backtest window (see _tod_atr_expanding_state docstring).
                now_ts = int(m15_rates["time"][-1])
                closed_ts = int(m15_rates["time"][-2])
                ist_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc).astimezone(IST)
                b = int((ist_dt.hour * 60 + ist_dt.minute) // bucket_minutes)
                r = _tod_atr_ratio_as_of(tod_state, b, closed_ts)
                return flat * r

            rm.get_latest_atr = _tod_get_latest_atr

        return rm, rm_mod

    def _session_multiplier(self, rm, ist: datetime) -> float:
        """SL multiplier for one decision instant.

        `sl_atr_mult_override` was declared in EngineConfig but wired to nothing
        (Phase 0 COR-004) -- setting it silently did no work at all. It is the
        only way to test stop distances other than the live session default,
        which Phase 1 showed is far too wide for a $100 account at current
        volatility. Kept as its own method so a test can pin the wiring.
        """
        if self.cfg.sl_atr_mult_override is not None:
            return float(self.cfg.sl_atr_mult_override)
        return float(rm.get_session_multiplier(ist))

    def _patch_strategy_mt5(self, strategies: Sequence[Any]) -> None:
        import src.strategies.base_strategy as base_mod

        base_mod.mt5 = self.stub  # type: ignore[assignment]
        for s in strategies:
            mod = __import__(s.__module__, fromlist=["mt5"])
            if hasattr(mod, "mt5"):
                mod.mt5 = self.stub

    # -- position lifecycle ----------------------------------------------

    def _open(self, strategy_name: str, magic: int, is_buy: bool, fill_price: float,
              ts: int, rm, m15_view: np.ndarray, session_mult: float, session: str,
              duplicate_of: Optional[int] = None, is_pyramid: bool = False,
              sl_atr_mult: Optional[float] = None,
              tp_atr_mult: Optional[float] = None,
              lots_override: Optional[float] = None) -> Optional[Position]:
        # Per-strategy exit geometry (rohith phase 3 portfolio_v4 legs). Mirrors
        # main_loop._execute_signal exactly: a strategy carrying its own
        # sl_atr_mult/tp_atr_mult overrides the session-default multiplier and
        # the shared TP_ATR_MULTIPLIER constant for this order only. A strategy
        # without these attributes (or with sl_atr_mult falsy) falls back to the
        # prior session_mult/global-TP behaviour unchanged.
        sl_mult = sl_atr_mult or session_mult
        stops = rm.calculate_atr_stops(fill_price, is_buy, m15_view, sl_mult, tp_atr_mult)
        if stops is None:
            return None

        if self.cfg.structural_tp and stops.atr > 0:
            self._apply_structural_tp(stops, fill_price, is_buy, m15_view)

        # A real account cannot open anything once equity is gone. Without this
        # the sizer keeps returning the broker minimum on a negative balance and
        # the equity curve runs off into fiction.
        if self.balance <= self.cfg.min_tradeable_balance:
            self.diag["entries_blocked_insufficient_equity"] += 1
            return None

        self.stub.balance = self.balance
        if self.cfg.sizing_mode == "fixed":
            lots = self.cfg.fixed_lots
        else:
            lots = rm.calculate_dynamic_lot_size(fill_price, stops.sl,
                                                 risk_pct=self.cfg.risk_pct)
            if self.cfg.lot_cap is not None:
                lots = min(lots, self.cfg.lot_cap)
        if lots_override is not None:
            lots = lots_override       # live ignores the caller's size (SizingLadder)
        if lots <= 0:
            return None

        # A real terminal rejects the order outright once free margin is gone
        # ("no money"). Without this the engine happily runs more concurrent
        # positions than the account could ever have carried.
        if not self._margin_allows(lots, fill_price):
            self.diag["entries_blocked_margin"] += 1
            return None

        pos = Position(
            ticket=self._next_ticket(),
            strategy=strategy_name,
            magic=magic,
            is_buy=is_buy,
            lots=lots,
            entry_price=fill_price,
            entry_time=ts,
            sl=stops.sl,
            tp=stops.tp,
            initial_sl=stops.sl,
            atr_at_entry=stops.atr,
            session=session,
            is_pyramid=is_pyramid,
            mfe_price=fill_price,
            mae_price=fill_price,
            price_current=fill_price,
        )
        pos.duplicate_of = duplicate_of
        self.positions.append(pos)
        if duplicate_of is not None:
            self.diag["duplicate_entries"] += 1
        if is_pyramid:
            self.diag["pyramid_entries"] += 1
        return pos

    def _apply_structural_tp(self, stops, fill_price: float, is_buy: bool,
                             m15_view: np.ndarray) -> None:
        """Pull `stops.tp` in to just before the nearest confirmed swing pivot,
        if one sits between the fill and the ATR target. Mutates `stops`."""
        try:
            from src.research.structure import compute as _struct_compute
        except Exception:
            return
        if m15_view is None or len(m15_view) < 3 * self.cfg.structural_tp_len:
            return
        sc = _struct_compute(m15_view, self.cfg.structural_tp_len)
        atr = stops.atr
        buf = self.cfg.structural_tp_buffer_atr * atr
        min_dist = self.cfg.structural_tp_min_atr * atr

        if is_buy:
            lvl = float(sc["pivot_high_val"][-1])
            if not np.isfinite(lvl) or lvl <= fill_price:
                return
            cand_tp = lvl - buf
            cand_dist = cand_tp - fill_price
            atr_dist = stops.tp - fill_price
            if min_dist <= cand_dist < atr_dist:
                stops.tp = round(cand_tp, 3)
                stops.tp_distance = round(cand_dist, 3)
                self.diag["structural_tp_applied"] = self.diag.get("structural_tp_applied", 0) + 1
        else:
            lvl = float(sc["pivot_low_val"][-1])
            if not np.isfinite(lvl) or lvl >= fill_price:
                return
            cand_tp = lvl + buf
            cand_dist = fill_price - cand_tp
            atr_dist = fill_price - stops.tp
            if min_dist <= cand_dist < atr_dist:
                stops.tp = round(cand_tp, 3)
                stops.tp_distance = round(cand_dist, 3)
                self.diag["structural_tp_applied"] = self.diag.get("structural_tp_applied", 0) + 1

    def _close(self, pos: Position, exit_price: float, ts: int, reason: str) -> None:
        direction = 1.0 if pos.is_buy else -1.0
        vpp = self._value_per_price(pos.lots)
        gross = (exit_price - pos.entry_price) * direction * vpp
        comm = self.cost.commission(pos.lots)
        # Overnight financing. Signed as the broker reports it, so a long's swap
        # is negative and adds to the cost; a short's is zero on this symbol.
        swap = self.cost.swap(pos.lots, pos.is_buy, pos.entry_time, ts,
                              self.spec.point, self.spec.value_per_price_unit_per_lot)
        nights = self.cost.nights_held(pos.entry_time, ts)
        net = gross - comm + swap
        self.diag["swap_nights_charged"] += nights
        self.diag["swap_paid"] += swap

        risk_price = abs(pos.entry_price - pos.initial_sl)
        r_mult = (exit_price - pos.entry_price) * direction / risk_price if risk_price else 0.0
        mfe_r = (pos.mfe_price - pos.entry_price) * direction / risk_price if risk_price else 0.0
        mae_r = (pos.mae_price - pos.entry_price) * direction / risk_price if risk_price else 0.0

        self.balance += net
        self.stub.balance = self.balance

        self.trades.append(
            Trade(
                ticket=pos.ticket,
                strategy=pos.strategy,
                is_buy=pos.is_buy,
                lots=pos.lots,
                entry_time=pos.entry_time,
                exit_time=ts,
                entry_price=pos.entry_price,
                exit_price=exit_price,
                sl=pos.sl,
                tp=pos.tp,
                initial_sl=pos.initial_sl,
                atr_at_entry=pos.atr_at_entry,
                session=pos.session,
                exit_reason=reason,
                gross_pl=gross,
                commission=comm,
                net_pl=net,
                r_multiple=r_mult,
                mae_price=pos.mae_price,
                mfe_price=pos.mfe_price,
                mae_r=mae_r,
                mfe_r=mfe_r,
                minutes_open=pos.minutes_open,
                minutes_to_mfe=pos.minutes_to_mfe,
                is_pyramid=pos.is_pyramid,
                duplicate_of=pos.duplicate_of,
                intrabar_ambiguous=pos.intrabar_ambiguous,
                balance_after=self.balance,
                swap=swap,
                nights_held=nights,
            )
        )
        self.positions.remove(pos)
        self.equity.append((ts, self.balance))
        if self.cfg.risk_rules_enforce:
            self._rr_after_close(pos, net, ts)

    def _rr_after_close(self, pos: Position, net: float, ts: int) -> None:
        """main_loop._record_closed_trades -> risk_rules.record_trade_result.

        Live learns of a close on the next loop and only if the position was seen
        open on an earlier loop (`known_position_tickets`); `streak_blind_spot`
        reproduces that: the position is "seen" iff it was still open when the
        next loop began, i.e. its (estimated) exit is >= 60s after its entry.
        """
        if self.cfg.streak_blind_spot and (ts + pos.hit_frac * 60.0) - pos.entry_time < 60.0:
            self.diag["streak_blind_closes"] = self.diag.get("streak_blind_closes", 0) + 1
            return
        now = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
        st = _rr._roll_anchors(self.rr_state, self.balance, now)   # same roll as main_loop L623
        if net < 0:                                                # risk_rules L253-268
            st.consecutive_losses += 1
            st.day_losing_trades += 1
            if st.consecutive_losses >= _rr.CONSEC_LOSSES_STOP_DAY:
                st.day_stopped_date = now.date().isoformat()
            elif st.consecutive_losses >= _rr.CONSEC_LOSSES_PAUSE:
                st.pause_until_ts = (now + timedelta(hours=_rr.CONSEC_LOSS_PAUSE_HOURS)).timestamp()
        else:
            st.consecutive_losses = 0
        self.rr_state = st

    def _note_hit(self, pos: Position, bar: np.ndarray, level: float,
                  spread_pts: Optional[float], point: float) -> None:
        """Estimate how far into the minute `level` was crossed (live-parity only).

        Walks the usual O-L-H-C (up bar) / O-H-L-C (down bar) path at uniform
        speed and returns the path fraction at which the (bid-equivalent) level is
        first reached. Used by the streak blind-spot rule to decide whether the
        bot's next 60s loop started before the position closed.
        """
        if not self.cfg.streak_blind_spot:
            return
        o, h, l, c = (float(bar[k]) for k in ("open", "high", "low", "close"))
        lvl = level if pos.is_buy else level - self.cost.spread_price(point, spread_pts)
        path = [o, l, h, c] if c >= o else [o, h, l, c]
        total = sum(abs(path[i + 1] - path[i]) for i in range(3))
        if total <= 0:
            pos.hit_frac = 0.5
            return
        run = 0.0
        for a, b in zip(path[:-1], path[1:]):
            if a != b and min(a, b) <= lvl <= max(a, b):
                pos.hit_frac = min(1.0, (run + abs(lvl - a)) / total)
                return
            run += abs(b - a)
        pos.hit_frac = 0.5

    def _walk_minute(self, pos: Position, bar: np.ndarray, ts: int, point: float,
                     ambiguous: bool, is_m15_close: bool = False) -> Optional[Tuple[float, str]]:
        """Advance one position through one M1 bar. Returns (exit_price, reason) if hit.

        Within a single minute the true tick order is still unknown, so a bar that
        touches both stop and target is resolved stop-first and the trade is
        flagged. At M1 that co-touch is rare; at M15 it was routine.
        """
        spread_pts = float(bar["spread"]) if "spread" in bar.dtype.names else None
        hi, lo = float(bar["high"]), float(bar["low"])
        cl = float(bar["close"])
        slip = self.cost.slip(point)
        
        is_trailing = pos.trail_active
        close_only = self.cfg.close_only_trail and is_trailing

        if pos.is_buy:
            # bars are bid-side; a long exits on bid
            pos.price_current = cl
            pos.mfe_price = max(pos.mfe_price, hi)
            pos.mae_price = min(pos.mae_price, lo)
            
            if close_only:
                # If close-only, we only check SL on the close of the M15 candle using the M15 close price
                hit_sl = is_m15_close and cl <= pos.sl
            else:
                hit_sl = lo <= pos.sl
                
            hit_tp = hi >= pos.tp
            if hit_sl and hit_tp:
                pos.intrabar_ambiguous = True
                self.diag["ambiguous_bars"] += 1
            if hit_sl:
                self._note_hit(pos, bar, pos.sl, spread_pts, point)
                return pos.sl - slip, "SL"
            if hit_tp:
                self._note_hit(pos, bar, pos.tp, spread_pts, point)
                return pos.tp, "TP"
        else:
            # a short exits on ask
            ask_hi = self.cost.ask(hi, point, spread_pts)
            ask_lo = self.cost.ask(lo, point, spread_pts)
            ask_cl = self.cost.ask(cl, point, spread_pts)
            
            pos.price_current = ask_cl
            pos.mfe_price = min(pos.mfe_price, ask_lo)
            pos.mae_price = max(pos.mae_price, ask_hi)
            
            if close_only:
                hit_sl = is_m15_close and ask_cl >= pos.sl
            else:
                hit_sl = ask_hi >= pos.sl
                
            hit_tp = ask_lo <= pos.tp
            if hit_sl and hit_tp:
                pos.intrabar_ambiguous = True
                self.diag["ambiguous_bars"] += 1
            if hit_sl:
                self._note_hit(pos, bar, pos.sl, spread_pts, point)
                return pos.sl + slip, "SL"
            if hit_tp:
                self._note_hit(pos, bar, pos.tp, spread_pts, point)
                return pos.tp, "TP"

        if ambiguous:
            pos.intrabar_ambiguous = True
        return None

    # -- main loop -------------------------------------------------------

    def run(self, strategies: Sequence[Any], start_ts: Optional[int] = None,
            end_ts: Optional[int] = None) -> BacktestResult:
        """Replay the live loop over cached history.

        `strategies` are live strategy instances. They are evaluated on the same
        250-bar window main_loop gives them, at the same cadence, and their
        signals are executed through the same RiskManager.
        """
        rm, _ = self._make_risk_manager()
        self._patch_strategy_mt5(strategies)

        point = self.spec.point
        cfg = self.cfg
        n = len(self.m15)
        self.equity.append((int(self._m15_t[cfg.warmup_bars]), self.balance))

        cached: Dict[str, Any] = {s.name: None for s in strategies}
        fired_on: Dict[str, int] = {s.name: -1 for s in strategies}

        daily_pl: Dict[Any, float] = {}
        shutdown_date = None
        peak_bal = self.balance
        equity_paused = False

        for i in range(cfg.warmup_bars, n - 1):
            bar_open = int(self._m15_t[i])
            bar_close = bar_open + 900
            nxt_open = int(self._m15_t[i + 1])

            # A gap (weekend/holiday) invalidates a carried signal: the live bot
            # would re-evaluate against fresh data on the far side.
            if nxt_open != bar_close:
                for k in cached:
                    cached[k] = None

            if start_ts and nxt_open < start_ts:
                continue
            if end_ts and nxt_open > end_ts:
                break

            m1_bars = self._m1_slice(nxt_open, nxt_open + 900)
            if m1_bars is None:
                self.diag["bars_without_m1"] += 1
                m1_bars = self.m15[i + 1: i + 2]
                coarse = True
            else:
                coarse = False

            m15_view = self._view(self.m15, self._m15_t, bar_close, cfg.history_bars, 900)
            if m15_view is None:
                continue
            d1_view = (
                self._view(self.d1, self._d1_t, bar_close, cfg.d1_history_bars, 86400)
                if self.d1 is not None else None
            )

            h4_view = (
                self._view(self.h4, self._h4_t, bar_close, 120, 14400)
                if self.h4 is not None else None
            )

            d1_bias = None
            choch_override = None   # for "d1_choch": direction a fresh H4 CHoCH allows
            if cfg.enable_d1_bias_gate:
                daily_bias = None
                d1_atr = None
                if d1_view is not None and len(d1_view) >= 20:
                    closes = d1_view["close"]
                    ema_p = 10 if cfg.direction_gate == "d1_ema10" else getattr(cfg, "d1_ema_period", 20)
                    ema_d = _ema(closes, ema_p)
                    if not np.isnan(ema_d[-1]):
                        daily_bias = "BULLISH" if closes[-1] > ema_d[-1] else "BEARISH"
                        hi, lo = d1_view["high"], d1_view["low"]
                        tr = np.maximum(hi[1:] - lo[1:],
                                        np.maximum(np.abs(hi[1:] - closes[:-1]),
                                                   np.abs(lo[1:] - closes[:-1])))
                        d1_atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else None
                        self._last_ema20 = float(ema_d[-1]); self._last_dclose = float(closes[-1])

                struct_bias = None
                if cfg.direction_gate in ("structure", "both") and len(m15_view) >= 60:
                    from src.research.structure import trend_series
                    _tr = trend_series(m15_view, cfg.structure_len)
                    struct_bias = "BULLISH" if _tr[-1] > 0 else "BEARISH"

                h4_bias = None
                if cfg.direction_gate in ("h4_structure", "d1_choch") and \
                        h4_view is not None and len(h4_view) >= 40:
                    from src.research.structure import compute as _sc
                    s4 = _sc(h4_view, 10)
                    h4_bias = "BULLISH" if s4["trend"][-1] > 0 else "BEARISH"
                    recent = s4["event"][-cfg.choch_lookback_h4:]
                    if 2 in recent:
                        choch_override = "BULLISH"
                    elif -2 in recent:
                        choch_override = "BEARISH"

                if cfg.direction_gate == "structure":
                    d1_bias = struct_bias
                elif cfg.direction_gate == "h4_structure":
                    d1_bias = h4_bias
                elif cfg.direction_gate == "both":
                    d1_bias = daily_bias if daily_bias == struct_bias else "CONFLICT"
                elif cfg.direction_gate == "d1_proximity":
                    if daily_bias and d1_atr and abs(self._last_dclose - self._last_ema20) \
                            < cfg.gate_prox_atr * d1_atr:
                        d1_bias = None          # transition zone -> allow both
                    else:
                        d1_bias = daily_bias
                elif cfg.direction_gate == "d1_choch":
                    d1_bias = daily_bias        # choch_override handled at signal time
                else:
                    d1_bias = daily_bias

            ist = datetime.fromtimestamp(nxt_open, tz=timezone.utc).astimezone(IST)
            session_mult = self._session_multiplier(rm, ist)
            session_name = rm.get_session_name(ist)
            today = ist.date()

            if shutdown_date is not None and shutdown_date != today:
                shutdown_date = None

            last_signal_eval = -(10 ** 9)
            for m in range(len(m1_bars)):
                bar = m1_bars[m]
                ts = int(bar["time"])
                spread_pts = float(bar["spread"]) if "spread" in bar.dtype.names else None
                current_ist = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)

                # Friday Kill Switch
                if market_hours.should_flatten_for_weekend(current_ist):
                    for pos in list(self.positions):
                        self._close(pos, pos.price_current, ts, "Weekend Gap Avoidance")

                is_m15_close = (m == len(m1_bars) - 1)
                
                # 1. Broker side: stops and targets fire on ticks, not on our loop.
                for pos in list(self.positions):
                    pos.minutes_open += 1
                    prev_mfe = pos.mfe_price
                    hit = self._walk_minute(pos, bar, ts, point, coarse, is_m15_close=is_m15_close)
                    if pos.mfe_price != prev_mfe:
                        pos.minutes_to_mfe = pos.minutes_open
                    if hit is not None:
                        self._close(pos, hit[0], ts, hit[1])

                # 1b. scripts/protect_profit.py -- its own process, polling every
                # 20s, so it acts every minute regardless of the bot's scan gates.
                if cfg.protect_profit and self.positions and not self._is_down("@protect_profit", ts):
                    self._protect_profit_step(bar, ts, m, m15_view)

                # 2. Bot side: the 60s scan.
                if m != 0 and (ts - bar_open) % cfg.loop_interval_sec != 0:
                    continue

                if self._down_windows and self._is_down("*", ts):
                    # bot not running: no evaluation/entries/management; a signal
                    # cached before the outage is not carried across it.
                    last_signal_eval = -(10 ** 9)
                    for k in cached:
                        cached[k] = None
                    continue

                spread_ok = spread_pts is None or spread_pts <= cfg.spread_gate_points
                if not spread_ok:
                    self.diag["entries_blocked_spread"] += 1
                    if cfg.spread_gate_blocks_management:
                        # HIGH-7: at HEAD the spread gate skips the rest of the
                        # iteration, so trailing stops freeze exactly when
                        # spreads blow out.
                        self.diag["management_skipped_spread"] += 1
                        continue
                if not spread_ok and cfg.live_exec_order:
                    # main_loop L329-332: wide spread -> manage, sleep, next scan
                    self._manage(rm, m15_view, bar, point, spread_pts)
                    continue

                # Gate 1b (main_loop L340-345): news blackout
                if cfg.news_blackout and self._news_blocked(current_ist):
                    self.diag["scans_news_blackout"] = self.diag.get("scans_news_blackout", 0) + 1
                    self._manage(rm, m15_view, bar, point, spread_pts)
                    continue

                # 3. Daily drawdown gate.
                if shutdown_date == today:
                    self._manage(rm, m15_view, bar, point, spread_pts)
                    continue
                pl_today = daily_pl.get(today, 0.0)
                if self._drawdown_breached(rm, d1_view, pl_today):
                    shutdown_date = today
                    self.diag["daily_shutdowns"] += 1
                    self._manage(rm, m15_view, bar, point, spread_pts)
                    continue

                # 3b. Equity-curve pause (opt-in). Manage open positions but
                # open nothing new while the account is deep below its peak.
                if cfg.equity_pause_dd > 0:
                    peak_bal = max(peak_bal, self.balance)
                    if not equity_paused and self.balance < peak_bal * (1 - cfg.equity_pause_dd):
                        equity_paused = True
                        self.diag["equity_pauses"] = self.diag.get("equity_pauses", 0) + 1
                    elif equity_paused and self.balance >= peak_bal * (1 - cfg.equity_resume_dd):
                        equity_paused = False
                    if equity_paused:
                        self._manage(rm, m15_view, bar, point, spread_pts)
                        continue

                # main_loop L448-451: no strategy evaluation in LONDON_NY_OVERLAP
                if cfg.skip_overlap_session and rm.get_session_name(current_ist) == "LONDON_NY_OVERLAP":
                    self.diag["scans_overlap_skipped"] = self.diag.get("scans_overlap_skipped", 0) + 1
                    self._manage(rm, m15_view, bar, point, spread_pts)
                    continue

                # 4. Strategy evaluation, on M5 boundaries as the M5 view advances.
                if spread_ok and ts - last_signal_eval >= cfg.resignal_interval_sec:
                    last_signal_eval = ts
                    m5_view = (
                        self._view(self.m5, self._m5_t, ts, cfg.m5_history_bars, 300)
                        if self.m5 is not None else None
                    )
                    for s in strategies:
                        if self._down_windows and self._is_down(s.name, ts):
                            cached[s.name] = None
                            continue
                        try:
                            cached[s.name] = s.evaluate(m15_view, m5_view)
                        except Exception as exc:
                            log.debug("%s raised at %s: %s", s.name, ts, exc)
                            cached[s.name] = None
                        if cached[s.name] is not None:
                            self.diag["signals_generated"] += 1

                # 5. Entries (with Highlander Rule)
                if spread_ok and cfg.live_exec_order:
                    self._parity_entries(strategies, cached, fired_on, bar_open, bar, ts,
                                         current_ist, spread_pts, m15_view, d1_view, d1_bias,
                                         choch_override, rm, point, coarse, is_m15_close,
                                         session_mult)
                elif spread_ok:
                    mh_ok, _ = market_hours.allow_new_entry(current_ist)
                    if not mh_ok:
                        # Time lock or rollover blocked entry
                        continue
                        
                    actionable_signals = []
                    for s in strategies:
                        sig = cached[s.name]
                        if sig is None:
                            continue
                        if cfg.dedup_per_candle and fired_on[s.name] == bar_open:
                            self.diag["signals_deduped"] += 1
                            continue
                        if d1_bias:
                            sig_dir = "BULLISH" if sig.is_buy else "BEARISH"
                            _ovr = (cfg.direction_gate == "d1_choch" and choch_override == sig_dir)
                            if not _ovr:
                                if d1_bias == "CONFLICT" or (sig.is_buy and d1_bias == "BEARISH") or (not sig.is_buy and d1_bias == "BULLISH"):
                                    self.diag["entries_blocked_d1_bias"] += 1
                                    continue
                        if not self._caps_allow(sig.is_buy):
                            self.diag["entries_blocked_caps"] += 1
                            continue
                            
                        # If passed all gates, it's actionable
                        actionable_signals.append((s, sig))

                    if actionable_signals:
                        # HIGHLANDER RULE: Execute only highest conviction signal
                        rank_order = {
                            "NVMR_TARGET_10_V5": 6,
                            "NVMR_TARGET_10": 6,
                            "BB_MEAN_REVERSION_V5": 5,
                            "BB_MEAN_REVERSION": 5,
                            "FVG_NY_SWEEP_OR_VOID": 5,
                            "FVG_NY_SWEEP": 4,
                            "FVG_NY_VOID": 3,
                            "FVG_NY_TIGHT_V5": 2,
                            "FVG_NY_TIGHT": 2,
                            "TREND_PULLBACK_V5": 2,
                            "TREND_PULLBACK": 2,
                            "FVG_ASIA_SWEEP": 1,
                            "NY_LIQUIDITY_EXPANSION_V5": 1,
                            "NY_LIQUIDITY_EXPANSION": 1,
                            "PDHLR_STRATEGY_V5": 1,
                            "PDHLR_STRATEGY": 1,
                        }
                        actionable_signals.sort(key=lambda x: rank_order.get(x[0].name.upper(), 0), reverse=True)
                        best_s, best_sig = actionable_signals[0]

                        # Block others
                        for other_s, _ in actionable_signals[1:]:
                            fired_on[other_s.name] = bar_open
                            self.diag["signals_deduped"] += 1

                        dup_of = None
                        same = [p for p in self.positions if p.strategy == best_s.name and p.is_buy == best_sig.is_buy]
                        if same:
                            dup_of = same[0].ticket
                        if fired_on[best_s.name] == bar_open:
                            self.diag["same_candle_refires"] += 1

                        base = float(bar["open"])
                        fill = self.cost.ask(base, point, spread_pts) if best_sig.is_buy else base
                        fill += self.cost.slip(point) * (1 if best_sig.is_buy else -1)

                        opened = self._open(best_s.name, best_s.magic, best_sig.is_buy, fill, ts, rm,
                                            m15_view, session_mult, session_name,
                                            duplicate_of=dup_of,
                                            sl_atr_mult=getattr(best_s, "sl_atr_mult", None),
                                            tp_atr_mult=getattr(best_s, "tp_atr_mult", None))
                        if opened is not None:
                            fired_on[best_s.name] = bar_open
                            # Coarse (no-M1) bars: the 15 minutes right after entry
                            # are the one bar where a 0.5xATR stop is most likely to
                            # be hit. Walk the new position through this same bar,
                            # stop-first on ambiguity, instead of skipping it.
                            if coarse and cfg.walk_entry_bar_coarse:
                                hit = self._walk_minute(opened, bar, ts, point, True,
                                                        is_m15_close=is_m15_close)
                                if hit is not None:
                                    self._close(opened, hit[0], ts, hit[1])

                # 6. Pyramiding, then management -- the order main_loop uses.
                if spread_ok and cfg.enable_pyramiding:
                    self._pyramid(rm, m15_view, bar, ts, point, spread_pts,
                                  session_mult, session_name)
                self._manage(rm, m15_view, bar, point, spread_pts)

            # attribute closed P/L to its IST day for the drawdown gate
            daily_pl = {}
            for t in self.trades:
                d = datetime.fromtimestamp(t.exit_time, tz=timezone.utc).astimezone(IST).date()
                daily_pl[d] = daily_pl.get(d, 0.0) + t.net_pl

        if self.positions:
            last = self.m15[-1]
            for pos in list(self.positions):
                self._close(pos, float(last["close"]), int(last["time"]), "END_OF_DATA")

        if cfg.record_decisions:
            self.diag["decisions"] = self.decisions
        if cfg.risk_rules_enforce:
            self.diag["risk_state_final"] = self.rr_state.to_dict()

        return BacktestResult(
            trades=self.trades,
            equity=self.equity,
            config=cfg.as_dict(),
            data_hash=self.bars.hash_key(),
            diagnostics=self.diag,
        )

    # -- loop components -------------------------------------------------

    def _caps_allow(self, is_buy: bool) -> bool:
        if len(self.positions) >= self.cfg.max_concurrent:
            return False
        same = sum(1 for p in self.positions if p.is_buy == is_buy)
        return same < self.cfg.max_same_direction

    # -- live-parity components -------------------------------------------

    _RANK_ORDER = {
        # identical to main_loop.py L516-533 / the legacy block in run()
        "NVMR_TARGET_10_V5": 6, "NVMR_TARGET_10": 6,
        "BB_MEAN_REVERSION_V5": 5, "BB_MEAN_REVERSION": 5,
        "FVG_NY_SWEEP_OR_VOID": 5, "FVG_NY_SWEEP": 4, "FVG_NY_VOID": 3,
        "FVG_NY_TIGHT_V5": 2, "FVG_NY_TIGHT": 2,
        "TREND_PULLBACK_V5": 2, "TREND_PULLBACK": 2,
        "FVG_ASIA_SWEEP": 1,
        "NY_LIQUIDITY_EXPANSION_V5": 1, "NY_LIQUIDITY_EXPANSION": 1,
        "PDHLR_STRATEGY_V5": 1, "PDHLR_STRATEGY": 1,
    }

    def _news_blocked(self, current_ist: datetime) -> bool:
        from src.core import news_filter
        blocked, _ = news_filter.is_near_news_event(current_ist)
        return bool(blocked)

    def _scan_d1_bias(self, d1_view, ts: int, static_bias: Optional[str]) -> Optional[str]:
        cfg = self.cfg
        if not cfg.enable_d1_bias_gate:
            return None
        if cfg.d1_intraday_override and cfg.direction_gate == "d1_ema20" and d1_view is not None:
            return self._live_d1_bias(d1_view, ts)
        return static_bias

    @staticmethod
    def _clean_reversal(is_buy: bool, m15_view: np.ndarray) -> bool:
        """scripts/protect_profit.clean_reversal_against on the last 40 M15 bars
        (copy_rates_from_pos(M15, 0, 40) -> [-1] forming, [-2] last closed)."""
        from scripts.protect_profit import clean_reversal_against
        return bool(clean_reversal_against(is_buy, m15_view[-40:]))

    def _protect_profit_step(self, bar, ts: int, m: int, m15_view: np.ndarray) -> None:
        """scripts/protect_profit.py main() loop body, once per M1 bar.

        The script polls every 20s (3 samples per minute); a 1-minute bar cannot
        say which prices it sampled, so the model is:
          * peak     = the position's favourable-extreme profit so far (polls catch
                       most intrabar extremes: the 2026-10-13 close logged peak
                       +6.32 against a bar extreme of +6.97);
          * giveback = fires when this bar's WORST profit lies in
                       [MIN_GREEN, GIVEBACK_FLOOR] and peak >= GIVEBACK_PEAK, at the
                       price of that worst point (a poll can land anywhere in the
                       band as price falls through it);
          * reversal = once per new M15 bar (first minute), profit measured at the
                       price at that bar's open, like `new_bar` in the script.
        Closing arms the leg's re-entry cooldown (`_set_cooldown`).
        """
        cfg = self.cfg
        point = self.spec.point
        spread_pts = float(bar["spread"]) if "spread" in bar.dtype.names else None
        for pos in list(self.positions):
            dirn = 1.0 if pos.is_buy else -1.0
            vpp = self._value_per_price(pos.lots)
            peak = (pos.mfe_price - pos.entry_price) * dirn * vpp
            if pos.is_buy:
                worst_px = float(bar["low"])                          # exits on bid
            else:
                worst_px = self.cost.ask(float(bar["high"]), point, spread_pts)   # exits on ask
            worst = (worst_px - pos.entry_price) * dirn * vpp
            reason, exit_px = None, 0.0
            if peak >= cfg.protect_giveback_peak and cfg.protect_min_green <= worst <= cfg.protect_giveback_floor:
                reason, exit_px = "PROTECT_GIVEBACK", worst_px
            elif m == 0:
                base = float(bar["open"])
                open_px = base if pos.is_buy else self.cost.ask(base, point, spread_pts)
                p_open = (open_px - pos.entry_price) * dirn * vpp
                if p_open >= cfg.protect_min_green and self._clean_reversal(pos.is_buy, m15_view):
                    reason, exit_px = "PROTECT_REVERSAL", open_px
            if reason is None:
                continue
            self._close(pos, exit_px, ts, reason)
            self.cooldown_until[pos.strategy] = ts + cfg.protect_cooldown_min * 60
            self.diag["protect_closes"] = self.diag.get("protect_closes", 0) + 1

    _CAP_REASONS = ("caps", "max_concurrent", "ladder_concurrent", "ladder_exposure",
                    "same_direction")

    def _ladder_sizing(self, ts: int) -> Tuple[float, int, float]:
        """(lots, max_concurrent, max_exposure) for the current balance, from the
        ladder table in force at `ts` (SizingLadder.get_sizing's exact walk)."""
        sched = self.cfg.sizing_ladder_schedule
        if not sched:
            return _SizingLadder.get_sizing(self.balance)
        table = sched[0][1]
        for eff, tbl in sorted(sched, key=lambda x: x[0]):
            if eff <= ts:
                table = tbl
        for threshold, lots, max_conc, max_exp in reversed(table):
            if self.balance >= threshold:
                return lots, max_conc, max_exp
        return table[0][1:]

    def _exec_gates(self, strat, sig, ts: int, current_ist: datetime,
                    spread_pts: Optional[float]) -> Tuple[Optional[str], Optional[float]]:
        """main_loop._execute_signal + ExecutionHandler.send_order gates, in live
        order. Returns (block_reason | None, lots_override | None)."""
        cfg = self.cfg
        # IV.6 / owner window (main_loop L752)
        ok, _ = market_hours.allow_new_entry(current_ist)
        if not ok:
            return "market_hours", None
        # per-strategy spread cap (L759-765)
        cap = getattr(strat, "max_spread_pts", None)
        if cfg.enforce_strategy_max_spread and cap and spread_pts is not None and spread_pts > cap:
            return "strategy_max_spread", None
        # executor.can_open_new_position (L767): MAX_CONCURRENT_POSITIONS
        if len(self.positions) >= cfg.max_concurrent:
            return "max_concurrent", None
        # risk_rules (L792-803). Evaluated even when not enforced (shadow), so the
        # state machine matches live; only blocks from risk_rules_enforce_from_ts.
        enforcing = False
        if cfg.risk_rules_enforce:
            enforcing = (cfg.risk_rules_enforce_from_ts == 0 or ts >= cfg.risk_rules_enforce_from_ts)
            equity = self.balance + self.floating_pl()
            dec, self.rr_state = _rr.evaluate(self.balance, equity, self.used_margin(),
                                              now=current_ist, state=self.rr_state)
            if enforcing and not dec.allow_new_entries:
                return "risk_rules: " + dec.reason, None
        lots = None
        if cfg.sizing_ladder_caps:
            # ExecutionHandler.send_order L158-168 + PreTradeVeto layers 1-4
            if self.balance < _SizingLadder.POSITION_FLOOR:
                return "position_floor", None
            lots, max_conc, max_exp = self._ladder_sizing(ts)
            if enforcing:                                          # veto layer 2 (L120-167)
                st = self.rr_state
                if st.pause_until_ts > 0 and ts < st.pause_until_ts:
                    return "veto_pause", None
                if st.week_start_balance > 0 and \
                        (st.week_start_balance - self.balance) / st.week_start_balance >= 0.15:
                    return "veto_weekly", None
                if st.month_start_balance > 0 and \
                        (st.month_start_balance - self.balance) / st.month_start_balance >= 0.25:
                    return "veto_monthly", None
            if len(self.positions) >= max_conc:                    # layer 3
                return "ladder_concurrent", None
            if sum(p.lots for p in self.positions) + lots > max_exp:   # layer 4
                return "ladder_exposure", None
            if sum(1 for p in self.positions if p.is_buy == sig.is_buy) >= cfg.max_same_direction:
                return "same_direction", None                      # send_order L234
        else:
            if not self._caps_allow(sig.is_buy):
                return "caps", None
        return None, lots

    def _parity_entries(self, strategies, cached, fired_on, bar_open, bar, ts, current_ist,
                        spread_pts, m15_view, d1_view, d1_bias_static, choch_override, rm,
                        point, coarse, is_m15_close, session_mult) -> None:
        """main_loop.py L453-557: filter -> Highlander -> execute -> mark fired.

        Differences from the legacy engine block: D1 bias is rebuilt per scan
        (intraday override), protect_profit cooldown is honoured, and the
        execution gates run AFTER Highlander with the candle marked fired
        whether or not the order goes through.
        """
        cfg = self.cfg
        actionable = []
        d1_bias = None
        d1_ready = False
        for s in strategies:
            sig = cached[s.name]
            if sig is None:
                continue
            if self._down_windows and self._is_down(s.name, ts):
                continue
            if cfg.dedup_per_candle and fired_on[s.name] == bar_open:
                self.diag["signals_deduped"] += 1
                continue
            if not d1_ready:
                d1_bias = self._scan_d1_bias(d1_view, ts, d1_bias_static)
                d1_ready = True
            if d1_bias:
                sig_dir = "BULLISH" if sig.is_buy else "BEARISH"
                ovr = (cfg.direction_gate == "d1_choch" and choch_override == sig_dir)
                if not ovr and (d1_bias == "CONFLICT" or (sig.is_buy and d1_bias == "BEARISH")
                                or (not sig.is_buy and d1_bias == "BULLISH")):
                    self.diag["entries_blocked_d1_bias"] += 1
                    self._decide(ts, s.name, sig.is_buy, f"d1_gate({d1_bias})")
                    continue
            if cfg.protect_profit and ts < self.cooldown_until.get(s.name, 0):
                self.diag["entries_blocked_cooldown"] = self.diag.get("entries_blocked_cooldown", 0) + 1
                self._decide(ts, s.name, sig.is_buy, "reversal_cooldown")
                continue
            actionable.append((s, sig))
        if not actionable:
            return

        actionable.sort(key=lambda x: self._RANK_ORDER.get(x[0].name.upper(), 0), reverse=True)
        best_s, best_sig = actionable[0]
        for other_s, other_sig in actionable[1:]:
            fired_on[other_s.name] = bar_open
            self.diag["signals_deduped"] += 1
            self._decide(ts, other_s.name, other_sig.is_buy, "highlander_lost")
        # live marks the candle fired after _execute_signal, whatever it returned
        fired_on[best_s.name] = bar_open

        reason, lots = self._exec_gates(best_s, best_sig, ts, current_ist, spread_pts)
        if reason is not None:
            key = "entries_blocked_caps" if reason in self._CAP_REASONS else "entries_blocked_gates"
            self.diag[key] = self.diag.get(key, 0) + 1
            self._decide(ts, best_s.name, best_sig.is_buy, "blocked:" + reason)
            return

        d = cfg.entry_delay_sec
        op, cl = float(bar["open"]), float(bar["close"])
        base = op if coarse else op + (cl - op) * (d / 60.0)
        fill = self.cost.ask(base, point, spread_pts) if best_sig.is_buy else base
        fill += self.cost.slip(point) * (1 if best_sig.is_buy else -1)

        dup_of = None
        same = [p for p in self.positions if p.strategy == best_s.name and p.is_buy == best_sig.is_buy]
        if same:
            dup_of = same[0].ticket
        session_name = rm.get_session_name(current_ist)
        opened = self._open(best_s.name, best_s.magic, best_sig.is_buy, fill, ts + d, rm,
                            m15_view, session_mult, session_name, duplicate_of=dup_of,
                            sl_atr_mult=getattr(best_s, "sl_atr_mult", None),
                            tp_atr_mult=getattr(best_s, "tp_atr_mult", None),
                            lots_override=lots)
        if opened is None:
            self._decide(ts, best_s.name, best_sig.is_buy, "blocked:open_failed")
            return
        opened.scan_ts, opened.delay_sec = ts, d
        self._decide(ts, best_s.name, best_sig.is_buy, "entered")
        if coarse and cfg.walk_entry_bar_coarse:
            hit = self._walk_minute(opened, bar, ts, point, True, is_m15_close=is_m15_close)
            if hit is not None:
                self._close(opened, hit[0], ts, hit[1])

    def _drawdown_breached(self, rm, d1_view, pl_today: float) -> bool:
        mode = self.cfg.daily_loss_limit_mode
        if mode == "off":
            return False
        if mode == "balance_pct":
            # The repaired form: a fraction of balance, including open P/L.
            limit = self.balance * self.cfg.daily_loss_limit_pct
            return (pl_today + self.floating_pl()) <= -limit
        # "atr_price" reproduced the pre-repair behaviour, which compared account
        # currency against a price-unit ATR. RiskManager no longer implements it,
        # so this now delegates to the repaired balance-fraction check with the
        # engine's simulated balance and floating P/L.
        return not rm.check_daily_drawdown(
            todays_pl=pl_today, floating_pl=self.floating_pl(), balance=self.balance
        )

    def _pyramid(self, rm, m15_view, bar, ts, point, spread_pts, session_mult, session_name):
        if not self.positions:
            return
        atr = rm.get_latest_atr(m15_view)
        if atr is None:
            return
        for pos in list(self.positions):
            if not self._caps_allow(pos.is_buy):
                continue
            existing = [p for p in self.positions
                        if p.is_buy == pos.is_buy and p.magic == pos.magic]
            if len(existing) >= 2:
                continue
            if not rm.check_pyramid_condition(pos.entry_price, pos.price_current,
                                              atr, pos.is_buy):
                continue
            base = float(bar["close"])
            fill = self.cost.ask(base, point, spread_pts) if pos.is_buy else base
            self._open(pos.strategy, pos.magic, pos.is_buy, fill, ts, rm, m15_view,
                       session_mult, session_name, is_pyramid=True)
            break

    def _manage(self, rm, m15_view, bar, point, spread_pts):
        if not self.positions:
            return
        # main_loop refetches only 20 M15 bars here, so ATR(14) is read six bars
        # after its seed. Reproduced deliberately -- see HIGH-8.
        short_view = m15_view[-20:]
        atr = rm.get_latest_atr(short_view)
        if atr is None:
            log.debug("_manage: ATR unavailable on short_view -- skipping management.")
            return

        if self.cfg.enable_trailing:
            for pos in list(self.positions):
                new_sl = rm.calculate_trailing_stop(pos, atr)
                if new_sl is not None:
                    pos.sl = new_sl
                    pos.trail_active = True

        # One-shot breakeven move: once favourable excursion reaches
        # be_trigger_atr * entry-ATR, pull the stop to entry +/- be_offset once.
        if self.cfg.be_trigger_atr > 0:
            for pos in list(self.positions):
                if pos.trail_active or pos.atr_at_entry <= 0:
                    continue
                a0 = pos.atr_at_entry
                off = self.cfg.be_offset_atr * a0
                if pos.is_buy:
                    mfe = (pos.mfe_price or pos.price_current) - pos.entry_price
                    be = pos.entry_price + off
                    if mfe >= self.cfg.be_trigger_atr * a0 and pos.sl < be:
                        pos.sl = be
                        pos.trail_active = True   # mark done -- one shot only
                else:
                    mfe = pos.entry_price - (pos.mfe_price or pos.price_current)
                    be = pos.entry_price - off
                    if mfe >= self.cfg.be_trigger_atr * a0 and (pos.sl > be or pos.sl == 0):
                        pos.sl = be
                        pos.trail_active = True

        if self.cfg.enable_consolidation_exit and rm.should_exit_consolidation(short_view):
            ts = int(bar["time"])
            for pos in list(self.positions):
                base = float(bar["close"])
                px = base if pos.is_buy else self.cost.ask(base, point, spread_pts)
                self._close(pos, px, ts, "CONSOLIDATION")


def _ema(prices: np.ndarray, period: int) -> np.ndarray:
    """Seeded exactly like BaseStrategy.ema so the D1 bias gate matches live."""
    prices = np.asarray(prices, dtype=float)
    out = np.full_like(prices, np.nan)
    if len(prices) < period:
        return out
    out[period - 1] = np.mean(prices[:period])
    mult = 2.0 / (period + 1)
    for i in range(period, len(prices)):
        out[i] = prices[i] * mult + out[i - 1] * (1 - mult)
    return out
