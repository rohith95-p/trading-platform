"""Regime-conditional trend (pre-registered, research/registry/PREREG_RegimeTrend_2026-10-18.md, commit d570fc4).

Implements the frozen rules exactly. Run once: python scripts/research/regime_trend_sim.py <out.json>
"""
import sys, os, json, math, csv, datetime as dt
from statistics import NormalDist
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(ROOT)
U = dt.timezone.utc
TS = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=U).timestamp())
DEV_A, VAL_A, HOLD_A = TS(2022, 8, 1), TS(2025, 1, 1), TS(2026, 7, 1)
SWAP_LONG_PER_NIGHT = -0.5          # price units per night for 1 oz (0.01 lot): -500 pts * 0.001
EVENTS_CSV = "research/events/usd_high_impact_2022_2026.csv"


def wilder(x, n):
    out = np.full(len(x), np.nan)
    if len(x) < n: return out
    out[n - 1] = np.mean(x[:n])
    for i in range(n, len(x)): out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def atr(h, l, c, n=14):
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc))); tr[0] = h[0] - l[0]
    return wilder(tr, n)


def ema(x, n):
    out = np.full(len(x), np.nan)
    if len(x) < n: return out
    out[n - 1] = np.mean(x[:n]); k = 2 / (n + 1)
    for i in range(n, len(x)): out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def load_events():
    ev = []
    if not os.path.exists(EVENTS_CSV): raise SystemExit("event calendar missing: " + EVENTS_CSV)
    for r in csv.DictReader(open(EVENTS_CSV, encoding="utf-8")):
        if r.get("verified", "").strip().lower() == "no": continue
        if "cancel" in r.get("notes", "").lower() and "not published" in r.get("notes", "").lower(): continue
        t = dt.datetime.fromisoformat(r["scheduled_utc"].replace("Z", "+00:00")).timestamp()
        ev.append((int(t), r["category"]))
    return sorted(ev)


def build(m15, d1, spread_mult=1.0):
    t = m15["time"].astype("int64"); o, h, l, c = (m15[k].astype(float) for k in ("open", "high", "low", "close"))
    sp = m15["spread"].astype(float) * 0.001 * spread_mult
    n = len(t)
    # ----- D1 (native, UTC midnight) : SMA200, ATR14
    dt_, dc = d1["time"].astype("int64"), d1["close"].astype(float)
    dh, dl = d1["high"].astype(float), d1["low"].astype(float)
    sma200 = np.full(len(dc), np.nan)
    for i in range(199, len(dc)): sma200[i] = dc[i - 199:i + 1].mean()
    datr = atr(dh, dl, dc, 14)
    day_end = dt_ + 86400
    def d1_state(ts):               # last D1 bar fully closed at ts
        i = int(np.searchsorted(day_end, ts, side="right")) - 1
        if i < 25 or np.isnan(sma200[i]) or np.isnan(datr[i - 20]): return None
        bias = 1 if dc[i] > sma200[i] else -1
        regime = (datr[i] > datr[i - 5]) and (datr[i] / datr[i - 20] > 1.05)
        return bias, regime
    # ----- H4 from M15 (UTC 4h buckets)
    b4 = t // 14400
    keys, start = np.unique(b4, return_index=True); bounds = list(start) + [n]
    H4 = dict(t=keys * 14400, o=np.array([o[bounds[k]] for k in range(len(keys))]),
              h=np.array([h[bounds[k]:bounds[k + 1]].max() for k in range(len(keys))]),
              l=np.array([l[bounds[k]:bounds[k + 1]].min() for k in range(len(keys))]),
              c=np.array([c[bounds[k + 1] - 1] for k in range(len(keys))]))
    return dict(t=t, o=o, h=h, l=l, c=c, sp=sp, n=n, H4=H4, keys=keys, bounds=bounds, d1_state=d1_state, atr15=atr(h, l, c, 14))


def run(B, events, spread_extra=0.0, entry_slip=0.0):
    t, o, h, l, c, sp, n = B["t"], B["o"], B["h"], B["l"], B["c"], B["sp"], B["n"]
    H4, keys, bounds, a15 = B["H4"], B["keys"], B["bounds"], B["atr15"]
    e20 = ema(H4["c"], 20)
    ev_t = np.array([e[0] for e in events]); ev_days = set(int(e[0] // 86400) for e in events)
    trades = []; busy_until = -1
    for k in range(25, len(keys) - 1):
        # H4 bar k closed at keys[k]*14400+14400 -> arms bucket k+1 (only if contiguous in time)
        T = int(H4["t"][k] + 14400)
        if int(H4["t"][k + 1]) != T: continue
        st = B["d1_state"](T - 1)
        if st is None or np.isnan(e20[k]): continue
        bias, regime = st
        if not regime: continue
        hold = (H4["l"][k] <= e20[k] and H4["c"][k] > e20[k]) if bias > 0 else (H4["h"][k] >= e20[k] and H4["c"][k] < e20[k])
        if not hold: continue
        a, b = bounds[k + 1], bounds[k + 2] if k + 2 < len(bounds) else n
        for j in range(a, b):
            ok = (c[j] > e20[k] and c[j] > o[j]) if bias > 0 else (c[j] < e20[k] and c[j] < o[j])
            if not ok: continue
            # signal at close of bar j -> entry at open of j+1 (consumes the armed window either way)
            if j + 1 >= n or np.isnan(a15[j]) or t[j + 1] - t[j] != 900: break
            te = int(t[j + 1])
            if te <= busy_until: break
            if ev_t.size and np.any((te >= ev_t - 1800) & (te <= ev_t + 3600)): break
            risk = a15[j]
            spr = sp[j + 1] + spread_extra
            entry = o[j + 1] + (spr + entry_slip if bias > 0 else 0.0) - (entry_slip if bias < 0 else 0.0)
            sl = entry - risk if bias > 0 else entry + risk
            tp = entry + 2 * risk if bias > 0 else entry - 2 * risk
            exit_px = None; reason = "TIME"; last = min(j + 48, n - 1); jj = j + 1
            while jj <= last:
                if bias > 0: hs, ht = l[jj] <= sl, h[jj] >= tp
                else: hs, ht = h[jj] + sp[jj] + spread_extra >= sl, l[jj] + sp[jj] + spread_extra <= tp
                if hs: exit_px, reason = sl, "SL"; break
                if ht: exit_px, reason = tp, "TP"; break
                jj += 1
            if exit_px is None:
                jj = last; exit_px = c[jj] + (0.0 if bias > 0 else sp[jj] + spread_extra)
            if bias > 0: exit_px -= entry_slip
            else: exit_px += entry_slip
            pnl = (exit_px - entry) if bias > 0 else (entry - exit_px)
            nights = int(t[jj] // 86400 - te // 86400)
            if bias > 0: pnl += SWAP_LONG_PER_NIGHT * nights
            busy_until = int(t[jj]) + 900
            utc_h = (te % 86400) // 3600
            sess = "Asia" if utc_h < 7 else "London" if utc_h < 12 else "Overlap" if utc_h < 16 else "NYlate" if utc_h < 21 else "Late"
            trades.append(dict(t=te, x=int(t[jj]), dir=int(bias), pnl=float(pnl), R=float(pnl / risk), reason=reason, sess=sess,
                               event_day=int((te // 86400) in ev_days), bars=int(jj - j)))
            break
    return trades


def pf(v):
    v = np.asarray(v); w = v[v > 0].sum(); lo = -v[v < 0].sum()
    return float(w / lo) if lo > 0 else float("inf")


def dsr(R, N=640):
    R = np.asarray(R, float); T = len(R)
    if T < 10 or R.std() == 0: return float("nan")
    sr = R.mean() / R.std(ddof=1)
    skew = float(((R - R.mean()) ** 3).mean() / R.std() ** 3); kurt = float(((R - R.mean()) ** 4).mean() / R.std() ** 4)
    g = 0.5772156649; nd = NormalDist()
    sr0 = math.sqrt(1.0 / T) * ((1 - g) * nd.inv_cdf(1 - 1.0 / N) + g * nd.inv_cdf(1 - 1.0 / (N * math.e)))
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr * sr))
    return float(nd.cdf((sr - sr0) * math.sqrt(T - 1) / denom))


def report(tr, lo, hi, label):
    s = [x for x in tr if lo <= x["t"] < hi]; out = dict(label=label, n=len(s))
    if not s: return out
    R = np.array([x["R"] for x in s]); P = np.array([x["pnl"] for x in s])
    eq = np.cumsum(R); dd = float((np.maximum.accumulate(np.concatenate([[0], eq])) - np.concatenate([[0], eq])).max())
    ls = cur = 0
    for r in R:
        cur = cur + 1 if r < 0 else 0; ls = max(ls, cur)
    mon = {}; qtr = {}
    for x in s:
        d = dt.datetime.fromtimestamp(x["t"], U); mon[d.strftime("%Y-%m")] = mon.get(d.strftime("%Y-%m"), 0) + x["R"]
        qk = f"{d.year}Q{(d.month - 1) // 3 + 1}"; qtr[qk] = qtr.get(qk, 0) + x["R"]
    net = R.sum()
    out.update(wins=int((R > 0).sum()), losses=int((R < 0).sum()), win=float((R > 0).mean() * 100), pf=pf(R), pf_dollar=pf(P),
               expR=float(R.mean()), net_R=float(net), net_usd_001=float(P.sum()), maxdd_R=dd, maxdd_pct_025=dd * 0.25, losing_streak=ls,
               avg_win=float(R[R > 0].mean()) if (R > 0).any() else 0.0, avg_loss=float(R[R < 0].mean()) if (R < 0).any() else 0.0,
               long_share=float(np.mean([x["dir"] > 0 for x in s]) * 100), avg_bars=float(np.mean([x["bars"] for x in s])),
               top_month_share=float(max(mon.values()) / net * 100) if net > 0 else None, top_qtr_share=float(max(qtr.values()) / net * 100) if net > 0 else None,
               top_trade_share=float(R.max() / net * 100) if net > 0 else None,
               by_year={y: dict(n=len([x for x in s if dt.datetime.fromtimestamp(x["t"], U).year == y]),
                                pf=pf([x["R"] for x in s if dt.datetime.fromtimestamp(x["t"], U).year == y] or [0])) for y in sorted({dt.datetime.fromtimestamp(x["t"], U).year for x in s})},
               by_session={k: dict(n=len([x for x in s if x["sess"] == k]), pf=pf([x["R"] for x in s if x["sess"] == k] or [0])) for k in ("Asia", "London", "Overlap", "NYlate", "Late")},
               event_day=dict(n=int(sum(x["event_day"] for x in s)), pf=pf([x["R"] for x in s if x["event_day"]] or [0])),
               normal_day=dict(n=int(sum(1 - x["event_day"] for x in s)), pf=pf([x["R"] for x in s if not x["event_day"]] or [0])),
               dsr=dsr(R), exits={k: len([x for x in s if x["reason"] == k]) for k in ("SL", "TP", "TIME")})
    return out


def main():
    outp = sys.argv[1]
    m15 = np.load("research/data/XAUUSDm_M15.npy"); d1 = np.load("research/data/XAUUSDm_D1.npy")
    events = load_events(); res = {}
    for name, sm, extra, slip in (("base", 1.0, 0.0, 0.0), ("stress_2x_spread_plus_slip", 2.0, 0.0, 0.30)):
        B = build(m15, d1, spread_mult=sm); tr = run(B, events, spread_extra=extra, entry_slip=slip)
        res[name] = dict(DEV=report(tr, DEV_A, VAL_A, "DEV"), VALIDATE=report(tr, VAL_A, HOLD_A, "VALIDATE"),
                         HOLDOUT=report(tr, HOLD_A, 2 ** 62, "HOLDOUT"), DEV_VAL=report(tr, DEV_A, HOLD_A, "DEV+VAL"))
        if name == "base": res["trades"] = tr
    json.dump(res, open(outp, "w"), default=float)
    print("n_events", len(events), "n_trades", len(res["trades"]))


if __name__ == "__main__":
    main()
