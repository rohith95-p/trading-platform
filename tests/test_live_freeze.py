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
    "DONCHIAN_TREND_V6": (7310, 2.0, 4.0),
    "ASIAN_RANGE_FILTERED_V6": (7320, 2.0, 3.5),
    "ASIAN_BREAKOUT_V6": (7311, 3.0, 5.0),
    "LONDON_MOMENTUM_TIGHT_V6": (7324, 2.0, 4.0),
    "NY_SESSION_REVERSAL_V6": (7313, 2.5, 4.5),
}


def test_live_portfolio_is_the_validated_five_legs():
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
