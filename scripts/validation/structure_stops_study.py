"""Structure-based stops vs the live ATR stops (pre-registered: research/registry/PREREG_StructureStops_2026-10-31.md).

    python scripts/validation/structure_stops_study.py
"""
import os
import sys
import json

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from scripts.validation import audit_data  # noqa: E402
from scripts.validation import independent_audit_run as base          # noqa: E402
from scripts.validation.sltp_sweep import (HOLE, LIVE as LIVE_AT_AUDIT, LOTS, VPP, SLIP,  # noqa: E402
                                           COMM, SWAP_LONG_NIGHT, friday_cut, stats)

# live stop/target multiples today (ARF stop moved 2.0 -> 2.5 on 2026-10-30)
LIVE = dict(LIVE_AT_AUDIT, ASIAN_RANGE_FILTERED_V6=(2.5, 3.5))
CLAMP = (0.5, 4.0)
BUF = 0.1
OUT = os.path.join("research", "results", "structure_stops_2026-10-31.json")


def exit_pl(t, sl, tp, T, H, L, C, SPR):
    """Net P&L of one entry with absolute stop/target prices (same exit model as sltp_sweep.replay)."""
    e, buy = t["entry_price"], t["is_buy"]
    i0 = np.searchsorted(T, (t["entry_time"] // 60) * 60, side="right")
    i1 = np.searchsorted(T, friday_cut(t["entry_time"]), side="left")
    h, l, s = H[i0:i1], L[i0:i1], SPR[i0:i1]
    hit_sl, hit_tp = ((l <= sl), (h >= tp)) if buy else ((h + s >= sl), (l + s <= tp))
    hit = hit_sl | hit_tp
    if hit.any():
        k = int(np.argmax(hit))
        px = (sl - SLIP if buy else sl + SLIP) if hit_sl[k] else tp
        xt = int(T[i0 + k])
    else:
        k = i1 - 1
        px = float(C[k]) if buy else float(C[k] + SPR[k])
        xt = int(T[k])
    gross = (px - e) * (1 if buy else -1) * LOTS * VPP
    nights = xt // 86400 - t["entry_time"] // 86400
    return gross - COMM + (SWAP_LONG_NIGHT * nights if buy else 0.0)


def levels(t, variant, m15):
    """(sl, tp) prices for a variant, or None if it does not apply to this strategy."""
    atr = abs(t["entry_price"] - t["initial_sl"]) / LIVE_AT_AUDIT[t["strategy"]][0]
    e, buy = t["entry_price"], t["is_buy"]
    if variant == "live":
        slm, tpm = LIVE[t["strategy"]]
        return (e - slm * atr, e + tpm * atr) if buy else (e + slm * atr, e - tpm * atr)
    kind, k = variant.rsplit("_", 1)
    k = float(k.rstrip("R"))
    tm = m15["time"].astype(np.int64)
    before = tm < (t["entry_time"] // 900) * 900                  # closed M15 bars only
    if kind.startswith("swing"):
        n = int(kind[5:])
        idx = np.where(before)[0][-n:]
        lo, hi = float(m15["low"][idx].min()), float(m15["high"][idx].max())
    elif kind == "range":
        if t["strategy"] not in ("ASIAN_RANGE_FILTERED_V6", "ASIAN_BREAKOUT_V6"):
            return None
        day = (t["entry_time"] // 86400) * 86400
        idx = np.where((tm >= day) & (tm < day + 21600))[0]
        lo, hi = float(m15["low"][idx].min()), float(m15["high"][idx].max())
    else:
        raise ValueError(variant)
    dist = (e - (lo - BUF * atr)) if buy else ((hi + BUF * atr) - e)
    dist = min(max(dist, CLAMP[0] * atr), CLAMP[1] * atr)
    return (e - dist, e + k * dist) if buy else (e + dist, e - k * dist)


def main():
    D, _src = audit_data.trades()
    B = base.bars()
    m1, m15 = B.m1, B.m15
    T = m1["time"].astype(np.int64)
    H, L, C = (m1[k].astype(float) for k in ("high", "low", "close"))
    SPR = np.where(m1["spread"] > 0, m1["spread"].astype(float), 260.0) * 0.001
    trades = {w: [t for t in D[w]["trades"] if not (HOLE[0] <= t["entry_time"] <= HOLE[1])]
              for w in ("DEV", "TEST", "RECENT")}
    variants = ["live"] + [f"swing{n}_{k}R" for n in (4, 8, 16) for k in (1.5, 2.0, 3.0)] + \
               [f"range_{k}R" for k in (1.0, 1.5, 2.0)]
    out, verdict = {}, {}
    for strat in LIVE:
        res = {}
        for v in variants:
            rows = {}
            for w, tr in trades.items():
                p = []
                for t in tr:
                    if t["strategy"] != strat:
                        continue
                    lv = levels(t, v, m15)
                    if lv is None:
                        break
                    p.append(exit_pl(t, *lv, T, H, L, C, SPR))
                else:
                    rows[w] = stats(p)
                    continue
                rows = None
                break
            if rows:
                fit = [x for w in ("DEV", "TEST") for x in [rows[w]]]
                rows["FIT"] = dict(net=round(fit[0]["net"] + fit[1]["net"], 2), dd=max(fit[0]["dd"], fit[1]["dd"]))
                res[v] = rows
        out[strat] = res
        live = res["live"]
        best = max((v for v in res if v != "live"), key=lambda v: res[v]["FIT"]["net"])
        b = res[best]
        passed = (b["FIT"]["net"] > live["FIT"]["net"] and b["RECENT"]["net"] >= live["RECENT"]["net"]
                  and b["FIT"]["dd"] <= 1.2 * live["FIT"]["dd"])
        verdict[strat] = dict(best=best, passed=passed)
        print(f"\n{strat}")
        for v in ["live"] + sorted((v for v in res if v != "live"), key=lambda v: -res[v]["FIT"]["net"])[:4]:
            r = res[v]
            print(f"  {v:12s} DEV+TEST ${r['FIT']['net']:7.0f} (DEV PF {r['DEV']['pf']:.2f}, TEST PF {r['TEST']['pf']:.2f}, "
                  f"worst DD ${r['FIT']['dd']:.0f}) | RECENT ${r['RECENT']['net']:6.0f} PF {r['RECENT']['pf']:.2f}"
                  f"{'   <- live' if v == 'live' else ''}")
        print(f"  best by the pre-registered rule: {best} -> {'PASS' if passed else 'fail'}")
    json.dump(dict(results=out, verdict=verdict), open(OUT, "w"), indent=0)


if __name__ == "__main__":
    main()
