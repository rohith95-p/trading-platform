"""Regression tests for the 2026-10-16 mechanical audit fixes."""
import os

from src.core import alerts, news_filter, risk_rules, trade_log, validation_ledger
from src.core.execution_handler import TradeRecord
from src.strategies.portfolio_atlas import PORTFOLIO


def test_trade_record_reads_like_mt5_result():
    r = TradeRecord(ticket=7, strategy="X", direction="BUY", price=1.0, sl=0.5, tp=2.0,
                    atr=1.0, session="S", timestamp_ist="t", lots=0.01)
    assert r.order == 7 and r.retcode == 10009 and r.lots == 0.01


def test_atlas_portfolio_magics():
    expected = {7310, 7311, 7313, 7320, 7324}
    assert expected == {int(c().magic) for c in PORTFOLIO}


def test_runtime_paths_are_absolute(monkeypatch):
    import importlib
    # conftest patches some of these per-test; check the module defaults on reload
    for mod, attr in ((trade_log, "LOG_DIR"), (risk_rules, "STATE_PATH"), (alerts, "ALERT_LOG"),
                      (validation_ledger, "LEDGER_PATH"), (news_filter, "NEWS_CALENDAR_PATH")):
        fresh = importlib.reload(mod)
        assert os.path.isabs(getattr(fresh, attr)), f"{mod.__name__}.{attr} is relative"
