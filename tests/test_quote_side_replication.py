"""Synthetic tests for conditional measurements, not a strategy simulator."""
import numpy as np
import pytest

from scripts.research.quote_side_replication import START, aggregate, features, match_controls, outcomes, validate


def quotes(count=120):
    dtype = [("time", "i8")] + [(f"{side}_{field}", "f8")
                                  for side in ("bid", "ask")
                                  for field in ("open", "high", "low", "close")]
    a = np.zeros(count, dtype=dtype)
    a["time"] = START + np.arange(count) * 60
    prices = 2000 + np.sin(np.arange(count)) * .2
    prices[80] += 10
    for side, offset in (("bid", -.25), ("ask", .25)):
        a[f"{side}_open"] = prices + offset
        a[f"{side}_close"] = prices + offset + .05
        a[f"{side}_high"] = prices + offset + .2
        a[f"{side}_low"] = prices + offset - .2
    return a


def test_return_scale_excludes_current_and_future_return():
    a = quotes()
    r, scale = features(a, 60)
    assert abs(r[80]) > 2 * scale[80]
    changed = a.copy()
    changed["bid_close"][80:] += 500
    changed["ask_close"][80:] += 500
    _, other = features(changed, 60)
    np.testing.assert_allclose(scale[:81], other[:81], equal_nan=True)


def test_endpoint_quote_side_reconciles_and_next_close_is_not_fill():
    a = quotes()
    d = outcomes(a, a["time"], 60)
    i = 80
    assert d["extreme"][i]
    assert d["direction"][i] == -1
    assert d["side"][i] == pytest.approx(a["bid_open"][81] - a["ask_open"][82])
    assert d["side"][i] == pytest.approx(d["mid"][i] - .5)
    altered = a.copy()
    altered["bid_close"][81] += 10
    altered["ask_close"][81] += 10
    e = outcomes(altered, altered["time"], 60)
    assert e["side"][i] == d["side"][i]
    assert e["reference"][i] != d["reference"][i]


def test_missing_intervening_minute_rejects_even_when_boundaries_exist():
    a = quotes()
    b = aggregate(a, 900)
    # M15 scale needs warmup; reproduce with a long enough series.
    a = quotes(1800)
    b = aggregate(a, 900)
    i = 80
    missing = a["time"][a["time"] != b["time"][i + 1] + 60]
    d = outcomes(b, missing, 900)
    assert not d["valid"][i]


def test_aggregation_never_fills_incomplete_utc_group():
    a = quotes()
    b = aggregate(a, 900)
    assert len(b) == 8
    reduced = np.delete(a, 20)
    c = aggregate(reduced, 900)
    assert len(c) == 7
    assert START + 900 not in c["time"]


def test_ordinary_control_outcome_cannot_include_extreme_signal_interval():
    x = dict(time=np.array([START, START + 60, START + 120]),
             return_=np.array([.1, .1, 2.]), rms=np.ones(3),
             extreme=np.array([False, False, True]), valid=np.ones(3, dtype=bool))
    paired, controls = match_controls(x, 60)
    np.testing.assert_array_equal(paired, [2])
    # Index1's forward outcome overlaps index2's signal interval.
    np.testing.assert_array_equal(controls, [0])


@pytest.mark.parametrize("defect", ["duplicate", "crossed", "nonfinite", "bad_ohlc"])
def test_source_quality_is_fail_closed(defect):
    a = quotes()
    if defect == "duplicate":
        a["time"][5] = a["time"][4]
    elif defect == "crossed":
        a["ask_open"][5] = a["bid_open"][5] - 1
    elif defect == "nonfinite":
        a["bid_close"][5] = np.nan
    else:
        a["bid_high"][5] = 1
    with pytest.raises(ValueError):
        validate(a)
