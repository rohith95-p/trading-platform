"""Headline numbers for the newest audit run: per window and per strategy.

Reads whatever `scripts/validation/independent_audit_run.py` last wrote and
prints net, profit factor, win rate, worst drawdown and trades per month, for the
whole portfolio and for each leg. No choices are made here -- it only reports.

Run: python -I scripts/validation/audit_stats.py
"""
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from scripts.validation import audit_data  # noqa: E402
from src.backtesting.master import M1_HOLE  # noqa: E402

OUT = os.path.join("research", "results", "audit_stats.json")


def stats(pls):
    a = np.asarray(pls, dtype=float)
    if not len(a):
        return dict(n=0, net=0.0, pf=0.0, win=0.0, dd=0.0, avg_win=0.0, avg_loss=0.0)
    wins, losses = a[a > 0], a[a <= 0]
    eq = np.cumsum(a)
    dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(eq) else 0.0
    gross_loss = float(-losses.sum())
    return dict(
        n=int(len(a)), net=round(float(a.sum()), 2),
        pf=round(float(wins.sum() / gross_loss), 3) if gross_loss > 0 else float("inf"),
        win=round(100 * float((a > 0).mean()), 1), dd=round(dd, 2),
        avg_win=round(float(wins.mean()), 2) if len(wins) else 0.0,
        avg_loss=round(float(losses.mean()), 2) if len(losses) else 0.0,
    )


def months(trades):
    if not trades:
        return 0.0
    t = sorted(int(x["entry_time"]) for x in trades)
    return max((t[-1] - t[0]) / (86400 * 30.44), 1 / 30.44)


def main():
    D, src = audit_data.trades()
    print(f"source: {src}\n")
    report = {"source": src}
    for win in [w for w in ("DEV", "TEST", "RECENT", "RECENT_CUT") if w in D]:
        raw = D[win]["trades"]
        tr = [t for t in raw if not (M1_HOLE[0] <= int(t["entry_time"]) <= M1_HOLE[1])]
        dropped = len(raw) - len(tr)
        s = stats([t["net_pl"] for t in tr])
        m = months(tr)
        m1 = D[win].get("m1", {})
        first = dt.datetime.utcfromtimestamp(min(int(t["entry_time"]) for t in tr)).strftime("%Y-%m-%d")
        last = dt.datetime.utcfromtimestamp(max(int(t["entry_time"]) for t in tr)).strftime("%Y-%m-%d")
        print(f"{win}  {first} -> {last}  ({m:.1f} months)")
        print(f"   portfolio: {s['n']:>4d} trades  net ${s['net']:>9,.2f}  PF {s['pf']:.2f}  "
              f"win {s['win']:>4.1f}%  worst drawdown ${s['dd']:,.2f}  "
              f"{s['n'] / m:.1f} trades/month")
        if dropped:
            print(f"   ({dropped} trades dropped: inside the M1 hole)")
        if m1:
            print(f"   M1 cover: {m1.get('bars_skipped_no_m1', '?')} candles with none "
                  f"(exits unchecked {m1.get('exits_unchecked_no_m1', '?')}), "
                  f"{m1.get('partial_m1_candles', '?')} partly covered "
                  f"({m1.get('partial_m1_minutes_missing', '?')} minutes missing)")
        per = {}
        for name in sorted({t["strategy"] for t in tr}):
            leg = [t["net_pl"] for t in tr if t["strategy"] == name]
            ls = stats(leg)
            per[name] = ls
            print(f"      {name:26s} {ls['n']:>4d}  net ${ls['net']:>9,.2f}  PF {ls['pf']:>5.2f}  "
                  f"win {ls['win']:>4.1f}%  avg win ${ls['avg_win']:>7,.2f}  "
                  f"avg loss ${ls['avg_loss']:>7,.2f}")
        report[win] = dict(first=first, last=last, months=round(m, 2), portfolio=s,
                           per_strategy=per, dropped_in_m1_hole=dropped, m1=m1)
        print()
    json.dump(report, open(OUT, "w"), indent=1)
    print(f"written to {OUT}")


if __name__ == "__main__":
    main()
