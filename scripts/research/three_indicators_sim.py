"""Three TradingView indicator strategies x fixed SL/TP pairs (pre-registered: research/registry/PREREG_ThreeIndicators_2026-10-19.md).

Run once: python scripts/research/three_indicators_sim.py <out.json>
"""
import sys, os, json, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regime_trend_sim as rt

rt.dsr.__defaults__ = (654,)
PAIRS = {"P1": (1.0, 1.5), "P2": (1.5, 3.0), "P3": (2.0, 2.0)}
WARM = 500
N_PLACEBO, SEED = 2000, 654


# ---------------------------------------------------------------- indicator helpers (NaN-aware)
def rma(x, n):
    out = np.full(len(x), np.nan); k = np.where(~np.isnan(x))[0]
    if len(k) < n: return out
    i0 = k[0] + n - 1
    out[i0] = np.mean(x[k[0]:i0 + 1])
    for i in range(i0 + 1, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n if not np.isnan(x[i]) else out[i - 1]
    return out


def ema_n(x, n):
    out = np.full(len(x), np.nan); k = np.where(~np.isnan(x))[0]
    if len(k) < n: return out
    i0 = k[0] + n - 1
    out[i0] = np.mean(x[k[0]:i0 + 1]); a = 2.0 / (n + 1)
    for i in range(i0 + 1, len(x)):
        out[i] = x[i] * a + out[i - 1] * (1 - a) if not np.isnan(x[i]) else out[i - 1]
    return out


def shift(x, k=1):
    out = np.full(len(x), np.nan); out[k:] = x[:-k]; return out


def crossover(a, b):
    a1, b1 = shift(a), shift(b)
    return (a > b) & (a1 <= b1)


def crossunder(a, b):
    a1, b1 = shift(a), shift(b)
    return (a < b) & (a1 >= b1)


def pine_cross(a, b):
    return crossover(a, b) | crossunder(a, b)


# ---------------------------------------------------------------- signals: +1 long, -1 short, 0 none; value at bar t is known at t's close
def sig_ema20(o, h, l, c):
    e = ema_n(c, 20); x = shift(c, 1)                      # x[t] = close[t-1]
    with np.errstate(invalid="ignore"):
        lg = crossover(x, e) & (c >= shift(h, 1))
        sh = crossunder(x, e) & (c <= shift(l, 1))
    s = np.zeros(len(c)); s[lg] = 1; s[sh] = -1; return s


def sig_utbot(o, h, l, c, key=1.0, period=10):
    n = len(c); xatr = rt.atr(h, l, c, period); nloss = key * xatr
    stop = np.zeros(n); prev = 0.0
    for i in range(n):
        if np.isnan(nloss[i]): stop[i] = prev; continue
        s_, s1 = c[i], (c[i - 1] if i > 0 else np.nan)
        if s_ > prev and s1 > prev: v = max(prev, s_ - nloss[i])
        elif s_ < prev and s1 < prev: v = min(prev, s_ + nloss[i])
        elif s_ > prev: v = s_ - nloss[i]
        else: v = s_ + nloss[i]
        stop[i] = v; prev = v
    buy = (c > stop) & crossover(c, stop)
    sell = (c < stop) & crossover(stop, c)
    s = np.zeros(n); s[buy] = 1; s[sell] = -1; s[np.isnan(xatr)] = 0; return s


def sig_qqe(o, h, l, c, rsi_len=14, sf=5, qqe=4.238):
    n = len(c); w = rsi_len * 2 - 1
    d = np.diff(c, prepend=np.nan)
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0); up[0] = dn[0] = np.nan
    ru, rd = rma(up, rsi_len), rma(dn, rsi_len)
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = 100 - 100 / (1 + ru / rd)
    rsima = ema_n(rsi, sf)
    atrrsi = np.abs(shift(rsima) - rsima)
    dar = ema_n(ema_n(atrrsi, w), w) * qqe
    longb = np.full(n, np.nan); shortb = np.full(n, np.nan)
    for i in range(1, n):
        if np.isnan(dar[i]) or np.isnan(rsima[i]): continue
        nl, ns = rsima[i] - dar[i], rsima[i] + dar[i]
        pl, ps_ = longb[i - 1], shortb[i - 1]
        longb[i] = max(pl, nl) if (not np.isnan(pl) and rsima[i - 1] > pl and rsima[i] > pl) else nl
        shortb[i] = min(ps_, ns) if (not np.isnan(ps_) and rsima[i - 1] < ps_ and rsima[i] < ps_) else ns
    with np.errstate(invalid="ignore"):
        cross1 = pine_cross(shift(longb), rsima)
        crossS = pine_cross(rsima, shift(shortb))
    trend = np.ones(n);
    for i in range(1, n):
        trend[i] = 1 if crossS[i] else -1 if cross1[i] else trend[i - 1]
    tl = np.where(trend == 1, longb, shortb)
    s = np.zeros(n); cl = cs = 0
    for i in range(n):
        if np.isnan(tl[i]) or np.isnan(rsima[i]): cl = cs = 0; continue
        cl = cl + 1 if tl[i] < rsima[i] else 0
        cs = cs + 1 if tl[i] > rsima[i] else 0
        if cl == 1: s[i] = 1
        elif cs == 1: s[i] = -1
    return s


SIGNALS = {"A_EMA20": sig_ema20, "B_UTBot": sig_utbot, "C_QQE": sig_qqe}


# ---------------------------------------------------------------- engine
def make_B(m15, spread_flat=None, spread_mult=1.0):
    t = m15["time"].astype("int64"); o, h, l, c = (m15[k].astype(float) for k in ("open", "high", "low", "close"))
    sp = (np.full(len(t), spread_flat) if spread_flat is not None else m15["spread"].astype(float) * 0.001) * spread_mult
    return dict(t=t, o=o, h=h, l=l, c=c, sp=sp, n=len(t), a=rt.atr(h, l, c, 14))


def engine(B, sig, ksl, ktp, slip=0.0):
    t, o, h, l, c, sp, a, n = B["t"], B["o"], B["h"], B["l"], B["c"], B["sp"], B["a"], B["n"]
    trades = []; busy = -1
    for j in np.nonzero(sig)[0]:
        d = int(sig[j])
        if j < WARM or j + 1 >= n or np.isnan(a[j]) or a[j] <= 0 or t[j + 1] - t[j] != 900: continue
        te = int(t[j + 1])
        if te <= busy: continue
        risk = ksl * a[j]; spr = sp[j + 1]
        entry = o[j + 1] + (spr + slip if d > 0 else 0.0) - (slip if d < 0 else 0.0)
        sl = entry - risk if d > 0 else entry + risk
        tp = entry + ktp * a[j] if d > 0 else entry - ktp * a[j]
        exit_px = None; reason = "TIME"; last = min(j + 48, n - 1); jj = j + 1
        while jj <= last:
            if d > 0: hs, ht = l[jj] <= sl, h[jj] >= tp
            else: hs, ht = h[jj] + sp[jj] >= sl, l[jj] + sp[jj] <= tp
            if hs: exit_px, reason = sl, "SL"; break
            if ht: exit_px, reason = tp, "TP"; break
            jj += 1
        if exit_px is None:
            jj = last; exit_px = c[jj] + (0.0 if d > 0 else sp[jj])
        exit_px = exit_px - slip if d > 0 else exit_px + slip
        pnl = (exit_px - entry) if d > 0 else (entry - exit_px)
        nights = int(t[jj] // 86400 - te // 86400)
        if d > 0: pnl += rt.SWAP_LONG_PER_NIGHT * nights
        busy = int(t[jj]) + 900
        h_ = (te % 86400) // 3600
        sess = "Asia" if h_ < 7 else "London" if h_ < 12 else "Overlap" if h_ < 16 else "NYlate" if h_ < 21 else "Late"
        trades.append(dict(t=te, x=int(t[jj]), dir=d, pnl=float(pnl), R=float(pnl / risk), reason=reason, sess=sess, event_day=0, bars=int(jj - j)))
    return trades


def periods(tr, lo_hi=None):
    rep = lambda lo, hi, lab: rt.report(tr, lo, hi, lab)
    return dict(DEV=rep(rt.DEV_A, rt.VAL_A, "DEV"), VALIDATE=rep(rt.VAL_A, rt.HOLD_A, "VALIDATE"),
                HOLDOUT=rep(rt.HOLD_A, 2 ** 62, "HOLDOUT"), DEV_VAL=rep(rt.DEV_A, rt.HOLD_A, "DEV+VAL"))


def gate(res, stress):
    d, v, dv = res["DEV"], res["VALIDATE"], res["DEV_VAL"]
    ho = res["HOLDOUT"]
    chk = {}
    chk["dev_pf>1.25&exp>0"] = bool(d.get("n", 0) > 0 and d["pf"] > 1.25 and d["expR"] > 0)
    chk["val_pf>1.25&exp>0"] = bool(v.get("n", 0) > 0 and v["pf"] > 1.25 and v["expR"] > 0)
    chk["n>=100"] = bool(dv.get("n", 0) >= 100)
    chk["maxdd<32R"] = bool(dv.get("n", 0) > 0 and dv["maxdd_R"] < 32)
    chk["no_qtr>40%"] = bool(dv.get("n", 0) > 0 and (dv["top_qtr_share"] is None or dv["top_qtr_share"] <= 40))
    chk["no_trade>15%"] = bool(dv.get("n", 0) > 0 and (dv["top_trade_share"] is None or dv["top_trade_share"] <= 15))
    chk["stress_exp>0"] = bool(stress["DEV_VAL"].get("n", 0) > 0 and stress["DEV_VAL"]["expR"] > 0)
    chk["dsr>=0.95"] = bool(dv.get("n", 0) > 0 and dv["dsr"] == dv["dsr"] and dv["dsr"] >= 0.95)
    chk["holdout_pf>1"] = bool(ho.get("n", 0) > 0 and ho["pf"] > 1.0)
    return chk


def placebo(B, nsig, ksl, ktp, n_valid_lo, n_valid_hi, real_expR):
    rng = np.random.default_rng(SEED); idx_pool = np.arange(max(WARM, n_valid_lo), n_valid_hi - 50)
    out = []
    for _ in range(N_PLACEBO):
        s = np.zeros(B["n"]); pick = rng.choice(idx_pool, size=min(nsig, len(idx_pool)), replace=False)
        s[pick] = rng.choice([-1, 1], size=len(pick))
        tr = engine(B, s, ksl, ktp)
        R = [x["R"] for x in tr if rt.DEV_A <= x["t"] < rt.HOLD_A]
        if R: out.append(float(np.mean(R)))
    out = np.array(out)
    return dict(p95=float(np.percentile(out, 95)), mean=float(out.mean()), p_value=float((out >= real_expR).mean()), reps=len(out))


def main():
    outp = sys.argv[1]
    m15 = np.load("research/data/XAUUSDm_M15.npy")
    B1, B2 = make_B(m15), make_B(m15, spread_mult=2.0)
    o, h, l, c = B1["o"], B1["h"], B1["l"], B1["c"]
    res = dict(trials={}, carried={})
    sigs = {k: f(o, h, l, c) for k, f in SIGNALS.items()}
    for sk, sig in sigs.items():
        res["trials"][sk] = {}
        for pk, (ksl, ktp) in PAIRS.items():
            tr = engine(B1, sig, ksl, ktp); trs = engine(B2, sig, ksl, ktp, slip=0.30)
            res["trials"][sk][pk] = dict(base=periods(tr), stress=periods(trs), n_raw_signals=int((sig != 0).sum()))
        # carried pair = highest DEV expectancy
        best = max(PAIRS, key=lambda pk: res["trials"][sk][pk]["base"]["DEV"].get("expR", -9) if res["trials"][sk][pk]["base"]["DEV"].get("n", 0) else -9)
        r = res["trials"][sk][best]
        ksl, ktp = PAIRS[best]
        in_dv = int(((B1["t"] >= rt.DEV_A) & (B1["t"] < rt.HOLD_A) & (sig != 0)).sum())
        lo = int(np.searchsorted(B1["t"], rt.DEV_A)); hi = int(np.searchsorted(B1["t"], rt.HOLD_A))
        pl = placebo(B1, in_dv, ksl, ktp, lo, hi, r["base"]["DEV_VAL"].get("expR", -9) if r["base"]["DEV_VAL"].get("n", 0) else -9)
        chk = gate(r["base"], r["stress"]); chk["beats_placebo_p95"] = bool(r["base"]["DEV_VAL"].get("n", 0) > 0 and r["base"]["DEV_VAL"]["expR"] > pl["p95"])
        res["carried"][sk] = dict(pair=best, placebo=pl, checks=chk, passed=bool(all(chk.values())))
    # 22-year descriptive robustness on the carried pair (flat $0.30 spread)
    big = np.load("research/data/kaggle_22yr/XAUUSDm_M15.npy")
    BL = make_B(big, spread_flat=0.30)
    res["robustness_22yr"] = {}
    for sk, f in SIGNALS.items():
        pk = res["carried"][sk]["pair"]; ksl, ktp = PAIRS[pk]
        sig = f(BL["o"], BL["h"], BL["l"], BL["c"]); tr = engine(BL, sig, ksl, ktp)
        eras = {}
        for nm, (a_, b_) in {"2004-2010": ((2004, 1, 1), (2011, 1, 1)), "2011-2018": ((2011, 1, 1), (2019, 1, 1)), "2019-2026": ((2019, 1, 1), (2027, 1, 1))}.items():
            T = lambda y: rt.TS(*y)
            eras[nm] = rt.report(tr, T(a_), T(b_), nm)
            eras[nm] = {k: eras[nm].get(k) for k in ("n", "pf", "expR", "net_R", "maxdd_R", "win")}
        res["robustness_22yr"][sk] = dict(pair=pk, eras=eras)
    json.dump(res, open(outp, "w"), indent=1, default=float)
    print({sk: (v["pair"], v["passed"]) for sk, v in res["carried"].items()})


if __name__ == "__main__":
    main()
