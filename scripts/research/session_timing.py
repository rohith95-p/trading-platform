"""Overlap-window and time-of-day analysis (pre-registered: research/registry/PREREG_SessionTiming_2026-10-19.md).

Run once: python scripts/research/session_timing.py <out.json>
"""
import sys, os, json, math, dataclasses, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(ROOT); sys.path.insert(0, ROOT)
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.strategies.portfolio_v5_core import PORTFOLIO

U = dt.timezone.utc
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
TS = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=U).timestamp())
DEV_A, VAL_A, VAL_B = TS(2022, 8, 1), TS(2025, 1, 1), TS(2026, 7, 1)
M1_A, M1_B = TS(2026, 7, 6), TS(2026, 10, 13)


def ist_hm(t):
    d = dt.datetime.fromtimestamp(t, U).astimezone(IST); return d.hour + d.minute / 60.0


def pf(v):
    v = np.asarray(v, float); w = v[v > 0].sum(); l = -v[v < 0].sum()
    return float(w / l) if l > 0 else float("inf") if w > 0 else 0.0


def st(trs):
    if not trs: return dict(n=0)
    pl = np.array([x.net_pl for x in trs]); r = np.array([x.r_multiple for x in trs])
    return dict(n=len(trs), win=float((pl > 0).mean() * 100), pf=pf(pl), expR=float(r.mean()), net=float(pl.sum()),
                t=float(r.mean() / (r.std(ddof=1) / math.sqrt(len(r)))) if len(r) > 2 and r.std(ddof=1) > 0 else None)


def maxdd(trs):
    pl = np.array([x.net_pl for x in sorted(trs, key=lambda x: x.exit_time)])
    if not len(pl): return 0.0
    eq = np.cumsum(pl); return float((np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max())


def bh(ps):
    ps = np.array(ps, float); o = np.argsort(ps); m = len(ps); out = np.full(m, np.nan); prev = 1.0
    for rank, i in reversed(list(enumerate(o, 1))):
        prev = min(prev, ps[i] * m / rank); out[i] = prev
    return out


def run(bars, skip_overlap, a, b):
    cfg = EngineConfig(sizing_mode="fixed", fixed_lots=0.01, starting_balance=10000.0, skip_overlap_session=skip_overlap)
    return BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg).run([c() for c in PORTFOLIO], a, b).trades


def split(trs, lo, hi): return [x for x in trs if lo <= x.entry_time < hi]
def in_ov(x): return 15.5 <= ist_hm(x.entry_time) < 17.5


def main():
    outp = sys.argv[1]
    bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1")); coarse = dataclasses.replace(bars, m1=None)
    out = {}
    runs = {}
    for label, b, a, e in (("coarse", coarse, DEV_A, VAL_B), ("m1", bars, M1_A, M1_B)):
        for skip in (True, False):
            runs[(label, skip)] = run(b, skip, a, e)
            print(label, "skip_overlap" if skip else "allow_overlap", len(runs[(label, skip)]), flush=True)
    # ---- Q1
    q1 = {}
    for label, per in (("coarse", {"DEV": (DEV_A, VAL_A), "VALIDATE": (VAL_A, VAL_B), "DEV+VAL": (DEV_A, VAL_B)}), ("m1", {"M1": (M1_A, M1_B)})):
        for pn, (lo, hi) in per.items():
            r0, r1 = split(runs[(label, True)], lo, hi), split(runs[(label, False)], lo, hi)
            q1[f"{label}|{pn}"] = dict(whole_R0=dict(**st(r0), maxdd=maxdd(r0)), whole_R1=dict(**st(r1), maxdd=maxdd(r1)),
                                      overlap_window_trades=st([x for x in r1 if in_ov(x)]), outside_overlap_trades_R1=st([x for x in r1 if not in_ov(x)]))
    o = q1
    d, v, dv, m1 = (o["coarse|DEV"]["overlap_window_trades"], o["coarse|VALIDATE"]["overlap_window_trades"],
                    o["coarse|DEV+VAL"]["overlap_window_trades"], o["m1|M1"]["overlap_window_trades"])
    ok = bool(d.get("n", 0) and d["pf"] > 1 and d["expR"] > 0 and v.get("n", 0) and v["pf"] > 1 and v["expR"] > 0 and dv.get("n", 0) >= 100
              and (m1.get("n", 0) < 30 or m1["pf"] >= 1.0))
    out["q1"] = dict(detail=q1, allow_overlap_verdict=ok)
    # ---- Q2 (hours from R1)
    r1c, r1m = runs[("coarse", False)], runs[("m1", False)]
    hours = {}
    for h in range(6, 22):
        sel = lambda trs: [x for x in trs if int(ist_hm(x.entry_time)) == h]
        hours[h] = dict(DEV=st(split(sel(r1c), DEV_A, VAL_A)), VALIDATE=st(split(sel(r1c), VAL_A, VAL_B)), M1=st(sel(r1m)))
    cand = [h for h in hours if hours[h]["DEV"].get("n", 0) >= 40]
    top = sorted(cand, key=lambda h: -hours[h]["DEV"]["expR"])[:3]
    vp = []
    for h in hours:
        s = hours[h]["VALIDATE"]
        t = s.get("t"); p = float(math.erfc(abs(t) / math.sqrt(2))) if t is not None else 1.0
        vp.append(p if (t is None or t > 0) else 1.0)       # one-sided "positive" test
    bhp = bh(vp)
    for i, h in enumerate(hours): hours[h]["VALIDATE_p"] = vp[i]; hours[h]["VALIDATE_bh_p"] = float(bhp[i])
    sel_ok = {h: bool(hours[h]["VALIDATE"].get("n", 0) >= 40 and hours[h]["VALIDATE"]["pf"] > 1 and hours[h]["VALIDATE"]["expR"] > 0) for h in top}
    topM1 = st([x for x in r1m if int(ist_hm(x.entry_time)) in top])
    stable = [h for h in hours if hours[h]["VALIDATE_bh_p"] < 0.05 and hours[h]["DEV"].get("expR", -1) > 0 and hours[h]["VALIDATE"].get("expR", -1) > 0]
    by_leg = {}
    for lg in sorted({x.strategy for x in r1c}):
        by_leg[lg] = dict(DEV=st(split([x for x in r1c if x.strategy == lg], DEV_A, VAL_A)), VALIDATE=st(split([x for x in r1c if x.strategy == lg], VAL_A, VAL_B)))
    out["q2"] = dict(hours=hours, dev_top3=top, dev_top3_confirmed_in_validate=sel_ok, top3_m1=topM1, stable_hours_bh=stable, by_leg=by_leg)
    json.dump(out, open(outp, "w"), indent=1, default=float)
    print("Q1 allow overlap:", ok, "| top3 DEV hours:", top, "confirmed:", sel_ok, "| stable:", stable)


if __name__ == "__main__":
    main()
