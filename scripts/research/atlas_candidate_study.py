"""Screen every strategy candidate on 1-minute data for an Atlas $5K / 0.02-lot portfolio.

Re-uses the merged M1 set and windows from atlas_filter_study.py. Each (strategy, window)
runs alone with live-parity execution; trades are saved so portfolios can be scored later.

Run: python -I scripts/research/atlas_candidate_study.py --run
     python -I scripts/research/atlas_candidate_study.py --score
"""
import argparse
import importlib
import inspect
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUT = os.path.join(ROOT, "research", "results", "atlas_candidate_study")
MODULES = ["src.strategies", "src.strategies.archive", "src.strategies._deprecated"]
SKIP_FILES = {"base_strategy.py", "__init__.py", "new_common.py"}


def _alias_old_paths():
    """Old modules import siblings as src.strategies.<name>; point those at the _deprecated copies."""
    for f in ("new_common", "bible_strategies", "ny_liquidity_expansion", "ny_session_suite",
              "liquidity_sweep_reversal", "grid_strategies", "h1_donchian"):
        if f"src.strategies.{f}" not in sys.modules:
            try:
                sys.modules[f"src.strategies.{f}"] = importlib.import_module(f"src.strategies._deprecated.{f}")
            except Exception:
                pass


def discover():
    _alias_old_paths()
    from src.strategies.base_strategy import BaseStrategy
    found, seen = [], set()
    for pkg in MODULES:
        for f in sorted(os.listdir(pkg.replace(".", "/"))):
            if not f.endswith(".py") or f in SKIP_FILES or f.startswith("_") or "portfolio" in f:
                continue
            try:
                m = importlib.import_module(f"{pkg}.{f[:-3]}")
            except Exception:
                continue
            for n, c in inspect.getmembers(m, inspect.isclass):
                if (issubclass(c, BaseStrategy) and c is not BaseStrategy and c.__module__ == m.__name__
                        and not inspect.isabstract(c)):
                    try:
                        name = c().name
                    except Exception:
                        continue
                    if name not in seen:
                        seen.add(name)
                        found.append((f"{pkg}.{f[:-3]}", n, name))
    return found


_BARS = None


def _job(modpath, clsname, wname, start, end):
    global _BARS
    _alias_old_paths()
    from scripts.research.atlas_filter_study import merged_bars
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.costs import SCENARIOS
    if _BARS is None:
        _BARS = merged_bars()
    cls = getattr(importlib.import_module(modpath), clsname)
    cfg = EngineConfig.live_parity_preset(
        sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
        risk_rules_enforce=False, sizing_ladder_caps=False, streak_blind_spot=False,
        max_concurrent=3, max_same_direction=2, history_bars=7500)
    try:
        res = BacktestEngine(bars=_BARS, cost=SCENARIOS["realistic_ecn"], config=cfg).run([cls()], start, end)
    except Exception as e:
        return modpath, clsname, wname, None, f"{type(e).__name__}: {e}"[:200]
    trades = [dict(entry_time=int(t.entry_time), exit_time=int(t.exit_time), net_pl=float(t.net_pl),
                   is_buy=bool(t.is_buy), strategy=str(t.strategy)) for t in res.trades]
    return modpath, clsname, wname, trades, None


def run(only=None):
    from scripts.research.atlas_filter_study import WINDOWS
    os.makedirs(OUT, exist_ok=True)
    cands = discover()
    if only:
        cands = [c for c in cands if c[2] in only or c[1] in only]
    print(f"{len(cands)} candidates x {len(WINDOWS)} windows", flush=True)
    results = {}
    with ProcessPoolExecutor(max_workers=min(24, os.cpu_count() or 4)) as ex:
        futs = [ex.submit(_job, m, c, w, s, e) for m, c, _ in cands for w, s, e in WINDOWS]
        for i, f in enumerate(as_completed(futs), 1):
            m, c, w, trades, err = f.result()
            key = f"{m}:{c}"
            results.setdefault(key, {})[w] = trades if err is None else {"error": err}
            print(f"[{i}/{len(futs)}] {c} {w}: " + (err or f"{len(trades)} trades"), flush=True)
            with open(os.path.join(OUT, "partial.jsonl"), "a") as fh:
                fh.write(json.dumps({"key": key, "window": w, "trades": trades, "error": err}) + "\n")
    path = os.path.join(OUT, "trades.json")
    old = json.load(open(path)) if os.path.exists(path) else {}
    old.update(results)
    json.dump(old, open(path, "w"))


# ---------------- scoring ----------------

def trading_days(start, end):
    from scripts.research.atlas_filter_study import merged_bars
    m15 = merged_bars().m15
    t = m15["time"][(m15["time"] >= start) & (m15["time"] < end)]
    return len(np.unique(t // 86400))


def stats(trades, n_days):
    if not trades:
        return dict(n=0, per_day=0, active=0, wr=0, pf=0, net=0, dd=0, worst_day=0)
    tr = sorted(trades, key=lambda r: r["exit_time"])
    pl = np.array([r["net_pl"] for r in tr])
    eq = np.cumsum(pl)
    dd = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    days = {}
    for r in tr:
        days[r["exit_time"] // 86400] = days.get(r["exit_time"] // 86400, 0) + r["net_pl"]
    g, l = pl[pl > 0].sum(), -pl[pl < 0].sum()
    return dict(n=len(pl), per_day=len(pl) / n_days, active=len({r["entry_time"] // 86400 for r in tr}) / n_days,
                wr=100 * (pl > 0).mean(), pf=(g / l) if l else 99.0, net=float(pl.sum()), dd=dd,
                worst_day=float(min(days.values())))


def score():
    from scripts.research.atlas_filter_study import WINDOWS
    data = json.load(open(os.path.join(OUT, "trades.json")))
    ndays = {w: trading_days(s, e) for w, s, e in WINDOWS}
    rows = []
    for key, ws in data.items():
        if any(isinstance(v, dict) for v in ws.values()):
            print(f"ERROR {key}: {[v for v in ws.values() if isinstance(v, dict)][0]}")
            continue
        st = {w: stats(ws.get(w, []), ndays[w]) for w in ndays}
        rows.append((key.split(":")[1], st))
    rows.sort(key=lambda r: -min(r[1][w]["pf"] for w in ndays))
    print(f"trading days: {ndays}\n")
    print(f"{'strategy':28s}" + "".join(f"| {w:^37s}" for w in ndays))
    print(f"{'':28s}" + "| tr/day   n   WR%   PF    net$  DD$  wDay$ " * len(ndays))
    for name, st in rows:
        line = f"{name[:28]:28s}"
        for w in ndays:
            s = st[w]
            line += f"| {s['per_day']:5.2f} {s['n']:4d} {s['wr']:5.1f} {s['pf']:4.2f} {s['net']:7.0f} {s['dd']:4.0f} {s['worst_day']:5.0f} "
        print(line)
    json.dump({n: s for n, s in rows}, open(os.path.join(OUT, "scores.json"), "w"), indent=1)


def combos(min_pf=1.0, max_size=6):
    """Best portfolios from candidates whose pooled PF over all windows >= min_pf.
    Trades are pooled post hoc (no shared position cap), so DD/day figures are slightly pessimistic
    on overlap but ignore cap-blocked trades."""
    from itertools import combinations
    from scripts.research.atlas_filter_study import WINDOWS
    data = json.load(open(os.path.join(OUT, "trades.json")))
    ndays = {w: trading_days(s, e) for w, s, e in WINDOWS}
    pool = {}
    for key, ws in data.items():
        if any(isinstance(v, dict) for v in ws.values()):
            continue
        allt = [t for w in ndays for t in ws.get(w, [])]
        if len(allt) >= 30 and stats(allt, 1)["pf"] >= min_pf:
            pool[key.split(":")[1]] = ws
    print(f"pool ({len(pool)}): {sorted(pool)}\n")
    best = []
    for k in range(1, min(max_size, len(pool)) + 1):
        for combo in combinations(sorted(pool), k):
            st = {w: stats([t for c in combo for t in pool[c].get(w, [])], ndays[w]) for w in ndays}
            if min(s["pf"] for s in st.values()) < 1.0:
                continue
            best.append((combo, st))
    best.sort(key=lambda b: -sum(b[1][w]["per_day"] * ndays[w] for w in ndays) / sum(ndays.values()))
    for combo, st in best[:15]:
        print(" + ".join(combo))
        for w in ndays:
            s = st[w]
            print(f"    {w:6s} tr/day {s['per_day']:.2f}  active days {100 * s['active']:3.0f}%  n {s['n']:4d}  WR {s['wr']:4.1f}%  "
                  f"PF {s['pf']:.2f}  net ${s['net']:6.0f}  maxDD ${s['dd']:4.0f}  worst day ${s['worst_day']:5.0f}")


PORTFOLIOS = {
    "current 3-leg": ["AsianBreakoutV6", "AsianRangeFilteredV6", "DonchianTrendV6"],
    "proposed 5-leg": ["AsianBreakoutV6", "AsianRangeFilteredV6", "DonchianTrendV6",
                       "LondonMomentumTightV6", "NYSessionReversalV6"],
}


def _portfolio_job(label, names, wname, start, end):
    global _BARS
    from scripts.research.atlas_filter_study import merged_bars
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.costs import SCENARIOS
    if _BARS is None:
        _BARS = merged_bars()
    by_name = {c[1]: c for c in discover()}
    classes = [getattr(importlib.import_module(by_name[n][0]), n) for n in names]
    cfg = EngineConfig.live_parity_preset(
        sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
        max_concurrent=3, max_same_direction=2, history_bars=7500)
    res = BacktestEngine(bars=_BARS, cost=SCENARIOS["realistic_ecn"], config=cfg).run([c() for c in classes], start, end)
    trades = [dict(entry_time=int(t.entry_time), exit_time=int(t.exit_time), net_pl=float(t.net_pl),
                   strategy=str(t.strategy)) for t in res.trades]
    return label, wname, trades


def confirm():
    """Shared-cap engine run (live parity, risk rules ON) for each portfolio, judged against Atlas $5K limits."""
    from scripts.research.atlas_filter_study import WINDOWS
    ndays = {w: trading_days(s, e) for w, s, e in WINDOWS}
    out = {}
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(_portfolio_job, lbl, names, w, s, e)
                for lbl, names in PORTFOLIOS.items() for w, s, e in WINDOWS]
        for f in as_completed(futs):
            lbl, w, trades = f.result()
            out.setdefault(lbl, {})[w] = trades
    json.dump(out, open(os.path.join(OUT, "portfolio_confirm.json"), "w"))
    for lbl in PORTFOLIOS:
        print(f"\n{lbl}: {' + '.join(PORTFOLIOS[lbl])}")
        for w in ndays:
            tr = sorted(out[lbl][w], key=lambda r: r["exit_time"])
            s = stats(tr, ndays[w])
            eq, peak, breach10, days = 5000.0, 5000.0, False, {}
            for r in tr:
                eq += r["net_pl"]
                peak = max(peak, eq)
                breach10 |= eq < peak - 500
                days[r["exit_time"] // 86400] = days.get(r["exit_time"] // 86400, 0) + r["net_pl"]
            cum, hit = 0.0, None
            for i, (d, pl) in enumerate(sorted(days.items())):
                cum += pl
                if hit is None and cum >= 150:
                    hit = (d - min(days)) if days else None
            print(f"  {w:6s} tr/day {s['per_day']:.2f} | days traded {100 * s['active']:3.0f}% | n {s['n']:4d} | WR {s['wr']:4.1f}% "
                  f"| PF {s['pf']:.2f} | net ${s['net']:6.0f} | maxDD ${s['dd']:4.0f} ({s['dd'] / 50:.1f}%) "
                  f"| worst day ${s['worst_day']:5.0f} | 10% DD breached: {breach10} | daily -$250 breached: {s['worst_day'] < -250} "
                  f"| days to +$150: {hit}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--combos", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args()
    if a.run:
        run(a.only)
    if a.score:
        score()
    if a.combos:
        combos()
    if a.confirm:
        confirm()
