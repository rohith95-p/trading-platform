"""Entry-filter study for the Atlas portfolio on 1-minute data.

M1 source: Kaggle archive (Eastern European clock, shifted to broker UTC) through
2026-02-17, broker M1 cache from 2026-07-02. Kaggle diverges from the broker feed
after 2026-02-17, so that span and the Feb-Jul gap are excluded.

Stage 1 (this script, --run): backtest with live-parity execution, record every
trade with features measured on bars closed before entry. Stage 2 (--score):
evaluate filters, thresholds picked on DEV only.

Run: python -I scripts/research/atlas_filter_study.py --run
     python -I scripts/research/atlas_filter_study.py --score
"""
import argparse
import dataclasses
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.strategies.portfolio_atlas import PORTFOLIO

OUT = os.path.join(ROOT, "research", "results", "atlas_filter_study")
KAGGLE_M1 = os.path.join(ROOT, "research", "data", "kaggle_22yr", "XAUUSDm_M1.npy")
utc = lambda *a: int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())
KAGGLE_END = utc(2026, 2, 18)

WINDOWS = [  # (name, start, end) -- every window is fully covered by M1
    ("DEV", utc(2022, 8, 1), utc(2024, 6, 1)),
    ("TEST", utc(2024, 6, 1), KAGGLE_END),
    ("RECENT", utc(2026, 7, 6), utc(2026, 10, 13)),
]


def kaggle_to_broker(arr):
    days = arr["time"] // 86400
    off = {}
    athens = ZoneInfo("Europe/Athens")
    for d in np.unique(days):
        t = dt.datetime.fromtimestamp(int(d) * 86400 + 43200, dt.timezone.utc)
        off[d] = int(t.astimezone(athens).utcoffset().total_seconds())
    out = arr.copy()
    out["time"] = arr["time"] - np.vectorize(off.get)(days)
    return out


def merged_bars():
    bars = load_bars("XAUUSDm")
    k = np.load(KAGGLE_M1, mmap_mode="r")
    k = np.array(k[(k["time"] >= utc(2022, 7, 1) - 86400) & (k["time"] < KAGGLE_END + 86400)])
    k = kaggle_to_broker(k)
    k = k[(k["time"] >= utc(2022, 7, 1)) & (k["time"] < KAGGLE_END)]
    b = bars.m1[bars.m1["time"] >= utc(2026, 7, 1)]
    m1 = np.concatenate([k.astype(b.dtype), b])
    m1 = m1[np.argsort(m1["time"], kind="stable")]
    return dataclasses.replace(bars, m1=m1)


# ---------------- indicators on closed bars ----------------

def ema(x, n):
    a, out = 2 / (n + 1), np.empty(len(x))
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def resample(m15, sec):
    g = m15["time"] // sec
    idx = np.r_[0, np.nonzero(np.diff(g))[0] + 1]
    hi = np.maximum.reduceat(m15["high"], idx)
    lo = np.minimum.reduceat(m15["low"], idx)
    cl = m15["close"][np.r_[idx[1:] - 1, len(m15) - 1]]
    return g[idx] * sec, hi, lo, cl


def atr(hi, lo, cl, n=14):
    pc = np.r_[cl[0], cl[:-1]]
    tr = np.maximum(hi - lo, np.maximum(abs(hi - pc), abs(lo - pc)))
    return ema(tr, 2 * n - 1)  # Wilder smoothing


def adx(hi, lo, cl, n=14):
    up, dn = np.diff(hi, prepend=hi[0]), -np.diff(lo, prepend=lo[0])
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(hi, lo, cl, n)
    pdi = 100 * ema(pdm, 2 * n - 1) / np.maximum(a, 1e-9)
    mdi = 100 * ema(mdm, 2 * n - 1) / np.maximum(a, 1e-9)
    dx = 100 * abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-9)
    return ema(dx, 2 * n - 1)


def build_features(m15):
    f = {}
    t4, h4h, h4l, h4c = resample(m15, 4 * 3600)
    f["h4"] = dict(t=t4, close=h4c, ema50=ema(h4c, 50), ema20=ema(h4c, 20))
    t1, h1h, h1l, h1c = resample(m15, 3600)
    f["h1"] = dict(t=t1, adx=adx(h1h, h1l, h1c))
    a15 = atr(m15["high"], m15["low"], m15["close"])
    # ATR percentile vs the trailing 20 trading days (~1900 M15 bars)
    w = 1920
    pct = np.full(len(a15), np.nan)
    for i in range(w, len(a15)):
        pct[i] = (a15[i - w:i] < a15[i]).mean()
    f["m15"] = dict(t=m15["time"], atr_pct=pct, spread=m15["spread"].astype(float))
    return f


def last_closed(times, period, ts):
    """Index of the last bar whose close time (start+period) is <= ts."""
    return int(np.searchsorted(times, ts - period, side="right")) - 1


def tag(trade, f):
    ts, buy = trade.entry_time, trade.is_buy
    h4 = f["h4"]; i4 = last_closed(h4["t"], 4 * 3600, ts)
    h1 = f["h1"]; i1 = last_closed(h1["t"], 3600, ts)
    m = f["m15"]; i15 = last_closed(m["t"], 900, ts)
    sgn = 1 if buy else -1
    return dict(
        strategy=trade.strategy, is_buy=buy, entry_time=ts, net_pl=trade.net_pl,
        r=trade.r_multiple, exit_reason=trade.exit_reason,
        h4_above_ema50=bool(sgn * (h4["close"][i4] - h4["ema50"][i4]) > 0),
        h4_ema20_over_50=bool(sgn * (h4["ema20"][i4] - h4["ema50"][i4]) > 0),
        adx_h1=float(h1["adx"][i1]),
        atr_pct=float(m["atr_pct"][i15]),
        spread_pts=float(m["spread"][i15 + 1]) if i15 + 1 < len(m["t"]) else float(m["spread"][i15]),
        hour_utc=dt.datetime.fromtimestamp(ts, dt.timezone.utc).hour,
    )


def run():
    os.makedirs(OUT, exist_ok=True)
    bars = merged_bars()
    feats = build_features(bars.m15)
    for name, start, end in WINDOWS:
        cfg = EngineConfig.live_parity_preset(
            sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
            risk_rules_enforce=False, sizing_ladder_caps=False, streak_blind_spot=False,
            max_concurrent=3, max_same_direction=2, history_bars=7500,
        )
        res = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg).run(
            [c() for c in PORTFOLIO], start, end)
        rows = [tag(t, feats) for t in res.trades]
        with open(os.path.join(OUT, f"trades_{name}.json"), "w") as fh:
            json.dump(rows, fh)
        print(f"{name}: {len(rows)} trades, net ${sum(r['net_pl'] for r in rows):.2f}", flush=True)


# ---------------- scoring ----------------

def stats(rows):
    if not rows:
        return dict(n=0, wr=0, pf=0, net=0, dd=0, exp=0)
    pl = np.array([r["net_pl"] for r in sorted(rows, key=lambda r: r["entry_time"])])
    g, l = pl[pl > 0].sum(), -pl[pl < 0].sum()
    eq = np.cumsum(pl)
    return dict(n=len(pl), wr=100 * (pl > 0).mean(), pf=(g / l) if l else float("inf"),
                net=pl.sum(), dd=float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max()),
                exp=pl.mean())


FILTERS = {
    "baseline": lambda r: True,
    "H4 close above/below EMA50 with trade": lambda r: r["h4_above_ema50"],
    "H4 EMA20 vs EMA50 with trade": lambda r: r["h4_ema20_over_50"],
    "H1 ADX >= 20": lambda r: r["adx_h1"] >= 20,
    "H1 ADX >= 25": lambda r: r["adx_h1"] >= 25,
    "H1 ADX < 30": lambda r: r["adx_h1"] < 30,
    "ATR pct 20-90": lambda r: 0.2 <= r["atr_pct"] <= 0.9,
    "ATR pct >= 30": lambda r: r["atr_pct"] >= 0.3,
    "ATR pct <= 80": lambda r: r["atr_pct"] <= 0.8,
    "spread <= 200 pts": lambda r: r["spread_pts"] <= 200,
    "spread <= 160 pts": lambda r: r["spread_pts"] <= 160,
}


def score():
    data = {}
    for name, _, _ in WINDOWS:
        with open(os.path.join(OUT, f"trades_{name}.json")) as fh:
            data[name] = json.load(fh)
    # session: drop hours that lost money on DEV only (needs >= 8 trades in the hour)
    dev = data["DEV"]
    bad_hours = sorted(h for h in set(r["hour_utc"] for r in dev)
                       if sum(1 for r in dev if r["hour_utc"] == h) >= 8
                       and sum(r["net_pl"] for r in dev if r["hour_utc"] == h) < 0)
    FILTERS[f"skip DEV-losing hours UTC {bad_hours}"] = lambda r: r["hour_utc"] not in bad_hours

    report = {}
    for fname, fn in FILTERS.items():
        report[fname] = {}
        for w in data:
            base, kept = stats(data[w]), stats([r for r in data[w] if fn(r)])
            kept["kept_pct"] = 100 * kept["n"] / base["n"] if base["n"] else 0
            report[fname][w] = kept
    by_strat = {}
    for w in data:
        for s in sorted(set(r["strategy"] for r in data[w])):
            by_strat.setdefault(s, {})[w] = stats([r for r in data[w] if r["strategy"] == s])
    with open(os.path.join(OUT, "filter_report.json"), "w") as fh:
        json.dump(dict(filters=report, by_strategy=by_strat, bad_hours=bad_hours), fh, indent=1)

    hdr = f"{'filter':44s}" + "".join(f"| {w:^34s}" for w in data)
    print(hdr + "\n" + f"{'':44s}" + "| kept%   n   WR%   PF    net$   DD$ " * len(data))
    for fname, ws in report.items():
        line = f"{fname[:44]:44s}"
        for w in data:
            s = ws[w]
            line += f"| {s['kept_pct']:4.0f} {s['n']:4d} {s['wr']:5.1f} {s['pf']:4.2f} {s['net']:7.0f} {s['dd']:5.0f} "
        print(line)
    print("\nby strategy:")
    for s, ws in by_strat.items():
        print(f"  {s:28s}" + "".join(f"| {w} n={v['n']} WR={v['wr']:.0f}% PF={v['pf']:.2f} net={v['net']:.0f} " for w, v in ws.items()))


def h4_aligned(m15_rates, is_buy, n=50):
    t, _, _, cl = resample(m15_rates[:-1], 4 * 3600)   # drop the forming M15 bar
    t, cl = t[:-1], cl[:-1]                            # drop the forming H4 bar
    if len(cl) < n:
        return True
    e = ema(cl, n)[-1]
    return cl[-1] > e if is_buy else cl[-1] < e


def make_filtered(base_cls):
    class Filtered(base_cls):
        def evaluate(self, m15_rates, m5_rates=None):
            sig = super().evaluate(m15_rates, m5_rates)
            if sig is not None and not h4_aligned(m15_rates, sig.is_buy):
                return None
            return sig
    Filtered.__name__ = base_cls.__name__
    return Filtered


def confirm():
    from src.backtesting.metrics import summarize
    from src.strategies.asian_range_filtered import AsianRangeFilteredV6
    bars = merged_bars()
    variants = {
        "baseline": list(PORTFOLIO),
        "H4 filter on AsianRangeFiltered": [make_filtered(c) if c is AsianRangeFilteredV6 else c for c in PORTFOLIO],
        "H4 filter on all 3": [make_filtered(c) for c in PORTFOLIO],
    }
    print(f"{'variant':34s}" + "".join(f"| {w:^40s}" for w, _, _ in WINDOWS))
    print(f"{'':34s}" + "|   n  WR%   PF   net$  maxDD%  worstDay$ " * len(WINDOWS))
    for vname, classes in variants.items():
        line = f"{vname:34s}"
        for w, start, end in WINDOWS:
            cfg = EngineConfig.live_parity_preset(
                sizing_mode="fixed", fixed_lots=0.02, starting_balance=500.0,
                risk_rules_enforce=False, sizing_ladder_caps=False, streak_blind_spot=False,
                max_concurrent=3, max_same_direction=2, history_bars=7500)
            res = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg).run(
                [c() for c in classes], start, end)
            d = summarize(res.trades, res.equity, 500.0).to_dict()
            day = {}
            for t in res.trades:
                k = t.exit_time // 86400
                day[k] = day.get(k, 0) + t.net_pl
            line += (f"| {d['trades']:4d} {d['win_rate']:4.1f} {d['profit_factor']:4.2f} {d['net_pl']:6.0f} "
                     f"{d['max_drawdown_pct']:6.1f} {min(day.values(), default=0):8.0f}   ")
        print(line, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    if a.score:
        score()
    if a.confirm:
        confirm()
