"""Two ledgers on one account: strategy view (own magics) vs account view (everything) (2026-10-18)."""
import json
from types import SimpleNamespace

import pytest

from src.core import scope


def pos(ticket, magic, profit=0.0, typ=0, vol=0.01, swap=0.0):
    return SimpleNamespace(ticket=ticket, magic=magic, profit=profit, type=typ, volume=vol, swap=swap,
                           symbol="XAUUSDm", comment="c")


OWN = frozenset({5001, 5002})


# ------------------------------------------------------------------ allowlist
def test_default_allowlist_loads_and_covers_portfolio():
    from src.strategies.portfolio_atlas import PORTFOLIO
    own = scope.load_own_magics()
    assert scope.check_portfolio_magics(PORTFOLIO, own) == []


def test_missing_portfolio_magic_is_reported():
    from src.strategies.portfolio_atlas import PORTFOLIO
    assert scope.check_portfolio_magics(PORTFOLIO, frozenset({1})) != []


@pytest.mark.parametrize("body", ["{not json", "{}", '{"ultra_core_magics": []}', '{"ultra_core_magics": ["a"]}',
                                  '{"ultra_core_magics": [true]}', '{"ultra_core_magics": [-1]}'])
def test_bad_allowlist_fails_closed(tmp_path, body):
    f = tmp_path / "m.json"
    f.write_text(body)
    with pytest.raises(scope.ScopeConfigError):
        scope.load_own_magics(str(f))


def test_missing_allowlist_file_fails_closed(tmp_path):
    with pytest.raises(scope.ScopeConfigError):
        scope.load_own_magics(str(tmp_path / "nope.json"))


# ------------------------------------------------------------------ split / report
def test_split_and_report():
    own, foreign = scope.split_positions([pos(1, 5001), pos(2, 5150001, profit=-66.12, typ=1)], OWN)
    assert [p.ticket for p in own] == [1] and [p.ticket for p in foreign] == [2]
    rep = scope.foreign_report(foreign)[0]
    assert rep["risk_scope"] == "account" and rep["magic"] == 5150001 and rep["ticket"] == 2
    assert rep["direction"] == "SELL" and rep["floating_pl"] == -66.12 and rep["volume"] == 0.01


def test_env_switches(monkeypatch):
    monkeypatch.delenv("ULTRA_ACCOUNT_WIDE_FLATTEN", raising=False)
    monkeypatch.delenv("ULTRA_BLOCK_ON_FOREIGN", raising=False)
    assert scope.account_wide_flatten_enabled() is False and scope.block_on_foreign_enabled() is True
    monkeypatch.setenv("ULTRA_ACCOUNT_WIDE_FLATTEN", "1")
    monkeypatch.setenv("ULTRA_BLOCK_ON_FOREIGN", "0")
    assert scope.account_wide_flatten_enabled() is True and scope.block_on_foreign_enabled() is False


# ------------------------------------------------------------------ fetcher scoping
class FakeFetcher:
    """Mirrors DataFetcher's scoping methods over a fixed position list."""
    def __init__(self, positions):
        self._p = positions

    def get_positions(self):
        return list(self._p)

    def get_own_positions(self):
        return scope.split_positions(self._p, OWN)[0]

    def get_foreign_positions(self):
        return scope.split_positions(self._p, OWN)[1]

    def get_foreign_exposure(self):
        return self.get_foreign_positions()

    def get_account_floating_pl(self):
        return sum(p.profit + p.swap for p in self._p)


def test_datafetcher_scoping(monkeypatch):
    from src.core import data_fetcher as df
    mixed = [pos(1, 5001, 5.0), pos(2, 5150001, -66.12)]
    monkeypatch.setattr(df.mt5, "positions_get", lambda **k: mixed, raising=False)
    monkeypatch.setattr(df.mt5, "initialize", lambda *a, **k: True, raising=False)
    f = df.DataFetcher("XAUUSDm", own_magics=OWN)
    assert [p.ticket for p in f.get_positions()] == [1, 2]
    assert [p.ticket for p in f.get_own_positions()] == [1]
    assert [p.ticket for p in f.get_foreign_positions()] == [2]


# ------------------------------------------------------------------ main_loop behaviour
def test_foreign_exposure_blocks_entry_without_touching_executor(monkeypatch):
    from src.core import main_loop as ml, live_status
    monkeypatch.delenv("ULTRA_MEASURE_ONLY", raising=False)
    monkeypatch.delenv("ULTRA_BLOCK_ON_FOREIGN", raising=False)
    monkeypatch.setattr(live_status, "_FOREIGN_SEEN", {"tickets": None})

    class Boom:
        def __getattr__(self, n):
            raise AssertionError(f"{n} must not be touched")

    sig = SimpleNamespace(strategy_name="T", direction_str="BUY", is_buy=True, magic=5001, direction=0)
    fetcher = FakeFetcher([pos(2, 5150001, -66.12)])
    assert ml._execute_signal(sig, None, fetcher, Boom(), Boom(), 1.0, "NY") is None


def test_foreign_alert_fires_once_per_ticket_set(monkeypatch):
    from src.core import main_loop as ml, live_status
    from src.core import alerts
    sent = []
    monkeypatch.setattr(alerts, "send", lambda m, severity=None, **k: sent.append(m))
    monkeypatch.setattr(live_status, "_FOREIGN_SEEN", {"tickets": None})
    f = [pos(2, 5150001)]
    ml._alert_foreign_exposure(f)
    ml._alert_foreign_exposure(f)
    assert len(sent) == 1 and "Other trades found" in sent[0]
    ml._alert_foreign_exposure([pos(2, 5150001), pos(3, 999)])
    assert len(sent) == 2


def test_kill_switch_closes_only_own_unless_account_wide(monkeypatch):
    from src.core import main_loop as ml, live_status
    from src.core import alerts
    monkeypatch.setattr(alerts, "send", lambda *a, **k: None)
    closed = []

    class Ex:
        def close_position(self, p, *a, **k):
            closed.append(p.ticket)
            return True

    fetch = FakeFetcher([pos(1, 5001), pos(2, 5150001)])
    monkeypatch.delenv("ULTRA_ACCOUNT_WIDE_FLATTEN", raising=False)
    ml._close_all_positions(fetch, Ex(), "test")
    assert closed == [1]                       # foreign ticket 2 untouched
    closed.clear()
    monkeypatch.setenv("ULTRA_ACCOUNT_WIDE_FLATTEN", "1")
    ml._close_all_positions(fetch, Ex(), "test")
    assert sorted(closed) == [1, 2]            # explicit opt-in only


# ------------------------------------------------------------------ veto: concurrency own-scoped, exposure account-wide
def test_veto_signature_accepts_own_positions():
    import inspect
    from src.core import pre_trade_veto as v
    assert "own_positions" in inspect.signature(v.PreTradeVeto.check).parameters


# ------------------------------------------------------------------ daily P&L costs, pending orders, reminder
def test_daily_pnl_counts_commission_fee_swap_on_entry_and_exit_deals(monkeypatch):
    from src.core import data_fetcher as df
    D = lambda **k: SimpleNamespace(symbol="XAUUSDm", magic=k.pop("magic", 5001), **k)
    deals = [D(type=0, entry=0, profit=0.0, swap=0.0, commission=-0.07, fee=-0.01),     # entry costs
             D(type=1, entry=1, profit=-1.00, swap=-0.02, commission=-0.07, fee=0.0),   # exit
             D(type=2, entry=0, profit=500.0, swap=0.0, commission=0.0, fee=0.0)]       # balance deposit: ignored
    monkeypatch.setattr(df.mt5, "history_deals_get", lambda *a, **k: deals, raising=False)
    monkeypatch.setattr(df.mt5, "initialize", lambda *a, **k: True, raising=False)
    f = df.DataFetcher("XAUUSDm", own_magics=OWN)
    assert round(f.get_todays_closed_pl(), 2) == -1.17


def test_foreign_pending_order_counts_as_foreign_exposure(monkeypatch):
    from src.core import data_fetcher as df
    order = SimpleNamespace(ticket=9, magic=777, symbol="XAUUSDm", type=2, volume_current=0.02, comment="")
    monkeypatch.setattr(df.mt5, "positions_get", lambda **k: [], raising=False)
    monkeypatch.setattr(df.mt5, "orders_get", lambda **k: [order, SimpleNamespace(ticket=10, magic=5001)], raising=False)
    monkeypatch.setattr(df.mt5, "initialize", lambda *a, **k: True, raising=False)
    f = df.DataFetcher("XAUUSDm", own_magics=OWN)
    assert [o.ticket for o in f.get_foreign_exposure()] == [9]
    assert scope.foreign_report(f.get_foreign_exposure())[0]["kind"] == "pending"


def test_foreign_alert_repeats_after_30_min_while_persisting(monkeypatch):
    from src.core import main_loop as ml, alerts, live_status
    sent = []
    monkeypatch.setattr(alerts, "send", lambda m, severity=None, **k: sent.append(m))
    monkeypatch.setattr(live_status, "_FOREIGN_SEEN", {"tickets": None})
    clock = [1000.0]
    monkeypatch.setattr(ml._time, "time", lambda: clock[0])
    f = [pos(2, 5150001)]
    ml._alert_foreign_exposure(f); ml._alert_foreign_exposure(f)
    assert len(sent) == 1
    clock[0] += 1801
    ml._alert_foreign_exposure(f)
    assert len(sent) == 2


# ------------------------------------------------------------------ spread blip must not burn the candle's signal
def test_spread_block_is_flagged_transient(monkeypatch):
    from unittest.mock import Mock
    from src.core import main_loop as ml, live_status
    monkeypatch.delenv("ULTRA_MEASURE_ONLY", raising=False)
    monkeypatch.setattr(ml.market_hours, "allow_new_entry", lambda *a, **k: (True, ""))
    fetcher = Mock(); fetcher.get_foreign_exposure.return_value = []
    risk = Mock(); risk.is_spread_ok.return_value = False
    strat = SimpleNamespace(max_spread_pts=250, name="FVG_NY_TIGHT_V5")
    sig = SimpleNamespace(strategy_name="FVG_NY_TIGHT_V5", direction_str="SELL", is_buy=False, magic=5005, direction=1)
    ml._TRANSIENT_BLOCK["flag"] = False
    assert ml._execute_signal(sig, None, fetcher, risk, Mock(), 1.0, "NY_MORNING", strat) is None
    assert ml._TRANSIENT_BLOCK["flag"] is True


# ------------------------------------------------------------------ live stops use closed bars, like the backtest
def test_stop_atr_excludes_the_bar_that_just_opened(monkeypatch):
    """copy_rates_from_pos(0) ends with the forming bar; its few seconds of range shrank the live ATR 5-9%
    below the backtest's (RESULT_StopRobustness_2026-11-01). The stop calculation must get closed bars only."""
    from unittest.mock import Mock
    import numpy as np
    from src.core import main_loop as ml, live_status
    monkeypatch.delenv("ULTRA_MEASURE_ONLY", raising=False)
    monkeypatch.setattr(ml.market_hours, "allow_new_entry", lambda *a, **k: (True, ""))
    fetcher = Mock(); fetcher.get_foreign_exposure.return_value = []
    risk = Mock(); risk.is_spread_ok.return_value = True; risk.calculate_atr_stops.return_value = None
    strat = SimpleNamespace(max_spread_pts=None, name="ASIAN_RANGE_FILTERED_V6", sl_atr_mult=2.5, tp_atr_mult=3.5)
    sig = SimpleNamespace(strategy_name="ASIAN_RANGE_FILTERED_V6", direction_str="SELL", is_buy=False,
                          magic=7320, direction=1)
    rates = np.zeros(30, dtype=[("time", "i8"), ("high", "f8"), ("low", "f8"), ("close", "f8")])
    rates["time"] = np.arange(30) * 900
    assert ml._execute_signal(sig, rates, fetcher, risk, Mock(), 1.0, "LONDON_OPEN", strat) is None
    passed = risk.calculate_atr_stops.call_args.args[2]
    assert len(passed) == 29 and passed["time"][-1] == 28 * 900      # forming bar (index 29) dropped
