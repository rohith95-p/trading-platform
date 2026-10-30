"""Are the live stop/target sizes (ATR multiples) the best ones? (owner 2026-10-30)

Takes the real entries of the live 4-leg setup (research/results/audit_2026-10-30/trades_no_donchian.json:
gate on, protector off, 24h, 0.02 lots) and replays each one on raw M1 bars with other stop/target multiples:
same costs as the engine (bar spread, 20-point slippage on stops, $3.50/lot commission, long swap) and the same
Friday 22:30 IST flatten. Entries stay fixed, so concurrency/Atlas-guard interactions are ignored; step 1 checks
that the replay reproduces the engine's own trades at the live multiples.

Selection is done on DEV + TEST only; RECENT (2026-07 to 2026-10) is kept as the unseen check.

    python scripts/validation/sltp_sweep.py
"""
import os
import sys
import json
import datetime as dt

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from scripts.validation import independent_audit_run as base   # noqa: E402

LIVE = {"ASIAN_RANGE_FILTERED_V6": (2.0, 3.5), "ASIAN_BREAKOUT_V6": (3.0, 5.0),
        "LONDON_MOMENTUM_TIGHT_V6": (2.0, 4.0), "NY_SESSION_REVERSAL_V6": (2.5, 4.5)}
SLS = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
TPS = (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 8.0)
LOTS, VPP, SLIP, COMM, SWAP_LONG_NIGHT = 0.02, 100.0, 0.020, 3.50 * 0.02, -515.5 * 0.001 * 100.0 * 0.02
HOLE = (dt.datetime(2025, 9, 14).timestamp(), dt.datetime(2025, 10, 15, 5).timestamp())
OUT = os.path.join("research", "results", "sltp_sweep_2026-10-30.json")


def friday_cut(ts: int) -> int:
    """Next Friday 17:00 UTC (22:30 IST) at or after ts."""
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    days = (4 - d.weekday()) % 7
    cut = (d + dt.timedelta(days=days)).replace(hour=17, minute=0, second=0, microsecond=0)
    if cut.timestamp() < ts:
        cut += dt.timedelta(days=7)
    return int(cut.timestamp())


def replay(t, sl_m, tp_m, T, H, L, C, SPR):
    """Net P&L of one entry with stop = sl_m x ATR and target = tp_m x ATR."""
    atr = abs(t["entry_price"] - t["initial_sl"]) / LIVE[t["strategy"]][0]
    e, buy = t["entry_price"], t["is_buy"]
    sl = e - sl_m * atr if buy else e + sl_m * atr
    tp = e + tp_m * atr if buy else e - tp_m * atr
    i0 = np.searchsorted(T, (t["entry_time"] // 60) * 60, side="right")
    cut = friday_cut(t["entry_time"])
    i1 = np.searchsorted(T, cut, side="left")          # engine closes before walking the 17:00 bar
    h, l, s = H[i0:i1], L[i0:i1], SPR[i0:i1]
    if buy:
        hit_sl, hit_tp = l <= sl, h >= tp
    else:
        hit_sl, hit_tp = h + s >= sl, l + s <= tp
    hit = hit_sl | hit_tp
    if hit.any():
        k = int(np.argmax(hit))
        px = (sl - SLIP if buy else sl + SLIP) if hit_sl[k] else tp
        xt = int(T[i0 + k])
    else:                                              # Friday close at the last walked bar's close
        k = i1 - 1
        px = float(C[k]) if buy else float(C[k] + SPR[k])
        xt = int(T[k])
    gross = (px - e) * (1 if buy else -1) * LOTS * VPP
    nights = xt // 86400 - t["entry_time"] // 86400
    return gross - COMM + (SWAP_LONG_NIGHT * nights if buy else 0.0)


def stats(p):
    p = np.asarray(p)
    if not len(p):
        return dict(n=0, net=0.0, pf=0.0, wr=0.0, dd=0.0)
    g, l = p[p > 0].sum(), -p[p < 0].sum()
    eq = np.cumsum(p)
    return dict(n=int(len(p)), net=round(float(p.sum()), 2), pf=round(float(g / l), 3) if l else 99.0,
                wr=round(float((p > 0).mean() * 100), 1),
                dd=round(float((np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max()), 2))


def main():
    D = json.load(open(os.path.join("research", "results", "audit_2026-10-30", "trades_no_donchian.json")))
    B = base.bars()
    m1 = B.m1
    T = m1["time"].astype(np.int64)
    H, L, C = (m1[k].astype(float) for k in ("high", "low", "close"))
    SPR = np.where(m1["spread"] > 0, m1["spread"].astype(float), 260.0) * 0.001
    trades = {w: [t for t in D[w]["trades"] if not (HOLE[0] <= t["entry_time"] <= HOLE[1])]
              for w in ("DEV", "TEST", "RECENT")}

    # 1. the replay must reproduce the engine at the live multiples
    for w, tr in trades.items():
        diffs = [abs(replay(t, *LIVE[t["strategy"]], T, H, L, C, SPR) - t["net_pl"]) for t in tr]
        print(f"replay check {w}: {sum(d < 0.01 for d in diffs)}/{len(diffs)} trades match the engine to the cent, "
              f"max diff ${max(diffs):.2f}")

    # 2. sweep
    out = {}
    for strat in LIVE:
        res = {}
        for slm in SLS:
            for tpm in TPS:
                key = f"{slm}/{tpm}"
                res[key] = {w: stats([replay(t, slm, tpm, T, H, L, C, SPR) for t in tr if t["strategy"] == strat])
                            for w, tr in trades.items()}
                fit = [replay(t, slm, tpm, T, H, L, C, SPR) for w in ("DEV", "TEST") for t in trades[w]
                       if t["strategy"] == strat]
                res[key]["FIT"] = stats(fit)
        out[strat] = res
    json.dump(out, open(OUT, "w"), indent=0)

    for strat, res in out.items():
        live = "%s/%s" % LIVE[strat]
        ranked = sorted(res, key=lambda k: res[k]["FIT"]["net"], reverse=True)
        print(f"\n{strat}  (live {live})")
        for k in [live] + [r for r in ranked[:5] if r != live]:
            f, r = res[k]["FIT"], res[k]["RECENT"]
            print(f"  SL {k.split('/')[0]:>3} x ATR / TP {k.split('/')[1]:>3} x ATR | DEV+TEST n={f['n']:3d} "
                  f"${f['net']:7.0f} PF {f['pf']:.2f} WR {f['wr']:.0f}% DD ${f['dd']:.0f} | RECENT ${r['net']:6.0f} "
                  f"PF {r['pf']:.2f}{'   <- live' if k == live else ''}")


if __name__ == "__main__":
    main()
