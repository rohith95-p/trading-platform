"""Gold event study around scheduled USD releases (protocol: research/registry/PROTOCOL_EventStudy_2026-10-18.md).

Descriptive only. Run once: python scripts/research/event_study.py <out.json>
"""
import sys, os, json, math, datetime as dt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regime_trend_sim as rt   # chdir to repo root; event loader

try:
    from scipy import stats as _st
except Exception:               # scipy not installed: normal approximation for t-tests
    _st = None

U = dt.timezone.utc


def p_ttest(x):
    x = np.asarray(x, float); n = len(x)
    if n < 3 or x.std(ddof=1) == 0: return float("nan"), float("nan")
    t = x.mean() / (x.std(ddof=1) / math.sqrt(n))
    if _st is not None: p = float(2 * _st.t.sf(abs(t), n - 1))
    else: p = float(math.erfc(abs(t) / math.sqrt(2)))
    return float(t), p


def p_binom(k, n):          # exact two-sided, p0 = 0.5
    if n == 0: return float("nan")
    pk = [math.comb(n, i) / 2 ** n for i in range(n + 1)]
    return float(min(1.0, sum(p for p in pk if p <= pk[k] + 1e-15)))


def bh(ps):
    ps = np.array(ps, float); idx = np.argsort(ps); m = len(ps); out = np.full(m, np.nan); prev = 1.0
    for rank, i in reversed(list(enumerate(idx, 1))):
        prev = min(prev, ps[i] * m / rank); out[i] = prev
    return out


def main():
    outp = sys.argv[1]
    m = np.load("research/data/XAUUSDm_M15.npy")
    t = m["time"].astype("int64"); o = m["open"].astype(float); h = m["high"].astype(float)
    l = m["low"].astype(float); c = m["close"].astype(float); sp = m["spread"].astype(float) * 0.001
    pc = np.concatenate([[c[0]], c[:-1]]); tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    pos = {int(x): i for i, x in enumerate(t)}
    import csv
    rows = list(csv.DictReader(open(rt.EVENTS_CSV, encoding="utf-8")))
    ev = []
    for r in rows:
        if r.get("verified", "").strip().lower() == "no": continue
        if "not published" in r.get("notes", "").lower(): continue
        ev.append((int(dt.datetime.fromisoformat(r["scheduled_utc"].replace("Z", "+00:00")).timestamp()), r["category"]))
    recs, dropped = [], 0
    for te, cat in sorted(ev):
        i = pos.get(te)
        if i is None or i < 8 or i + 8 >= len(t): dropped += 1; continue
        # contiguous 15-min bars from -8 .. +8 (covers -120min..+120min)
        if t[i + 8] - t[i - 8] != 16 * 900: dropped += 1; continue
        A = float(tr[i - 8:i].mean())
        if A <= 0: dropped += 1; continue
        P0 = o[i]
        def r(hmin): return float(c[i + hmin // 15 - 1] - P0)
        r15, r30, r60, r120 = r(15), r(30), r(60), r(120)
        volr = float(tr[i:i + 4].mean() / A)
        sp0 = float(np.median(sp[i - 8:i])) or 1e-9
        mfe = float(h[i:i + 8].max() - P0); mae = float(P0 - l[i:i + 8].min())
        trend = 1 if P0 - o[i - 8] > 0 else -1
        recs.append(dict(t=te, cat=cat, year=dt.datetime.fromtimestamp(te, U).year, A=A, r15=r15, r30=r30, r60=r60, r120=r120,
                         r15A=r15 / A, drift=r120 - r15, driftA=(r120 - r15) / A, volr=volr, sp_e=float(sp[i] / sp0), sp_15=float(sp[i + 1] / sp0),
                         mfeA=mfe / A, maeA=mae / A, trend=trend,
                         rev=int(np.sign(r15) != 0 and np.sign(r120 - r15) == -np.sign(r15)), cont=int(np.sign(r15) != 0 and np.sign(r120 - r15) == np.sign(r15))))
    cats = ["NFP", "CPI", "PCE", "FOMC_STATEMENT", "FOMC_PRESSER"]
    out = dict(n_events_total=len(ev), dropped=dropped, by_cat={}, tests=[])
    pv = []; names = []
    for cat in cats:
        s = [x for x in recs if x["cat"] == cat]
        if not s: continue
        volr = np.array([x["volr"] for x in s]); r15 = np.array([x["r15A"] for x in s]); dr = np.array([x["driftA"] for x in s])
        k_rev = sum(x["rev"] for x in s); n_dir = sum(x["rev"] + x["cont"] for x in s)
        up = int((volr > 1).sum())
        d = dict(n=len(s), median_volr=float(np.median(volr)), pct_volr_gt1=float(100 * up / len(s)), median_spread_ratio_event=float(np.median([x["sp_e"] for x in s])),
                 median_spread_ratio_15=float(np.median([x["sp_15"] for x in s])), mean_r15_A=float(r15.mean()), mean_drift_A=float(dr.mean()),
                 reversal_rate=float(100 * k_rev / n_dir) if n_dir else None, median_mfe_A=float(np.median([x["mfeA"] for x in s])),
                 median_mae_A=float(np.median([x["maeA"] for x in s])), median_A=float(np.median([x["A"] for x in s])))
        # five declared questions
        tests = [("volr>1", p_binom(up, len(s))), ("mean r15", p_ttest(r15)[1]), ("mean drift", p_ttest(dr)[1]),
                 ("reversal 50%", p_binom(k_rev, n_dir))]
        d["p"] = {nm: p for nm, p in tests}
        by_year = {}
        for y in sorted({x["year"] for x in s}):
            sy = [x for x in s if x["year"] == y]
            by_year[y] = dict(n=len(sy), mean_r15_A=float(np.mean([x["r15A"] for x in sy])), mean_drift_A=float(np.mean([x["driftA"] for x in sy])),
                              median_volr=float(np.median([x["volr"] for x in sy])),
                              reversal_rate=float(100 * sum(x["rev"] for x in sy) / max(1, sum(x["rev"] + x["cont"] for x in sy))))
        d["by_year"] = by_year
        out["by_cat"][cat] = d
        for nm, p in tests: pv.append(p); names.append(f"{cat}:{nm}")
    adj = bh([p if p == p else 1.0 for p in pv])
    out["tests"] = [dict(test=n, p=float(p), bh_p=float(a)) for n, p, a in zip(names, pv, adj)]
    json.dump(out, open(outp, "w"), indent=1, default=float)
    print("events used", len(recs), "dropped", dropped, "scipy", _st is not None)


if __name__ == "__main__":
    main()
