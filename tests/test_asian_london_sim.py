"""Mechanics of the frozen trial-#641 simulator on synthetic data (no real-data result is looked at here)."""
import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "research"))
import asian_london_sim as al  # noqa: E402

DAY = 86400
T0 = 1_640_995_200 + 3 * 86400        # 2022-01-04 00:00 UTC (Tuesday)


def synth(days=700, seed=3, drift=0.02):
    rng = np.random.default_rng(seed)
    rows = []
    px = 1800.0
    for d in range(days):
        base = T0 + d * DAY
        if ((base // DAY) + 4) % 7 >= 5:      # skip weekends (epoch day 0 = Thursday)
            continue
        for k in range(96):
            px += drift + rng.normal(0, 0.6 if 28 <= k < 40 else 0.25)
            rows.append((base + k * 900, px, px + abs(rng.normal(0, .3)), px - abs(rng.normal(0, .3)), px + rng.normal(0, .1), 20))
    m15 = np.array(rows, dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"), ("close", "f8"), ("spread", "i8")])
    # make open == previous close, high/low consistent
    m15["open"][1:] = m15["close"][:-1]
    m15["high"] = np.maximum(m15["high"], np.maximum(m15["open"], m15["close"]))
    m15["low"] = np.minimum(m15["low"], np.minimum(m15["open"], m15["close"]))
    day = m15["time"] // DAY
    u, s = np.unique(day, return_index=True); b = list(s) + [len(m15)]
    d1 = np.array([(u[i] * DAY, m15["open"][b[i]], m15["high"][b[i]:b[i + 1]].max(), m15["low"][b[i]:b[i + 1]].min(),
                    m15["close"][b[i + 1] - 1], 0) for i in range(len(u))],
                  dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"), ("close", "f8"), ("tick_volume", "i8")])
    return m15, d1


def test_invariants_on_synthetic_trend():
    m15, d1 = synth()
    B = al.build(m15, d1)
    tr = al.run(B, [])
    assert len(tr) > 5
    t = m15["time"]
    for x in tr:
        h = (x["t"] % DAY) / 3600
        assert 7.25 <= h <= 10.25                 # entry = open of the bar AFTER a signal bar opened in [07:00, 10:00)
        assert x["x"] > x["t"] - 1                # exit never before entry
        assert (x["x"] % DAY) / 3600 < 16         # forced flat before 16:00 UTC
        assert x["reason"] in ("SL", "TP", "TIME")
        if x["reason"] == "SL": assert x["R"] < 0.05
        if x["reason"] == "TP": assert x["R"] > 1.5
    days = [x["t"] // DAY for x in tr]
    assert len(days) == len(set(days))            # max one trade per day
    assert all(x["dir"] == 1 for x in tr)         # rising series -> only longs (D1 SMA200 bias)


def test_news_blackout_removes_entries():
    m15, d1 = synth()
    B = al.build(m15, d1)
    base = al.run(B, [])
    ev = [(x["t"] - 600, "CPI") for x in base]      # an event 10 min before every entry
    assert al.run(B, ev) == [] or len(al.run(B, ev)) < len(base)
    assert al.run(B, ev) == []


def test_stress_costs_never_improve_results():
    m15, d1 = synth()
    a = al.run(al.build(m15, d1), [])
    b = al.run(al.build(m15, d1, spread_mult=2.0), [], entry_slip=0.30)
    assert len(a) == len(b)
    assert sum(x["pnl"] for x in b) <= sum(x["pnl"] for x in a)


def test_no_lookahead_future_bars_do_not_change_past_trades():
    m15, d1 = synth()
    full = al.run(al.build(m15, d1), [])
    cut = len(m15) - 96 * 20
    part = al.run(al.build(m15[:cut], d1[d1["time"] < m15["time"][cut]]), [])
    cutoff_t = m15["time"][cut - 96 * 2]
    assert [x for x in full if x["x"] < cutoff_t] == [x for x in part if x["x"] < cutoff_t]
