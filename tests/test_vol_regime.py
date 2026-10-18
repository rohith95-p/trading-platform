import pytest

from src.core import vol_regime as vr


def test_classify_buckets_and_boundaries():
    assert vr.classify(50, False) == vr.Regime("NORMAL", True, 1.0)
    assert vr.classify(25.0, False).name == "NORMAL" and vr.classify(85.0, False).name == "NORMAL"
    assert vr.classify(24.99, False) == vr.Regime("LOW", True, 0.5)
    assert vr.classify(85.01, False) == vr.Regime("HIGH", True, 0.5)


def test_event_overrides_everything_and_blocks():
    assert vr.classify(50, True) == vr.Regime("EVENT", False, 0.0)
    assert vr.classify(None, True).name == "EVENT"


def test_missing_input_fails_closed():
    r = vr.classify(None, False)
    assert r.name == "UNKNOWN" and r.allowed is False and r.risk_multiplier == 0.0


def test_percentile_excludes_current_and_needs_history():
    hist = list(range(1000))
    assert vr.atr_percentile(hist, 500) == pytest.approx(50.0, abs=0.1)
    assert vr.atr_percentile(list(range(100)), 50) is None          # < MIN_HISTORY
    assert vr.atr_percentile(hist, None) is None
    assert vr.atr_percentile(hist, float("nan")) is None


def test_percentile_uses_only_the_last_window():
    hist = [1000.0] * 5000 + [1.0] * vr.WINDOW
    assert vr.atr_percentile(hist, 2.0) == 100.0                     # old large values are out of the window


def test_event_window_is_30_before_60_after():
    e = 100_000
    assert vr.near_event(e - 1800, [e]) and vr.near_event(e + 3600, [e])
    assert not vr.near_event(e - 1801, [e]) and not vr.near_event(e + 3601, [e])
    assert not vr.near_event(e, [])
