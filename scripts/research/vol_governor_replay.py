"""Replay failed strategies with/without the volatility governor (pre-registered: PREREG_VolGovernor_2026-10-18.md).

Run once: python scripts/research/vol_governor_replay.py <out.json>
"""
import sys, os, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regime_trend_sim as rt          # chdir to repo root; atr, load_events
import fvggold_sim as fg
from src.core import vol_regime as vr

SEED, SHUFFLES = 641, 5000


def h1_atr_series():
    m = np.load("research/data/XAUUSDm_M15.npy")
    t = m["time"].astype("int64"); h = m["high"].astype(float); l = m["low"].astype(float); c = m["close"].astype(float)
    hb = t // 3600
    keys, st, cnt = np.unique(hb, return_index=True, return_counts=True)
    ok = np.array([cnt[k] == 4 and t[st[k] + 3] - t[st[k]] == 2700 for k in range(len(keys))])
    keys, st = keys[ok], st[ok]
    H, L, C = (np.array([h[s:s + 4].max() for s in st]), np.array([l[s:s + 4].min() for s in st]), c[st + 3])
    return keys * 3600, rt.atr(H, L, C, 14)


def regime_at(ts, H1t, a1, ev):
    k = int(np.searchsorted(H1t + 3600, ts, side="right")) - 1       # last H1 bar fully closed at ts
    if k < 1: return vr.classify(None, vr.near_event(ts, ev))
    return vr.classify(vr.atr_percentile(list(a1[max(0, k - vr.WINDOW):k]), a1[k]), vr.near_event(ts, ev))


def maxdd(x):
    eq = np.cumsum(x); return float((np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max()) if len(x) else 0.0


def metrics(t_exit, pnl):
    o = np.argsort(t_exit); p = np.asarray(pnl, float)[o]; te = np.asarray(t_exit)[o]
    dd = maxdd(p); net = float(p.sum())
    days = {}
    for ti, v in zip(te, p): days[int(ti // 86400)] = days.get(int(ti // 86400), 0.0) + v
    q = np.sort(p); k = max(1, int(0.05 * len(q)))
    return dict(n_nonzero=int((p != 0).sum()), net=net, maxdd=dd, calmar=(net / dd if dd > 0 else float("nan")),
                worst_day=float(min(days.values())) if days else 0.0, cvar5=float(q[:k].mean()))


def replay(name, trades, H1t, a1, ev):
    rows = []
    for tr in trades:
        r = regime_at(tr["t_in"], H1t, a1, ev)
        if r.name == "UNKNOWN": continue                             # warm-up: dropped from BOTH arms
        rows.append((tr["t_in"], tr["t_out"], tr["pnl"], r))
    if len(rows) < 30: return dict(name=name, error="too few trades after warm-up", n=len(rows))
    t_out = np.array([x[1] for x in rows]); pnl = np.array([x[2] for x in rows]); mult = np.array([x[3].risk_multiplier for x in rows])
    base = metrics(t_out, pnl); gov = metrics(t_out, pnl * mult)
    rng = np.random.default_rng(SEED); cal = []
    for _ in range(SHUFFLES):
        m = rng.permutation(mult); mm = metrics(t_out, pnl * m)
        cal.append(mm["calmar"])
    cal = np.array([x for x in cal if x == x])
    p95 = float(np.percentile(cal, 95)); pval = float((cal >= gov["calmar"]).mean())
    by = {}
    for x in rows:
        d = by.setdefault(x[3].name, dict(n=0, sum=0.0, wins=0)); d["n"] += 1; d["sum"] += x[2]; d["wins"] += x[2] > 0
    reg = {k: dict(n=v["n"], avg_pnl=v["sum"] / v["n"], win_pct=100 * v["wins"] / v["n"]) for k, v in by.items()}
    return dict(name=name, n=len(rows), baseline=base, governed=gov, placebo_calmar_p95=p95, placebo_p=pval,
                better_than_baseline=bool(gov["calmar"] > base["calmar"]), beats_placebo=bool(gov["calmar"] > p95), regimes=reg)


def main():
    outp = sys.argv[1]
    H1t, a1 = h1_atr_series(); ev = [e[0] for e in rt.load_events()]
    sets = {}
    cx = fg.Ctx(); p = fg.P(pending="age", fillbar="path")
    trs = fg.simulate(cx, p, "2022-09-01", "2026-10-14")
    sets["FvgGold_B_path"] = [dict(t_in=x["fill_t"], t_out=x["exit_t"], pnl=x["pnl"]) for x in trs]
    r640 = json.load(open("research/registry/regime_trend_result_2026-10-18.json"))["trades"]
    sets["Trial640"] = [dict(t_in=x["t"], t_out=x["x"], pnl=x["R"]) for x in r640]
    r641 = json.load(open("research/registry/asian_london_result_2026-10-18.json"))["trades"]
    sets["Trial641_reported_only"] = [dict(t_in=x["t"], t_out=x["x"], pnl=x["R"]) for x in r641]
    out = {k: replay(k, v, H1t, a1, ev) for k, v in sets.items()}
    json.dump(out, open(outp, "w"), indent=1, default=float)
    print({k: (v.get("n"), v.get("error")) for k, v in out.items()})


if __name__ == "__main__":
    main()
