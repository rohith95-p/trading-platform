"""Asian-range / London continuation (pre-registered: research/registry/PREREG_AsianRangeLondon_2026-10-18.md, trial #641).

Implements the frozen rules exactly. Run once: python scripts/research/asian_london_sim.py <out.json>
"""
import sys, os, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regime_trend_sim as rt   # frozen helpers from trial #640 (atr, pf, dsr, report, load_events, windows)

rt.dsr.__defaults__ = (641,)          # trial count N = 641 for this hypothesis
SWAP_LONG_PER_NIGHT = rt.SWAP_LONG_PER_NIGHT
DAY = 86400


def build(m15, d1, spread_mult=1.0):
    t = m15["time"].astype("int64"); o, h, l, c = (m15[k].astype(float) for k in ("open", "high", "low", "close"))
    sp = m15["spread"].astype(float) * 0.001 * spread_mult
    n = len(t)
    dt_, dc = d1["time"].astype("int64"), d1["close"].astype(float)
    sma200 = np.full(len(dc), np.nan)
    for i in range(199, len(dc)): sma200[i] = dc[i - 199:i + 1].mean()
    day_end = dt_ + DAY

    def bias_at(ts):                      # last fully closed D1 bar
        i = int(np.searchsorted(day_end, ts, side="right")) - 1
        if i < 200 or np.isnan(sma200[i]): return None
        return 1 if dc[i] > sma200[i] else -1

    # H1 from M15: UTC hour buckets, complete (4 contiguous bars) only
    hb = t // 3600
    keys, start, cnt = np.unique(hb, return_index=True, return_counts=True)
    ok = np.array([cnt[k] == 4 and t[start[k] + 3] - t[start[k]] == 2700 for k in range(len(keys))])
    keys, start = keys[ok], start[ok]
    H1 = dict(t=keys * 3600, o=o[start], h=np.array([h[s:s + 4].max() for s in start]),
              l=np.array([l[s:s + 4].min() for s in start]), c=c[start + 3])
    # ATR on contiguous runs only is overkill; gaps (weekends) are bridged exactly like #640's ATR on M15.
    a1 = rt.atr(H1["h"], H1["l"], H1["c"], 14)
    return dict(t=t, o=o, h=h, l=l, c=c, sp=sp, n=n, bias_at=bias_at, H1=H1, a1=a1)


def run(B, events, spread_extra=0.0, entry_slip=0.0):
    t, o, h, l, c, sp, n = B["t"], B["o"], B["h"], B["l"], B["c"], B["sp"], B["n"]
    H1t, a1 = B["H1"]["t"], B["a1"]
    ev_t = np.array([e[0] for e in events]); ev_days = set(int(e[0] // DAY) for e in events)
    days = t // DAY
    udays, dstart = np.unique(days, return_index=True); dbounds = list(dstart) + [n]
    widths = []                                     # Asian widths of previous valid days
    trades = []
    for di, day in enumerate(udays):
        a, b = dbounds[di], dbounds[di + 1]
        base = int(day) * DAY
        if dt_weekday(base) >= 5: continue
        idx = np.arange(a, b); tt = t[idx]
        asia = idx[(tt >= base) & (tt < base + 7 * 3600)]
        if len(asia) < 24:                          # invalid Asian session: no trade, not added to history
            continue
        ah, al = h[asia].max(), l[asia].min(); width = ah - al
        hist = widths[-60:]; widths.append(width)
        if len(hist) < 30: continue
        lo_p, hi_p = np.percentile(hist, 25), np.percentile(hist, 75)
        if not (lo_p <= width <= hi_p): continue
        win = idx[(tt >= base + 7 * 3600) & (tt < base + 10 * 3600)]
        sig = None
        for j in win:                               # first close outside the range consumes the day
            if c[j] > ah: sig = (j, 1); break
            if c[j] < al: sig = (j, -1); break
        if sig is None: continue
        j, d = sig
        if j + 1 >= n or t[j + 1] - t[j] != 900: continue
        bias = B["bias_at"](int(t[j]) + 900 - 1)
        if bias is None or bias != d: continue
        # H1 volatility: last closed H1 at the signal bar close vs 5 H1 bars earlier
        k = int(np.searchsorted(H1t + 3600, int(t[j]) + 900, side="right")) - 1
        if k < 20 or np.isnan(a1[k]) or np.isnan(a1[k - 5]) or not (a1[k] > a1[k - 5]): continue
        te = int(t[j + 1])
        if ev_t.size and np.any((te >= ev_t - 1800) & (te <= ev_t + 3600)): continue
        risk = float(a1[k])
        spr = sp[j + 1] + spread_extra
        entry = o[j + 1] + (spr + entry_slip if d > 0 else 0.0) - (entry_slip if d < 0 else 0.0)
        sl = entry - risk if d > 0 else entry + risk
        tp = entry + 2 * risk if d > 0 else entry - 2 * risk
        cutoff = base + 16 * 3600
        exit_px = None; reason = "TIME"; jj = j + 1; last = j + 1
        while jj < n and t[jj] < cutoff:
            last = jj
            if d > 0: hs, ht = l[jj] <= sl, h[jj] >= tp
            else: hs, ht = h[jj] + sp[jj] + spread_extra >= sl, l[jj] + sp[jj] + spread_extra <= tp
            if hs: exit_px, reason = sl, "SL"; break
            if ht: exit_px, reason = tp, "TP"; break
            jj += 1
        if exit_px is None:
            jj = last; exit_px = c[jj] + (0.0 if d > 0 else sp[jj] + spread_extra)
        exit_px = exit_px - entry_slip if d > 0 else exit_px + entry_slip
        pnl = (exit_px - entry) if d > 0 else (entry - exit_px)
        nights = int(t[jj] // DAY - te // DAY)
        if d > 0: pnl += SWAP_LONG_PER_NIGHT * nights
        utc_h = (te % DAY) // 3600
        sess = "Asia" if utc_h < 7 else "London" if utc_h < 12 else "Overlap" if utc_h < 16 else "NYlate" if utc_h < 21 else "Late"
        trades.append(dict(t=te, x=int(t[jj]), dir=int(d), pnl=float(pnl), R=float(pnl / risk), reason=reason, sess=sess,
                           event_day=int((te // DAY) in ev_days), bars=int(jj - j)))
    return trades


def dt_weekday(ts):
    import datetime as dtm
    return dtm.datetime.fromtimestamp(ts, dtm.timezone.utc).weekday()


def main():
    outp = sys.argv[1]
    m15 = np.load("research/data/XAUUSDm_M15.npy"); d1 = np.load("research/data/XAUUSDm_D1.npy")
    events = rt.load_events(); res = {}
    for name, sm, extra, slip in (("base", 1.0, 0.0, 0.0), ("stress_2x_spread_plus_slip", 2.0, 0.0, 0.30)):
        B = build(m15, d1, spread_mult=sm); tr = run(B, events, spread_extra=extra, entry_slip=slip)
        rep = lambda lo, hi, lab: rt.report(tr, lo, hi, lab)
        res[name] = dict(DEV=rep(rt.DEV_A, rt.VAL_A, "DEV"), VALIDATE=rep(rt.VAL_A, rt.HOLD_A, "VALIDATE"),
                         HOLDOUT=rep(rt.HOLD_A, 2 ** 62, "HOLDOUT"), DEV_VAL=rep(rt.DEV_A, rt.HOLD_A, "DEV+VAL"))
        if name == "base": res["trades"] = tr
    json.dump(res, open(outp, "w"), default=float)
    print("n_trades", len(res["trades"]))


if __name__ == "__main__":
    main()
