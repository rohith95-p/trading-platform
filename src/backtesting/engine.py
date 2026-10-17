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

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


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
              tp_atr_mult: Optional[float] = None) -> Optional[Position]:
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
                return pos.sl - slip, "SL"
            if hit_tp:
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
                return pos.sl + slip, "SL"
            if hit_tp:
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

                # 2. Bot side: the 60s scan.
                if m != 0 and (ts - bar_open) % cfg.loop_interval_sec != 0:
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

                # 4. Strategy evaluation, on M5 boundaries as the M5 view advances.
                if spread_ok and ts - last_signal_eval >= cfg.resignal_interval_sec:
                    last_signal_eval = ts
                    m5_view = (
                        self._view(self.m5, self._m5_t, ts, cfg.m5_history_bars, 300)
                        if self.m5 is not None else None
                    )
                    for s in strategies:
                        try:
                            cached[s.name] = s.evaluate(m15_view, m5_view)
                        except Exception as exc:
                            log.debug("%s raised at %s: %s", s.name, ts, exc)
                            cached[s.name] = None
                        if cached[s.name] is not None:
                            self.diag["signals_generated"] += 1

                # 5. Entries (with Highlander Rule)
                if spread_ok:
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
