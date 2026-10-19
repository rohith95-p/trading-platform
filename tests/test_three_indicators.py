"""Mechanics of the frozen indicator ports (synthetic data only; no real-data result is looked at)."""
import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "research"))
import three_indicators_sim as ti  # noqa: E402


def walk(n=3000, seed=1, drift=0.0):
    rng = np.random.default_rng(seed)
    c = 1800 + np.cumsum(rng.normal(drift, 0.8, n)); o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + abs(rng.normal(0, .3, n)); l = np.minimum(o, c) - abs(rng.normal(0, .3, n))
    return o, h, l, c


def test_crossover_helpers():
    a = np.array([1.0, 2, 3, 2, 1]); b = np.full(5, 1.5)
    assert list(ti.crossover(a, b)) == [False, True, False, False, False]
    assert list(ti.crossunder(a, b)) == [False, False, False, False, True]
    assert list(ti.pine_cross(a, b)) == [False, True, False, False, True]


def test_signals_are_valid_and_have_no_lookahead():
    o, h, l, c = walk()
    for name, f in ti.SIGNALS.items():
        s = f(o, h, l, c)
        assert set(np.unique(s)) <= {-1.0, 0.0, 1.0}
        assert (s != 0).sum() > 10, name
        k = 2000                                       # truncating the future must not change past signals
        s2 = f(o[:k], h[:k], l[:k], c[:k])
        assert np.array_equal(s[:k - 1], s2[:k - 1]), name


def test_ema20_rule_hand_case():
    # close rises through the EMA, then a bar closes at/above the previous high -> long on that bar
    c = np.r_[np.full(40, 100.0), 99.0, 101.0, 102.5, 103.0]
    h = c + 0.2; l = c - 0.2; o = np.r_[c[0], c[:-1]]
    s = ti.sig_ema20(o, h, l, c)
    assert (s == 1).any() and not (s == -1).any()


def test_ut_bot_buys_after_a_breakout():
    c = np.r_[np.linspace(110, 100, 60), np.linspace(100, 112, 30)]          # falls below the trailing stop, then crosses up through it
    h = c + 0.2; l = c - 0.2; o = np.r_[c[0], c[:-1]]
    s = ti.sig_utbot(o, h, l, c)
    assert (s[60:] == 1).any() and not (s[:60] == 1).any()


def test_engine_stop_first_costs_and_one_position():
    o, h, l, c = walk(drift=0.0)
    m = np.zeros(len(c), dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"), ("close", "f8"), ("spread", "i8")])
    m["time"] = 1_700_000_000 + np.arange(len(c)) * 900; m["open"], m["high"], m["low"], m["close"], m["spread"] = o, h, l, c, 250
    B = ti.make_B(m); s = np.zeros(len(c)); s[600:2000:7] = 1
    tr = ti.engine(B, s, 1.0, 1.5)
    assert tr and all(x["x"] >= x["t"] for x in tr)
    ts = sorted(tr, key=lambda x: x["t"])
    assert all(b["t"] > a["x"] for a, b in zip(ts, ts[1:]))           # one position at a time
    tr2 = ti.engine(ti.make_B(m, spread_mult=2.0), s, 1.0, 1.5, slip=0.30)
    assert sum(x["pnl"] for x in tr2) <= sum(x["pnl"] for x in tr)     # costs never help
