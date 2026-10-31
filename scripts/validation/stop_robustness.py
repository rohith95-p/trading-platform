"""Are the live ATR stops the right stops? (pre-registered: research/registry/PREREG_StopRobustness_2026-11-01.md)

    python scripts/validation/stop_robustness.py
"""
import os
import sys
import json
import datetime as dt

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from scripts.validation import audit_data  # noqa: E402
from scripts.validation import independent_audit_run as base          # noqa: E402
from scripts.validation.sltp_sweep import HOLE, LIVE as LIVE_AT_AUDIT, VPP, COMM, SWAP_LONG_NIGHT, friday_cut, stats  # noqa: E402

LIVE = dict(LIVE_AT_AUDIT, ASIAN_RANGE_FILTERED_V6=(2.5, 3.5))
LOTS = 0.02
W = ("DEV", "TEST", "RECENT")
OUT = os.path.join("research", "results", "stop_robustness_2026-11-01.json")


def wilder_atr(h, l, c, period):
    tr = np.empty_like(h)
    tr[0] = h[0] - l[0]
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    atr = np.full_like(tr, np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(tr)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def resample_h1(m15):
    t = m15["time"].astype(np.int64)
    key = t // 3600
    starts = np.r_[0, np.where(np.diff(key) != 0)[0] + 1]
    ends = np.r_[starts[1:], len(t)]
    h = np.array([m15["high"][a:b].max() for a, b in zip(starts, ends)], float)
    l = np.array([m15["low"][a:b].min() for a, b in zip(starts, ends)], float)
    c = np.array([m15["close"][b - 1] for b in ends], float)
    return key[starts] * 3600, h, l, c


def at_entry(times, series, bar_sec, entry_ts):
    """Value of `series` on the last bar fully closed before entry."""
    i = np.searchsorted(times, entry_ts - bar_sec, side="right") - 1
    return float(series[i]) if i >= 0 else float("nan")


def exit_pl(t, sl, tp, A, spread_mult=1.0, slip=0.020, flip=False):
    T, H, L, C, SPR = A
    e = t["entry_price"]
    buy = (not t["is_buy"]) if flip else t["is_buy"]
    i0 = np.searchsorted(T, (t["entry_time"] // 60) * 60, side="right")
    i1 = np.searchsorted(T, friday_cut(t["entry_time"]), side="left")
    h, l, s = H[i0:i1], L[i0:i1], SPR[i0:i1] * spread_mult
    hit_sl, hit_tp = ((l <= sl), (h >= tp)) if buy else ((h + s >= sl), (l + s <= tp))
    hit = hit_sl | hit_tp
    if hit.any():
        k = int(np.argmax(hit))
        px = (sl - slip if buy else sl + slip) if hit_sl[k] else tp
        xt = int(T[i0 + k])
    else:
        k = i1 - 1
        px = float(C[k]) if buy else float(C[k] + s[-1])
        xt = int(T[k])
    extra_entry_spread = (spread_mult - 1.0) * float(SPR[i0 - 1]) if buy else 0.0   # buys fill at ask
    gross = (px - e - extra_entry_spread) * (1 if buy else -1) * LOTS * VPP
    nights = xt // 86400 - t["entry_time"] // 86400
    return gross - COMM + (SWAP_LONG_NIGHT * nights if buy else 0.0)


def levels(e, buy, sl_d, tp_d):
    return (e - sl_d, e + tp_d) if buy else (e + sl_d, e - tp_d)


def main():
    rng = np.random.default_rng(1101)
    D, _src = audit_data.trades()
    B = base.bars()
    m1, m15, d1 = B.m1, B.m15, B.d1
    A = (m1["time"].astype(np.int64), m1["high"].astype(float), m1["low"].astype(float), m1["close"].astype(float),
         np.where(m1["spread"] > 0, m1["spread"].astype(float), 260.0) * 0.001)
    tr = {w: [t for t in D[w]["trades"] if not (HOLE[0] <= t["entry_time"] <= HOLE[1])] for w in W}
    allt = [t for w in W for t in tr[w]]
    for t in allt:
        t["_atr"] = abs(t["entry_price"] - t["initial_sl"]) / LIVE_AT_AUDIT[t["strategy"]][0]   # live ATR at entry

    # volatility measures at entry
    mt = m15["time"].astype(np.int64)
    mh, ml, mc = (m15[k].astype(float) for k in ("high", "low", "close"))
    ht, hh, hl, hc = resample_h1(m15)
    dtm = d1["time"].astype(np.int64)
    dh, dl, dc = (d1[k].astype(float) for k in ("high", "low", "close"))
    series = {"atr7_m15": (mt, wilder_atr(mh, ml, mc, 7), 900), "atr14_m15": (mt, wilder_atr(mh, ml, mc, 14), 900),
              "atr28_m15": (mt, wilder_atr(mh, ml, mc, 28), 900), "atr14_h1": (ht, wilder_atr(hh, hl, hc, 14), 3600),
              "atr14_d1": (dtm, wilder_atr(dh, dl, dc, 14), 86400)}
    for t in allt:
        for name, (tm, s, sec) in series.items():
            t["_" + name] = at_entry(tm, s, sec, t["entry_time"])

    def run(measure, stress=None, flip=False):
        out = {}
        for strat, (slm, tpm) in LIVE.items():
            dev = [t for t in tr["DEV"] if t["strategy"] == strat]
            if measure == "live":
                k = 1.0
            elif measure == "fixed":
                fixed_sl = float(np.median([slm * t["_atr"] for t in dev]))
            else:
                k = float(np.median([t["_atr"] for t in dev]) / np.median([t["_" + measure] for t in dev]))
            for w in W:
                for t in tr[w]:
                    if t["strategy"] != strat:
                        continue
                    if measure == "fixed":
                        sl_d, tp_d = fixed_sl, fixed_sl * tpm / slm
                    else:
                        vol = t["_atr"] if measure == "live" else t["_" + measure]
                        sl_d, tp_d = slm * k * vol, tpm * k * vol
                    buy = (not t["is_buy"]) if flip else t["is_buy"]
                    sl, tp = levels(t["entry_price"], buy, sl_d, tp_d)
                    kw = stress or {}
                    out.setdefault(w, []).append((t["entry_time"], exit_pl(t, sl, tp, A, flip=flip, **kw)))
        return {w: [p for _, p in sorted(v)] for w, v in out.items()}, out

    report = {}
    live_pl, live_raw = run("live")
    report["live"] = {w: stats(live_pl[w]) for w in W}

    # T2 volatility measures
    print("T2  same average stop size, different volatility measure (net $ / PF)")
    print(f"    {'measure':10s} " + "  ".join(f"{w:>16s}" for w in W))
    for m in ["live", "atr7_m15", "atr14_m15", "atr28_m15", "atr14_h1", "atr14_d1", "fixed"]:
        pl = live_pl if m == "live" else run(m)[0]
        st = {w: stats(pl[w]) for w in W}
        report["T2_" + m] = st
        beats = m != "live" and all(st[w]["net"] > report["live"][w]["net"] for w in W)
        print(f"    {m:10s} " + "  ".join(f"${st[w]['net']:7.0f} PF {st[w]['pf']:.2f}" for w in W)
              + ("   <- beats live in all three" if beats else ""))

    # T3 flip
    fl = run("live", flip=True)[0]
    report["T3_flip"] = {w: stats(fl[w]) for w in W}
    print("\nT3  same entry times, opposite direction: " +
          "  ".join(f"{w} ${report['T3_flip'][w]['net']:.0f} PF {report['T3_flip'][w]['pf']:.2f}" for w in W))

    # T4 costs
    print("\nT4  cost stress (net $ / PF)")
    for name, kw in [("spread x1.5", dict(spread_mult=1.5)), ("spread x2", dict(spread_mult=2.0)),
                     ("slippage 60pt", dict(slip=0.060))]:
        pl = run("live", stress=kw)[0]
        st = {w: stats(pl[w]) for w in W}
        report["T4_" + name] = st
        print(f"    {name:14s} " + "  ".join(f"{w} ${st[w]['net']:.0f} PF {st[w]['pf']:.2f}" for w in W))

    # T5 Monte Carlo: block bootstrap by month
    rows = sorted((ts, p) for v in live_raw.values() for ts, p in v)
    months = {}
    for ts, p in rows:
        months.setdefault(dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m"), []).append(p)
    blocks = list(months.values())
    nets, dd_hit, win_first = [], 0, 0
    N = 20000
    for _ in range(N):
        seq = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), 6)])
        eq = np.cumsum(seq)
        peak = np.maximum.accumulate(np.r_[0, eq])[1:]
        dd = peak - eq
        nets.append(eq[-1] if len(eq) else 0.0)
        breach = np.argmax(dd >= 500) if (dd >= 500).any() else None
        target = np.argmax(eq >= 150) if (eq >= 150).any() else None
        dd_hit += breach is not None
        win_first += target is not None and (breach is None or target < breach)
    nets = np.array(nets)
    report["T5"] = dict(p5=float(np.percentile(nets, 5)), p50=float(np.median(nets)), p95=float(np.percentile(nets, 95)),
                        p_loss=float((nets < 0).mean()), p_dd500=dd_hit / N, p_target_first=win_first / N,
                        months=len(blocks))
    r = report["T5"]
    print(f"\nT5  Monte Carlo, 6-month paths from {len(blocks)} real months: 5th ${r['p5']:.0f} | median ${r['p50']:.0f} | "
          f"95th ${r['p95']:.0f} | P(6 months negative) {r['p_loss']:.0%} | P($500 drawdown) {r['p_dd500']:.1%} | "
          f"P(+$150 before -$500) {r['p_target_first']:.0%}")
    json.dump(report, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
