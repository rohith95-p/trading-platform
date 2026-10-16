"""Stage 1b — slow (H4/D1) pre-registered hypotheses across the six instruments.

Same protocol as multi_asset_screen.py: hypotheses fixed in advance; DEV (start->2024-12-31), VALIDATE
(2025-01-01->2026-06-30), HOLDOUT (2026-07-01->end, read once); BH/Bonferroni across all tests.

Position model (volatility-targeted, daily-return units):
  * signal known at the close of bar i -> position established at the OPEN of bar i+1 -> earns open(i+1)->open(i+2)
  * weight = target_vol / EWMA-vol (lambda 0.94, info up to bar i), capped; target 1 % per day
  * cost per unit of turnover = half the bar spread (as % of price) [bars are bid; a round trip pays one spread]
  * swap: broker swap points x point / price per night held (long uses swap_long, short swap_short; negative = cost)
Results are per-bar returns in "vol-target %" units; Sharpe is annualised with bars-per-year from the data.

Usage: python multi_asset_slow.py <out.json>
"""
import sys, os, json, math, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multi_asset_screen import SPECS, TS, DEV_END, VAL_END, ema, atr, rolling  # noqa: E402

TARGET = 0.01      # 1 % daily vol target per asset
WCAP = 4.0

# id, kind, label, params, applies_to
HYP = [
    ("S1a", "tsmom", "Time-series momentum 20d (D1)", dict(n=20)),
    ("S1b", "tsmom", "Time-series momentum 60d (D1)", dict(n=60)),
    ("S1c", "tsmom", "Time-series momentum 120d (D1)", dict(n=120)),
    ("S1d", "tsmom", "Time-series momentum 250d (D1)", dict(n=250)),
    ("S2a", "emax", "EMA 20/100 cross trend (D1)", dict(f=20, s=100)),
    ("S2b", "emax", "EMA 50/200 cross trend (D1)", dict(f=50, s=200)),
    ("S3a", "donch", "Donchian 50 entry / 25 exit, long+short (D1)", dict(n=50, m=25)),
    ("S3b", "donch", "Donchian 120 entry / 60 exit, long+short (H4, ~20d/10d)", dict(n=120, m=60, tf="H4")),
    ("S4a", "tsmom_er", "TS momentum 60d only when Kaufman efficiency ratio(30) > 0.25 (D1)", dict(n=60, er=0.25)),
]
PORT = [  # portfolio-level
    ("P1a", "port_ts", "Equal-weight portfolio of TS momentum 60d across all assets", dict(n=60)),
    ("P1b", "port_ts", "Equal-weight portfolio of TS momentum 120d across all assets", dict(n=120)),
    ("P2a", "xsmom", "Cross-sectional momentum 60d: long top-2 / short bottom-2 of 6 assets (D1)", dict(n=60)),
    ("P2b", "xsmom", "Cross-sectional momentum 120d: long top-2 / short bottom-2 of 6 assets (D1)", dict(n=120)),
]
CARRY = ("C1", "carry", "Broker-swap carry proxy: hold the direction with the better swap (FX only; weak proxy for true carry)", {})


def load(sym, tf):
    p = f"research/data/{sym}_{tf}.npy"
    a = np.load(p)
    d = dict(t=a["time"].astype("int64"), o=a["open"].astype(float), h=a["high"].astype(float),
             l=a["low"].astype(float), c=a["close"].astype(float), sp=a["spread"].astype(float))
    if sym in ("EURUSDm", "GBPUSDm") and tf in ("H1", "H4"):
        k = d["t"] >= TS(2017, 3, 1); d = {x: v[k] for x, v in d.items()}
    return d


def ewvol(ret, lam=0.94):
    v = np.zeros(len(ret)); s = np.nanvar(ret[:30]) if len(ret) > 30 else 1e-4
    for i in range(len(ret)):
        v[i] = s
        r = ret[i] if np.isfinite(ret[i]) else 0.0
        s = lam * s + (1 - lam) * r * r
    return np.sqrt(v)


def positions(kind, p, B):
    c, h, l = B["c"], B["h"], B["l"]; n = len(c); pos = np.zeros(n)
    if kind in ("tsmom", "tsmom_er"):
        N = p["n"]
        for i in range(N, n):
            s = 1.0 if c[i] > c[i - N] else -1.0
            if kind == "tsmom_er":
                net = abs(c[i] - c[i - 30]) if i >= 30 else 0; path = np.abs(np.diff(c[i - 30:i + 1])).sum() if i >= 30 else 1
                er = net / path if path > 0 else 0
                if er <= p["er"]: s = 0.0
            pos[i] = s
    elif kind == "emax":
        ef, es = ema(c, p["f"]), ema(c, p["s"])
        for i in range(p["s"], n): pos[i] = 1.0 if ef[i] > es[i] else -1.0
    elif kind == "donch":
        N, M = p["n"], p["m"]; st = 0.0
        hh, ll = rolling(h, N, np.max), rolling(l, N, np.min); xh, xl = rolling(h, M, np.max), rolling(l, M, np.min)
        for i in range(N + 1, n):
            if st == 0:
                if c[i] > hh[i - 1]: st = 1.0
                elif c[i] < ll[i - 1]: st = -1.0
            elif st > 0 and c[i] < xl[i - 1]: st = 0.0
            elif st < 0 and c[i] > xh[i - 1]: st = 0.0
            pos[i] = st
    return pos


def returns_stream(B, pos, spec, swap_dir=None):
    """Per-bar vol-targeted return series (times = establishment bar i+1)."""
    o, t, c, sp = B["o"], B["t"], B["c"], B["sp"] * spec["point"]
    n = len(o)
    rn = np.full(n, np.nan); rn[:-1] = o[1:] / o[:-1] - 1.0           # open(j)->open(j+1)
    vol = ewvol(np.concatenate([[np.nan], c[1:] / c[:-1] - 1.0]))
    w = np.clip(TARGET / np.maximum(vol, 0.0015), 0, WCAP)
    x_t, x = [], []; prev = 0.0
    for i in range(n - 2):
        p_i = pos[i] * w[i]
        ret = p_i * rn[i + 1]
        turn = abs(p_i - prev); prev = p_i
        cost = turn * (sp[i + 1] / o[i + 1]) / 2.0
        nights = int(t[i + 2] // 86400 - t[i + 1] // 86400)
        swap = 0.0
        if p_i != 0 and nights > 0:
            sw = spec["swap_long"] if p_i > 0 else spec["swap_short"]
            swap = abs(p_i) * sw * spec["point"] / o[i + 1] * nights       # negative = cost
        x_t.append(int(t[i + 1])); x.append(ret - cost + swap)
    return np.array(x_t), np.array(x)


def stats(tt, x, bars_per_year):
    out = {}
    for name, lo, hi in (("dev", -1, DEV_END), ("val", DEV_END, VAL_END), ("hold", VAL_END, 2 ** 62)):
        m = (tt >= lo) & (tt < hi); r = x[m]
        if len(r) < 60: out[name] = dict(n=int(len(r))); continue
        mu, sd = r.mean(), r.std(ddof=1)
        t_ = mu / (sd / math.sqrt(len(r))) if sd > 0 else 0.0
        eq = np.cumsum(r); dd = float((np.maximum.accumulate(np.concatenate([[0], eq])) - np.concatenate([[0], eq])).max())
        out[name] = dict(n=int(len(r)), sharpe=float(mu / sd * math.sqrt(bars_per_year)) if sd > 0 else 0.0, t=float(t_),
                         p=math.erfc(abs(t_) / math.sqrt(2)), total=float(eq[-1] * 100), maxdd=dd * 100,
                         pf=float(r[r > 0].sum() / -r[r < 0].sum()) if (r < 0).any() else float("inf"))
    return out


def bpy(B):
    span = (B["t"][-1] - B["t"][0]) / 86400 / 365.25
    return len(B["t"]) / span


def main():
    out = sys.argv[1]; rows = []; D1 = {}; streams = {}
    for sym in SPECS:
        D1[sym] = load(sym, "D1")
    for sym, spec in SPECS.items():
        for hid, kind, label, p in HYP:
            B = load(sym, p.get("tf", "D1")) if p.get("tf") else D1[sym]
            pos = positions(kind, p, B)
            tt, x = returns_stream(B, pos, spec)
            rows.append(dict(symbol=sym, id=hid, kind=kind, label=label, params=p, stats=stats(tt, x, bpy(B))))
            if hid in ("S1b", "S1c"): streams[(sym, hid)] = (tt, x)
        # carry proxy (FX)
        if sym in ("EURUSDm", "GBPUSDm", "USDJPYm"):
            B = D1[sym]; d = 1.0 if spec["swap_long"] > spec["swap_short"] else -1.0
            tt, x = returns_stream(B, np.full(len(B["c"]), d), spec)
            rows.append(dict(symbol=sym, id="C1", kind="carry", label=CARRY[2], params=dict(direction=d), stats=stats(tt, x, bpy(B))))
        print(sym, "done", flush=True)
    # portfolio tests: average of per-asset streams on common timestamps
    def combine(hid):
        ds = {s: dict(zip(*streams[(s, hid)])) for s in SPECS}
        allt = sorted(set().union(*[set(v) for v in ds.values()]))
        tt, xs = [], []
        for t in allt:
            vals = [ds[s][t] for s in SPECS if t in ds[s]]
            if vals: tt.append(t); xs.append(np.mean(vals))
        return np.array(tt), np.array(xs)
    for pid, kind, label, p in PORT:
        if kind == "port_ts":
            tt, x = combine("S1b" if p["n"] == 60 else "S1c"); bp = 365 * (len(tt) / ((tt[-1] - tt[0]) / 86400))
            rows.append(dict(symbol="PORTFOLIO", id=pid, kind=kind, label=label, params=p, stats=stats(tt, x, bp)))
        else:
            N = p["n"]; syms = list(SPECS)
            dates = sorted(set().union(*[set(D1[s]["t"]) for s in syms])); idx = {s: {t: i for i, t in enumerate(D1[s]["t"])} for s in syms}
            tt, xs = [], []; prevw = {s_: 0.0 for s_ in syms}
            for k in range(N, len(dates) - 2):
                t0 = dates[k]; sc = {}
                for s_ in syms:
                    i = idx[s_].get(t0)
                    if i is not None and i >= N and i + 2 < len(D1[s_]["c"]): sc[s_] = (D1[s_]["c"][i] / D1[s_]["c"][i - N] - 1.0, i)
                if len(sc) < 4: continue
                rk = sorted(sc, key=lambda s_: sc[s_][0]); legs = {rk[-1]: 1, rk[-2]: 1, rk[0]: -1, rk[1]: -1}
                r = 0.0; neww = {}
                for s_ in syms:
                    sg = legs.get(s_, 0)
                    if s_ in sc:
                        B = D1[s_]; i = sc[s_][1]
                        vol = ewvol(np.concatenate([[np.nan], B["c"][1:i + 1] / B["c"][:i] - 1.0]))[-1]
                        wgt = sg * min(TARGET / max(vol, 0.0015), WCAP) / 4.0
                        rn = B["o"][i + 2] / B["o"][i + 1] - 1.0
                        r += wgt * rn - abs(wgt - prevw[s_]) * (B["sp"][i + 1] * SPECS[s_]["point"] / B["o"][i + 1]) / 2.0
                        nights = int(B["t"][i + 2] // 86400 - B["t"][i + 1] // 86400)
                        if wgt != 0: r += abs(wgt) * (SPECS[s_]["swap_long"] if wgt > 0 else SPECS[s_]["swap_short"]) * SPECS[s_]["point"] / B["o"][i + 1] * nights
                        neww[s_] = wgt
                    else: neww[s_] = 0.0
                prevw = neww
                tt.append(int(dates[k + 1])); xs.append(r)
            tt, x = np.array(tt), np.array(xs); order = np.argsort(tt); tt, x = tt[order], x[order]
            rows.append(dict(symbol="PORTFOLIO", id=pid, kind=kind, label=label, params=p, stats=stats(tt, x, 252)))
    ps = sorted([(r["stats"]["dev"].get("p", 1.0), k) for k, r in enumerate(rows) if "p" in r["stats"].get("dev", {})]); m = len(ps)
    for rank, (p, k) in enumerate(ps, 1):
        rows[k]["dev_p_bonf"] = min(1.0, p * m); rows[k]["dev_q_bh"] = min(1.0, p * m / rank)
    json.dump(dict(n_tests=m, rows=rows), open(out, "w"), default=float)
    print("tests:", m)


if __name__ == "__main__":
    main()
