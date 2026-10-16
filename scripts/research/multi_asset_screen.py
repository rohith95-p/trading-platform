"""Multi-asset, pre-registered hypothesis screen (Stage 1).

Hypotheses are FIXED in HYPOTHESES below before any result is seen (small grid; the total number of tests is
reported and multiple-testing adjustments are applied). Chronological splits:
    DEV      : data start -> 2024-12-31   (used to rank / discard)
    VALIDATE : 2025-01-01 -> 2026-06-30   (must confirm; sign and PF > 1)
    HOLDOUT  : 2026-07-01 -> data end     (reported ONCE for survivors; never used to choose anything)

Execution model (tier 1, conservative): signal on the CLOSED H1/D1 bar, entry at the NEXT bar open paying the
bar's spread (long at ask, short at bid); stops/targets walked from the entry bar, stop-first when a bar touches
both; shorts exit on the ask (high+spread); max holding bars -> exit at close; swap charged per rollover night
(broker swap points x point; weekends not tripled -> slight under-statement); no slippage beyond spread (see
cost stress in the report script). Results are in R (risk = initial stop distance).

Usage: python multi_asset_screen.py <out.json> [symbols comma list]
"""
import sys, os, json, math, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

# Broker values read from MT5 on the Exness demo 2026-10-16 (see docs/research/DATA_COVERAGE_2026-10-16.md)
SPECS = {  # point, swap_long_pts, swap_short_pts (points per lot per night, broker units), weekend market
    "XAUUSDm": dict(point=0.001, swap_long=-500.0, swap_short=0.0, weekend=False),
    "EURUSDm": dict(point=1e-5, swap_long=-5.5, swap_short=0.0, weekend=False),
    "GBPUSDm": dict(point=1e-5, swap_long=-2.0, swap_short=-0.7, weekend=False),
    "USDJPYm": dict(point=1e-3, swap_long=0.0, swap_short=-13.9, weekend=False),
    "BTCUSDm": dict(point=0.01, swap_long=-1910.2, swap_short=0.0, weekend=True),
    "ETHUSDm": dict(point=0.01, swap_long=-57.1, swap_short=0.0, weekend=True),
}
U = dt.timezone.utc
TS = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=U).timestamp())
DEV_END, VAL_END = TS(2025, 1, 1), TS(2026, 7, 1)

# id, family, source/hypothesis, params   (every entry is a pre-registered test)
HYPOTHESES = [
    ("T1a", "trend", "Donchian breakout (turtle-style channel breakout), H1", dict(kind="donchian", n=55, sl=2.0, rr=3.0)),
    ("T1b", "trend", "Donchian breakout, H1, wider", dict(kind="donchian", n=100, sl=3.0, rr=3.0)),
    ("T2a", "trend", "EMA50>EMA200 trend + pullback to EMA20 resume, H1", dict(kind="pullback", sl=1.5, rr=2.0)),
    ("T2b", "trend", "EMA50>EMA200 trend + pullback to EMA20 resume, H1, wider", dict(kind="pullback", sl=2.5, rr=2.0)),
    ("M1a", "meanrev", "Bollinger(20,2)+RSI(14) 30/70 fade, H1", dict(kind="bbfade", sl=1.5, rr=1.0)),
    ("M1b", "meanrev", "Bollinger(20,2.5)+RSI(14) 25/75 fade, H1", dict(kind="bbfade2", sl=2.0, rr=1.0)),
    ("B1a", "breakout", "Prior-day range breakout (first close beyond prior D high/low), H1", dict(kind="pdrange", sl=1.5, rr=2.0)),
    ("B1b", "breakout", "UTC-day opening-range (first 4h) breakout, H1", dict(kind="orb", sl=1.5, rr=2.0)),
    ("V1a", "volatility", "Squeeze (BB width in lowest 20% of 100 bars) then breakout of 20-bar range, H1", dict(kind="squeeze", sl=1.5, rr=2.5)),
    ("V1b", "volatility", "ATR expansion (ATR14 > 1.5x its 100-bar median) continuation of the bar direction, H1", dict(kind="atrexp", sl=1.5, rr=2.0)),
    ("MO1a", "momentum", "Time-series momentum N=20d, daily", dict(kind="tsmom", n=20)),
    ("MO1b", "momentum", "Time-series momentum N=60d, daily", dict(kind="tsmom", n=60)),
    ("MO1c", "momentum", "Time-series momentum N=120d, daily", dict(kind="tsmom", n=120)),
]


# ------------------------------------------------------------------ data
def load(sym, tf):
    p = f"research/data/{sym}_{tf}.npy"
    return np.load(p) if os.path.exists(p) else None


def to_h1(m15):
    t = m15["time"].astype("int64"); hour = t // 3600
    keys, st = np.unique(hour, return_index=True)
    b = list(st) + [len(m15)]
    o = np.array([m15["open"][b[k]] for k in range(len(keys))], float)
    h = np.array([m15["high"][b[k]:b[k + 1]].max() for k in range(len(keys))], float)
    l = np.array([m15["low"][b[k]:b[k + 1]].min() for k in range(len(keys))], float)
    c = np.array([m15["close"][b[k + 1] - 1] for k in range(len(keys))], float)
    sp = np.array([m15["spread"][b[k]:b[k + 1]].mean() for k in range(len(keys))], float)
    full = np.array([b[k + 1] - b[k] for k in range(len(keys))])
    return dict(t=keys * 3600, o=o, h=h, l=l, c=c, sp=sp, full=full)


def to_d1(d1):
    return dict(t=d1["time"].astype("int64"), o=d1["open"].astype(float), h=d1["high"].astype(float),
                l=d1["low"].astype(float), c=d1["close"].astype(float), sp=d1["spread"].astype(float))


# ------------------------------------------------------------------ indicators (causal)
def ema(x, n):
    out = np.full(len(x), np.nan); k = 2 / (n + 1)
    if len(x) < n: return out
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)): out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def atr(h, l, c, n=14):
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.full(len(c), np.nan)
    if len(c) < n: return out
    out[n - 1] = tr[:n].mean()
    for i in range(n, len(c)): out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def rolling(x, n, fn):
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)): out[i] = fn(x[i - n + 1:i + 1])
    return out


def rsi(c, n=14):
    out = np.full(len(c), np.nan)
    if len(c) <= n: return out
    d = np.diff(c); g = np.where(d > 0, d, 0.0); ls = np.where(d < 0, -d, 0.0)
    ag, al = g[:n].mean(), ls[:n].mean()
    out[n] = 100 - 100 / (1 + ag / al) if al > 0 else 100
    for i in range(n, len(d)):
        ag = (ag * (n - 1) + g[i]) / n; al = (al * (n - 1) + ls[i]) / n
        out[i + 1] = 100 - 100 / (1 + ag / al) if al > 0 else 100
    return out


# ------------------------------------------------------------------ signals: +1/-1/0 on closed bar i (acts at i+1 open)
def signals(kind, p, B):
    o, h, l, c, t = B["o"], B["h"], B["l"], B["c"], B["t"]; n = len(c); s = np.zeros(n, np.int8)
    a = atr(h, l, c)
    if kind == "donchian":
        N = p["n"]
        hh = rolling(h, N, np.max); ll = rolling(l, N, np.min)
        for i in range(N + 1, n):
            up = c[i] > hh[i - 1]; dn = c[i] < ll[i - 1]
            prev_up = c[i - 1] > hh[i - 2]; prev_dn = c[i - 1] < ll[i - 2]
            if up and not prev_up: s[i] = 1
            elif dn and not prev_dn: s[i] = -1
    elif kind == "pullback":
        e20, e50, e200 = ema(c, 20), ema(c, 50), ema(c, 200)
        for i in range(201, n):
            if e50[i] > e200[i] and l[i - 1] <= e20[i - 1] and c[i] > e20[i] and c[i] > c[i - 1]: s[i] = 1
            elif e50[i] < e200[i] and h[i - 1] >= e20[i - 1] and c[i] < e20[i] and c[i] < c[i - 1]: s[i] = -1
    elif kind in ("bbfade", "bbfade2"):
        k, lo_r, hi_r = (2.0, 30, 70) if kind == "bbfade" else (2.5, 25, 75)
        m_ = rolling(c, 20, np.mean); sd = rolling(c, 20, np.std); r = rsi(c)
        for i in range(30, n):
            if c[i] < m_[i] - k * sd[i] and r[i] < lo_r: s[i] = 1
            elif c[i] > m_[i] + k * sd[i] and r[i] > hi_r: s[i] = -1
    elif kind == "pdrange":
        day = t // 86400
        dh, dl = {}, {}
        for i in range(n):
            dh[day[i]] = max(dh.get(day[i], -1e18), h[i]); dl[day[i]] = min(dl.get(day[i], 1e18), l[i])
        fired = set()
        for i in range(30, n):
            d = day[i]; pd = d - 1
            while pd not in dh and pd > d - 5: pd -= 1
            if pd not in dh or d in fired: continue
            if c[i] > dh[pd]: s[i] = 1; fired.add(d)
            elif c[i] < dl[pd]: s[i] = -1; fired.add(d)
    elif kind == "orb":
        day = t // 86400; hour = (t % 86400) // 3600
        rng = {}
        for i in range(n):
            if hour[i] < 4:
                r = rng.get(day[i], [-1e18, 1e18]); r[0] = max(r[0], h[i]); r[1] = min(r[1], l[i]); rng[day[i]] = r
        fired = set()
        for i in range(30, n):
            d = day[i]
            if hour[i] < 4 or d not in rng or d in fired: continue
            if c[i] > rng[d][0]: s[i] = 1; fired.add(d)
            elif c[i] < rng[d][1]: s[i] = -1; fired.add(d)
    elif kind == "squeeze":
        m_ = rolling(c, 20, np.mean); sd = rolling(c, 20, np.std); w = (4 * sd) / m_
        hh = rolling(h, 20, np.max); ll = rolling(l, 20, np.min)
        for i in range(125, n):
            thr = np.percentile(w[i - 100:i], 20)
            if w[i - 1] <= thr:
                if c[i] > hh[i - 1]: s[i] = 1
                elif c[i] < ll[i - 1]: s[i] = -1
    elif kind == "atrexp":
        med = rolling(a, 100, np.median)
        for i in range(120, n):
            if a[i] > 1.5 * med[i] and abs(c[i] - o[i]) > 0.8 * a[i]:
                s[i] = 1 if c[i] > o[i] else -1
    return s, a


# ------------------------------------------------------------------ trade simulation
def simulate(B, s, a, spec, sl, rr, max_bars=100):
    o, h, l, c, t, sp = B["o"], B["h"], B["l"], B["c"], B["t"], B["sp"] * spec["point"]
    n = len(c); out = []  # (entry_time, R)
    i = 0
    while i < n - 2:
        d = s[i]
        if d == 0 or not np.isfinite(a[i]) or a[i] <= 0: i += 1; continue
        risk = sl * a[i]
        if d > 0: entry = o[i + 1] + sp[i + 1]; stop, tgt = entry - risk, entry + rr * risk
        else: entry = o[i + 1]; stop, tgt = entry + risk, entry - rr * risk
        exit_px = None; j = i + 1; jend = min(i + 1 + max_bars, n)
        while j < jend:
            if d > 0: hs, ht = l[j] <= stop, h[j] >= tgt
            else: hs, ht = h[j] + sp[j] >= stop, l[j] + sp[j] <= tgt
            if hs: exit_px = stop; break
            if ht: exit_px = tgt; break
            j += 1
        if exit_px is None:
            j = jend - 1; exit_px = c[j] + (sp[j] if d < 0 else 0.0)
        pnl = (exit_px - entry) if d > 0 else (entry - exit_px)
        nights = int(t[min(j, n - 1)] // 86400 - t[i + 1] // 86400)
        swap_pts = spec["swap_long"] if d > 0 else spec["swap_short"]
        pnl += swap_pts * spec["point"] * nights          # swap points are negative = cost
        out.append((int(t[i + 1]), pnl / risk)); i = j + 1
    return out


def simulate_tsmom(D, N, spec):
    c, t = D["c"], D["t"]; sp = D["sp"] * spec["point"]; out = []; prev = 0
    for i in range(N, len(c) - 1):
        pos = 1 if c[i] > c[i - N] else -1
        r = (c[i + 1] - c[i]) * pos
        if pos != prev: r -= sp[i]; prev = pos
        swap = spec["swap_long"] if pos > 0 else spec["swap_short"]
        r += swap * spec["point"]
        out.append((int(t[i + 1]), r))
    atr_d = atr(D["h"], D["l"], c); k = np.nanmedian(atr_d)
    return [(tt, r / k) for tt, r in out]      # normalise by median daily ATR so values are comparable


# ------------------------------------------------------------------ stats
def pf(R):
    R = np.asarray(R); w = R[R > 0].sum(); lo = -R[R < 0].sum()
    return float(w / lo) if lo > 0 else float("inf")


def tstat(R):
    R = np.asarray(R)
    return float(R.mean() / (R.std(ddof=1) / math.sqrt(len(R)))) if len(R) > 2 and R.std() > 0 else 0.0


def pval(t): return math.erfc(abs(t) / math.sqrt(2))  # two-sided normal approx


def split_stats(tr):
    res = {}
    for name, lo, hi in (("dev", -1, DEV_END), ("val", DEV_END, VAL_END), ("hold", VAL_END, 2 ** 62)):
        R = np.array([r for tt, r in tr if lo <= tt < hi])
        if len(R) < 5: res[name] = dict(n=len(R)); continue
        res[name] = dict(n=len(R), win=float((R > 0).mean() * 100), pf=pf(R), exp=float(R.mean()), t=tstat(R), p=pval(tstat(R)))
    return res


def main():
    out = sys.argv[1]; syms = sys.argv[2].split(",") if len(sys.argv) > 2 else list(SPECS)
    rows = []
    for sym in syms:
        spec = SPECS[sym]; m15, d1, h1n = load(sym, "M15"), load(sym, "D1"), load(sym, "H1")
        if h1n is not None and not (m15 is not None and h1n["time"][-1] < m15["time"][-1] - 30 * 86400):   # native H1 unless stale
            H1 = dict(t=h1n["time"].astype("int64"), o=h1n["open"].astype(float), h=h1n["high"].astype(float),
                      l=h1n["low"].astype(float), c=h1n["close"].astype(float), sp=h1n["spread"].astype(float))
        elif m15 is not None: H1 = to_h1(m15)
        else: print("no H1/M15 for", sym); continue
        if sym in ("EURUSDm", "GBPUSDm"):     # before 2017-03-01 the "H1" cache is one daily bar per day (see DATA_COVERAGE)
            keep = H1["t"] >= TS(2017, 3, 1); H1 = {k: v[keep] for k, v in H1.items()}
        D1 = to_d1(d1) if d1 is not None else None
        print(sym, "H1 bars", len(H1["c"]), flush=True)
        for hid, fam, src, p in HYPOTHESES:
            if p["kind"] == "tsmom":
                if D1 is None: continue
                tr = simulate_tsmom(D1, p["n"], spec)
            else:
                s, a = signals(p["kind"], p, H1)
                tr = simulate(H1, s, a, spec, p["sl"], p["rr"])
            st = split_stats(tr)
            rows.append(dict(symbol=sym, id=hid, family=fam, source=src, params=p, stats=st))
            d, v = st.get("dev", {}), st.get("val", {})
            print(f"  {hid} dev n={d.get('n')} PF={d.get('pf', 0):.2f} t={d.get('t', 0):+.1f} | val n={v.get('n')} PF={v.get('pf', 0):.2f} t={v.get('t', 0):+.1f}", flush=True)
    # multiple-testing: Benjamini-Hochberg across all dev p-values, Bonferroni too
    ps = sorted([(r["stats"]["dev"].get("p", 1.0), k) for k, r in enumerate(rows) if "p" in r["stats"].get("dev", {})])
    m = len(ps)
    for rank, (p, k) in enumerate(ps, 1):
        rows[k]["dev_p_bonf"] = min(1.0, p * m); rows[k]["dev_q_bh"] = min(1.0, p * m / rank)
    json.dump(dict(n_tests=m, splits=dict(dev_end=DEV_END, val_end=VAL_END), rows=rows), open(out, "w"), default=float)
    print("tests:", m)


if __name__ == "__main__":
    main()
