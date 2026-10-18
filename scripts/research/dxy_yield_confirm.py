"""DXY / yield confirmation of gold trend, stage 1 (pre-registered: research/registry/PREREG_DxyYieldConfirm_2026-10-18.md, trial #645).

Run once: python scripts/research/dxy_yield_confirm.py <out.json>
"""
import sys, os, json, math, csv, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(ROOT)
COST = 0.0002          # 0.02% per position change


def sma(x, n):
    out = np.full(len(x), np.nan)
    c = np.cumsum(np.insert(x, 0, 0.0))
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def era(d):
    return "2000-2010" if d.year <= 2010 else "2011-2018" if d.year <= 2018 else "2019-2026"


def stats(ret, pos, dates):
    """Net daily strategy returns with a flat cost on every position change."""
    chg = np.abs(np.diff(np.concatenate([[0], pos])))
    net = pos * ret - chg * COST
    eq = np.cumprod(1 + net)
    dd = float((np.maximum.accumulate(eq) / eq - 1).max())
    ann = float(eq[-1] ** (252 / max(1, len(net))) - 1) if len(net) else 0.0
    sh = float(net.mean() / net.std() * math.sqrt(252)) if net.std() > 0 else 0.0
    return dict(ann_ret=ann, sharpe=sh, maxdd=dd, days_in_market=float((pos != 0).mean() * 100))


def main():
    outp = sys.argv[1]
    rows = list(csv.DictReader(open("research/data/d1_study/master.csv", encoding="utf-8")))
    dates = [dt.date.fromisoformat(r["Date"]) for r in rows]
    g = np.array([float(r["gold"]) for r in rows]); d = np.array([float(r["dxy"]) for r in rows]); y = np.array([float(r["y10"]) for r in rows])
    ok = ~(np.isnan(g) | np.isnan(d) | np.isnan(y))
    dates = [x for x, k in zip(dates, ok) if k]; g, d, y = g[ok], d[ok], y[ok]
    n = len(g)
    sg, sd = sma(g, 100), sma(d, 50)
    y20 = np.full(n, np.nan); y20[20:] = y[20:] - y[:-20]
    s = np.where(g > sg, 1, -1).astype(float); s[np.isnan(sg)] = 0
    cl = (s == 1) & (d < sd) & (y20 <= 0); cs = (s == -1) & (d > sd) & (y20 >= 0)
    valid = (s != 0) & ~np.isnan(sd) & ~np.isnan(y20)
    C = (cl | cs) & valid; U = ~(cl | cs) & valid
    # state at t, return t -> t+1
    ret = np.full(n, np.nan); ret[:-1] = g[1:] / g[:-1] - 1
    x = s * ret * 100                                      # signed return in %, next day
    idx = np.where(valid & ~np.isnan(ret))[0]
    xC, xU = x[idx[C[idx]]], x[idx[U[idx]]]
    se = math.sqrt(xC.var(ddof=1) / len(xC) + xU.var(ddof=1) / len(xU))
    tstat = (xC.mean() - xU.mean()) / se
    p_one = 0.5 * math.erfc(tstat / math.sqrt(2))          # one-sided C > U
    out = dict(first=str(dates[0]), last=str(dates[-1]), n_days=int(n), n_C=int(len(xC)), n_U=int(len(xU)),
               mean_C=float(xC.mean()), mean_U=float(xU.mean()), diff=float(xC.mean() - xU.mean()), t=float(tstat), p_one_sided=float(p_one),
               long_share_C=float(cl[idx][C[idx]].mean() * 100), eras={})
    for e in ("2000-2010", "2011-2018", "2019-2026"):
        m = np.array([era(dates[i]) == e for i in idx])
        a = x[idx][m & C[idx]]; b = x[idx][m & U[idx]]
        pos_c = np.where(C, s, 0.0)[idx][m]; base = s[idx][m]; r_ = ret[idx][m]
        dd_ = [dates[i] for i in idx[m]]
        out["eras"][e] = dict(n_C=int(len(a)), n_U=int(len(b)), mean_C=float(a.mean()) if len(a) else None, mean_U=float(b.mean()) if len(b) else None,
                              confirmed_strategy=stats(r_, pos_c, dd_), baseline_sma100=stats(r_, base, dd_))
    pos_c = np.where(C, s, 0.0)[idx]; base = s[idx]; r_ = ret[idx]; dd_ = [dates[i] for i in idx]
    out["full"] = dict(confirmed_strategy=stats(r_, pos_c, dd_), baseline_sma100=stats(r_, base, dd_))
    json.dump(out, open(outp, "w"), indent=1, default=float)
    print("C", len(xC), "U", len(xU), "diff", round(out["diff"], 4), "p", round(p_one, 4))


if __name__ == "__main__":
    main()
