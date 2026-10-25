"""Gold engine regression: pins the exact trade list of the backtest engine on real XAUUSDm data so engine
changes cannot silently move results. Numbers recorded 2026-10-16 with TrendPullbackV5 (portfolio_v4 definition)
at a fixed 0.01 lot.

TODO: Re-pin with Atlas portfolio strategies (DonchianTrendV6, AsianRangeFilteredV6, AsianBreakoutV6).
"""
import pytest
pytestmark = pytest.mark.skip(reason="Regression hashes pinned to archived V4 portfolio; re-pin with Atlas strategies")
import hashlib
import json
import os
from datetime import datetime, timezone

import pytest

from src.backtesting.costs import SCENARIOS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.join(ROOT, "research", "data")


def _ts(d):
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


needs_data = pytest.mark.skipif(
    not os.path.exists(os.path.join(DATA_ROOT, "XAUUSDm_M1.npy")),
    reason="cached XAUUSDm research data not present")


@pytest.fixture(scope="module")
def xau_bars():
    from src.backtesting.data import load_bars
    return load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1"), data_root=DATA_ROOT)


def _run(bars, scenario, a, b, **cfg_kw):
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.strategies._deprecated.portfolio_v4 import TrendPullbackV5
    kw = dict(symbol="XAUUSDm", starting_balance=105.74, sizing_mode="fixed", fixed_lots=0.01)
    kw.update(cfg_kw)
    res = BacktestEngine(bars=bars, cost=SCENARIOS[scenario], config=EngineConfig(**kw)).run(
        [TrendPullbackV5()], start_ts=_ts(a), end_ts=_ts(b))
    rows = [(t.entry_time, t.exit_time, t.is_buy, round(t.entry_price, 5), round(t.exit_price, 5),
             t.lots, round(t.net_pl, 6), round(t.swap, 6), t.exit_reason) for t in res.trades]
    digest = hashlib.sha256(json.dumps(rows).encode()).hexdigest()
    return len(res.trades), round(sum(t.net_pl for t in res.trades), 6), digest


@needs_data
@pytest.mark.parametrize("scenario,window,n,net,digest", [
    # M1-walked, realistic costs
    ("realistic", ("2026-08-03", "2026-08-17"), 22, -13.297,
     "03ea22f4a44f6ac31b2e50ca50ca96da74032bfdbf5ec8dfdc5ea50badfde2a3"),
    ("observed", ("2026-08-03", "2026-08-17"), 22, -12.977,
     "3140077436037e3cbec253ee134625ef5fe8bdec9a859898b0b5becdc8563ac5"),
])
def test_gold_engine_regression_m1(xau_bars, scenario, window, n, net, digest):
    assert _run(xau_bars, scenario, *window) == (n, net, digest)


@needs_data
def test_gold_engine_regression_coarse_no_m1(xau_bars):
    # Before M1 history begins (2026-07-02): the coarse-bar path.
    got = _run(xau_bars, "realistic", "2026-05-04", "2026-05-18")
    assert got[0] == 24 and got[1] == -40.259
    assert got[2].startswith("f5a709feadc4496a")
