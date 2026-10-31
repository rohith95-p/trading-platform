"""Strategy-specific stops/targets vs live ATR stops (pre-registered: research/registry/PREREG_StrategyStops_2026-10-31.md).

    python scripts/validation/strategy_stops_study.py
"""
import os
import sys
import json
from itertools import product

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from scripts.validation import audit_data  # noqa: E402
from scripts.validation import independent_audit_run as base          # noqa: E402
from scripts.validation.sltp_sweep import (HOLE, LIVE as LIVE_AT_AUDIT, VPP, SLIP, COMM,  # noqa: E402
                                           SWAP_LONG_NIGHT, friday_cut, stats)
from src.strategies.base_strategy import BaseStrategy                  # noqa: E402

LIVE = dict(LIVE_AT_AUDIT, ASIAN_RANGE_FILTERED_V6=(2.5, 3.5))      # live today
BASE_LOTS, BUF, CLAMP = 0.02, 0.1, (0.5, 4.0)
ASIAN = ("ASIAN_RANGE_FILTERED_V6", "ASIAN_BREAKOUT_V6")
GRID = {
    **{s: (("ar_far", "ar_mid", "ar_in25", "bc"), ("mm1", "mm1.5", "mm2", "r2", "atr")) for s in ASIAN},
    "LONDON_MOMENTUM_TIGHT_V6": (("lr_far", "lr_mid", "imp4", "ema21"), ("lrx0.5", "lrx1", "pd", "r2", "atr")),
    "NY_SESSION_REVERSAL_V6": (("wick", "wick_wide"), ("lr_mid", "lr_far", "r2", "atr")),
}
OUT = os.path.join("research", "results", "strategy_stops_2026-10-31.json")


def context(t, m15):
    """Strategy levels from M15 bars closed before the entry."""
    tm = m15["time"].astype(np.int64)
    hi, lo, cl = (m15[k].astype(float) for k in ("high", "low", "close"))
    day = (t["entry_time"] // 86400) * 86400
    closed = tm < (t["entry_time"] // 900) * 900
    c = {}
    a = np.where((tm >= day) & (tm < day + 21600) & closed)[0]
    if len(a):
        c["ar"] = (lo[a].min(), hi[a].max())
    b = np.where(tm == day + 25200)[0]
    if len(b):
        c["bc"] = (lo[b[0]], hi[b[0]])
    lr = np.where((tm >= day + 25200) & (tm < day + 42300) & closed)[0]
    if len(lr):
        c["lr"] = (lo[lr].min(), hi[lr].max())
        c["ema21"] = float(BaseStrategy.ema(cl[lr], min(21, len(lr)))[-1])
        c["imp4"] = (lo[lr[-4:]].min(), hi[lr[-4:]].max())
    sc = np.where(tm == (t["entry_time"] // 900) * 900 - 900)[0]
    if len(sc):
        c["sc"] = (lo[sc[0]], hi[sc[0]])
    prev = np.where(tm < day)[0]
    if len(prev):
        pday = (tm[prev[-1]] // 86400) * 86400
        p = np.where((tm >= pday) & (tm < pday + 86400))[0]
        c["pd"] = (lo[p].min(), hi[p].max())
    return c


def levels(t, s_name, t_name, c):
    """(stop price, target price, stop distance) for one trade, or None if the context is missing."""
    strat, e, buy = t["strategy"], t["entry_price"], t["is_buy"]
    atr = abs(e - t["initial_sl"]) / LIVE_AT_AUDIT[strat][0]
    sgn = 1 if buy else -1
    try:
        if s_name == "live":
            dist = LIVE[strat][0] * atr
        else:
            if s_name.startswith("ar"):
                lo, hi = c["ar"]
                w = hi - lo
                level = {"ar_far": lo if buy else hi, "ar_mid": (lo + hi) / 2,
                         "ar_in25": (hi - 0.25 * w) if buy else (lo + 0.25 * w)}[s_name]
            elif s_name == "bc":
                level = c["bc"][0] if buy else c["bc"][1]
            elif s_name in ("lr_far", "lr_mid"):
                lo, hi = c["lr"]
                level = (lo if buy else hi) if s_name == "lr_far" else (lo + hi) / 2
            elif s_name == "imp4":
                level = c["imp4"][0] if buy else c["imp4"][1]
            elif s_name == "ema21":
                level = c["ema21"]
            elif s_name in ("wick", "wick_wide"):
                level = c["sc"][0] if buy else c["sc"][1]
            else:
                raise ValueError(s_name)
            extra = 0.5 * atr if s_name == "wick_wide" else 0.0
            dist = sgn * (e - level) + (BUF * atr) + extra
        dist = min(max(dist, CLAMP[0] * atr), CLAMP[1] * atr)
        atr_tp = e + sgn * LIVE[strat][1] * atr
        if t_name in ("live", "atr"):
            tp = atr_tp
        elif t_name == "r2":
            tp = e + sgn * 2 * dist
        elif t_name.startswith("mm"):
            lo, hi = c["ar"]
            k = float(t_name[2:])
            tp = (hi + k * (hi - lo)) if buy else (lo - k * (hi - lo))
        elif t_name.startswith("lrx"):
            lo, hi = c["lr"]
            tp = e + sgn * float(t_name[3:]) * (hi - lo)
        elif t_name == "pd":
            tp = c["pd"][1] if buy else c["pd"][0]
        elif t_name in ("lr_mid", "lr_far"):
            lo, hi = c["lr"]
            tp = (lo + hi) / 2 if t_name == "lr_mid" else (hi if buy else lo)
        else:
            raise ValueError(t_name)
    except KeyError:
        return None
    if sgn * (tp - e) <= 0:            # target already behind the entry -> live ATR target
        tp = atr_tp
    return e - sgn * dist, tp, dist, atr


def exit_pl(t, sl, tp, lots, A):
    T, H, L, C, SPR = A
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
    gross = (px - e) * (1 if buy else -1) * lots * VPP
    nights = xt // 86400 - t["entry_time"] // 86400
    scale = lots / BASE_LOTS
    return gross - COMM * scale + (SWAP_LONG_NIGHT * scale * nights if buy else 0.0)


def main():
    rng = np.random.default_rng(31)
    D, _src = audit_data.trades()
    B = base.bars()
    m1, m15 = B.m1, B.m15
    A = (m1["time"].astype(np.int64), m1["high"].astype(float), m1["low"].astype(float), m1["close"].astype(float),
         np.where(m1["spread"] > 0, m1["spread"].astype(float), 260.0) * 0.001)
    W = ("DEV", "TEST", "RECENT")
    trades = {w: [t for t in D[w]["trades"] if not (HOLE[0] <= t["entry_time"] <= HOLE[1])] for w in W}
    out, verdicts = {}, []
    for strat, (stops, targets) in GRID.items():
        tr = {w: [t for t in trades[w] if t["strategy"] == strat] for w in W}
        ctx = {id(t): context(t, m15) for w in W for t in tr[w]}
        live_dist = {}
        pl = {}                                                      # (variant, mode) -> {window: [pl]}
        for (s_name, t_name) in [("live", "live")] + list(product(stops, targets)):
            for mode in ("fixed", "eqrisk"):
                if s_name == "live" and mode == "eqrisk":
                    continue
                key = f"{s_name}/{t_name}/{mode}"
                pl[key] = {}
                for w in W:
                    row = []
                    for t in tr[w]:
                        lv = levels(t, s_name, t_name, ctx[id(t)]) or levels(t, "live", "live", ctx[id(t)])
                        sl, tp, dist, atr = lv
                        if s_name == "live":
                            live_dist[id(t)] = dist
                        lots = BASE_LOTS
                        if mode == "eqrisk":
                            lots = min(0.04, max(0.01, round(BASE_LOTS * live_dist[id(t)] / dist, 2)))
                        row.append(exit_pl(t, sl, tp, lots, A))
                    pl[key][w] = row
        live = pl["live/live/fixed"]
        live_s = {w: stats(live[w]) for w in W}
        res = {k: {w: stats(v[w]) for w in W} for k, v in pl.items()}
        out[strat] = res
        print(f"\n{strat}  live: DEV ${live_s['DEV']['net']:.0f} TEST ${live_s['TEST']['net']:.0f} "
              f"RECENT ${live_s['RECENT']['net']:.0f} (DD {max(live_s['DEV']['dd'], live_s['TEST']['dd']):.0f})")
        for mode in ("fixed", "eqrisk"):
            keys = [k for k in pl if k.endswith("/" + mode) and not k.startswith("live")]
            best_dev = max(keys, key=lambda k: res[k]["DEV"]["net"])
            cand = max(keys, key=lambda k: res[k]["DEV"]["net"] + res[k]["TEST"]["net"])
            c1 = res[best_dev]["TEST"]["net"] > live_s["TEST"]["net"]
            c2 = res[cand]["RECENT"]["net"] >= live_s["RECENT"]["net"]
            dd_c = max(res[cand]["DEV"]["dd"], res[cand]["TEST"]["dd"])
            dd_l = max(live_s["DEV"]["dd"], live_s["TEST"]["dd"])
            c3 = dd_c <= 1.2 * dd_l
            diff = np.array([a - b for w in W for a, b in zip(pl[cand][w], live[w])])
            idx = rng.integers(0, len(diff), (20000, len(diff)))
            p_better = float((diff[idx].mean(1) > 0).mean())
            c4 = p_better >= 0.90
            ok = c1 and c2 and c3 and c4
            verdicts.append(dict(strategy=strat, mode=mode, candidate=cand, walk_forward_A=c1, walk_forward_B=c2,
                                 drawdown_ok=c3, p_better=round(p_better, 3), passed=ok))
            r = res[cand]
            print(f"  [{mode:6s}] candidate {cand:24s} DEV ${r['DEV']['net']:6.0f} TEST ${r['TEST']['net']:6.0f} "
                  f"RECENT ${r['RECENT']['net']:6.0f} DD ${dd_c:.0f} | WF-A({best_dev.split('/')[0]}/"
                  f"{best_dev.split('/')[1]}) {'ok' if c1 else 'FAIL'} WF-B {'ok' if c2 else 'FAIL'} "
                  f"DD {'ok' if c3 else 'FAIL'} MC P={p_better:.2f} {'ok' if c4 else 'FAIL'} -> {'PASS' if ok else 'fail'}")
    json.dump(dict(results=out, verdicts=verdicts), open(OUT, "w"), indent=0)


if __name__ == "__main__":
    main()
