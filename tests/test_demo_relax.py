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
    d, s = run()
    assert d.allow_new_entries is True and not s.hard_halt_reason


def test_live_loop_on_demo_ignores_a_stale_persisted_halt(monkeypatch):
    fake_mt5(monkeypatch, 0)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
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


def test_demo_still_obeys_the_daily_loss_cap(monkeypatch):
    fake_mt5(monkeypatch, 0)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    d, _ = rr.evaluate(111.15, 104.0, now=NOW, state=state(day_start_balance=111.15))   # -6.4% today
    assert d.allow_new_entries is False and "daily loss" in d.reason


def test_switch_can_be_turned_off(monkeypatch):
    fake_mt5(monkeypatch, 0)
    monkeypatch.setattr(rr, "LIVE_CONTEXT", True)
    monkeypatch.setattr(rr, "DEMO_RELAX_HARD_HALTS", False)
    d, _ = run()
    assert d.allow_new_entries is False and "HARD HALT" in d.reason
