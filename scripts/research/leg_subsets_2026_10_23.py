"""Frozen runner for research/registry/PREREG_LegSubsets_2026-10-23.md. Run: venv\\Scripts\\python.exe -I scripts/research/leg_subsets_2026_10_23.py"""
import dataclasses, datetime as dt, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from src.backtesting.costs import SCENARIOS
from src.backtesting.data import load_bars
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.strategies.portfolio_v5_core import BBMeanReversionV5, FVGNYTightV5, NVMRPortfolioV5, TrendPullbackV5

ts = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())
SETS = {"H1_all4": [TrendPullbackV5, BBMeanReversionV5, NVMRPortfolioV5, FVGNYTightV5],
        "H2_no_trendpullback": [BBMeanReversionV5, NVMRPortfolioV5, FVGNYTightV5],
        "H3_nvmr_bb": [NVMRPortfolioV5, BBMeanReversionV5]}
SPLITS = {"DEV": (ts(2022, 8, 1), ts(2024, 7, 1)), "VALIDATE": (ts(2024, 7, 1), ts(2025, 7, 1)),
          "HOLDOUT": (ts(2025, 7, 1), ts(2026, 7, 2))}
bars = dataclasses.replace(load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1")), m1=None)   # coarse, entry bar tested


def pf(p):
    p = np.asarray(p, float); w, l = p[p > 0].sum(), -p[p < 0].sum()
    return float(w / l) if l > 0 else float("inf")


def boot_p5(p, n=5000, seed=7):
    p = np.asarray(p, float); r = np.random.default_rng(seed)
    return float(np.percentile([pf(p[r.integers(0, len(p), len(p))]) for _ in range(n)], 5)) if len(p) else float("nan")


out, pooled = {}, {}
for name, legs in SETS.items():
    pooled[name] = []
    for sp, (a, b) in SPLITS.items():
        t0 = time.time()
        cfg = EngineConfig(sizing_mode="fixed", fixed_lots=0.01, starting_balance=10000.0)
        res = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg).run([c() for c in legs], a, b)
        p = [t.net_pl for t in res.trades]
        if sp != "HOLDOUT":
            pooled[name] += p
        per = {}
        for t in res.trades:
            per.setdefault(t.strategy, []).append(t.net_pl)
        out[f"{name}|{sp}"] = dict(n=len(p), win=round(100 * sum(x > 0 for x in p) / max(len(p), 1), 1), pf=round(pf(p), 3),
                                   net=round(sum(p), 2), per_leg={k: [len(v), round(pf(v), 3), round(sum(v), 2)] for k, v in per.items()})
        print(f"{name:22s} {sp:8s} n={len(p):5d} win={out[f'{name}|{sp}']['win']:5.1f}% PF={out[f'{name}|{sp}']['pf']:.3f} net=${sum(p):9.2f}  "
              f"({time.time()-t0:.0f}s)  legs={out[f'{name}|{sp}']['per_leg']}", flush=True)
    out[f"{name}|POOLED_DEV+VAL_boot_p5_PF"] = round(boot_p5(pooled[name]), 3)
    print(f"{name:22s} DEV+VAL bootstrap 5th-pct PF = {out[f'{name}|POOLED_DEV+VAL_boot_p5_PF']}", flush=True)

print("\nPASS RULE:")
for name in SETS:
    d, v, h = out[f"{name}|DEV"], out[f"{name}|VALIDATE"], out[f"{name}|HOLDOUT"]
    ok1 = d["pf"] >= 1.15 and d["n"] >= 150 and v["pf"] >= 1.15 and v["n"] >= 150
    ok2 = h["pf"] >= 1.0
    ok3 = out[f"{name}|POOLED_DEV+VAL_boot_p5_PF"] > 1.0
    print(f"  {name:22s} rule1(DEV&VAL PF>=1.15,n>=150)={ok1}  rule2(HOLDOUT PF>=1)={ok2}  rule3(boot p5>1)={ok3}  => {'PASS' if ok1 and ok2 and ok3 else 'FAIL'}")
json.dump(out, open(os.path.join("research", "registry", "leg_subsets_result_2026-10-23.json"), "w"), indent=1)
