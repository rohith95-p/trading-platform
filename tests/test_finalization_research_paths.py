import numpy as np
import pandas as pd

from scripts.research.delayed_macro_agreement import macro_side_at
from scripts.research.path_risk import risk_paths
from scripts.research.selection_pbo import selection_pbo


def test_macro_signal_ignores_current_and_immediately_previous_row():
    dates = pd.date_range("2025-01-06", periods=5)
    macro = pd.DataFrame({"dxy": [5, 4, 3, 9, 11], "y10": [3, 2, 1, 7, 8]}, index=dates)
    asof = dates[-1:]
    side, feature = macro_side_at(asof, macro)
    assert side.tolist() == [1] and feature[0] == dates[2]
    macro.loc[dates[-2]:] *= -1
    assert macro_side_at(asof, macro)[0].tolist() == [1]
    assert macro_side_at(pd.DatetimeIndex(["2025-02-01"]), macro)[0].tolist() == [0]


def test_cscv_detects_a_winner_that_changes_in_every_complement():
    panel = [[1, -2], [2, -1], [-2, 1], [-1, 2]]
    result = selection_pbo(panel, blocks=2)
    assert result["pbo"] == result["negative_test_fraction"] == 1
    assert [s["winners"] for s in result["splits"]] == [[0], [1]]
    assert selection_pbo([[1, 1]] * 4, blocks=2)["pbo"] is None


def test_barrier_research_keeps_cotouches_separate_from_directional_hits():
    bars = np.zeros(80, dtype=[("time", "i8"), ("open", "f8"), ("low", "f8"), ("high", "f8")])
    bars["time"] = np.arange(80) * 900
    bars["open"] = bars["low"] = bars["high"] = 100
    bars["high"][64], bars["low"][64] = 102, 98
    result = risk_paths(bars, np.full(80, .01))
    assert result["eligible"] == result["ambiguous"] == 1
    assert result["upper_first"] == result["lower_first"] == result["timeout"] == 0
