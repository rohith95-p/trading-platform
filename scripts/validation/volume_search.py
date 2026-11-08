"""Volume-conditioned direction search: FIT on 2004-2016, CHECK on 2016-2022.

Pre-registered: research/registry/PREREG_VolumeSearch_2026-11-09.md
Read that first. The candidates, thresholds, gates, the re-spending of both
windows and the recorded prior (low) were all fixed before this ran.

Every backtest here is recorded to the trial ledger automatically, WITH its
return series -- so for the first time the deflated Sharpe can be reported at a
correlation-aware effective trial count instead of a raw guess.

    python -I scripts/validation/volume_search.py --stage fit
    python -I scripts/validation/volume_search.py --stage check
"""
from __future__ import annotations

import argparse
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
CONTROL_SEEDS = (1, 2, 3)
MAX_ADVANCE = 2
PRIOR_TRIALS = 209          # backfilled floor, see backfill_trial_ledger.py


def utc(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())


STAGES = {
    "fit": dict(
        windows=[("2004-2008", utc(2004, 7, 1), utc(2008, 1, 1)),
                 ("2008-2012", utc(2008, 1, 1), utc(2012, 1, 1)),
                 ("2012-2016", utc(2012, 1, 1), utc(2016, 1, 1))],
        label="2004-2016", min_trades=500, min_pf=1.15),
    "check": dict(
        windows=[("2016-2020", utc(2016, 1, 1), utc(2020, 1, 1)),
                 ("2020-2022", utc(2020, 1, 1), utc(2022, 8, 1))],
        label="2016-2022", min_trades=300, min_pf=1.15),
}


def out_path(stage):
    return os.path.join(REG, "volume_search_%s_2026-11-09.json" % stage)


# -- direction arms (same mechanism as signal_or_cost.py; both engine traps
#    documented there apply: keep __module__, keep *args) --------------------
def _flip(sig):
    f = not sig.is_buy
    return replace(sig, is_buy=f, direction=0 if f else 1)


def _coin(seed, magic, ts):
    key = "%s:%s:%s" % (seed, magic, ts)
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
    wins, losses = a[a > 0], a[a < 0]
    eq = np.cumsum(a)
    dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
    gl = float(-losses.sum())
    return dict(n=int(len(a)), net=round(float(a.sum()), 2),
                pf=round(float(wins.sum() / gl), 3) if gl > 0 else float("inf"),
                win=round(100 * float((a > 0).mean()), 1), dd=round(dd, 2),
                avg_win=round(float(wins.mean()), 2) if len(wins) else 0.0,
                avg_loss=round(float(losses.mean()), 2) if len(losses) else 0.0)


def job(era, a, b, specs, purpose):
    os.environ["ULTRA_TRIAL_PURPOSE"] = purpose
    os.environ["ULTRA_TRIAL_NOTE"] = "PREREG_VolumeSearch_2026-11-09"
    from src.backtesting.costs import SCENARIOS
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.master import load_master
    from src.strategies.volume_candidates import candidates

    factory = dict(candidates())
    bars = load_master(("M15", "M1", "D1"), start=a, end=b)
    out = {}
    for cid, mode, seed in specs:
        cfg = EngineConfig.live_parity_preset(
            sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
            max_concurrent=5, max_same_direction=5, history_bars=7500,
            protect_profit=False, m1_policy="skip", enable_d1_bias_gate=False)
        eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg)
        res = eng.run([build(factory[cid], mode, seed)], a, b)
        out["%s|%s|%d" % (cid, mode, seed)] = [float(t.net_pl) for t in res.trades]
    return era, out


def run(stage, specs, workers, purpose):
    cfg = STAGES[stage]
    t0 = time.time()
    pooled = {}
    args = [(w[0], w[1], w[2], specs, purpose) for w in cfg["windows"]]
    with ProcessPoolExecutor(min(workers, len(args))) as ex:
        for era, got in ex.map(job, *zip(*args)):
            for k, v in got.items():
                pooled.setdefault(k, []).extend(v)
            print("  [%5.0fs] %s done (%d arms)" % (time.time() - t0, era, len(got)),
                  flush=True)
    return pooled


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", required=True, choices=list(STAGES))
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    stage = args.stage
    scfg = STAGES[stage]

    from src.research import ledger as L
    from src.strategies.volume_candidates import candidates

    allc = candidates()
    if stage == "fit":
        ids = [c for c, _ in allc]
    else:
        p = out_path("fit")
        if not os.path.exists(p):
            print("run --stage fit first")
            return 2
        ids = json.load(open(p))["advancing"]
        if not ids:
            print("nothing advanced from FIT -- per the pre-registration, stop here.")
            return 0

    # The holdout ledger will refuse this window unless the reuse is deliberate
    # and recorded. It is: both historical windows are already spent, which the
    # pre-registration discloses.
    L.spend_window(scfg["label"], scfg["windows"][0][1], scfg["windows"][-1][2],
                   stage, allow_respend=True,
                   reason=("owner instruction 2026-11-09 to run the volume search; "
                           "PREREG_VolumeSearch_2026-11-09 discloses that no clean "
                           "historical window remains and that the real verdict is "
                           "forward"))

    print("VOLUME SEARCH -- stage %s" % stage.upper())
    print("pre-registration: research/registry/PREREG_VolumeSearch_2026-11-09.md")
    print("windows: %s (%s) -- RE-SPENT, logged"
          % (scfg["label"], ", ".join(w[0] for w in scfg["windows"])))
    print("gate: >=%d trades, PF >=%.2f, above its own coin-flip max"
          % (scfg["min_trades"], scfg["min_pf"]))
    print("candidates: %d\n" % len(ids))

    pooled = run(stage, [(c, "real", 0) for c in ids], args.workers, stage)
    real = {c: stats(pooled["%s|real|0" % c]) for c in ids}

    print("\n%-20s %7s %10s %6s %6s %9s %9s %9s" % (
        "candidate", "trades", "net $", "PF", "win%", "avg win", "avg loss", "worst DD"))
    print("-" * 90)
    for c in sorted(ids, key=lambda k: -real[k]["pf"]):
        s = real[c]
        print("%-20s %7d %10.2f %6.2f %6.1f %9.2f %9.2f %9.2f" % (
            c, s["n"], s["net"], s["pf"], s["win"], s["avg_win"], s["avg_loss"], s["dd"]))

    eligible = [c for c in ids if real[c]["n"] >= scfg["min_trades"]
                and real[c]["pf"] >= scfg["min_pf"]]
    under = [c for c in ids if real[c]["n"] < scfg["min_trades"]]
    print("\ncleared the trade+PF gate: %s" % (", ".join(eligible) or "none"))
    if under:
        print("inconclusive, below %d trades: %s"
              % (scfg["min_trades"], ", ".join(under)))

    controls = {}
    if eligible:
        print("\nrunning %d coin-flip control arms..."
              % (len(eligible) * len(CONTROL_SEEDS)))
        cp = run(stage, [(c, "coin", s) for c in eligible for s in CONTROL_SEEDS],
                 args.workers, stage + "-control")
        for c in eligible:
            band = [stats(cp["%s|coin|%d" % (c, s)])["pf"] for s in CONTROL_SEEDS]
            controls[c] = band
            print("  %-20s real PF %.2f   chance band %.2f-%.2f   %s" % (
                c, real[c]["pf"], min(band), max(band),
                "ABOVE CHANCE" if real[c]["pf"] > max(band) else "inside chance"))

    passed = [c for c in eligible if real[c]["pf"] > max(controls[c])]
    passed.sort(key=lambda k: -real[k]["pf"])
    advancing = passed[:MAX_ADVANCE] if stage == "fit" else passed

    # -- the effective trial count, computable for the first time -----------
    keff = {}
    try:
        recs = L.trials(purpose=stage)
        keff = L.effective_trials(recs)
        print("\neffective independent trials over this stage's %d recorded trials:"
              % len(recs))
        for k in ("k_raw", "k_eff", "reduction_pct", "note"):
            if keff.get(k) is not None:
                print("   %-16s %s" % (k, keff[k]))
    except Exception as exc:
        keff = {"error": str(exc)}

    report = dict(stage=stage, gate=dict(min_trades=scfg["min_trades"],
                                         min_pf=scfg["min_pf"]),
                  real=real, controls=controls, eligible=eligible,
                  underpowered=under, passed=passed, advancing=advancing,
                  k_eff=keff, prior_trials=PRIOR_TRIALS,
                  window=scfg["label"], respent=True)
    json.dump(report, open(out_path(stage), "w"), indent=1, default=str)

    print("")
    if not passed:
        print("RESULT: no candidate beat its own chance band at %s." % stage.upper())
        print("Per the pre-registration, the search is CLOSED -- no swept")
        print("thresholds, no third geometry, no extra signal, no re-cut windows.")
        vb = [c for c in ids if c.startswith("VOLBREAK")]
        vd = [c for c in ids if c.startswith("VOLDIVERG")]
        if vb and vd and not any(c in passed for c in vb + vd):
            print("")
            print("And the pre-committed finding: VOLBREAK and VOLDIVERG are exact")
            print("inverses on identical structure, and BOTH sit inside chance.")
            print("Volume regime carries no directional information.")
    else:
        print("RESULT: %d candidate(s) beat chance at %s: %s"
              % (len(passed), stage.upper(), ", ".join(passed)))
        if stage == "fit":
            print("advancing (cap %d): %s" % (MAX_ADVANCE, ", ".join(advancing)))
        else:
            print("NOTE: this is a re-spent window, so it is NOT an out-of-sample")
            print("verdict. The real test is forward on the live demo.")
    print("\nwritten to %s" % out_path(stage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
