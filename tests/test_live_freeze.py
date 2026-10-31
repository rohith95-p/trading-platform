"""Freeze guard for the live Atlas setup (owner 2026-10-30: "if a system is changed, nothing [should break]").

Every number the live bot trades with is pinned here. A change to any of them fails CI, so it cannot reach the
VPS by accident; a deliberate change updates this file in the same commit, with the reason in the message.
"""
import os
from datetime import time

from src.atlas.rules import Thresholds
from src.core import execution_handler as eh, market_hours as mh, risk_rules
from src.strategies.portfolio_atlas import PORTFOLIO

# name: (magic, sl_atr_mult, tp_atr_mult)
LIVE_LEGS = {
    "ASIAN_RANGE_FILTERED_V6": (7320, 2.5, 3.5),
    "ASIAN_BREAKOUT_V6": (7311, 3.0, 5.0),
    "LONDON_MOMENTUM_TIGHT_V6": (7324, 2.0, 4.0),
    "NY_SESSION_REVERSAL_V6": (7313, 2.5, 4.5),
}


def test_live_portfolio_is_the_validated_four_legs():
    got = {}
    for cls in PORTFOLIO:
        s = cls()
        got[s.name] = (s.magic, s.sl_atr_mult, s.tp_atr_mult)
    assert got == LIVE_LEGS


def test_daily_trend_gate_applies_to_every_live_leg():
    """Owner 2026-10-30: live runs the gated system that was validated (skipping it was break-even, PF 0.99)."""
    from src.core import main_loop
    assert main_loop.ENABLE_D1_GATE is True
    assert all(getattr(cls(), "skip_d1_gate", False) is False for cls in PORTFOLIO)


def test_sizing_and_position_caps():
    assert eh.FIXED_LOT_SIZE == 0.02
    assert eh.MAX_CONCURRENT_POSITIONS == 3
    assert eh.MAX_TOTAL_VOLUME == 0.06
    assert eh.MAX_SAME_DIRECTION_POSITIONS == 3
    # (balance upper bound, lots per order, max total lots, max positions)
    assert risk_rules.SIZING_LADDER == ((200.0, 0.01, 0.01, 1), (400.0, 0.01, 0.02, 2),
                                        (800.0, 0.01, 0.03, 3), (float("inf"), 0.02, 0.06, 3))
    assert risk_rules.sizing_for_balance(5000.0) == (0.02, 0.06, 3)


def test_atlas_safety_thresholds():
    t = Thresholds()
    assert (t.hard_fraction, t.protector_soft_pct, t.protector_flatten_pct) == (0.8, 0.01, 0.015)
    assert (t.margin_order_cap, t.margin_flatten) == (0.50, 0.65)


def test_trading_hours():
    assert mh.TRADING_WINDOW_IST == (6.0, 21.5)          # only when ULTRA_TRADE_24H is not 1
    assert mh.FRIDAY_NO_NEW_IST == time(21, 30)
    assert mh.FRIDAY_FLATTEN_IST == time(22, 30)


def test_switch_defaults_when_env_is_unset(monkeypatch):
    """With no .env.local the safe defaults apply: protector on, hourly pulse on, day window enforced."""
    import importlib
    from scripts import watchdog
    for k in ("ULTRA_PROTECT_PROFIT", "ULTRA_PULSE_EVERY_H", "ULTRA_TRADE_24H"):
        monkeypatch.delenv(k, raising=False)
    try:
        assert importlib.reload(watchdog).PROTECT_PROFIT_ON is True
        assert watchdog.PULSE_EVERY_H == 1
        assert importlib.reload(mh).ENFORCE_TRADING_WINDOW is True
    finally:
        importlib.reload(watchdog)
        importlib.reload(mh)


def test_the_live_configuration_is_one_a_recorded_backtest_actually_tested(monkeypatch):
    """The config-integrity gate, exercised.

    This gate exists because the same failure keeps happening here: a cap or a
    leg changes and no backtest is re-run. On 2026-11-01 the ledger's newest
    entry was still the V5 portfolio with 2-position caps, so the gate had been
    failing and the bot was only starting with ULTRA_ALLOW_UNVALIDATED=1 -- the
    guard switched off. Recording the audited config fixed that, and this test
    keeps it fixed: change a live number without re-recording and CI fails.
    """
    from src.core import market_hours, validation_ledger

    # The VPS runs with ULTRA_TRADE_24H=1, so the fingerprint that has to be in
    # the ledger is the 24-hour one. The test environment leaves the trading
    # window on, which would fingerprint a configuration the VPS never runs.
    monkeypatch.setattr(market_hours, "ENFORCE_TRADING_WINDOW", False)
    report = validation_ledger.check_live_config()
    assert report["validated"], (
        "the live configuration matches no recorded backtest. Re-run "
        "scripts/validation/independent_audit_run.py and record it with "
        "validation_ledger.record(), rather than setting ULTRA_ALLOW_UNVALIDATED=1. "
        f"Differences from the newest entry: {report['diff']}")


def test_the_exit_code_that_was_measured_net_negative_stays_deleted():
    """Trailing and pyramiding: PF 0.592 with them on against 1.478 with them off.

    Both flags were silently flipped back on once before (commit b8ab85c,
    2026-09-24). The code is gone now, so flipping a flag cannot bring the
    behaviour back -- this checks neither the flags nor the code return.
    """
    import inspect

    from src.core import main_loop

    assert main_loop.ENABLE_TRAILING is False
    assert main_loop.ENABLE_PYRAMIDING is False
    src = inspect.getsource(main_loop)
    assert "_check_pyramiding" not in src
    assert "calculate_trailing_stop" not in src
    assert "virtual_sl" not in src


def test_the_engine_will_not_resolve_an_exit_on_a_fifteen_minute_candle():
    """The default has to stay strict: coarse candles read PF 1.38 against 0.93."""
    from src.backtesting.engine import EngineConfig

    assert EngineConfig().m1_policy == "require"


def test_the_price_archive_stops_where_it_stops_agreeing_with_the_broker():
    """From January 2026 the archive and the broker differ by more than $1 on 29%
    of candles (scripts/validation/data_check.py, 2026-11-01)."""
    import datetime as dt

    from src.backtesting import master

    assert master.KAGGLE_END == int(dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    assert master.window("TEST")[1] == master.KAGGLE_END
