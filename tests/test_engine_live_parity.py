"""Unit tests for the engine's opt-in LIVE-PARITY gates (2026-10-17).

Every gate models one thing the live demo bot (src/core/main_loop.py,
scripts/protect_profit.py, src/core/risk_rules.py, src/core/sizing_ladder.py)
does that the backtest engine did not. All tests use synthetic bars -- no MT5, no
cached research data -- and each one pairs the "flag on" behaviour with the
"flag off" (legacy) behaviour so a default-off regression is caught too.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from src.backtesting.costs import SCENARIOS
from src.backtesting.data import BarSet, SymbolSpec
from src.backtesting.engine import (BacktestEngine, EngineConfig, Position, _PARITY_FLAGS)
from src.strategies.base_strategy import Signal

UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))
RATE_DTYPE = np.dtype([("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"),
                       ("close", "<f8"), ("tick_volume", "<u8"), ("spread", "<i4"),
                       ("real_volume", "<u8")])
SPEC = SymbolSpec(symbol="XAUUSDm", digits=3, point=0.001, trade_tick_size=0.001,
                  trade_tick_value=0.1, volume_min=0.01, volume_max=200.0, volume_step=0.01,
                  contract_size=100.0)


def ts(y, mo, d, h=0, mi=0):
    return int(datetime(y, mo, d, h, mi, tzinfo=UTC).timestamp())


T0 = ts(2026, 9, 30)               # Wednesday 2026-10-07 is the test day
DAY = ts(2026, 10, 7)
DAYS = 8


# ---------------------------------------------------------------------------
# synthetic data
# ---------------------------------------------------------------------------

def _agg(m1: np.ndarray, step: int) -> np.ndarray:
    t = m1["time"]
    bucket = t - (t % step)
    out = []
    for b in np.unique(bucket):
        seg = m1[bucket == b]
        out.append((b, seg["open"][0], seg["high"].max(), seg["low"].min(), seg["close"][-1],
                    int(seg["tick_volume"].sum()), int(seg["spread"].max()), 0))
    return np.array(out, dtype=RATE_DTYPE)


def make_bars(price_fn=None, spread=200, d1=None, days=DAYS) -> BarSet:
    """M1 random-walk-ish series (deterministic) with M5/M15/D1 aggregated from it.

    `price_fn(t) -> price` overrides the base wiggle for controlled paths.
    `d1` = (closes list for the 60 days before T0) to control the daily EMA gate.
    """
    n = days * 1440
    times = T0 + 60 * np.arange(n + 1)
    rng = np.random.default_rng(7)
    base = 4000.0 + 2.0 * np.sin(times / 2500.0) + np.cumsum(rng.normal(0, 0.12, n + 1)) * 0.2
    p = np.array([price_fn(int(t)) if price_fn else base[i] for i, t in enumerate(times)])
    if price_fn:
        p = np.where(np.isnan(p), base, p)
    m1 = np.zeros(n, dtype=RATE_DTYPE)
    m1["time"] = times[:-1]
    m1["open"] = p[:-1]
    m1["close"] = p[1:]
    m1["high"] = np.maximum(p[:-1], p[1:]) + 0.05
    m1["low"] = np.minimum(p[:-1], p[1:]) - 0.05
    m1["tick_volume"] = 100
    m1["spread"] = spread
    m15, m5 = _agg(m1, 900), _agg(m1, 300)
    d1_new = _agg(m1, 86400)
    closes = d1 if d1 is not None else [3900.0 + i for i in range(60)]
    pre = np.zeros(len(closes), dtype=RATE_DTYPE)
    pre["time"] = T0 - 86400 * (len(closes) - np.arange(len(closes)))
    pre["close"] = closes
    pre["open"] = np.array(closes) - 0.5
    pre["high"] = np.array(closes) + 2
    pre["low"] = np.array(closes) - 2
    pre["spread"] = spread
    d1_all = np.concatenate([pre, d1_new])
    return BarSet(symbol="XAUUSDm", m15=m15, m5=m5, m1=m1, d1=d1_all, spec=SPEC, manifests={})


class Fire:
    """Strategy double: emits a fixed signal when the last CLOSED M15 candle's open
    time is in `candles` (exactly the way real strategies read rates[-2])."""
    sl_atr_mult = 0.5
    tp_atr_mult = 1.5

    def __init__(self, name="TREND_PULLBACK_V5", magic=5001, is_buy=True, candles=(), **attrs):
        self.name, self.magic, self.is_buy, self.candles = name, magic, is_buy, set(candles)
        for k, v in attrs.items():
            setattr(self, k, v)

    def evaluate(self, m15, m5=None):
        if int(m15["time"][-2]) in self.candles:
            return Signal(direction=0 if self.is_buy else 1, strategy_name=self.name,
                          magic=self.magic, is_buy=self.is_buy)
        return None


def held(**kw):
    """A leg whose stop/target are so far away the position stays open all day."""
    kw.setdefault("sl_atr_mult", 40.0)
    kw.setdefault("tp_atr_mult", 120.0)
    return Fire(**kw)


def run(bars, strategies, a=DAY, b=DAY + 86400 - 3600, **cfg):
    kw = dict(symbol="XAUUSDm", starting_balance=500.0, sizing_mode="fixed", fixed_lots=0.01,
              enable_d1_bias_gate=False)
    kw.update(cfg)
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["observed"], config=EngineConfig(**kw))
    return eng, eng.run(strategies, a, b)


C_NY = DAY + 13 * 3600           # candle opening 13:00 UTC = 18:30 IST (NY_MORNING, tradable)
C_OVERLAP = DAY + 11 * 3600      # candle opening 11:00 UTC = 16:30 IST (LONDON_NY_OVERLAP)


@pytest.fixture(scope="module")
def flat_bars():
    return make_bars()


# ---------------------------------------------------------------------------
# presets / defaults
# ---------------------------------------------------------------------------

def test_every_parity_flag_defaults_off_and_preset_turns_them_on():
    base = EngineConfig()
    for f in _PARITY_FLAGS:
        assert getattr(base, f) is False, f
    assert base.entry_delay_sec == 0 and base.risk_rules_enforce_from_ts == 0
    assert base.disabled_windows is None and base.sizing_ladder_schedule is None

    p = EngineConfig.live_parity_preset()
    for f in _PARITY_FLAGS:
        assert getattr(p, f) is True, f
    assert p.spread_gate_blocks_management is False and p.sizing_mode == "fixed"
    assert 0 < p.entry_delay_sec < 60
    assert EngineConfig.live_parity_preset(protect_profit=False).protect_profit is False
    assert EngineConfig(live_parity=True).news_blackout is True
    with pytest.raises(TypeError):
        EngineConfig.live_parity_preset(not_a_field=1)


def test_protect_constants_are_pinned_to_the_script():
    from scripts import protect_profit as pp
    c = EngineConfig()
    assert (c.protect_giveback_peak, c.protect_giveback_floor, c.protect_min_green,
            c.protect_cooldown_min) == (pp.GIVEBACK_PEAK, pp.GIVEBACK_FLOOR, pp.MIN_GREEN, pp.COOLDOWN_MIN)


def test_entry_delay_must_be_under_a_minute(flat_bars):
    with pytest.raises(ValueError):
        BacktestEngine(bars=flat_bars, cost=SCENARIOS["observed"], config=EngineConfig(entry_delay_sec=60))


# ---------------------------------------------------------------------------
# (2) overlap-session skip
# ---------------------------------------------------------------------------

def test_overlap_session_skips_evaluation_only_when_flagged(flat_bars):
    s = lambda: [Fire(candles=[C_OVERLAP])]
    _, off = run(flat_bars, s())
    assert len(off.trades) == 1                                   # legacy engine trades the overlap
    eng, on = run(flat_bars, s(), skip_overlap_session=True)
    assert len(on.trades) == 0
    assert on.diagnostics["scans_overlap_skipped"] > 0


def test_non_overlap_signal_still_trades_with_overlap_skip(flat_bars):
    _, res = run(flat_bars, [Fire(candles=[C_NY])], skip_overlap_session=True)
    assert len(res.trades) == 1


# ---------------------------------------------------------------------------
# (3) per-strategy spread cap
# ---------------------------------------------------------------------------

def test_strategy_max_spread_pts_blocks_entry(flat_bars):
    wide = make_bars(spread=300)             # under the global 350-pt gate, over the leg's 250
    mk = lambda: [Fire(name="FVG_NY_TIGHT_V5", magic=5005, candles=[C_NY], max_spread_pts=250)]
    _, off = run(wide, mk(), live_exec_order=True)
    assert len(off.trades) == 1              # flag off: cap not enforced
    _, on = run(wide, mk(), live_exec_order=True, enforce_strategy_max_spread=True)
    assert len(on.trades) == 0
    # within the cap it trades
    _, ok = run(flat_bars, mk(), live_exec_order=True, enforce_strategy_max_spread=True)
    assert len(ok.trades) == 1


def test_blocked_best_signal_still_marks_the_candle_fired_for_losers(flat_bars):
    """main_loop L549-557: Highlander winner is marked fired even if _execute_signal
    blocked it, and the losers are marked fired too -- nothing retries that candle."""
    wide = make_bars(spread=300)
    best = Fire(name="NVMR_TARGET_10_V5", magic=5003, candles=[C_NY], max_spread_pts=250)
    loser = Fire(name="TREND_PULLBACK_V5", magic=5001, candles=[C_NY])
    _, res = run(wide, [best, loser], live_exec_order=True, enforce_strategy_max_spread=True)
    assert len(res.trades) == 0
    # legacy engine pre-filters and would have traded the loser's... best here (no cap applied)
    _, legacy = run(wide, [Fire(name="NVMR_TARGET_10_V5", magic=5003, candles=[C_NY], max_spread_pts=250),
                           Fire(candles=[C_NY])])
    assert len(legacy.trades) == 1


# ---------------------------------------------------------------------------
# (4) sizing-ladder concurrency / exposure
# ---------------------------------------------------------------------------

def _hold_open_bars():
    """Price drifts up slowly so BUYs stay open (0.5xATR stop / 1.5xATR target far enough)."""
    return make_bars(price_fn=lambda t: 4000.0 + 0.0005 * (t - T0) / 60.0)


def test_ladder_allows_one_position_under_100_and_two_above(flat_bars):
    bars = _hold_open_bars()
    cands = [C_NY, C_NY + 900]
    mk = lambda: [held(candles=cands[:1]), held(name="BB_MEAN_REVERSION_V5", magic=5002, candles=cands[1:])]
    _, free = run(bars, mk(), live_exec_order=True, starting_balance=90.0)
    assert len(free.trades) == 2                       # no ladder flag -> engine max_concurrent 2
    _, capped = run(bars, mk(), live_exec_order=True, sizing_ladder_caps=True, starting_balance=150.0)
    assert len(capped.trades) == 1                     # < $200: one position (current ladder)
    _, two = run(bars, mk(), live_exec_order=True, sizing_ladder_caps=True, starting_balance=300.0)
    assert len(two.trades) == 2                        # $200-400: two positions (current ladder)


def test_ladder_schedule_swaps_tables_over_time(flat_bars):
    bars = _hold_open_bars()
    old = ((0.0, 0.01, 1, 0.01), (100.0, 0.01, 1, 0.01), (200.0, 0.01, 2, 0.02))
    new = ((0.0, 0.01, 1, 0.01), (100.0, 0.01, 2, 0.02), (200.0, 0.01, 2, 0.02))
    cands = [C_NY, C_NY + 900]
    mk = lambda: [held(candles=cands[:1]), held(name="BB_MEAN_REVERSION_V5", magic=5002, candles=cands[1:])]
    _, a = run(bars, mk(), live_exec_order=True, sizing_ladder_caps=True, starting_balance=150.0,
               sizing_ladder_schedule=[(0, old), (DAY + 86400, new)])
    assert len(a.trades) == 1                          # old table in force at the signal time
    _, b = run(bars, mk(), live_exec_order=True, sizing_ladder_caps=True, starting_balance=150.0,
               sizing_ladder_schedule=[(0, old), (DAY, new)])
    assert len(b.trades) == 2                          # new table already effective


def test_ladder_exposure_cap_blocks_even_when_concurrency_allows():
    bars = _hold_open_bars()
    table = ((0.0, 0.01, 3, 0.01),)                    # 3 positions allowed but only 0.01 lot exposure
    cands = [C_NY, C_NY + 900]
    strat = [held(candles=cands[:1]), held(name="BB_MEAN_REVERSION_V5", magic=5002, candles=cands[1:])]
    eng, res = run(bars, strat, live_exec_order=True, sizing_ladder_caps=True,
                   sizing_ladder_schedule=[(0, table)])
    assert len(res.trades) == 1
    assert res.diagnostics["entries_blocked_caps"] >= 1


def test_ladder_lots_override_the_engine_fixed_lot(flat_bars):
    bars = _hold_open_bars()
    table = ((0.0, 0.03, 1, 0.03),)
    _, res = run(bars, [held(candles=[C_NY])], live_exec_order=True, sizing_ladder_caps=True,
                 sizing_ladder_schedule=[(0, table)])
    assert res.trades[0].lots == pytest.approx(0.03)


def test_position_floor_blocks_entry():
    bars = _hold_open_bars()
    _, res = run(bars, [held(candles=[C_NY])], live_exec_order=True, sizing_ladder_caps=True,
                 starting_balance=40.0, min_tradeable_balance=5.0)
    assert len(res.trades) == 0                        # SizingLadder.POSITION_FLOOR = $50


# ---------------------------------------------------------------------------
# (1) risk_rules
# ---------------------------------------------------------------------------

def _falling_bars():
    """Steady fall: every BUY is stopped out within a few minutes."""
    return make_bars(price_fn=lambda t: 4000.0 - 0.02 * (t - T0) / 60.0)


def _three_buys():
    cands = [C_NY, C_NY + 900, C_NY + 1800]
    return [Fire(candles=cands[:1]),
            Fire(name="BB_MEAN_REVERSION_V5", magic=5002, candles=cands[1:2]),
            Fire(name="NVMR_TARGET_10_V5", magic=5003, candles=cands[2:])]


def test_early_phase_two_losing_trades_cap_blocks_third_entry():
    bars = _falling_bars()
    _, off = run(bars, _three_buys(), live_exec_order=True, starting_balance=150.0)
    assert len(off.trades) == 3 and all(t.net_pl < 0 for t in off.trades)
    eng, on = run(bars, _three_buys(), live_exec_order=True, risk_rules_enforce=True, starting_balance=150.0)
    assert len(on.trades) == 2                                    # third blocked: 2 losing trades today
    assert eng.rr_state.day_losing_trades == 2


def test_enforce_from_ts_runs_state_machine_but_only_blocks_later():
    bars = _falling_bars()
    _, shadow = run(bars, _three_buys(), live_exec_order=True, risk_rules_enforce=True,
                    risk_rules_enforce_from_ts=DAY + 86400, starting_balance=150.0)
    assert len(shadow.trades) == 3                                # shadow: counted, not blocking
    assert shadow.diagnostics["risk_state_final"]["day_losing_trades"] == 3


def test_three_consecutive_losses_pause_new_entries_for_four_hours():
    bars = _falling_bars()
    cands = [C_NY, C_NY + 900, C_NY + 1800, C_NY + 2700]
    strat = [Fire(candles=cands[:1]), Fire(name="BB_MEAN_REVERSION_V5", magic=5002, candles=cands[1:2]),
             Fire(name="NVMR_TARGET_10_V5", magic=5003, candles=cands[2:3]),
             Fire(name="FVG_NY_TIGHT_V5", magic=5005, candles=cands[3:])]
    eng, res = run(bars, strat, live_exec_order=True, risk_rules_enforce=True, starting_balance=500.0)
    assert len(res.trades) == 3                                   # balance >= $400: no 2-loss cap; 4th paused
    assert eng.rr_state.consecutive_losses == 3
    assert eng.rr_state.pause_until_ts > C_NY + 2700


def test_five_losses_stop_the_day_and_a_win_resets_the_streak():
    from src.backtesting.engine import Position
    eng = BacktestEngine(bars=make_bars(), cost=SCENARIOS["observed"], config=EngineConfig(risk_rules_enforce=True))
    pos = Position(ticket=1, strategy="x", magic=1, is_buy=True, lots=0.01, entry_price=4000.0,
                   entry_time=DAY, sl=0, tp=0, atr_at_entry=1.0, session="s")
    when = DAY + 14 * 3600
    for i in range(5):
        eng.balance = 500.0
        eng._rr_after_close(pos, -1.0, when + i * 600)
    assert eng.rr_state.consecutive_losses == 5
    assert eng.rr_state.day_stopped_date == datetime.fromtimestamp(when, UTC).astimezone(IST).date().isoformat()
    eng._rr_after_close(pos, +2.0, when + 4000)
    assert eng.rr_state.consecutive_losses == 0


def test_daily_loss_cap_three_percent_of_day_start_below_400():
    eng = BacktestEngine(bars=make_bars(), cost=SCENARIOS["observed"],
                         config=EngineConfig(risk_rules_enforce=True, live_exec_order=True))
    now = datetime.fromtimestamp(C_NY + 900, UTC).astimezone(IST)
    from src.core import risk_rules
    dec, st = risk_rules.evaluate(200.0, 200.0, 0.0, now=now, state=eng.rr_state)   # anchors day at $200
    assert dec.allow_new_entries
    dec, _ = risk_rules.evaluate(200.0, 193.9, 0.0, now=now, state=st)              # -3.05% equity
    assert not dec.allow_new_entries and "daily loss" in dec.reason
    dec, _ = risk_rules.evaluate(200.0, 194.5, 0.0, now=now, state=st)              # -2.75%
    assert dec.allow_new_entries


def test_peak_drawdown_hard_halt_via_seed_state():
    bars = _hold_open_bars()
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["observed"],
                         config=EngineConfig(symbol="XAUUSDm", starting_balance=150.0, sizing_mode="fixed",
                                             enable_d1_bias_gate=False, live_exec_order=True,
                                             risk_rules_enforce=True))
    eng.seed_risk_state(peak_equity=300.0)               # 150 is a 50% drawdown from peak
    res = eng.run([Fire(candles=[C_NY])], DAY, DAY + 20 * 3600)
    assert len(res.trades) == 0
    assert "peak drawdown" in res.diagnostics["risk_state_final"]["hard_halt_reason"]


def test_seed_risk_state_rejects_unknown_fields(flat_bars):
    eng = BacktestEngine(bars=flat_bars, cost=SCENARIOS["observed"], config=EngineConfig())
    with pytest.raises(TypeError):
        eng.seed_risk_state(nonsense=1)


def test_streak_blind_spot_ignores_positions_closed_within_one_scan():
    eng = BacktestEngine(bars=make_bars(), cost=SCENARIOS["observed"],
                         config=EngineConfig(risk_rules_enforce=True, streak_blind_spot=True))
    t = DAY + 14 * 3600

    def pos(entry_off, frac):
        return Position(ticket=1, strategy="x", magic=1, is_buy=True, lots=0.01, entry_price=4000.0,
                        entry_time=t + entry_off, sl=0, tp=0, atr_at_entry=1.0, session="s", hit_frac=frac)

    eng.balance = 500.0
    eng._rr_after_close(pos(30, 0.2), -1.0, t + 60)         # held ~ 50s -> the next loop never saw it
    assert eng.rr_state.consecutive_losses == 0
    assert eng.diag["streak_blind_closes"] == 1
    eng._rr_after_close(pos(30, 0.9), -1.0, t + 60)         # held ~ 84s -> recorded
    assert eng.rr_state.consecutive_losses == 1


def test_note_hit_estimates_position_of_the_crossing_inside_the_minute():
    eng = BacktestEngine(bars=make_bars(), cost=SCENARIOS["observed"],
                         config=EngineConfig(streak_blind_spot=True))
    bar = np.array([(0, 100.0, 100.5, 96.0, 99.0, 1, 0, 0)], dtype=RATE_DTYPE)[0]
    p = Position(ticket=1, strategy="x", magic=1, is_buy=True, lots=0.01, entry_price=100.0,
                 entry_time=0, sl=98.0, tp=105.0, atr_at_entry=1.0, session="s")
    eng._note_hit(p, bar, 98.0, 0, 0.001)
    # bar is down (O 100 -> H 100.5 -> L 96 -> C 99): stop at 98 is crossed on the way down
    assert 0.1 < p.hit_frac < 0.8
    q = Position(ticket=2, strategy="x", magic=1, is_buy=True, lots=0.01, entry_price=100.0,
                 entry_time=0, sl=99.99, tp=105.0, atr_at_entry=1.0, session="s")
    eng._note_hit(q, bar, 99.99, 0, 0.001)
    assert q.hit_frac < p.hit_frac                           # nearer stop -> earlier in the minute


# ---------------------------------------------------------------------------
# (5) D1 intraday override
# ---------------------------------------------------------------------------

def _bullish_d1():
    # steady +4/day: median |diff| = 4, last closed bar well above EMA20 -> BULLISH
    return [3600.0 + 4 * i for i in range(60)]


def test_d1_forming_bar_is_built_from_m1_without_lookahead():
    bars = make_bars(price_fn=lambda t: 4000.0 + (t - DAY) / 60.0 * 0.1 if t >= DAY else 4000.0)
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["observed"], config=EngineConfig())
    now = DAY + 10 * 3600
    o, h, l, c = eng._forming_d1(now)
    assert o == pytest.approx(4000.0)                     # first M1 open of the UTC day
    assert c == pytest.approx(4000.0 + 600 * 0.1, abs=0.2)  # last fully closed M1 before `now`
    assert h >= c >= l
    # nothing after `now` leaks in
    assert eng._forming_d1(DAY + 60)[3] < c


def _d1_view_for(bars, eng, ts_now):
    idx_cut = ts_now
    return eng._view(bars.d1, eng._d1_t, idx_cut, 50, 86400)


def test_d1_intraday_override_flips_bias_when_forming_bar_moves_against_it():
    # day opens at 4000 and sells off 30 points by 10:00 UTC
    fall = lambda t: (4000.0 - 30.0 * min(1.0, (t - DAY) / 36000.0)) if t >= DAY else 4000.0
    bars = make_bars(price_fn=fall, d1=_bullish_d1())
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["observed"],
                         config=EngineConfig(d1_intraday_override=True, d1_intraday_override_mult=1.0))
    now = DAY + 10 * 3600
    view = _d1_view_for(bars, eng, now)
    assert eng._live_d1_bias(view, now) == "BEARISH"       # |move| 30 >= 1.0 x median 4 -> overridden
    eng.cfg.d1_intraday_override_mult = 100.0              # threshold far above the move
    assert eng._live_d1_bias(view, now) == "BULLISH"       # closed-bar bias stands
    # early in the day the move is small -> still bullish at mult 1.0
    eng.cfg.d1_intraday_override_mult = 1.0
    early = DAY + 5 * 60
    assert eng._live_d1_bias(_d1_view_for(bars, eng, early), early) == "BULLISH"


def test_d1_override_threshold_is_a_multiple_of_the_median_abs_daily_close_diff():
    # closed-bar bias BEARISH (falling daily closes, |diff| = 4); the forming bar rallies +12
    up = lambda t: (4000.0 + 12.0 * min(1.0, (t - DAY) / 36000.0)) if t >= DAY else 4000.0
    bars = make_bars(price_fn=up, d1=[4400.0 - 4 * i for i in range(60)])
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["observed"],
                         config=EngineConfig(d1_intraday_override=True))
    now = DAY + 10 * 3600
    view = _d1_view_for(bars, eng, now)
    # median |diff| of the last 15 closes (forming bar included) is 4, move is +12 -> ratio 3.0
    eng.cfg.d1_intraday_override_mult = 2.0      # the multiple the bot actually ran 2026-10-05..15
    assert eng._live_d1_bias(view, now) == "BULLISH"
    eng.cfg.d1_intraday_override_mult = 3.5
    assert eng._live_d1_bias(view, now) == "BEARISH"
    # too few daily bars -> no bias at all (main_loop requires >= 21)
    assert eng._live_d1_bias(view[-10:], now) is None


def test_d1_override_blocks_counter_trend_entry_end_to_end():
    fall = lambda t: (4000.0 - 30.0 * min(1.0, (t - DAY) / 36000.0)) if t >= DAY else 4000.0
    bars = make_bars(price_fn=fall, d1=_bullish_d1())
    mk = lambda: [Fire(candles=[C_NY])]                      # BUY
    _, closed_only = run(bars, mk(), enable_d1_bias_gate=True, live_exec_order=True)
    assert len(closed_only.trades) == 1                      # closed bar says BULLISH -> BUY passes
    _, overridden = run(bars, mk(), enable_d1_bias_gate=True, live_exec_order=True, d1_intraday_override=True)
    assert len(overridden.trades) == 0
    assert overridden.diagnostics["entries_blocked_d1_bias"] >= 1


# ---------------------------------------------------------------------------
# (6) protect_profit
# ---------------------------------------------------------------------------

def _bar(o, h, l, c, spread=0):
    return np.array([(0, o, h, l, c, 1, spread, 0)], dtype=RATE_DTYPE)[0]


def _engine_with_position(is_buy=True, entry=4000.0, mfe=None, price_current=None, strategy="TREND_PULLBACK_V5"):
    eng = BacktestEngine(bars=make_bars(), cost=SCENARIOS["frictionless"],
                         config=EngineConfig(protect_profit=True, symbol="XAUUSDm"))
    p = Position(ticket=1, strategy=strategy, magic=5001, is_buy=is_buy, lots=0.01, entry_price=entry,
                 entry_time=DAY, sl=entry - 4 if is_buy else entry + 4, tp=entry + 10 if is_buy else entry - 10,
                 atr_at_entry=2.0, session="s",
                 mfe_price=mfe if mfe is not None else entry,
                 price_current=price_current if price_current is not None else entry)
    eng.positions.append(p)
    return eng, p


def test_protect_giveback_closes_green_position_and_arms_cooldown():
    # long: peak +7 (>= 6), now falling back through +0.8 (inside [0.5, 1.0])
    eng, p = _engine_with_position(mfe=4007.0)
    eng.cfg.protect_giveback_peak, eng.cfg.protect_giveback_floor = 6.0, 1.0
    view = np.zeros(60, dtype=RATE_DTYPE)
    eng._protect_profit_step(_bar(4001.5, 4001.6, 4000.8, 4001.0), DAY + 600, 5, view)
    assert eng.positions == [] and eng.trades[-1].exit_reason == "PROTECT_GIVEBACK"
    assert eng.trades[-1].exit_price == pytest.approx(4000.8)        # worst point in the band
    assert eng.cooldown_until["TREND_PULLBACK_V5"] == DAY + 600 + 45 * 60


def test_protect_giveback_needs_peak_and_a_green_floor():
    for mfe, worst in ((4004.0, 4000.8),      # peak only +4 < 6
                       (4007.0, 4000.2),      # fell below MIN_GREEN (0.5): stop handles it
                       (4007.0, 4003.0)):     # still well in profit (3 > floor 1.0)
        eng, p = _engine_with_position(mfe=mfe)
        eng._protect_profit_step(_bar(worst + 0.3, worst + 0.5, worst, worst + 0.2), DAY + 600, 5,
                                 np.zeros(60, dtype=RATE_DTYPE))
        assert len(eng.positions) == 1, (mfe, worst)


def test_protect_giveback_short_uses_ask_side():
    eng = BacktestEngine(bars=make_bars(), cost=SCENARIOS["observed"], config=EngineConfig(protect_profit=True))
    p = Position(ticket=1, strategy="S", magic=5001, is_buy=False, lots=0.01, entry_price=4000.0,
                 entry_time=DAY, sl=4004.0, tp=3990.0, atr_at_entry=2.0, session="s",
                 mfe_price=3993.0, price_current=3999.0)
    eng.positions.append(p)
    # bar high 3998.9 bid + 200pt spread (0.2) -> ask 3999.1 -> short profit 0.9 inside [0.5, 1.0]
    eng._protect_profit_step(_bar(3998.5, 3998.9, 3998.0, 3998.4, spread=200), DAY + 600, 5,
                             np.zeros(60, dtype=RATE_DTYPE))
    assert eng.positions == [] and eng.trades[-1].exit_reason == "PROTECT_GIVEBACK"


def _reversal_view(bearish: bool):
    """40 M15 bars, trend up, then a strong bearish bar closing below the prior low at [-2]."""
    n = 40
    v = np.zeros(n, dtype=RATE_DTYPE)
    c = 4000.0 + np.arange(n) * 0.5
    v["open"], v["close"] = c - 0.2, c
    v["high"], v["low"] = c + 0.4, c - 0.5
    if bearish:
        j = n - 2
        v["open"][j], v["close"][j] = c[j] + 3.0, c[j] - 6.0
        v["high"][j], v["low"][j] = c[j] + 3.2, c[j] - 6.2          # body/range > 55%, closes < prior low
    v["time"] = DAY + 900 * np.arange(n)
    return v


def test_protect_clean_reversal_closes_green_long_on_new_m15_bar_only():
    eng, p = _engine_with_position(entry=3999.0, price_current=4000.0)
    view = _reversal_view(True)
    eng._protect_profit_step(_bar(4000.0, 4000.2, 3999.8, 4000.0), DAY + 900, 3, view)     # m != 0
    assert len(eng.positions) == 1                                   # not a fresh M15 bar -> not checked
    eng._protect_profit_step(_bar(4000.0, 4000.2, 3999.8, 4000.0), DAY + 900, 0, view)     # first minute
    assert eng.positions == [] and eng.trades[-1].exit_reason == "PROTECT_REVERSAL"


def test_protect_reversal_ignores_losing_positions_and_calm_bars():
    eng, _ = _engine_with_position(entry=4001.0, price_current=4000.0)        # underwater
    eng._protect_profit_step(_bar(4000.0, 4000.2, 3999.8, 4000.0), DAY + 900, 0, _reversal_view(True))
    assert len(eng.positions) == 1
    eng2, _ = _engine_with_position(entry=3999.0, price_current=4000.0)       # green but no reversal bar
    eng2._protect_profit_step(_bar(4000.0, 4000.2, 3999.8, 4000.0), DAY + 900, 0, _reversal_view(False))
    assert len(eng2.positions) == 1


def test_protect_cooldown_blocks_reentry_until_it_expires():
    bars = _hold_open_bars()
    cands = [C_NY + 900, C_NY + 3600]            # decided at C_NY+1800 and C_NY+4500
    mk = lambda: [held(candles=cands)]
    kw = dict(symbol="XAUUSDm", starting_balance=500.0, sizing_mode="fixed", enable_d1_bias_gate=False,
              live_exec_order=True, max_concurrent=3, max_same_direction=3)
    _, base = run(bars, mk(), live_exec_order=True, max_concurrent=3, max_same_direction=3)
    assert len(base.trades) == 2
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["observed"], config=EngineConfig(protect_profit=True, **kw))
    eng.cooldown_until["TREND_PULLBACK_V5"] = C_NY + 1800 + 45 * 60      # a reversal close just before the 1st signal
    res = eng.run(mk(), DAY, DAY + 86400 - 3600)
    assert len(res.trades) == 1                                           # 1st blocked, 2nd (>45 min later) allowed
    assert res.trades[0].entry_time >= C_NY + 4500
    assert res.diagnostics["entries_blocked_cooldown"] >= 1
    # cooldown is only honoured when protect_profit is on
    eng2 = BacktestEngine(bars=bars, cost=SCENARIOS["observed"], config=EngineConfig(protect_profit=False, **kw))
    eng2.cooldown_until["TREND_PULLBACK_V5"] = C_NY + 1800 + 45 * 60
    assert len(eng2.run(mk(), DAY, DAY + 86400 - 3600).trades) == 2


# ---------------------------------------------------------------------------
# (7) entry delay
# ---------------------------------------------------------------------------

def test_entry_delay_fills_at_the_interpolated_price_inside_the_first_minute():
    # price rises 0.6 per minute -> 30s in is 0.3 above the minute's open
    bars = make_bars(price_fn=lambda t: 4000.0 + 0.6 * (t - T0) / 60.0 * 0.05)
    _, none = run(bars, [Fire(is_buy=False, candles=[C_NY])], live_exec_order=True)
    _, late = run(bars, [Fire(is_buy=False, candles=[C_NY])], live_exec_order=True, entry_delay_sec=30)
    dp = late.trades[0].entry_price - none.trades[0].entry_price
    assert dp == pytest.approx(0.5 * 0.6 * 0.05, abs=1e-6)                # SELL fills on bid
    assert late.trades[0].entry_time - none.trades[0].entry_time == 30


def test_entry_delay_zero_is_identical_to_the_legacy_fill(flat_bars):
    _, legacy = run(flat_bars, [Fire(candles=[C_NY])])
    _, parity0 = run(flat_bars, [Fire(candles=[C_NY])], live_exec_order=True)
    a, b = legacy.trades[0], parity0.trades[0]
    assert (a.entry_time, a.entry_price, a.sl, a.tp) == (b.entry_time, b.entry_price, b.sl, b.tp)


# ---------------------------------------------------------------------------
# bot downtime / retired legs
# ---------------------------------------------------------------------------

def test_whole_bot_down_window_suppresses_entries(flat_bars):
    _, up = run(flat_bars, [Fire(candles=[C_NY])])
    assert len(up.trades) == 1
    _, down = run(flat_bars, [Fire(candles=[C_NY])], disabled_windows={"*": [(C_NY, C_NY + 2400)]})
    assert len(down.trades) == 0
    _, after = run(flat_bars, [Fire(candles=[C_NY])], disabled_windows={"*": [(C_NY - 7200, C_NY + 600)]},
                   live_exec_order=True)
    # outage ends 5 min after the signal bar closes at C_NY+900? it ends BEFORE -> trade allowed
    assert len(after.trades) == 1


def test_per_strategy_window_only_silences_that_strategy(flat_bars):
    a = Fire(candles=[C_NY])
    b = Fire(name="BB_MEAN_REVERSION_V5", magic=5002, candles=[C_NY + 900])
    _, res = run(flat_bars, [a, b], disabled_windows={"TREND_PULLBACK_V5": [(DAY, DAY + 86400)]})
    assert [t.strategy for t in res.trades] == ["BB_MEAN_REVERSION_V5"]


def test_protect_watcher_window_disables_only_protection():
    eng, p = _engine_with_position(mfe=4007.0)
    eng.cfg.protect_giveback_floor = 1.0
    eng._down_windows = {"@protect_profit": [(0, DAY + 10**6)]}
    assert eng._is_down("@protect_profit", DAY + 5)
    assert not eng._is_down("TREND_PULLBACK_V5", DAY + 5)


# ---------------------------------------------------------------------------
# news blackout
# ---------------------------------------------------------------------------

def test_news_blackout_blocks_entries_when_flagged(monkeypatch, flat_bars):
    from src.core import news_filter
    monkeypatch.setattr(news_filter, "is_near_news_event", lambda now=None: (True, "NFP"))
    _, off = run(flat_bars, [Fire(candles=[C_NY])])
    assert len(off.trades) == 1
    _, on = run(flat_bars, [Fire(candles=[C_NY])], news_blackout=True)
    assert len(on.trades) == 0
    assert on.diagnostics["scans_news_blackout"] > 0


# ---------------------------------------------------------------------------
# parity preset end-to-end smoke test
# ---------------------------------------------------------------------------

def test_live_parity_preset_runs_end_to_end(flat_bars):
    cfg = EngineConfig.live_parity_preset(symbol="XAUUSDm", starting_balance=150.0, record_decisions=True,
                                          enable_d1_bias_gate=False)
    eng = BacktestEngine(bars=flat_bars, cost=SCENARIOS["observed"], config=cfg)
    res = eng.run([Fire(candles=[C_NY])], DAY, DAY + 86400 - 3600)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.lots == pytest.approx(0.01)
    assert t.entry_time - (C_NY + 900) == cfg.entry_delay_sec
    assert any(d["outcome"] == "entered" for d in res.diagnostics["decisions"])


# ---------------------------------------------------------------------------
# missing M1 data (2026-11-01): the engine refuses the M15 fallback by default
# ---------------------------------------------------------------------------

def _bars_with_m1_hole(bars, hole_start, hole_end):
    """Same series with every M1 bar in [hole_start, hole_end) removed."""
    import dataclasses
    t = bars.m1["time"].astype(np.int64)
    keep = (t < hole_start) | (t >= hole_end)
    return dataclasses.replace(bars, m1=bars.m1[keep])


def test_missing_m1_raises_instead_of_resolving_exits_on_m15(flat_bars):
    from src.backtesting.engine import MissingM1Error

    holed = _bars_with_m1_hole(flat_bars, C_NY + 900, C_NY + 1800)
    with pytest.raises(MissingM1Error) as exc:
        run(holed, [Fire(candles=[C_NY])])
    assert "no M1 bars" in str(exc.value)
    assert exc.value.ts == C_NY + 900


def test_coarse_policy_restores_the_old_m15_fallback(flat_bars):
    holed = _bars_with_m1_hole(flat_bars, C_NY + 900, C_NY + 1800)
    eng, res = run(holed, [Fire(candles=[C_NY])], m1_policy="coarse")
    assert res.diagnostics["bars_without_m1"] >= 1


def test_m1_series_entirely_absent_is_refused(flat_bars):
    import dataclasses

    from src.backtesting.engine import MissingM1Error

    with pytest.raises(MissingM1Error):
        run(dataclasses.replace(flat_bars, m1=None), [Fire(candles=[C_NY])])


def test_m1_policy_rejects_an_unknown_value():
    with pytest.raises(ValueError, match="m1_policy"):
        EngineConfig(m1_policy="whatever")


def test_require_is_the_default_so_a_silent_fallback_cannot_come_back():
    assert EngineConfig().m1_policy == "require"
    assert EngineConfig.live_parity_preset().m1_policy == "require"


def test_skip_policy_never_resolves_on_m15_and_counts_what_it_cost(flat_bars):
    # the signal on C_NY fills on the next candle; hole the one after that, so a
    # position is open while the minute prices are missing
    holed = _bars_with_m1_hole(flat_bars, C_NY + 1800, C_NY + 2700)
    eng, res = run(holed, [held(candles=[C_NY])], m1_policy="skip")
    d = res.diagnostics
    assert d["bars_skipped_no_m1"] == 1
    assert d["bars_without_m1"] == 0          # no M15 substitution happened
    assert d["exits_unchecked_no_m1"] >= 1    # the held position went unchecked


def test_skip_policy_does_not_fill_an_entry_without_minute_prices(flat_bars):
    holed = _bars_with_m1_hole(flat_bars, C_NY + 900, C_NY + 1800)
    eng, res = run(holed, [Fire(candles=[C_NY])], m1_policy="skip")
    assert res.diagnostics["bars_skipped_no_m1"] == 1
    assert not [t for t in res.trades if t.entry_time < C_NY + 1800]


def test_skip_policy_reports_zero_when_m1_is_complete(flat_bars):
    eng, res = run(flat_bars, [Fire(candles=[C_NY])], m1_policy="skip")
    assert res.diagnostics["bars_skipped_no_m1"] == 0
    assert res.diagnostics["exits_unchecked_no_m1"] == 0
