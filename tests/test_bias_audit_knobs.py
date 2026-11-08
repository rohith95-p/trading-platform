"""The bias-audit knobs must default to the behaviour every published result used.

PREREG_BiasAudit_2026-11-09 added two EngineConfig fields so the engine's known
intrabar biases could be bounded by measurement. If either one's default drifts,
every number in research/registry/ silently changes meaning.
"""
import numpy as np
import pytest

from src.backtesting.engine import EngineConfig


def test_defaults_preserve_published_behaviour():
    c = EngineConfig()
    assert c.ambiguous_resolution == "sl_first", (
        "every published result resolved intrabar ambiguity stop-first")
    assert c.gap_fill_stops is False, (
        "every published result filled stops exactly at the level")


def test_live_parity_preset_does_not_enable_them():
    c = EngineConfig.live_parity_preset()
    assert c.ambiguous_resolution == "sl_first"
    assert c.gap_fill_stops is False


def test_knobs_are_settable_through_the_preset():
    c = EngineConfig.live_parity_preset(ambiguous_resolution="tp_first",
                                        gap_fill_stops=True)
    assert c.ambiguous_resolution == "tp_first"
    assert c.gap_fill_stops is True


def test_unknown_field_still_raises():
    with pytest.raises(TypeError):
        EngineConfig.live_parity_preset(ambigous_resolution="tp_first")  # typo


def _bar(o, h, l, c, spread=200.0):
    a = np.zeros(1, dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"),
                           ("low", "f8"), ("close", "f8"), ("spread", "f8"),
                           ("tick_volume", "i8")])
    a[0] = (0, o, h, l, c, spread, 1)
    return a[0]


class _Pos:
    """Only the attributes _stop_fill touches."""

    def __init__(self, is_buy, sl, lots=0.02):
        self.is_buy = is_buy
        self.sl = sl
        self.lots = lots


def _engine_shell(gap_fill):
    """A BacktestEngine is heavy; _stop_fill only needs cfg, diag, cost, spec."""
    from src.backtesting.costs import SCENARIOS
    from src.backtesting.engine import BacktestEngine

    class Shell:
        cfg = EngineConfig(gap_fill_stops=gap_fill)
        cost = SCENARIOS["realistic_ecn"]
        diag = {"gapped_stops": 0, "gapped_stop_extra_usd": 0.0}

        def _value_per_price(self, lots):
            return 100.0 * lots

    s = Shell()
    s._stop_fill = BacktestEngine._stop_fill.__get__(s, Shell)
    return s


def test_long_stop_fills_at_level_by_default_even_on_a_gap():
    s = _engine_shell(gap_fill=False)
    pos = _Pos(is_buy=True, sl=2000.0)
    # bar opens 10 dollars BELOW the stop: a real fill would be far worse
    px = s._stop_fill(pos, _bar(1990.0, 1995.0, 1985.0, 1992.0), 0.001, 0.0, 200.0)
    assert px == pytest.approx(2000.0)
    assert s.diag["gapped_stops"] == 0


def test_long_stop_fills_at_the_gap_when_enabled():
    s = _engine_shell(gap_fill=True)
    pos = _Pos(is_buy=True, sl=2000.0)
    px = s._stop_fill(pos, _bar(1990.0, 1995.0, 1985.0, 1992.0), 0.001, 0.0, 200.0)
    assert px == pytest.approx(1990.0)
    assert s.diag["gapped_stops"] == 1
    # 10 dollars x 100 oz/lot x 0.02 lots = $20 of loss the default hides
    assert s.diag["gapped_stop_extra_usd"] == pytest.approx(20.0)


def test_no_gap_means_no_penalty_even_when_enabled():
    s = _engine_shell(gap_fill=True)
    pos = _Pos(is_buy=True, sl=2000.0)
    # opens above the stop and only later trades through it
    px = s._stop_fill(pos, _bar(2005.0, 2006.0, 1998.0, 1999.0), 0.001, 0.0, 200.0)
    assert px == pytest.approx(2000.0)
    assert s.diag["gapped_stops"] == 0


def test_short_stop_gap_uses_the_ask_side():
    s = _engine_shell(gap_fill=True)
    pos = _Pos(is_buy=False, sl=2000.0)
    # bid opens at 2000.5, ask = 2000.5 + 200*0.001 = 2000.7, through a 2000 stop
    px = s._stop_fill(pos, _bar(2000.5, 2001.0, 1999.0, 2000.0), 0.001, 0.0, 200.0)
    assert px == pytest.approx(2000.7)
    assert s.diag["gapped_stops"] == 1
