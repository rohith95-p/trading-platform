"""Daily abnormal-return fade (pre-registered: research/registry/PREREG_AbnormalFade_2026-10-18.md, trial #643).

Run once: python scripts/research/abnormal_fade_sim.py <out.json>
"""
import sys, os, json, math, csv, datetime as dt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regime_trend_sim as rt

rt.dsr.__defaults__ = (643,)
DAY = 86400


def rolling_std_prior(r, n=60):
    """std of the n returns BEFORE index i (i excluded)."""
    out = np.full(len(r), np.nan)
    for i in range(n, len(r)):
        out[i] = r[i - n:i].std(ddof=1)
    return out


def part_a():
    d = np.load("research/data/kaggle_22yr/XAUUSDm_D1.npy")
    t = d["time"].astype("int64"); c = d["close"].astype(float)
    r = np.full(len(c), np.nan); r[1:] = c[1:] / c[:-1] - 1
    sd = rolling_std_prior(np.nan_to_num(r), 60)
    z = r / sd
    idx = [i for i in range(61, len(c) - 1) if abs(z[i]) > 2 and not np.isnan(z[i]) and not np.isnan(r[i + 1])
           and t[i + 1] - t[i] <= 4 * DAY]
    fade = np.array([-np.sign(r[i]) * r[i + 1] * 100 for i in idx])
    out = dict(first=dt.datetime.fromtimestamp(int(t[0]), dt.timezone.utc).isoformat(), last=dt.datetime.fromtimestamp(int(t[-1]), dt.timezone.utc).isoformat(),
               n_days=len(c), n_events=len(idx))
    if len(fade) >= 3 and fade.std(ddof=1) > 0:
        tt = fade.mean() / (fade.std(ddof=1) / math.sqrt(len(fade)))
        out.update(mean_fade_pct=float(fade.mean()), hit_rate=float((fade > 0).mean() * 100), t=float(tt), p_normal=float(math.erfc(abs(tt) / math.sqrt(2))))
        half = len(idx) // 2
        for nm, sl in (("first_half", slice(0, half)), ("second_half", slice(half, None))):
            f = fade[sl]
            out[nm] = dict(n=len(f), mean_fade_pct=float(f.mean()), hit_rate=float((f > 0).mean() * 100))
        yrs = {}
        for i, f in zip(idx, fade):
            y = dt.datetime.fromtimestamp(int(t[i]), dt.timezone.utc).year; yrs.setdefault(y, []).append(f)
        out["by_year"] = {y: dict(n=len(v), mean_fade_pct=float(np.mean(v))) for y, v in sorted(yrs.items())}
    return out


def part_b(spread_mult=1.0, spread_extra=0.0, slip=0.0):
    m = np.load("research/data/XAUUSDm_M15.npy"); d1 = np.load("research/data/XAUUSDm_D1.npy")
    t = m["time"].astype("int64"); o, h, l, c = (m[k].astype(float) for k in ("open", "high", "low", "close"))
    sp = m["spread"].astype(float) * 0.001 * spread_mult
    n = len(t)
    dtm, dc = d1["time"].astype("int64"), d1["close"].astype(float)
    dh, dl = d1["high"].astype(float), d1["low"].astype(float)
    atrd = rt.atr(dh, dl, dc, 14)
    r = np.full(len(dc), np.nan); r[1:] = dc[1:] / dc[:-1] - 1
    sd = rolling_std_prior(np.nan_to_num(r), 60)
    events = rt.load_events(); ev_t = np.array([e[0] for e in events]); fomc_days = {int(e[0] // DAY) for e in events if e[1] == "FOMC_STATEMENT"}
    ev_days = {int(e[0] // DAY) for e in events}
    pos = {int(x): i for i, x in enumerate(t)}
    trades = []
    for i in range(61, len(dc) - 1):
        if np.isnan(atrd[i]) or np.isnan(sd[i]) or sd[i] == 0 or np.isnan(r[i]): continue
        if dtm[i + 1] - dtm[i] > 4 * DAY: continue
        z = r[i] / sd[i]
        if abs(z) <= 2: continue
        day = int(dtm[i] // DAY)
        if day in fomc_days: continue
        d = -1 if z > 0 else 1                                   # FADE
        te = int(dtm[i + 1]) + 7 * 3600
        j = pos.get(te)
        if j is None: continue
        if ev_t.size and np.any((ev_t >= te) & (ev_t <= te + 4 * 3600)): continue
        risk = float(atrd[i]); spr = sp[j] + spread_extra
        entry = o[j] + (spr + slip if d > 0 else 0.0) - (slip if d < 0 else 0.0)
        sl = entry - risk if d > 0 else entry + risk
        tp = entry + 1.5 * risk if d > 0 else entry - 1.5 * risk
        end_day = int(dtm[i + 1]) + DAY
        exit_px = None; reason = "TIME"; jj = j; last = j
        while jj < n and t[jj] < end_day:
            last = jj
            if d > 0: hs, ht = l[jj] <= sl, h[jj] >= tp
            else: hs, ht = h[jj] + sp[jj] + spread_extra >= sl, l[jj] + sp[jj] + spread_extra <= tp
            if hs: exit_px, reason = sl, "SL"; break
            if ht: exit_px, reason = tp, "TP"; break
            jj += 1
        if exit_px is None:
            jj = last; exit_px = c[jj] + (0.0 if d > 0 else sp[jj] + spread_extra)
        exit_px = exit_px - slip if d > 0 else exit_px + slip
        pnl = (exit_px - entry) if d > 0 else (entry - exit_px)
        nights = int(t[jj] // DAY - te // DAY)
        if d > 0: pnl += rt.SWAP_LONG_PER_NIGHT * nights
        trades.append(dict(t=te, x=int(t[jj]), dir=int(d), pnl=float(pnl), R=float(pnl / risk), reason=reason, sess="London",
                           event_day=int((te // DAY) in ev_days), bars=int(jj - j)))
    return trades


def main():
    outp = sys.argv[1]
    res = dict(part_a=part_a())
    for name, sm, slip in (("base", 1.0, 0.0), ("stress_2x_spread_plus_slip", 2.0, 0.30)):
        tr = part_b(spread_mult=sm, slip=slip)
        rep = lambda lo, hi, lab: rt.report(tr, lo, hi, lab)
        res[name] = dict(DEV=rep(rt.DEV_A, rt.VAL_A, "DEV"), VALIDATE=rep(rt.VAL_A, rt.HOLD_A, "VALIDATE"),
                         HOLDOUT=rep(rt.HOLD_A, 2 ** 62, "HOLDOUT"), DEV_VAL=rep(rt.DEV_A, rt.HOLD_A, "DEV+VAL"))
        if name == "base": res["trades"] = tr
    json.dump(res, open(outp, "w"), default=float, indent=1)
    print("n_trades", len(res["trades"]), "part_a events", res["part_a"].get("n_events"))


if __name__ == "__main__":
    main()
