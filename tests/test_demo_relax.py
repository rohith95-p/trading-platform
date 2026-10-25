"""Demo-only relaxation of the monthly-loss / peak-drawdown hard halts (owner decision 2026-10-21)."""
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.core import risk_rules as rr

NOW = datetime(2026, 10, 21, 18, 45, tzinfo=rr.IST)


def state(**kw):
    s = rr.RiskState()
    s.peak_equity = 186.14; s.month_start_balance = 161.38; s.week_start_balance = 111.15
    s.day_start_balance = 111.15; s.day_anchor_date = NOW.date().isoformat()
    s.week_anchor_date = (NOW.date() - __import__("datetime").timedelta(days=NOW.weekday())).isoformat()
    s.month_anchor = "2026-10"
    for k, v in kw.items(): setattr(s, k, v)
    return s


def fake_mt5(monkeypatch, trade_mode, demo_const=0):
    import MetaTrader5 as mt5
    monkeypatch.setattr(mt5, "account_info", lambda: None if trade_mode is None else SimpleNamespace(trade_mode=trade_mode), raising=False)
    monkeypatch.setattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", demo_const, raising=False)


def run(equity=111.15, **kw):
    d, s = rr.evaluate(111.15, equity, now=NOW, state=state(**kw))
    return d, s


def test_default_context_keeps_hard_halts(monkeypatch):
    fake_mt5(monkeypatch, 0)                                   # a demo account, but NOT the live loop (e.g. a backtest)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", False)
    d, s = run()
    assert d.allow_new_entries is False and "HARD HALT" in d.reason and s.hard_halt_reason


def test_live_loop_on_demo_relaxes_peak_and_monthly(monkeypatch):
    fake_mt5(monkeypatch, 0)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    monkeypatch.setattr(rr, "DEMO_RELAX_HARD_HALTS", True)
    d, s = run()
    assert d.allow_new_entries is True and not s.hard_halt_reason


def test_live_loop_on_demo_ignores_a_stale_persisted_halt(monkeypatch):
    fake_mt5(monkeypatch, 0)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    monkeypatch.setattr(rr, "DEMO_RELAX_HARD_HALTS", True)
    d, _ = run(hard_halt_reason="monthly loss 31.1% >= 25%")
    assert d.allow_new_entries is True


@pytest.mark.parametrize("mode", [2, 1])                       # real, contest
def test_real_money_keeps_every_hard_halt(monkeypatch, mode):
    fake_mt5(monkeypatch, mode)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    d, s = run()
    assert d.allow_new_entries is False and "HARD HALT" in d.reason
    d2, _ = run(hard_halt_reason="x")
    assert d2.allow_new_entries is False


def test_unknown_account_fails_closed(monkeypatch):
    fake_mt5(monkeypatch, None)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    d, _ = run()
    assert d.allow_new_entries is False and "HARD HALT" in d.reason


def _daily_state():
    return state(peak_equity=111.15, month_start_balance=111.15, day_start_balance=111.15)


def test_daily_loss_cap_off_only_on_demo_in_live_loop(monkeypatch):
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    monkeypatch.setattr(rr, "DEMO_RELAX_DAILY_CAP", True)
    fake_mt5(monkeypatch, 0)
    d, _ = rr.evaluate(111.15, 104.0, now=NOW, state=_daily_state())                   # -6.4% today
    assert d.allow_new_entries is True
    for mode in (2, None):                                      # real / unknown account: the cap applies
        fake_mt5(monkeypatch, mode)
        d, _ = rr.evaluate(111.15, 104.0, now=NOW, state=_daily_state())
        assert d.allow_new_entries is False and "daily loss" in d.reason
    monkeypatch.setattr(rr, "LIVE_CONTEXT", False); fake_mt5(monkeypatch, 0)          # backtest context unchanged
    d, _ = rr.evaluate(111.15, 104.0, now=NOW, state=_daily_state())
    assert d.allow_new_entries is False and "daily loss" in d.reason
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True); monkeypatch.setattr(rr, "DEMO_RELAX_DAILY_CAP", False)
    d, _ = rr.evaluate(111.15, 104.0, now=NOW, state=_daily_state())
    assert d.allow_new_entries is False and "daily loss" in d.reason


def test_demo_still_obeys_the_weekly_cap(monkeypatch):
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True); fake_mt5(monkeypatch, 0)
    d, _ = rr.evaluate(111.15, 92.0, now=NOW, state=_daily_state())                    # -17% this week
    assert d.allow_new_entries is False and "WEEK HALTED" in d.reason


def test_switch_can_be_turned_off(monkeypatch):
    fake_mt5(monkeypatch, 0)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    monkeypatch.setattr(rr, "DEMO_RELAX_HARD_HALTS", False)
    d, _ = run()
    assert d.allow_new_entries is False and "HARD HALT" in d.reason


# ------------------------------------------------------------------ the pre-trade veto repeats the monthly cap
def _veto_state(month_start=161.38):
    return SimpleNamespace(pause_until_ts=0.0, consecutive_losses=0, week_start_balance=111.15, month_start_balance=month_start)


def test_veto_monthly_cap_relaxed_only_on_demo_in_live_loop(monkeypatch):
    from src.core.pre_trade_veto import PreTradeVeto
    monkeypatch.setattr(rr, "ENFORCE", True)
    monkeypatch.setattr(rr, "DEMO_RELAX_HARD_HALTS", True)
    v = PreTradeVeto()
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    fake_mt5(monkeypatch, 0)
    assert v._check_circuit_breakers(111.15, _veto_state()).allow is True
    fake_mt5(monkeypatch, 2)                                    # real money: the cap applies
    d = v._check_circuit_breakers(111.15, _veto_state()); assert d.allow is False and "Monthly" in d.reason
    fake_mt5(monkeypatch, None)                                 # unknown account: the cap applies
    assert v._check_circuit_breakers(111.15, _veto_state()).allow is False
    monkeypatch.setattr(rr, "LIVE_CONTEXT", False); fake_mt5(monkeypatch, 0)   # backtest context: the cap applies
    assert v._check_circuit_breakers(111.15, _veto_state()).allow is False
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True); fake_mt5(monkeypatch, 0)
    assert v._check_circuit_breakers(80.0, SimpleNamespace(pause_until_ts=0.0, consecutive_losses=0, week_start_balance=111.15, month_start_balance=161.38)).allow is False  # weekly cap (28%) still applies


# ------------------------------------------------------------------ streak breakers (3-loss pause, 2 losing trades/day)
def _streak_state(**kw):
    return state(peak_equity=111.15, month_start_balance=111.15, **kw)


def test_streak_breakers_off_only_on_demo_in_live_loop(monkeypatch):
    import time
    paused = dict(consecutive_losses=3, day_losing_trades=2, pause_until_ts=time.time() + 3600)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    monkeypatch.setattr(rr, "DEMO_RELAX_STREAK_BREAKERS", True)
    fake_mt5(monkeypatch, 0)
    d, _ = rr.evaluate(111.15, 111.15, now=NOW, state=_streak_state(**paused))
    assert d.allow_new_entries is True
    for mode in (2, None):                                      # real / unknown account: both breakers apply again
        fake_mt5(monkeypatch, mode)
        d, _ = rr.evaluate(111.15, 111.15, now=NOW, state=_streak_state(**paused))
        assert d.allow_new_entries is False and ("losing trades" in d.reason or "pause" in d.reason)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", False); fake_mt5(monkeypatch, 0)
    d, _ = rr.evaluate(111.15, 111.15, now=NOW, state=_streak_state(**paused))
    assert d.allow_new_entries is False                          # backtest context unchanged


def test_demo_still_stops_the_day_after_five_losses_and_obeys_daily_cap(monkeypatch):
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True); fake_mt5(monkeypatch, 0)
    d, _ = rr.evaluate(111.15, 111.15, now=NOW, state=_streak_state(day_stopped_date=NOW.date().isoformat()))
    assert d.allow_new_entries is False and "day stopped" in d.reason


def test_third_loss_does_not_set_a_pause_on_demo(monkeypatch):
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    monkeypatch.setattr(rr, "DEMO_RELAX_STREAK_BREAKERS", True)
    fake_mt5(monkeypatch, 0)
    s = rr.record_trade_result(-4.0, now=NOW, state=_streak_state(consecutive_losses=2))
    assert s.consecutive_losses == 3 and s.pause_until_ts == 0.0
    fake_mt5(monkeypatch, 2)                                    # real money: the pause is set
    s2 = rr.record_trade_result(-4.0, now=NOW, state=_streak_state(consecutive_losses=2))
    assert s2.pause_until_ts > 0


def test_veto_pause_relaxed_on_demo_only(monkeypatch):
    import time
    from src.core.pre_trade_veto import PreTradeVeto
    monkeypatch.setattr(rr, "ENFORCE", True); monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    monkeypatch.setattr(rr, "DEMO_RELAX_STREAK_BREAKERS", True)
    st = SimpleNamespace(pause_until_ts=time.time() + 3600, consecutive_losses=3, week_start_balance=111.15, month_start_balance=111.15)
    fake_mt5(monkeypatch, 0); assert PreTradeVeto()._check_circuit_breakers(111.15, st).allow is True
    fake_mt5(monkeypatch, 2); assert PreTradeVeto()._check_circuit_breakers(111.15, st).allow is False
