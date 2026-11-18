import numpy as np
import pandas as pd

from scripts.research.market_atlas import quality, return_features, hour_from_m15, clustered_effect
from src.backtesting.master import HOLDOUT_FROM


def bars(times, prices):
    a = np.zeros(len(times), dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"), ("close", "f8")])
    a["time"] = times
    for name in ("open", "high", "low", "close"):
        a[name] = prices
    return a


def test_features_are_prefix_causal_and_do_not_bridge_gap():
    a = bars(np.arange(150)*60, 100*np.exp(np.arange(150)*.001))
    a["time"][80:] += 3600
    r, scale = return_features(a, 60)
    assert np.isnan(r[80])
    assert np.isnan(scale[80])
    np.testing.assert_allclose(scale[81], .001, atol=1e-12)
    b = a.copy()
    b["close"][100:] *= 1.7
    rb, sb = return_features(b, 60)
    np.testing.assert_allclose(rb[:100], return_features(a, 60)[0][:100], equal_nan=True)
    np.testing.assert_allclose(sb[:101], return_features(a, 60)[1][:101], equal_nan=True)
    gap = bars(np.r_[np.arange(100)*60, 7200+np.arange(80)*60], np.exp(np.arange(180)*.001)*100)
    r, scale = return_features(gap, 60)
    assert np.isnan(r[100])
    assert np.isfinite(scale[101])


def test_holdout_bad_prices_never_enter_quality_counts():
    a = bars([HOLDOUT_FROM-60, HOLDOUT_FROM], [100, -1])
    report = quality(pd.DataFrame(a), 60)
    assert report["holdout_rows_excluded"] == 1
    assert report["invalid_ohlc"] == 0
    assert report["analyzed_preholdout_rows"] == 1


def test_hourly_aggregation_refuses_missing_quarter():
    a = bars([0, 900, 1800, 2700, 3600, 4500, 6300], [100]*7)
    out = hour_from_m15(a)
    assert len(out) == 1
    assert out["time"][0] == 0


def test_month_cluster_estimate_weights_observations_and_contrast():
    values = np.array([1., 1., 3., 0., 0., 0.])
    m = np.array(["2020-01", "2020-01", "2020-02", "2020-01", "2020-02", "2020-02"])
    effect = clustered_effect(values, np.array([1, 1, 1, 0, 0, 0], bool), m,
                              np.array([0, 0, 0, 1, 1, 1], bool))
    assert np.isclose(effect["estimate_log_return"], 5/3)
    assert effect["observations"] == 3
    assert effect["bootstrap_replicates"] == 999
