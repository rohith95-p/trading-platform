"""The live four legs on 18 years that never picked them.

Pre-registered: research/registry/PREREG_EighteenYearHoldout_2026-11-07.md
Read that first -- the eras, the metrics and the pass bar were fixed before this
ran, and so was the commitment not to rescue a bad result by re-cutting them.

    python -I scripts/validation/eighteen_year_holdout.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

os.environ["ULTRA_TRADE_24H"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUT = os.path.join("research", "registry", "eighteen_year_holdout_2026-11-07.json")


def utc(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())


# Fixed in the pre-registration, before any of this was run.
ERAS = [
    ("E1 2004-2008", utc(2004, 7, 1), utc(2008, 1, 1)),
    ("E2 2008-2012", utc(2008, 1, 1), utc(2012, 1, 1)),
    ("E3 2012-2016", utc(2012, 1, 1), utc(2016, 1, 1)),
    ("E4 2016-2020", utc(2016, 1, 1), utc(2020, 1, 1)),
    ("E5 2020-2022", utc(2020, 1, 1), utc(2022, 8, 1)),
]


def stats(pls):
    a = np.asarray(pls, dtype=float)
    if not len(a):
        return dict(n=0, net=0.0, pf=0.0, win=0.0, dd=0.0, avg_win=0.0, avg_loss=0.0)
    wins, losses = a[a > 0], a[a <= 0]
    eq = np.cumsum(a)
    dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
    gl = float(-losses.sum())
    return dict(n=int(len(a)), net=round(float(a.sum()), 2),
                pf=round(float(wins.sum() / gl), 3) if gl > 0 else float("inf"),
                win=round(100 * float((a > 0).mean()), 1), dd=round(dd, 2),
                avg_win=round(float(wins.mean()), 2) if len(wins) else 0.0,
                avg_loss=round(float(losses.mean()), 2) if len(losses) else 0.0)


def job(name, a, b):
    from src.backtesting.costs import SCENARIOS
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.master import load_master
    from src.strategies.portfolio_atlas import PORTFOLIO

    bars = load_master(("M15", "M1", "D1"), start=a, end=b)
    cfg = EngineConfig.live_parity_preset(
        sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
        max_concurrent=3, max_same_direction=3, history_bars=7500,
        protect_profit=False, m1_policy="skip")
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg)
    res = eng.run([c() for c in PORTFOLIO], a, b)
    d = res.diagnostics
    rows = [dict(t=int(t.entry_time), strategy=t.strategy, net=float(t.net_pl))
            for t in res.trades]
    return name, rows, dict(bars_skipped_no_m1=d["bars_skipped_no_m1"],
                            exits_unchecked_no_m1=d["exits_unchecked_no_m1"],
                            partial_m1_candles=d["partial_m1_candles"])


def main() -> int:
    print("18-year holdout: the live 4 legs on data that never selected them")
    print("pre-registration: research/registry/PREREG_EighteenYearHoldout_2026-11-07.md\n")
    out = {}
    with ProcessPoolExecutor(3) as ex:
        for name, rows, m1 in ex.map(job, *zip(*ERAS)):
            out[name] = dict(trades=rows, m1=m1)
            print(f"  done {name}: {len(rows)} trades "
                  f"(candles with no M1 {m1['bars_skipped_no_m1']}, "
                  f"exits unchecked {m1['exits_unchecked_no_m1']})", flush=True)

    print(f"\n{'era':16s} {'trades':>7s} {'net $':>10s} {'PF':>6s} {'win%':>6s} "
          f"{'avg win':>9s} {'avg loss':>9s} {'worst DD':>10s} {'tr/mo':>7s}")
    print("-" * 92)
    pooled = []
    report = {}
    for name, a, b in ERAS:
        rows = out[name]["trades"]
        pls = [r["net"] for r in rows]
        pooled += pls
        s = stats(pls)
        months = (b - a) / (86400 * 30.44)
        report[name] = dict(s, months=round(months, 1), m1=out[name]["m1"])
        print(f"{name:16s} {s['n']:>7d} {s['net']:>10,.2f} {s['pf']:>6.2f} {s['win']:>6.1f} "
              f"{s['avg_win']:>9,.2f} {s['avg_loss']:>9,.2f} {s['dd']:>10,.2f} "
              f"{s['n'] / months:>7.1f}")

    p = stats(pooled)
    report["POOLED"] = p
    print("-" * 92)
    print(f"{'POOLED 18 yr':16s} {p['n']:>7d} {p['net']:>10,.2f} {p['pf']:>6.2f} {p['win']:>6.1f} "
          f"{p['avg_win']:>9,.2f} {p['avg_loss']:>9,.2f} {p['dd']:>10,.2f}")

    # per leg, pooled
    print("\nper leg, pooled over all 18 years:")
    for leg in sorted({r["strategy"] for name in out for r in out[name]["trades"]}):
        pls = [r["net"] for name in out for r in out[name]["trades"] if r["strategy"] == leg]
        s = stats(pls)
        report["leg_" + leg] = s
        print(f"   {leg:28s} {s['n']:>6d} trades  net {s['net']:>9,.2f}  "
              f"PF {s['pf']:>5.2f}  win {s['win']:>5.1f}%")

    # the pre-registered bar
    eras_above_1 = sum(1 for name, _, _ in ERAS if report[name]["pf"] > 1.0)
    print(f"\neras with PF above 1.00: {eras_above_1} of {len(ERAS)}")
    if p["pf"] >= 1.15 and eras_above_1 >= 4:
        verdict = "PASS -- an edge that holds on data which never chose these legs"
    elif p["pf"] >= 1.05 and eras_above_1 >= 3:
        verdict = "WEAK PASS -- an edge too small to rely on; not real-money evidence"
    else:
        verdict = ("FAIL -- these legs have no demonstrated edge; the 2024-2026 result "
                   "was selection, not skill")
    report["verdict"] = verdict
    print(f"\nVERDICT (bar set before the run): {verdict}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(report, open(OUT, "w"), indent=1, default=str)
    print(f"\nwritten to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
