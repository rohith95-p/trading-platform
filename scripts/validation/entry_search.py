"""The entry-signal search: 21 candidates, SELECT -> CONFIRM -> JUDGE.

Pre-registered: research/registry/PREREG_EntrySearch_2026-11-07.md
Windows, candidates, thresholds, gates and the consequence of a null result were
all fixed there before this ran. This script enforces them rather than trusting
me to: which candidates advance is read from the previous stage's saved JSON, and
the "top 3 only" cap is applied in code.

    python -I scripts/validation/entry_search.py --stage select
    python -I scripts/validation/entry_search.py --stage confirm
    python -I scripts/validation/entry_search.py --stage judge
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import numpy as np

os.environ["ULTRA_TRADE_24H"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

REG = os.path.join("research", "registry")


def out_path(stage, swap=True):
    tag = stage if swap else stage + "_noswap"
    return os.path.join(REG, "entry_search_%s_2026-11-07.json" % tag)


def utc(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())


# Frozen in the pre-registration.
STAGES = {
    "select": [("2004-2008", utc(2004, 7, 1), utc(2008, 1, 1)),
               ("2008-2012", utc(2008, 1, 1), utc(2012, 1, 1)),
               ("2012-2016", utc(2012, 1, 1), utc(2016, 1, 1))],
    "confirm": [("2016-2020", utc(2016, 1, 1), utc(2020, 1, 1)),
                ("2020-2022", utc(2020, 1, 1), utc(2022, 8, 1))],
    "judge": [("2022-2024", utc(2022, 8, 1), utc(2024, 8, 1)),
              ("2024-2026", utc(2024, 8, 1), utc(2026, 11, 1))],
}

GATES = {"select": dict(min_trades=150, min_pf=1.15),
         "confirm": dict(min_trades=150, min_pf=1.10),
         "judge": dict(min_trades=150, min_pf=1.10)}

CONTROL_SEEDS = (1, 2, 3)
MAX_ADVANCE = 3


# -- direction arms --------------------------------------------------------
# Same mechanism as scripts/validation/signal_or_cost.py. Both traps documented
# there apply here too: keep __module__ (the engine patches its clock stub by
# s.__module__) and keep *args (the engine calls evaluate(m15, m5) while
# BaseStrategy documents evaluate(rates); a narrow override raises TypeError
# into an except Exception and silently reports zero signals).
def _flip(sig):
    f = not sig.is_buy
    return replace(sig, is_buy=f, direction=0 if f else 1)


def _coin(seed, magic, ts):
    key = str(seed) + ":" + str(magic) + ":" + str(ts)
    return bool(hashlib.blake2b(key.encode(), digest_size=8).digest()[0] & 1)


def build(make, mode, seed):
    inst = make()
    if mode == "real":
        return inst
    cls = type(inst)

    class Arm(cls):
        def _twist(self, sig, rates):
            if sig is None:
                return sig
            if mode == "inverse":
                return _flip(sig)
            want = _coin(seed, self.magic, int(rates[-1]["time"]))
            return sig if sig.is_buy == want else _flip(sig)

        def evaluate(self, *a, **kw):
            return self._twist(super().evaluate(*a, **kw), a[0])

    Arm.__name__ = cls.__name__
    Arm.__module__ = cls.__module__
    return Arm(sl_atr_mult=inst.sl_atr_mult, tp_atr_mult=inst.tp_atr_mult,
               magic=inst.magic)


def stats(pls):
    a = np.asarray(pls, dtype=float)
    if not len(a):
        return dict(n=0, net=0.0, pf=0.0, win=0.0, avg_win=0.0, avg_loss=0.0, dd=0.0)
    wins, losses = a[a > 0], a[a <= 0]
    eq = np.cumsum(a)
    dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
    gl = float(-losses.sum())
    return dict(n=int(len(a)), net=round(float(a.sum()), 2),
                pf=round(float(wins.sum() / gl), 3) if gl > 0 else float("inf"),
                win=round(100 * float((a > 0).mean()), 1), dd=round(dd, 2),
                avg_win=round(float(wins.mean()), 2) if len(wins) else 0.0,
                avg_loss=round(float(losses.mean()), 2) if len(losses) else 0.0)


def job(era, a, b, specs, swap):
    """One window, many candidate/arm pairs, so the window's bars load once."""
    from src.backtesting.costs import SCENARIOS
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.master import load_master
    from src.strategies.search_candidates import candidates

    factory = dict(candidates())
    cost = SCENARIOS["realistic_ecn"]
    if not swap:
        cost = dataclasses.replace(cost, enable_swap=False)

    bars = load_master(("M15", "M1", "D1"), start=a, end=b)
    out = {}
    for cid, mode, seed in specs:
        cfg = EngineConfig.live_parity_preset(
            sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
            max_concurrent=3, max_same_direction=3, history_bars=7500,
            protect_profit=False, m1_policy="skip", enable_d1_bias_gate=False)
        eng = BacktestEngine(bars=bars, cost=cost, config=cfg)
        res = eng.run([build(factory[cid], mode, seed)], a, b)
        out["%s|%s|%d" % (cid, mode, seed)] = [float(t.net_pl) for t in res.trades]
    return era, out


def run(stage, specs, swap, workers):
    """Pool each candidate/arm across the stage's windows."""
    windows = STAGES[stage]
    t0 = time.time()
    pooled = {}
    with ProcessPoolExecutor(min(workers, len(windows))) as ex:
        args = [(w[0], w[1], w[2], specs, swap) for w in windows]
        for era, got in ex.map(job, *zip(*args)):
            for key, pls in got.items():
                pooled.setdefault(key, []).extend(pls)
            print("  [%5.0fs] %s done (%d arms)" % (time.time() - t0, era, len(got)),
                  flush=True)
    return pooled


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", required=True, choices=list(STAGES))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--no-swap", action="store_true",
                    help="swap disabled, for the robustness check at judge")
    args = ap.parse_args()
    stage, swap = args.stage, not args.no_swap

    from src.strategies.search_candidates import candidates
    allc = candidates()

    # Which candidates are in play: all of them at select, otherwise exactly the
    # ones the previous stage advanced. Read from disk, not from memory, so the
    # pre-registered cap is enforced rather than recalled.
    if stage == "select":
        ids = [c for c, _ in allc]
    else:
        prev = "select" if stage == "confirm" else "confirm"
        p = out_path(prev)
        if not os.path.exists(p):
            print("stage %s requires %s first (%s missing)" % (stage, prev, p))
            return 2
        ids = json.load(open(p))["advancing"]
        if not ids:
            print("nothing advanced from %s -- per the pre-registration, stop here."
                  % prev)
            return 0

    gate = GATES[stage]
    print("ENTRY SEARCH -- stage %s%s" % (stage.upper(), "" if swap else " (swap off)"))
    print("pre-registration: research/registry/PREREG_EntrySearch_2026-11-07.md")
    print("windows: " + ", ".join(w[0] for w in STAGES[stage]))
    print("candidates: %d   gate: >=%d trades, PF >=%.2f, and above its own "
          "control max\n" % (len(ids), gate["min_trades"], gate["min_pf"]))

    # ---- pass 1: the real arms ------------------------------------------
    pooled = run(stage, [(c, "real", 0) for c in ids], swap, args.workers)
    real = {c: stats(pooled["%s|real|0" % c]) for c in ids}

    print("\n%-18s %7s %10s %6s %6s %9s %9s %9s" % (
        "candidate", "trades", "net $", "PF", "win%", "avg win", "avg loss", "worst DD"))
    print("-" * 88)
    for c in sorted(ids, key=lambda k: -real[k]["pf"]):
        s = real[c]
        print("%-18s %7d %10.2f %6.2f %6.1f %9.2f %9.2f %9.2f" % (
            c, s["n"], s["net"], s["pf"], s["win"], s["avg_win"], s["avg_loss"], s["dd"]))

    # ---- pass 2: controls, only where the PF/trade gate is already cleared
    eligible = [c for c in ids
                if real[c]["n"] >= gate["min_trades"] and real[c]["pf"] >= gate["min_pf"]]
    underpowered = [c for c in ids if real[c]["n"] < gate["min_trades"]]
    print("\ncleared the trade+PF gate: %s" % (", ".join(eligible) or "none"))
    if underpowered:
        print("inconclusive, below %d trades: %s"
              % (gate["min_trades"], ", ".join(underpowered)))

    controls = {}
    if eligible:
        print("\nrunning %d coin-flip control arms..." % (len(eligible) * len(CONTROL_SEEDS)))
        cspecs = [(c, "coin", s) for c in eligible for s in CONTROL_SEEDS]
        cp = run(stage, cspecs, swap, args.workers)
        for c in eligible:
            band = [stats(cp["%s|coin|%d" % (c, s)])["pf"] for s in CONTROL_SEEDS]
            controls[c] = band
            print("  %-18s real PF %.2f   control band %.2f-%.2f  %s" % (
                c, real[c]["pf"], min(band), max(band),
                "ABOVE CHANCE" if real[c]["pf"] > max(band) else "inside chance"))

    passed = [c for c in eligible if real[c]["pf"] > max(controls[c])]
    passed.sort(key=lambda k: -real[k]["pf"])
    advancing = passed[:MAX_ADVANCE] if stage != "judge" else passed

    report = dict(stage=stage, swap=swap, gate=gate, real=real, controls=controls,
                  eligible=eligible, underpowered=underpowered, passed=passed,
                  advancing=advancing,
                  windows=[[w[0], w[1], w[2]] for w in STAGES[stage]])
    json.dump(report, open(out_path(stage, swap), "w"), indent=1, default=str)

    print("")
    if not passed:
        print("RESULT: no candidate beat its own chance band at stage %s." % stage.upper())
        print("Per the pre-registration, that is the end of this search -- no widened")
        print("family list, no extra geometries, no swept thresholds, no re-cut windows.")
    else:
        print("RESULT: %d candidate(s) beat chance at %s: %s"
              % (len(passed), stage.upper(), ", ".join(passed)))
        if stage != "judge":
            print("advancing (cap %d): %s" % (MAX_ADVANCE, ", ".join(advancing)))
    print("\nwritten to %s" % out_path(stage, swap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
