"""Price-data integrity report: one place that says what we actually have.

Every number in this project comes from bars, and those bars come from three
different places (a 22-year Kaggle archive, the broker's own M1/M15 cache, and a
later top-up). Until now the merge lived inside research scripts, so nothing said
out loud how much of each window is real broker data or whether the archive even
agrees with the broker.

This prints, and writes to research/results/data_check.json:

  1. coverage      -- first/last bar and bar count per source and timeframe
  2. gaps          -- non-weekend holes, biggest first, per source
  3. agreement     -- the Kaggle archive against the broker's own M15 over the
                      span both cover: how many bars match, and by how much
  4. windows       -- for each research window, the share of expected M1 minutes
                      actually present in the merged master series

Run: python -I scripts/validation/data_check.py
"""
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.backtesting.master import (MASTER_SOURCES, WINDOWS, load_master,  # noqa: E402
                                    non_weekend_gaps, read_source)

OUT = os.path.join("research", "results", "data_check.json")
utc = lambda ts: dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def agg_m15(m1):
    """Aggregate M1 bars into M15 candles (open/high/low/close)."""
    b = (m1["time"].astype(np.int64) // 900) * 900
    idx = np.r_[0, np.nonzero(np.diff(b))[0] + 1]
    ends = np.r_[idx[1:], len(b)]
    return (b[idx],
            np.maximum.reduceat(m1["high"].astype(float), idx),
            np.minimum.reduceat(m1["low"].astype(float), idx),
            m1["close"].astype(float)[ends - 1],
            ends - idx)


def main():
    report = {"generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}

    # ---- 1/2 coverage and gaps, per source --------------------------------
    print("1. coverage")
    cov = {}
    series = {}
    for src in MASTER_SOURCES:
        for tf in src.timeframes:
            arr = read_source(src, tf)
            if arr is None:
                continue
            series[(src.name, tf)] = arr
            gaps = non_weekend_gaps(arr, tf)
            cov[f"{src.name}/{tf}"] = dict(
                bars=int(len(arr)), first=utc(arr["time"][0]), last=utc(arr["time"][-1]),
                non_weekend_gaps=len(gaps),
                missing_bars=int(sum(g["missing_bars"] for g in gaps)),
                worst=[dict(after=utc(g["after"]), missing_bars=g["missing_bars"]) for g in gaps[:3]],
            )
            c = cov[f"{src.name}/{tf}"]
            print(f"   {src.name:>8s} {tf:4s} {c['bars']:>9,d} bars  {c['first']} -> {c['last']}"
                  f"   holes {c['non_weekend_gaps']:>4d} ({c['missing_bars']:,d} bars)")
    report["coverage"] = cov

    print("\n2. biggest non-weekend holes")
    for key, c in cov.items():
        if c["worst"]:
            print(f"   {key:16s} " + "  ".join(f"{w['after']} (-{w['missing_bars']})" for w in c["worst"]))

    # ---- 3 archive vs broker ---------------------------------------------
    print("\n3. Kaggle archive vs the broker's own M15, where both have data")
    agree = {}
    kag = series.get(("kaggle", "M1"))
    brk = series.get(("broker", "M15"))
    if kag is not None and brk is not None:
        kt, kh, kl, kc, kn = agg_m15(kag)
        full = kn == 15                      # only compare complete 15-minute candles
        kt, kh, kl, kc = kt[full], kh[full], kl[full], kc[full]
        bt = brk["time"].astype(np.int64)
        lo = max(kt.min(), bt.min())
        hi = min(kt.max(), bt.max())
        both = np.intersect1d(kt[(kt >= lo) & (kt <= hi)], bt[(bt >= lo) & (bt <= hi)])
        ki = np.searchsorted(kt, both)
        bi = np.searchsorted(bt, both)
        dc = np.abs(kc[ki] - brk["close"].astype(float)[bi])
        dh = np.abs(kh[ki] - brk["high"].astype(float)[bi])
        dl = np.abs(kl[ki] - brk["low"].astype(float)[bi])
        n_k = int(((kt >= lo) & (kt <= hi)).sum())
        n_b = int(((bt >= lo) & (bt <= hi)).sum())
        agree = dict(
            overlap_from=utc(lo), overlap_to=utc(hi),
            kaggle_candles=n_k, broker_candles=n_b, matched=int(len(both)),
            matched_pct=round(100 * len(both) / max(n_b, 1), 2),
            close_diff_median=round(float(np.median(dc)), 4),
            close_diff_p95=round(float(np.percentile(dc, 95)), 4),
            close_diff_max=round(float(dc.max()), 4),
            close_within_10c_pct=round(100 * float((dc <= 0.10).mean()), 2),
            high_diff_p95=round(float(np.percentile(dh, 95)), 4),
            low_diff_p95=round(float(np.percentile(dl, 95)), 4),
        )
        a = agree
        print(f"   overlap {a['overlap_from']} -> {a['overlap_to']}")
        print(f"   candles: broker {a['broker_candles']:,d}, archive {a['kaggle_candles']:,d}, "
              f"same timestamp {a['matched']:,d} ({a['matched_pct']}% of broker)")
        print(f"   |close difference|: median ${a['close_diff_median']}, 95th ${a['close_diff_p95']}, "
              f"max ${a['close_diff_max']}; within 10c on {a['close_within_10c_pct']}%")
        print(f"   |high| 95th ${a['high_diff_p95']}   |low| 95th ${a['low_diff_p95']}")
    else:
        print("   skipped: need both the Kaggle M1 archive and the broker M15 cache")
    report["agreement"] = agree

    # ---- 4 window coverage in the merged master --------------------------
    print("\n4. research windows against the merged master M1")
    bars = load_master(("M15", "M1", "D1"))
    t = bars.m1["time"].astype(np.int64)
    win = {}
    for name, a, b in WINDOWS:
        inside = t[(t >= a) & (t < b)]
        # expected minutes = Mon 00:00 - Fri 21:00 UTC, the hours the broker quotes
        days = np.arange(a // 86400, b // 86400)
        wd = np.array([dt.datetime.fromtimestamp(int(d) * 86400, dt.timezone.utc).weekday() for d in days])
        expected = int((wd < 5).sum() * 1380)
        src_counts = {}
        for s in MASTER_SOURCES:
            seg = s.span_for(a, b)
            if seg:
                src_counts[s.name] = f"{utc(seg[0])} -> {utc(seg[1])}"
        win[name] = dict(from_=utc(a), to=utc(b), m1_bars=int(len(inside)),
                         expected_approx=expected,
                         coverage_pct=round(100 * len(inside) / max(expected, 1), 1),
                         sources=src_counts)
        w = win[name]
        print(f"   {name:7s} {w['from_']} -> {w['to']}  M1 {w['m1_bars']:>9,d} "
              f"(~{w['coverage_pct']}% of quoted minutes)  from: {', '.join(src_counts) or 'none'}")
    report["windows"] = win

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(report, open(OUT, "w"), indent=1)
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
