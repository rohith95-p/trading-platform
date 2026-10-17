"""D1 gate rules (owner, 2026-10-17): a bearish daily trend blocks buys; the intraday override may only
tighten; a missing bias fails closed. Covers the live bot (main_loop) and the engine mirror."""
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from src.core import main_loop as ml


def sig(is_buy):
    return SimpleNamespace(is_buy=is_buy)


@pytest.mark.parametrize("closed,intraday,ok", [
    ("BULLISH", "BEARISH", True),     # crash day: tighten
    ("BEARISH", "BULLISH", False),    # bounce day: must NOT loosen
    ("BULLISH", "BULLISH", False),
    ("BEARISH", "BEARISH", False),
])
def test_override_may_only_tighten(closed, intraday, ok):
    assert ml._override_may_apply(closed, intraday) is ok


def test_bearish_blocks_buys_allows_sells_bullish_the_reverse():
    assert ml._d1_bias_allows(sig(True), "BEARISH", "X") is False
    assert ml._d1_bias_allows(sig(False), "BEARISH", "X") is True
    assert ml._d1_bias_allows(sig(False), "BULLISH", "X") is False
    assert ml._d1_bias_allows(sig(True), "BULLISH", "X") is True


def test_missing_bias_fails_closed_when_gate_enabled():
    with patch.object(ml, "ENABLE_D1_GATE", True):
        assert ml._d1_bias_allows(sig(True), None, "X") is False
        assert ml._d1_bias_allows(sig(False), None, "X") is False


def test_missing_bias_allowed_only_when_gate_disabled():
    with patch.object(ml, "ENABLE_D1_GATE", False):
        assert ml._d1_bias_allows(sig(True), None, "X") is True


def _view(closed_down=True, last_move=+50.0, n=30):
    """D1 view: steadily falling (BEARISH) or rising closes; the last bar is the forming bar."""
    dt_ = np.dtype([("open", "f8"), ("close", "f8")])
    arr = np.zeros(n, dtype=dt_)
    base = 4300.0
    for i in range(n - 1):
        px = base - 10 * i if closed_down else base + 10 * i
        arr[i] = (px, px)
    last = arr[n - 2]["close"]
    arr[n - 1] = (last, last + last_move)
    return arr


def _engine_bias(view, tighten_only):
    from src.backtesting.engine import BacktestEngine
    eng = SimpleNamespace(cfg=SimpleNamespace(d1_intraday_override_mult=1.0, d1_override_tighten_only=tighten_only),
                          diag={}, _forming_d1=lambda ts: None)
    return BacktestEngine._live_d1_bias(eng, view, 0)


def test_engine_as_ran_override_can_flip_bearish_to_bullish():
    assert _engine_bias(_view(closed_down=True, last_move=+50.0), tighten_only=False) == "BULLISH"


def test_engine_tighten_only_keeps_bearish_on_a_big_up_day():
    assert _engine_bias(_view(closed_down=True, last_move=+50.0), tighten_only=True) == "BEARISH"


def test_engine_tighten_only_still_turns_bullish_bearish_on_a_crash_day():
    assert _engine_bias(_view(closed_down=False, last_move=-50.0), tighten_only=True) == "BEARISH"
