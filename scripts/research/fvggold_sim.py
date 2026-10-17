#!/usr/bin/env python
"""Standalone research simulator of the FvgGold v2.01 MQL5 EA (github.com/foeed/FvgGold-EA).

Research only. Does not import or touch the main engine. XAUUSDm, UTC bar-open times.
Run with: venv\\Scripts\\python.exe -I scripts/research/fvggold_sim.py [--report]

Rules were transcribed from the EA source (read via WebFetch, never executed):
  * FVG: 3 closed M15 candles, older=shift i, middle=i-1, newer=i-2 (i>=3 -> age 2..20 bars).
    bull: low[newer] > high[older]  (top=low[newer], bottom=high[older])
    bear: high[newer] < low[older]  (top=low[older], bottom=high[newer])
    size >= MinGapSize * SYMBOL_POINT.
  * Score = min(gap/ATR,1)*30 + body/range(middle)*30 + 20*(type==H1 bias) + (1-age/20)*10
            + 10*(bull: bid<H1 EMA50 | bear: bid>EMA50) + 20 if OB confluence. Need >= MinScoreFVG.
  * Bias = sign(H1 EMA50 - EMA200) using the FORMING H1 bar (price = current bid).
  * Killzone (GMT): 07-10 or 12-21 (the "NY" window re-uses KZ_OverlapStart -> 12..21).
  * Buy limit @ bottom+buf/2, SL bottom-buf; sell limit @ top-buf/2, SL top+buf; TP = 1.5R.
    Order is GTC (never expires, never cancelled); MaxTrades=1 counts pending orders.
  * Zone pruned when bid<mid (bull) / ask>mid (bear) or wall-clock age >= 20 bars.
  * Break-even: bid-open >= 0.5*ATR -> SL = open+2pt (mirrored for shorts).
  * Daily loss limit: closed-deal P/L of the UTC day <= -5 blocks NEW placements only.

Simulation approximations (all conservative or neutral, documented in the audit doc):
  * The EA runs on every tick; this sim evaluates the decision logic once, at each M15 bar open
    (bid = bar open, ask = open + spread). Intra-bar re-scoring/placement is not modelled.
  * ATR(14) shift-0 is approximated by ATR of the last closed bar.
  * Fills/stop walk uses M1 sub-bars where M1 data exist (2026-07-02 on), else the M15 bar (stop-first).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "research" / "data"


def ts(s: str) -> int:
    return int(dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())


@dataclass(frozen=True)
class P:
    point: float = 0.001          # SYMBOL_POINT used for MinGapSize/OB sizes/BE offset (our broker: 0.001)
    min_gap_pts: float = 25.0
    max_age: int = 20
    min_age: int = 2
    buf: float = 3.0
    min_score: float = 50.0
    w_gap: float = 30.0
    w_disp: float = 30.0
    w_htf: float = 20.0
    w_fresh: float = 10.0
    w_pd: float = 10.0
    use_ob: bool = True
    ob_imp_atr: float = 1.5
    ob_lookback: int = 50
    ob_min_pts: float = 10.0
    ob_bonus: float = 20.0
    ob_maxdist_pts: float = 200.0
    ema_fast: int = 50
    ema_slow: int = 200
    lot: float = 0.01
    max_trades: int = 1
    daily_loss: float = 5.0
    rr: float = 1.5
    use_kz: bool = True
    kz_prefer_overlap: bool = False
    be_on: bool = True
    be_atr: float = 0.5
    be_off_pts: float = 2.0
    stops_level_pts: float = 0.0
    use_bias: bool = True         # ablation (b): False -> no H1 trend gating
    market_entry: bool = False    # ablation (e)
    spread_mult: float = 1.0
    slip_per_fill: float = 0.0    # USD (1 oz) adverse on each of entry and exit
    swap_long_night: float = 0.5  # USD per night per 0.01 lot, long only
    fillbar: str = "on"           # fill-bar TP/BE: on = allowed (user spec), off = never, path = only if bar path (O-L-H-C bull / O-H-L-C bear) allows
    use_m1: bool = True
    pending: str = "gtc"          # gtc = as coded (never cancelled); age = cancel when FVG ages out; zone = cancel when zone dies


class Ctx:
    def __init__(self):
        a = np.load(DATA / "XAUUSDm_M15.npy")
        self.t = a["time"].astype(np.int64)
        self.o = a["open"]; self.h = a["high"]; self.l = a["low"]; self.c = a["close"]
        self.spr = a["spread"].astype(float) * 0.001
        n = len(self.t)
        # ATR14 (SMA of TR), value at bar j uses bars <= j
        pc = np.r_[self.c[0], self.c[:-1]]
        tr = np.maximum(self.h - self.l, np.maximum(np.abs(self.h - pc), np.abs(self.l - pc)))
        cs = np.cumsum(tr)
        atr = np.full(n, np.nan)
        atr[14:] = (cs[14:] - cs[:-14]) / 14.0
        atr[13] = cs[13] / 14.0
        self.atr = atr
        # H1 EMAs on closed bars
        h1 = np.load(DATA / "XAUUSDm_H1.npy")
        self.h1t = h1["time"].astype(np.int64)
        self.h1c = h1["close"]
        self.ema = {}
        for per in (50, 200):
            al = 2.0 / (per + 1)
            e = np.empty(len(self.h1c)); e[0] = self.h1c[0]
            for i in range(1, len(e)):
                e[i] = al * self.h1c[i] + (1 - al) * e[i - 1]
            self.ema[per] = e
        hf = (self.t // 3600) * 3600
        self.jc = np.searchsorted(self.h1t, hf, side="left") - 1  # last closed H1 bar before the forming one
        # M1
        m1 = np.load(DATA / "XAUUSDm_M1.npy")
        self.m1t = m1["time"].astype(np.int64)
        self.m1o = m1["open"]; self.m1h = m1["high"]; self.m1l = m1["low"]; self.m1c = m1["close"]
        self.m1spr = m1["spread"].astype(float) * 0.001
        self.m1_lo = np.searchsorted(self.m1t, self.t, side="left")
        self.m1_hi = np.searchsorted(self.m1t, self.t + 900, side="left")
        self.body = np.abs(self.c - self.o)
        self.rng = self.h - self.l
        self.n = n

    def idx(self, date: str) -> int:
        return int(np.searchsorted(self.t, ts(date), side="left"))


def swap_nights(fill_t: int, exit_t: int) -> float:
    d0, d1 = fill_t // 86400, exit_t // 86400
    w = 0.0
    for d in range(d0, d1):
        wd = (d + 3) % 7  # Mon=0
        w += 3.0 if wd == 2 else (0.0 if wd >= 5 else 1.0)
    return w


def simulate(cx: Ctx, p: P, start: str, end: str) -> list[dict]:
    t, o, h, l, c, spr_a = cx.t, cx.o, cx.h, cx.l, cx.c, cx.spr * p.spread_mult
    pt = p.point
    k0 = max(cx.idx(start), 260)
    k1 = cx.idx(end)
    # --- gap patterns (middle bar m; older m-1; newer m+1) ---
    n = cx.n
    bull = np.zeros(n, bool); bear = np.zeros(n, bool)
    top = np.zeros(n); bot = np.zeros(n)
    bull[1:-1] = l[2:] > h[:-2]
    bear[1:-1] = (h[2:] < l[:-2]) & ~bull[1:-1]
    top[1:-1] = np.where(bull[1:-1], l[2:], l[:-2])
    bot[1:-1] = np.where(bull[1:-1], h[:-2], h[2:])
    size = np.where(bull | bear, top - bot, 0.0)
    isgap = (bull | bear) & (size / pt >= p.min_gap_pts)
    gtype = np.where(bull, 1, -1)
    disp = np.where(cx.rng > 0, cx.body / np.where(cx.rng > 0, cx.rng, 1), 0.0)
    # OB patterns (impulse j, OB candle j-1)
    bullc = c > o; bearc = c < o
    obtype = np.zeros(n, int)
    obtype[1:] = np.where(bullc[1:] & bearc[:-1], 1, np.where(bearc[1:] & bullc[:-1], -1, 0))
    obtop = np.zeros(n); obbot = np.zeros(n)
    obtop[1:] = np.maximum(o[:-1], c[:-1]); obbot[1:] = np.minimum(o[:-1], c[:-1])
    obok = (obtype != 0)
    obok[1:] &= ((obtop[1:] - obbot[1:]) / pt >= p.ob_min_pts)
    obt_prior = np.zeros(n, np.int64); obt_prior[1:] = t[:-1]
    gap_idx = np.nonzero(isgap)[0]

    def has_ob(zt, ztop, zbot, k, atr, bid, ask):
        lo = max(k - 54, 1); hi = k - 1  # j in [k-54, k-2]
        js = np.arange(lo, hi)
        if len(js) == 0:
            return False
        m = obok[js] & (obtype[js] == zt) & (cx.body[js] >= p.ob_imp_atr * atr)
        m &= (t[k] - obt_prior[js]) < p.ob_lookback * 900
        if zt == 1:
            m &= bid >= obbot[js]
        else:
            m &= ask <= obtop[js]
        if not m.any():
            return False
        jj = js[m]
        ot, ob = obtop[jj], obbot[jj]
        ov = (ztop >= ob) & (zbot <= ot)
        if zt == 1:
            dist = zbot - ot
        else:
            dist = ob - ztop
        px = (dist >= 0) & (dist <= p.ob_maxdist_pts * pt)
        return bool((ov | px).any())

    zones: dict[int, dict] = {}
    pend = None
    pos = None
    trades: list[dict] = []
    daypl: dict[int, float] = {}
    trig_off = p.be_off_pts * pt
    a50, a200 = 2.0 / (p.ema_fast + 1), 2.0 / (p.ema_slow + 1)
    e50, e200 = cx.ema[50], cx.ema[200]
    if (p.ema_fast, p.ema_slow) != (50, 200):
        raise SystemExit("EMA periods other than 50/200 not precomputed")

    def close_pos(exit_t, exit_px, reason):
        nonlocal pos
        sd = pos["side"]
        gross = (exit_px - pos["entry"]) if sd == 1 else (pos["entry"] - exit_px)
        slip = 2 * p.slip_per_fill
        swp = -p.swap_long_night * swap_nights(pos["fill_t"], exit_t) if sd == 1 else 0.0
        pnl = (gross - slip) * (p.lot / 0.01) + swp * (p.lot / 0.01)
        tr = dict(pos); tr.update(exit_t=int(exit_t), exit=float(exit_px), reason=reason,
                                   pnl=float(pnl), swap=float(swp), gross=float(gross))
        trades.append(tr)
        d = int(exit_t // 86400)
        daypl[d] = daypl.get(d, 0.0) + pnl
        pos = None

    def walk_sub(so, sh, sl_, sc, sp, st, atr_trig):
        """Process one sub-bar. Returns nothing; mutates pend/pos."""
        nonlocal pend, pos
        just_filled = False
        if pend is not None and pos is None:
            if pend["side"] == 1:
                if sl_ + sp <= pend["entry"]:
                    fp = min(pend["entry"], so + sp)
                    just_filled = True
            else:
                if sh >= pend["entry"]:
                    fp = max(pend["entry"], so)
                    just_filled = True
            if just_filled:
                pos = dict(pend); pos["entry"] = fp; pos["fill_t"] = int(st); pos["be"] = False
                pos["limit"] = pend["entry"]
                pend = None
        if pos is None:
            return
        sd = pos["side"]
        if not just_filled or p.fillbar == "on":
            allow_tp = True
        elif p.fillbar == "off":
            allow_tp = False
        elif sd == 1:
            allow_tp = sc > so or sc >= pos["tp"]
        else:
            allow_tp = sc < so or sc + sp <= pos["tp"]
        if sd == 1:
            if sl_ <= pos["sl"]:
                close_pos(st, min(pos["sl"], so), "BE" if pos["be"] else "SL"); return
            if sh >= pos["tp"] and allow_tp:
                close_pos(st, pos["tp"], "TP"); return
            if p.be_on and not pos["be"] and allow_tp and (sh - pos["entry"]) >= atr_trig and pos["sl"] < pos["entry"]:
                pos["sl"] = pos["entry"] + trig_off; pos["be"] = True
        else:
            if sh + sp >= pos["sl"]:
                close_pos(st, max(pos["sl"], so + sp), "BE" if pos["be"] else "SL"); return
            if sl_ + sp <= pos["tp"] and allow_tp:
                close_pos(st, pos["tp"], "TP"); return
            if p.be_on and not pos["be"] and allow_tp and (pos["entry"] - (sl_ + sp)) >= atr_trig and pos["sl"] > pos["entry"]:
                pos["sl"] = pos["entry"] - trig_off; pos["be"] = True

    for k in range(k0, k1):
        T = int(t[k]); day = T // 86400
        atr = cx.atr[k - 1]
        sp = spr_a[k]
        bid = o[k]; ask = o[k] + sp
        # ---- forming-H1 EMAs & bias ----
        jc = cx.jc[k]
        f50 = a50 * bid + (1 - a50) * e50[jc]
        f200 = a200 * bid + (1 - a200) * e200[jc]
        bias = 1 if f50 > f200 else (-1 if f50 < f200 else 0)
        # ---- prune zones (time + mitigation at current price) ----
        for m in list(zones):
            z = zones[m]
            if T - t[m] >= p.max_age * 900:
                del zones[m]
            elif z["type"] == 1 and bid < z["mid"]:
                del zones[m]
            elif z["type"] == -1 and ask > z["mid"]:
                del zones[m]
        if pend is not None and p.pending != "gtc":
            if p.pending == "age" and T - t[pend["zone_m"]] >= p.max_age * 900:
                pend = None
            elif p.pending == "zone" and pend["zone_m"] not in zones:
                pend = None
        dlimit = p.daily_loss > 0 and daypl.get(day, 0.0) <= -p.daily_loss
        if not dlimit:
            # ---- detect / score ----
            lo = np.searchsorted(gap_idx, k - p.max_age)
            hi = np.searchsorted(gap_idx, k - p.min_age, side="right")
            for m in gap_idx[lo:hi][::-1]:  # newer gaps first (i ascending)
                m = int(m)
                if m in zones:
                    continue
                if T - t[m] >= p.max_age * 900:
                    continue
                a = k - m
                zt = int(gtype[m]); ztop = top[m]; zbot = bot[m]; mid = 0.5 * (ztop + zbot)
                if zt == 1 and bid < mid:
                    continue
                if zt == -1 and ask > mid:
                    continue
                if not np.isfinite(atr) or atr <= 0:
                    continue
                sc = min((ztop - zbot) / atr, 1.0) * p.w_gap + disp[m] * p.w_disp
                if zt == bias:
                    sc += p.w_htf
                sc += (1 - a / p.max_age) * p.w_fresh
                if (zt == 1 and bid < f50) or (zt == -1 and bid > f50):
                    sc += p.w_pd
                sc = round(sc, 1)
                if p.use_ob and sc < p.min_score and sc + p.ob_bonus >= p.min_score:
                    if has_ob(zt, ztop, zbot, k, atr, bid, ask):
                        sc = round(sc + p.ob_bonus, 1)
                elif p.use_ob and sc >= p.min_score:
                    if has_ob(zt, ztop, zbot, k, atr, bid, ask):
                        sc = round(sc + p.ob_bonus, 1)
                if sc < p.min_score:
                    continue
                zones[m] = dict(type=zt, top=ztop, bot=zbot, mid=mid, score=sc, placed=False, m=m)
            # ---- placement ----
            gate_bias = (bias != 0) if p.use_bias else True
            if p.use_kz:
                hr = (T // 3600) % 24
                kz = (hr == 7 or hr == 8 or hr == 9 or 12 <= hr < 21) if not p.kz_prefer_overlap else (12 <= hr < 16)
            else:
                kz = True
            slot_free = pos is None and pend is None
            if gate_bias and kz and slot_free:
                for m, z in zones.items():
                    if z["placed"] or (p.use_bias and z["type"] != bias) or z["score"] < p.min_score:
                        continue
                    zt = z["type"]
                    if zt == 1:
                        entry = z["bot"] + p.buf * 0.5; sl = z["bot"] - p.buf
                    else:
                        entry = z["top"] - p.buf * 0.5; sl = z["top"] + p.buf
                    mind = p.stops_level_pts * pt + sp
                    if p.market_entry:
                        entry = ask if zt == 1 else bid
                    else:
                        if zt == 1 and (ask - entry) < mind:
                            continue
                        if zt == -1 and (entry - bid) < mind:
                            continue
                    if (zt == 1 and sl >= entry) or (zt == -1 and sl <= entry):
                        continue
                    dist = abs(entry - sl)
                    tp = entry + zt * dist * p.rr
                    z["placed"] = True
                    od = dict(side=zt, entry=float(entry), sl=float(sl), tp=float(tp), score=z["score"],
                              place_t=T, place_k=k, hour=int((T // 3600) % 24), risk=float(dist), zone_m=m,
                              gap=float(z["top"] - z["bot"]), age=int(k - m))
                    if p.market_entry:
                        pos = dict(od); pos["fill_t"] = T; pos["be"] = False; pos["limit"] = entry
                    else:
                        pend = od
                    break
        # ---- walk bar k ----
        if pend is not None or pos is not None:
            trig = p.be_atr * atr if np.isfinite(atr) else 1e9
            lo1, hi1 = cx.m1_lo[k], cx.m1_hi[k]
            if p.use_m1 and hi1 - lo1 >= 10:
                for q in range(lo1, hi1):
                    walk_sub(cx.m1o[q], cx.m1h[q], cx.m1l[q], cx.m1c[q], cx.m1spr[q] * p.spread_mult, cx.m1t[q], trig)
                    if pend is None and pos is None:
                        break
            else:
                walk_sub(o[k], h[k], l[k], c[k], sp, T, trig)
        # ---- intrabar mitigation of stored zones (affects next bar) ----
        for m in list(zones):
            z = zones[m]
            if (z["type"] == 1 and l[k] < z["mid"]) or (z["type"] == -1 and h[k] + sp > z["mid"]):
                del zones[m]
    # annotate fill delay
    for tr in trades:
        tr["delay_min"] = (tr["fill_t"] - tr["place_t"]) / 60.0
    INFO["end_pending"] = None if pend is None else dict(pend)
    INFO["end_pos"] = None if pos is None else dict(pos)
    return trades


INFO: dict = {}


# ------------------------------------------------------------------ stats
def stats(trs: list[dict], start_bal: float = 10000.0) -> dict:
    if not trs:
        return dict(n=0, win=0.0, pf=float("nan"), exp_r=0.0, net=0.0, dd=0.0, dd_pct=0.0, avg=0.0, be=0)
    trs = sorted(trs, key=lambda x: x["exit_t"])
    pnl = np.array([x["pnl"] for x in trs])
    risk = np.array([x["risk"] for x in trs])
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    eq = start_bal + np.cumsum(pnl)
    peak = np.maximum.accumulate(np.r_[start_bal, eq])[1:]
    ddv = (peak - eq)
    return dict(n=len(trs), win=float((pnl > 0).mean() * 100), pf=float(gw / gl) if gl > 0 else float("inf"),
                exp_r=float((pnl / risk).mean()), net=float(pnl.sum()), dd=float(ddv.max()),
                dd_pct=float((ddv / peak).max() * 100), avg=float(pnl.mean()),
                be=int(sum(1 for x in trs if x["reason"] == "BE")),
                tp=int(sum(1 for x in trs if x["reason"] == "TP")),
                sl=int(sum(1 for x in trs if x["reason"] == "SL")),
                max_win=float(pnl.max()), max_loss=float(pnl.min()))


def fmt(s: dict) -> str:
    if s["n"] == 0:
        return "n=0"
    return (f"n={s['n']:4d} win={s['win']:5.1f}% PF={s['pf']:5.2f} E[R]={s['exp_r']:+.3f} "
            f"net=${s['net']:+9.2f} avg=${s['avg']:+.2f} maxDD=${s['dd']:.1f}({s['dd_pct']:.2f}%) "
            f"[TP{s.get('tp',0)} SL{s.get('sl',0)} BE{s.get('be',0)}]")


def by(trs, keyf):
    out = {}
    for x in trs:
        out.setdefault(keyf(x), []).append(x)
    return dict(sorted(out.items(), key=lambda kv: str(kv[0])))


def yr(x):
    return dt.datetime.fromtimestamp(x["fill_t"], dt.timezone.utc).year


def kzname(x):
    h = x["hour"]
    return "London07-10" if h < 10 else ("Overlap12-16" if h < 16 else "NYlate16-21")


def sbucket(x):
    s = x["score"]
    return "50-59" if s < 60 else ("60-69" if s < 70 else "70+")


PERIODS = {
    "DEV": ("2022-07-01", "2025-01-01"),
    "VALIDATE": ("2025-01-01", "2026-07-01"),
    "HOLDOUT": ("2026-07-01", "2027-01-01"),
}


def slice_tr(trs, a, b):
    return [x for x in trs if ts(a) <= x["fill_t"] < ts(b)]


def run_all(cx, p, label, quiet=False):
    trs = simulate(cx, p, "2022-07-20", "2027-01-01")
    res = {"ALL": stats(trs)}
    for nm, (a, b) in PERIODS.items():
        res[nm] = stats(slice_tr(trs, a, b))
    res["DEV+VAL"] = stats(slice_tr(trs, "2022-07-01", "2026-07-01"))
    if not quiet:
        print(f"== {label}")
        for k_, v in res.items():
            print(f"  {k_:9s} {fmt(v)}")
    return trs, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    cx = Ctx()
    A_on = P()                                   # AS CODED: GTC pending orders (jam MaxTrades=1), fill-bar TP allowed
    A_path = replace(A_on, fillbar="path")
    B_on = P(pending="age")                      # VARIANT B: pending cancelled when its FVG ages out
    B_path = replace(B_on, fillbar="path")       # primary honest estimate (path model calibrated on M1 holdout)
    base = B_path
    out = {}

    print("### CLAIM REPLICATION (0.01 lot, $10,000, fresh state at window start)")
    cfgs = {"A as-coded/on": A_on, "A as-coded/path": A_path, "B age-cancel/on": B_on, "B age-cancel/path": B_path,
            "B path pt0.01": replace(B_path, point=0.01),
            "B path v2.0-defaults(55,RR2,overlap)": replace(B_path, min_score=55.0, rr=2.0, kz_prefer_overlap=True),
            "A on v2.0-defaults(55,RR2,overlap)": replace(A_on, min_score=55.0, rr=2.0, kz_prefer_overlap=True)}
    for nm, (a, b) in {"Jan-Jul2026": ("2026-01-01", "2026-08-01"), "Apr-Jul2026": ("2026-04-01", "2026-08-01")}.items():
        for lab, pp in cfgs.items():
            trs = simulate(cx, pp, a, b)
            s_ = stats(trs)
            out[f"claim|{nm}|{lab}"] = s_
            print(f"{nm:12s} {lab:38s} {fmt(s_)}")
            if lab == "B age-cancel/path":
                print(f"{'':12s} max single win ${s_['max_win']:.2f}, max single loss ${s_['max_loss']:.2f}")

    print("\n### FULL RUN A (as coded; GTC pending)")
    for lab, pp in {"A/on": A_on, "A/path": A_path}.items():
        trsA, resA = run_all(cx, pp, lab)
        out["full|" + lab] = resA
        print("  last trade exit:", dt.datetime.fromtimestamp(trsA[-1]["exit_t"], dt.timezone.utc), "stuck pending order:", INFO.get("end_pending"))
    for k_, v in by(trsA, yr).items():
        print(f"  A/path {k_} {fmt(stats(v))}")

    print("\n### FULL RUN B (age-cancel) fill-bar modes")
    for lab, pp in {"B/on (user-spec literal)": B_on, "B/off (pessimistic)": replace(B_on, fillbar="off")}.items():
        _, r_ = run_all(cx, pp, lab)
        out["full|" + lab] = r_
    print("\n### FULL RUN B/path (PRIMARY)")
    trs, res = run_all(cx, base, "B/path")
    out["full|B/path"] = res
    full = trs
    print("\n-- by year (fill year)")
    for k_, v in by(full, yr).items():
        print(f"  {k_} {fmt(stats(v))}")
    print("-- by killzone (placement hour)")
    for k_, v in by(full, kzname).items():
        print(f"  {k_:13s} {fmt(stats(v))}")
    print("-- by score bucket")
    for k_, v in by(full, sbucket).items():
        print(f"  {k_:6s} {fmt(stats(v))}")
    print("-- long vs short")
    for k_, v in by(full, lambda x: "long" if x["side"] == 1 else "short").items():
        print(f"  {k_:6s} {fmt(stats(v))}")
    dm = np.array([x["delay_min"] for x in full])
    print(f"-- fill delay (min): median {np.median(dm):.0f}, p90 {np.percentile(dm,90):.0f}, same-bar fills {np.mean(dm==0)*100:.1f}%")
    sw = sum(x["swap"] for x in full)
    print(f"-- total swap ${sw:.2f}; gross price P&L ${sum(x['gross'] for x in full):.2f}; BE exits {sum(1 for x in full if x['reason']=='BE')} of {len(full)}")
    print(f"-- mean entry-to-SL risk ${np.mean([x['risk'] for x in full]):.2f}; mean pnl of BE exits ${np.mean([x['pnl'] for x in full if x['reason']=='BE']):+.3f}")
    out["full|by_year"] = {str(k_): stats(v) for k_, v in by(full, yr).items()}
    out["full|by_kz"] = {k_: stats(v) for k_, v in by(full, kzname).items()}
    out["full|by_score"] = {k_: stats(v) for k_, v in by(full, sbucket).items()}
    out["full|by_side"] = {k_: stats(v) for k_, v in by(full, lambda x: "long" if x["side"] == 1 else "short").items()}
    out["full|swap"] = sw

    print("\n### SENSITIVITIES on B/path (full period)")
    sens = {
        "point0.01 (gap>=$0.25, OB dist $2)": replace(base, point=0.01),
        "v2.0 defaults (score55,RR2,overlap-only)": replace(base, min_score=55.0, rr=2.0, kz_prefer_overlap=True),
        "pending cancelled when zone dies": replace(base, pending="zone"),
        "stops_level 50pts": replace(base, stops_level_pts=50.0),
        "swap x3 (-1.5/night long)": replace(base, swap_long_night=1.5),
        "zero swap": replace(base, swap_long_night=0.0),
        "no M1 (M15 only, path)": replace(base, use_m1=False),
        "spread x2": replace(base, spread_mult=2.0),
        "slippage $0.30/fill": replace(base, slip_per_fill=0.30),
        "spread x2 + slip $0.30/fill": replace(base, spread_mult=2.0, slip_per_fill=0.30),
    }
    for lab, pp in sens.items():
        _, r_ = run_all(cx, pp, "SENS " + lab)
        out["sens|" + lab] = r_

    abl = {
        "(a) no score filter": dict(min_score=-1.0),
        "(b) no H1 trend filter": dict(use_bias=False),
        "(c) no killzone": dict(use_kz=False),
        "(d) no break-even": dict(be_on=False),
        "(e) market entry at gap formation": dict(market_entry=True),
        "(f) no OB bonus": dict(use_ob=False),
    }
    for mode, b0 in {"path": B_path, "on": B_on}.items():
        print(f"\n### ABLATION B/{mode} (judge on DEV+VAL only; holdout shown for info)")
        _, r_ = run_all(cx, b0, f"ABL B/{mode} baseline")
        out[f"abl|{mode}|baseline"] = r_
        for lab, kw in abl.items():
            _, r_ = run_all(cx, replace(b0, **kw), f"ABL B/{mode} " + lab)
            out[f"abl|{mode}|" + lab] = r_
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
