"""New strategy families for the Atlas search (2026-10-29), research-only.

Protocol (fixed before any result was seen):
  1. Every variant below runs alone on DEV (2022-08 -> 2024-06), $5K, 0.02 lots, live parity.
  2. Survivors: DEV PF >= 1.20 and n >= 60.
  3. Survivors then run on TEST and RECENT, which they have never been tuned on.
     Pass: TEST PF >= 1.15 and RECENT PF >= 1.0.
  4. Passing variants go into a shared-cap portfolio confirm with the live 5-leg.
Nothing here is wired into live trading.

Run: python -I scripts/research/atlas_new_families.py --dev
     python -I scripts/research/atlas_new_families.py --oos
     python -I scripts/research/atlas_new_families.py --confirm NAME [NAME ...]
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.strategies.base_strategy import BaseStrategy, Signal, mt5  # noqa: E402

OUT = os.path.join(ROOT, "research", "results", "atlas_new_families")
# ULTRA_TRADE_24H=1 lifts the live 06:00-21:30 IST entry window (src/core/market_hours.py)
RESULTS = "results_24h.json" if os.getenv("ULTRA_TRADE_24H") == "1" else "results.json"
H = 3600


# ---------------- helpers on closed M15 bars ----------------

def _closed(m15):
    return m15[:-1]  # [-1] is the forming bar


def _daily(r):
    """Completed-day OHLC from closed M15 bars (today's partial day is the last row)."""
    day = r["time"] // 86400
    u, idx = np.unique(day, return_index=True)
    ends = np.r_[idx[1:], len(r)]
    o = r["open"][idx]
    h = np.maximum.reduceat(r["high"], idx)
    lo = np.minimum.reduceat(r["low"], idx)
    c = r["close"][ends - 1]
    return u, o, h, lo, c


def _ema(x, n):
    a = 2.0 / (n + 1)
    out = np.empty(len(x))
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def _atr(r, n=14):
    pc = np.r_[r["close"][0], r["close"][:-1]]
    tr = np.maximum(r["high"] - r["low"], np.maximum(abs(r["high"] - pc), abs(r["low"] - pc)))
    return float(tr[-n:].mean())


def _h1_close(r):
    hr = r["time"] // H
    u, idx = np.unique(hr, return_index=True)
    ends = np.r_[idx[1:], len(r)]
    return r["close"][ends - 1]


class _Family(BaseStrategy):
    execute_immediately = True
    edge_trigger = True
    session = (0.0, 24.0)
    skip_d1_gate = True

    def __init__(self, name, magic, sl, tp, **p):
        self.name, self.magic = name, magic
        self.sl_atr_mult, self.tp_atr_mult = sl, tp
        self.p = p
        self._last_key = None

    def _sig(self, is_buy, key):
        if key == self._last_key:
            return None
        self._last_key = key
        return Signal(direction=mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
                      strategy_name=self.name, magic=self.magic, is_buy=is_buy)

    def evaluate(self, m15_rates, m5_rates=None):
        if m15_rates is None or len(m15_rates) < 600:
            return None
        r = _closed(m15_rates)
        t = int(r["time"][-1])
        return self.decide(r, t, t // 86400, t % 86400)

    def check_pending_confirmation(self, m15_rates):
        return None

    def set_pending(self, signal, candle_time):
        pass


# ---------------- families ----------------

class ORB(_Family):
    """Opening-range breakout: range of `bars` M15 bars from `hour`; first close beyond it
    within the next `window` bars."""
    def decide(self, r, t, day, sod):
        h0, nb, win = self.p["hour"] * H, self.p["bars"], self.p["window"]
        end = h0 + nb * 900
        if not (end <= sod < end + win * 900):
            return None
        today = (r["time"] // 86400 == day)
        rng = today & (r["time"] % 86400 >= h0) & (r["time"] % 86400 < end)
        if rng.sum() < nb:
            return None
        hi, lo = r["high"][rng].max(), r["low"][rng].min()
        if hi - lo < self.p.get("min_atr", 0.5) * _atr(r):
            return None
        c, pc = r["close"][-1], r["close"][-2]
        if c > hi and pc <= hi:
            return self._sig(True, day)
        if c < lo and pc >= lo:
            return self._sig(False, day)
        return None


class PDHL(_Family):
    """Previous-day high/low breakout between hours h0..h1, optional D1 EMA20 trend filter."""
    def decide(self, r, t, day, sod):
        if not (self.p["h0"] * H <= sod < self.p["h1"] * H):
            return None
        u, o, h, lo, c = _daily(r)
        if len(u) < 25 or u[-1] != day:
            return None
        pdh, pdl = h[-2], lo[-2]
        trend = 0
        if self.p.get("trend"):
            e = _ema(c[:-1], 20)
            trend = 1 if c[-2] > e[-1] else -1
        cl, pc = r["close"][-1], r["close"][-2]
        if cl > pdh and pc <= pdh and trend >= 0:
            return self._sig(True, day)
        if cl < pdl and pc >= pdl and trend <= 0:
            return self._sig(False, day)
        return None


class TrendPullbackRSI2(_Family):
    """RSI(2) extreme against an H1 EMA50/EMA200 trend, h0..h1, once per day."""
    def decide(self, r, t, day, sod):
        if not (self.p["h0"] * H <= sod < self.p["h1"] * H):
            return None
        h1 = _h1_close(r)[:-1]  # completed hours
        if len(h1) < 220:
            return None
        e50, e200 = _ema(h1, 50)[-1], _ema(h1, 200)[-1]
        up, dn = h1[-1] > e50 > e200, h1[-1] < e50 < e200
        cl = r["close"][-30:]
        d = np.diff(cl)
        g, l = np.where(d > 0, d, 0), np.where(d < 0, -d, 0)
        ag, al = g[-2:].mean(), l[-2:].mean()
        rsi = 100 if al == 0 else 100 - 100 / (1 + ag / al)
        k = self.p["rsi"]
        if up and rsi < k:
            return self._sig(True, day)
        if dn and rsi > 100 - k:
            return self._sig(False, day)
        return None


class SessionMove(_Family):
    """At `hour`, if price moved more than k*ATR since `from_hour` today, follow (cont) or fade it."""
    def decide(self, r, t, day, sod):
        if sod != self.p["hour"] * H - 900:  # the bar ending at `hour` just closed
            return None
        today = r["time"] // 86400 == day
        start = today & (r["time"] % 86400 == self.p["from_hour"] * H)
        if not start.any():
            return None
        mv = r["close"][-1] - r["open"][start][0]
        if abs(mv) < self.p["k"] * _atr(r):
            return None
        up = mv > 0
        return self._sig(up if self.p["mode"] == "cont" else not up, day)


class NarrowDayBreak(_Family):
    """Yesterday inside day / NR-n day; first close beyond yesterday's range between h0..h1."""
    def decide(self, r, t, day, sod):
        if not (self.p["h0"] * H <= sod < self.p["h1"] * H):
            return None
        u, o, h, lo, c = _daily(r)
        if len(u) < 10 or u[-1] != day:
            return None
        rngs = h[:-1] - lo[:-1]
        kind = self.p["kind"]
        if kind == "inside":
            ok = h[-2] <= h[-3] and lo[-2] >= lo[-3]
        else:
            ok = rngs[-1] <= rngs[-kind:].min()
        if not ok:
            return None
        cl, pc = r["close"][-1], r["close"][-2]
        if cl > h[-2] and pc <= h[-2]:
            return self._sig(True, day)
        if cl < lo[-2] and pc >= lo[-2]:
            return self._sig(False, day)
        return None


class PrevWeekBreak(_Family):
    """First close beyond the previous week's high/low, h0..h1, once per week."""
    def decide(self, r, t, day, sod):
        if not (self.p["h0"] * H <= sod < self.p["h1"] * H):
            return None
        wk = (r["time"] // 86400 + 3) // 7  # Monday-based week number
        cur = wk[-1]
        prev = wk == cur - 1
        if prev.sum() < 200:
            return None
        hi, lo = r["high"][prev].max(), r["low"][prev].min()
        cl, pc = r["close"][-1], r["close"][-2]
        if cl > hi and pc <= hi:
            return self._sig(True, int(cur))
        if cl < lo and pc >= lo:
            return self._sig(False, int(cur))
        return None


class H1Squeeze(_Family):
    """H1 Bollinger width in its lowest `pct`% of the last 120 hours, then a close outside the band."""
    def decide(self, r, t, day, sod):
        if not (self.p["h0"] * H <= sod < self.p["h1"] * H) or sod % H != H - 900:
            return None
        h1 = _h1_close(r)
        if len(h1) < 150:
            return None
        win = np.lib.stride_tricks.sliding_window_view(h1, 20)
        mid, sd = win.mean(1), win.std(1)
        width = 4 * sd / mid
        if width[-2] > np.percentile(width[-121:-1], self.p["pct"]):
            return None
        if h1[-1] > mid[-1] + 2 * sd[-1]:
            return self._sig(True, day)
        if h1[-1] < mid[-1] - 2 * sd[-1]:
            return self._sig(False, day)
        return None


# ---------------- round 2: published gold anomalies, with time exits ----------------
# Sources: Blose/Gondhalekar/Kort 2018 (gold overnight returns positive, daytime negative);
# CBS thesis 2019 "hat-shaped" intraday pattern (gold rises in eastern hours);
# Friday gold drift (Thu close -> Fri close); daily RSI(2) mean reversion (Connors-style).
# Live entries are only allowed 00:30-16:00 UTC (TRADING_WINDOW_IST), Friday flatten 17:00 UTC,
# so every entry below sits inside that window.

class _Timed(_Family):
    """Adds `max_hold_sec`: TimedEngine closes the position at market after that long."""
    def __init__(self, name, magic, sl, tp, hold_h, **p):
        super().__init__(name, magic, sl, tp, **p)
        self.max_hold_sec = int(hold_h * H)


def _d1_trend(r, n):
    u, o, h, lo, c = _daily(r)
    if len(u) < n + 2:
        return 0
    e = _ema(c[:-1], n)
    return 1 if c[-2] > e[-1] else -1


class AsiaDrift(_Timed):
    """Buy at `hour` UTC (Asian session), hold `hold_h` hours. Optional D1 trend filter."""
    def decide(self, r, t, day, sod):
        if sod != self.p["hour"] * H - 900:
            return None
        if self.p.get("trend") and _d1_trend(r, 20) < 0:
            return None
        return self._sig(True, day)


class DayTrend(_Timed):
    """At `hour` UTC, trade in the D1 EMA20 direction (or only shorts in downtrends), hold `hold_h`."""
    def decide(self, r, t, day, sod):
        if sod != self.p["hour"] * H - 900:
            return None
        tr = _d1_trend(r, 20)
        if self.p["mode"] == "short_dn":
            return self._sig(False, day) if tr < 0 else None
        if self.p["mode"] == "fade":
            tr = -tr
        return self._sig(tr > 0, day) if tr else None


class FridayDrift(_Timed):
    """Buy Thursday at 15:45 UTC, hold into Friday (weekend flatten closes it by 17:00 UTC)."""
    def decide(self, r, t, day, sod):
        if sod != 15 * H + 1800 or (day + 4) % 7 != 4:  # bar 15:30-15:45 just closed, Thursday
            return None
        if self.p.get("trend") and _d1_trend(r, 20) < 0:
            return None
        return self._sig(True, day)


class DailyRSI2(_Timed):
    """At 15:45 UTC: RSI(2) of daily closes (today's 15:45 price as today's close) extreme,
    in the direction of the D1 EMA50 trend; hold `hold_h`."""
    def decide(self, r, t, day, sod):
        if sod != 15 * H + 1800:
            return None
        u, o, h, lo, c = _daily(r)
        if len(u) < 55:
            return None
        cl = c.copy()  # last element is today's price at 15:45
        d = np.diff(cl[-4:])
        g, l = np.where(d > 0, d, 0)[-2:].mean(), np.where(d < 0, -d, 0)[-2:].mean()
        rsi = 100 if l == 0 else 100 - 100 / (1 + g / l)
        tr = 1 if cl[-2] > _ema(cl[:-1], 50)[-1] else -1
        k = self.p["rsi"]
        if rsi < k and tr > 0:
            return self._sig(True, day)
        if rsi > 100 - k and tr < 0 and not self.p.get("long_only"):
            return self._sig(False, day)
        return None


def timed_engine_cls():
    from src.backtesting.engine import BacktestEngine

    class TimedEngine(BacktestEngine):
        """BacktestEngine + market close of any position whose strategy has max_hold_sec."""
        def run(self, strategies, start_ts=None, end_ts=None, *a, **k):
            self._hold = {s.name: s.max_hold_sec for s in strategies if getattr(s, "max_hold_sec", 0)}
            return super().run(strategies, start_ts, end_ts, *a, **k)

        def _manage(self, rm, m15_view, bar, point, spread_pts):
            if self._hold:
                ts = int(bar["time"])
                for pos in list(self.positions):
                    hold = self._hold.get(pos.strategy)
                    if hold and ts - pos.entry_time >= hold:
                        base = float(bar["close"])
                        px = base if pos.is_buy else self.cost.ask(base, point, spread_pts)
                        self._close(pos, px, ts, "TIME_EXIT")
            super()._manage(rm, m15_view, bar, point, spread_pts)

    return TimedEngine


def variants():
    v, m = [], [7400]

    def add(cls, label, sl, tp, **p):
        m[0] += 1
        v.append((cls.__name__, f"{label}_sl{sl}_tp{tp}", m[0], sl, tp, p))

    for hour in (7, 8, 13):
        for bars in (2, 4):
            for sl, tp in ((1.5, 3.0), (3.0, 5.0)):
                add(ORB, f"ORB_h{hour}_b{bars}", sl, tp, hour=hour, bars=bars, window=8)
    for h0, h1 in ((7, 12), (13, 17)):
        for trend in (0, 1):
            for sl, tp in ((1.5, 3.0), (3.0, 5.0)):
                add(PDHL, f"PDHL_{h0}-{h1}_tr{trend}", sl, tp, h0=h0, h1=h1, trend=trend)
    for rsi in (5, 10):
        for h0, h1 in ((7, 12), (13, 18)):
            for sl, tp in ((2.0, 3.0), (3.0, 4.5)):
                add(TrendPullbackRSI2, f"RSI2_{rsi}_{h0}-{h1}", sl, tp, rsi=rsi, h0=h0, h1=h1)
    for hour, frm in ((13, 7), (14, 7), (19, 13)):
        for k in (2.0, 4.0):
            for mode in ("cont", "fade"):
                add(SessionMove, f"MOVE_{frm}to{hour}_k{k}_{mode}", 2.0, 3.0, hour=hour, from_hour=frm, k=k, mode=mode)
    for kind in ("inside", 4, 7):
        for sl, tp in ((1.5, 3.0), (3.0, 5.0)):
            add(NarrowDayBreak, f"NARROW_{kind}", sl, tp, kind=kind, h0=7, h1=17)
    for sl, tp in ((1.5, 3.0), (3.0, 5.0)):
        add(PrevWeekBreak, "PWEEK", sl, tp, h0=7, h1=17)
    for pct in (10, 25):
        for sl, tp in ((1.5, 3.0), (3.0, 5.0)):
            add(H1Squeeze, f"SQZ_p{pct}", sl, tp, pct=pct, h0=7, h1=18)
    return v


def variants2():
    v, m = [], [7460]

    def add(cls, label, sl, tp, **p):
        m[0] += 1
        v.append((cls.__name__, f"{label}_sl{sl}_tp{tp}", m[0], sl, tp, p))

    for hour in (1, 2):
        for hold in (5, 6):
            for trend in (0, 1):
                add(AsiaDrift, f"ASIADRIFT_h{hour}_hold{hold}_tr{trend}", 4.0, 8.0, hour=hour, hold_h=hold, trend=trend)
    for hour in (7, 13):
        for mode in ("with", "fade", "short_dn"):
            add(DayTrend, f"DAYTREND_h{hour}_{mode}", 4.0, 6.0, hour=hour, hold_h=16 - hour, mode=mode)
    for trend in (0, 1):
        add(FridayDrift, f"FRIDAY_tr{trend}", 4.0, 8.0, hold_h=24, trend=trend)
    for rsi in (10, 25):
        for hold in (24, 48):
            add(DailyRSI2, f"DRSI2_{rsi}_hold{hold}", 6.0, 10.0, rsi=rsi, hold_h=hold)
        add(DailyRSI2, f"DRSI2_{rsi}_hold24_long", 6.0, 10.0, rsi=rsi, hold_h=24, long_only=1)
    return v


def build(spec):
    clsname, name, magic, sl, tp, p = spec
    return globals()[clsname](name, magic, sl, tp, **p)


def variants3():
    """Night entries -- only reachable with ULTRA_TRADE_24H=1."""
    v, m = [], [7480]
    for hour in (22, 23):
        for hold in (7, 8):
            for trend in (0, 1):
                m[0] += 1
                v.append(("AsiaDrift", f"NIGHTDRIFT_h{hour}_hold{hold}_tr{trend}_sl4.0_tp8.0", m[0], 4.0, 8.0,
                          dict(hour=hour, hold_h=hold, trend=trend)))
    return v


def all_variants():
    return variants() + variants2() + variants3()


# ---------------- running ----------------

_BARS = None


def _job(spec, wname, start, end):
    global _BARS
    from scripts.research.atlas_filter_study import merged_bars
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.costs import SCENARIOS
    if _BARS is None:
        _BARS = merged_bars()
    cfg = EngineConfig.live_parity_preset(
        sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
        risk_rules_enforce=False, sizing_ladder_caps=False, streak_blind_spot=False,
        max_concurrent=3, max_same_direction=2, history_bars=7500)
    try:
        res = timed_engine_cls()(bars=_BARS, cost=SCENARIOS["realistic_ecn"], config=cfg).run([build(spec)], start, end)
    except Exception as e:
        return spec[1], wname, None, f"{type(e).__name__}: {e}"[:200]
    return spec[1], wname, [dict(entry_time=int(t.entry_time), exit_time=int(t.exit_time),
                                 net_pl=float(t.net_pl), is_buy=bool(t.is_buy), strategy=str(t.strategy))
                            for t in res.trades], None


def _stats(tr):
    pl = np.array([t["net_pl"] for t in sorted(tr, key=lambda t: t["exit_time"])])
    if not len(pl):
        return dict(n=0, wr=0, pf=0, net=0, dd=0)
    eq = np.r_[0, np.cumsum(pl)]
    g, l = pl[pl > 0].sum(), -pl[pl < 0].sum()
    return dict(n=len(pl), wr=100 * (pl > 0).mean(), pf=g / l if l else 99.0, net=float(pl.sum()),
                dd=float((np.maximum.accumulate(eq) - eq).max()))


def _run(specs, windows, fname):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, fname)
    res = json.load(open(path)) if os.path.exists(path) else {}
    jobs = [(s, w, a, b) for s in specs for w, a, b in windows if w not in res.get(s[1], {})]
    print(f"{len(jobs)} jobs", flush=True)
    with ProcessPoolExecutor(max_workers=min(26, os.cpu_count() or 4)) as ex:
        futs = [ex.submit(_job, *j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            name, w, trades, err = f.result()
            res.setdefault(name, {})[w] = trades if err is None else {"error": err}
            s = _stats(trades) if trades is not None else None
            print(f"[{i}/{len(jobs)}] {name} {w}: " + (err or f"n {s['n']} PF {s['pf']:.2f} net ${s['net']:.0f}"),
                  flush=True)
            json.dump(res, open(path, "w"))
    return res


def report(res, windows):
    rows = []
    for name, ws in res.items():
        if any(isinstance(x, dict) for x in ws.values()):
            print("ERROR", name, ws)
            continue
        rows.append((name, {w: _stats(ws[w]) for w, _, _ in windows if w in ws}))
    rows.sort(key=lambda r: -r[1].get("DEV", {"pf": 0})["pf"])
    for name, st in rows:
        print(f"{name:34s}" + "".join(f"| {w} n {s['n']:4d} WR {s['wr']:4.1f} PF {s['pf']:4.2f} net {s['net']:6.0f} DD {s['dd']:4.0f} "
                                       for w, s in st.items()))
    return rows


def _portfolio_job(label, new_names, wname, start, end):
    global _BARS
    from scripts.research.atlas_filter_study import merged_bars
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.costs import SCENARIOS
    from src.strategies.portfolio_atlas import PORTFOLIO
    if _BARS is None:
        _BARS = merged_bars()
    by_name = {s[1]: s for s in all_variants()}
    strats = [c() for c in PORTFOLIO] + [build(by_name[n]) for n in new_names]
    cfg = EngineConfig.live_parity_preset(
        sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
        max_concurrent=3, max_same_direction=2, history_bars=7500)
    res = timed_engine_cls()(bars=_BARS, cost=SCENARIOS["realistic_ecn"], config=cfg).run(strats, start, end)
    return label, wname, [dict(entry_time=int(t.entry_time), exit_time=int(t.exit_time), net_pl=float(t.net_pl),
                               strategy=str(t.strategy)) for t in res.trades]


def confirm(new_names):
    """Live 5-leg alone vs live 5-leg + new survivors: shared caps, risk rules ON, $5K, 0.02 lots."""
    from scripts.research.atlas_filter_study import WINDOWS
    from scripts.research.atlas_candidate_study import stats, trading_days
    ndays = {w: trading_days(s, e) for w, s, e in WINDOWS}
    ports = {"live 5-leg": [], "5-leg + new": list(new_names)}
    out = {}
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(_portfolio_job, lbl, n, w, s, e) for lbl, n in ports.items() for w, s, e in WINDOWS]
        for f in as_completed(futs):
            lbl, w, tr = f.result()
            out.setdefault(lbl, {})[w] = tr
    json.dump(out, open(os.path.join(OUT, "portfolio_confirm.json"), "w"))
    for lbl in ports:
        print(f"\n{lbl}: {ports[lbl]}")
        for w in ndays:
            tr = sorted(out[lbl][w], key=lambda r: r["exit_time"])
            s = stats(tr, ndays[w])
            months = {}
            for r in tr:
                k = r["exit_time"] // (86400 * 30.44)
                months[k] = months.get(k, 0) + r["net_pl"]
            mv = np.array(list(months.values())) if months else np.zeros(1)
            print(f"  {w:6s} tr/day {s['per_day']:.2f} | days traded {100 * s['active']:3.0f}% | n {s['n']:4d} | WR {s['wr']:4.1f}% "
                  f"| PF {s['pf']:.2f} | net ${s['net']:6.0f} | avg month ${mv.mean():5.0f} | months+ {(mv > 0).sum()}/{len(mv)} "
                  f"| maxDD ${s['dd']:4.0f} | worst day ${s['worst_day']:5.0f}")


def main():
    from scripts.research.atlas_filter_study import WINDOWS
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--oos", action="store_true")
    ap.add_argument("--confirm", nargs="+")
    ap.add_argument("--round", type=int, default=1)
    a = ap.parse_args()
    if a.confirm:
        confirm(a.confirm)
        return
    specs = {1: variants, 2: variants2, 3: variants3, 0: all_variants}[a.round]()
    dev = [w for w in WINDOWS if w[0] == "DEV"]
    if a.dev:
        report({k: v for k, v in _run(specs, dev, RESULTS).items() if k in {s[1] for s in specs}}, dev)
    if a.oos:
        res = json.load(open(os.path.join(OUT, RESULTS)))
        keep = [s for s in specs if s[1] in res and isinstance(res[s[1]].get("DEV"), list)
                and (st := _stats(res[s[1]]["DEV"]))["pf"] >= 1.20 and st["n"] >= 60]
        print(f"DEV survivors ({len(keep)}/{len(specs)}): {[s[1] for s in keep]}")
        res = _run(keep, WINDOWS, RESULTS)
        report({s[1]: res[s[1]] for s in keep}, WINDOWS)


if __name__ == "__main__":
    main()
