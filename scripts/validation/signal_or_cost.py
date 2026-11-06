"""Do these entries carry direction, or are they coin flips paying the spread?

Pre-registered: research/registry/PREREG_SignalOrCost_2026-11-07.md
Read that first. The arms, the chance baseline and the meaning of each outcome
were fixed before this ran, including the commitment that a null result ends the
tuning plan instead of starting a sweep.

Costs are set to zero on purpose. That is a diagnostic, not a proposal.

    python -I scripts/validation/signal_or_cost.py
    python -I scripts/validation/signal_or_cost.py --eras E5 --arms B
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

OUT = os.path.join("research", "registry", "signal_or_cost_2026-11-07.json")


def utc(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())


# The same five eras as the 18-year holdout, unchanged.
ERAS = [
    ("E1 2004-2008", utc(2004, 7, 1), utc(2008, 1, 1)),
    ("E2 2008-2012", utc(2008, 1, 1), utc(2012, 1, 1)),
    ("E3 2012-2016", utc(2012, 1, 1), utc(2016, 1, 1)),
    ("E4 2016-2020", utc(2016, 1, 1), utc(2020, 1, 1)),
    ("E5 2020-2022", utc(2020, 1, 1), utc(2022, 8, 1)),
]

# arm -> (direction mode, seed, D1 gate on?)
ARMS = {
    "A real, gate on": ("real", 0, True),
    "B real, gate off": ("real", 0, False),
    "C inverted": ("inverse", 0, False),
    "D control seed 1": ("coin", 1, False),
    "D control seed 2": ("coin", 2, False),
    "D control seed 3": ("coin", 3, False),
}


def _flip(sig):
    flipped = not sig.is_buy
    return replace(sig, is_buy=flipped, direction=0 if flipped else 1)


def _coin(seed, magic, ts):
    """Deterministic across processes -- builtin hash() is salted per process."""
    key = str(seed) + ":" + str(magic) + ":" + str(ts)
    return bool(hashlib.blake2b(key.encode(), digest_size=8).digest()[0] & 1)


def build_legs(mode, seed):
    """Wrap each live leg so entry timing is untouched and only direction moves."""
    from src.strategies.portfolio_atlas import PORTFOLIO

    def wrap(cls):
        class Arm(cls):
            def _twist(self, sig, rates):
                if sig is None or mode == "real":
                    return sig
                if mode == "inverse":
                    return _flip(sig)
                want = _coin(seed, self.magic, int(rates[-1]["time"]))
                return sig if sig.is_buy == want else _flip(sig)

            # *args, not a fixed signature: the engine calls
            # `s.evaluate(m15_view, m5_view)` while BaseStrategy documents
            # `evaluate(rates)`. A one-argument override raises TypeError straight
            # into the engine's `except Exception`, which logs at debug level and
            # records no signal -- so a signature mismatch here looks exactly like
            # a strategy that never fires. It cost an hour; don't narrow these.
            def evaluate(self, *a, **kw):
                return self._twist(super().evaluate(*a, **kw), a[0])

            def check_pending_confirmation(self, *a, **kw):
                return self._twist(
                    super().check_pending_confirmation(*a, **kw), a[0])

        Arm.__name__ = cls.__name__
        # BacktestEngine._patch_strategy_mt5 does
        # `__import__(s.__module__, fromlist=["mt5"])` to swap in its clock stub.
        # A subclass defined here would point it at THIS module, so the real
        # strategy module would keep the live MT5 clock and every session-time
        # check would miss -- silently, as zero signals. Keep the leg's own
        # module so the engine patches what it means to patch.
        Arm.__module__ = cls.__module__
        return Arm

    return [wrap(c)() for c in PORTFOLIO]


def stats(pls):
    a = np.asarray(pls, dtype=float)
    if not len(a):
        return dict(n=0, net=0.0, pf=0.0, win=0.0, avg_win=0.0, avg_loss=0.0)
    wins, losses = a[a > 0], a[a <= 0]
    gl = float(-losses.sum())
    return dict(n=int(len(a)), net=round(float(a.sum()), 2),
                pf=round(float(wins.sum() / gl), 3) if gl > 0 else float("inf"),
                win=round(100 * float((a > 0).mean()), 1),
                avg_win=round(float(wins.mean()), 2) if len(wins) else 0.0,
                avg_loss=round(float(losses.mean()), 2) if len(losses) else 0.0)


def job(era, a, b, arms):
    """All arms for one era, so the era's minute bars are loaded once."""
    from src.backtesting.costs import SCENARIOS
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.master import load_master

    bars = load_master(("M15", "M1", "D1"), start=a, end=b)
    out = {}
    for arm in arms:
        mode, seed, gate = ARMS[arm]
        cfg = EngineConfig.live_parity_preset(
            sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
            max_concurrent=3, max_same_direction=3, history_bars=7500,
            protect_profit=False, m1_policy="skip", enable_d1_bias_gate=gate)
        eng = BacktestEngine(bars=bars, cost=SCENARIOS["frictionless"], config=cfg)
        res = eng.run(build_legs(mode, seed), a, b)
        out[arm] = [float(t.net_pl) for t in res.trades]
    return era, out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eras", nargs="*", default=None, help="era prefixes, e.g. E5")
    ap.add_argument("--arms", nargs="*", default=None, help="arm letters, e.g. B D")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    eras = [e for e in ERAS
            if not args.eras or any(e[0].startswith(p) for p in args.eras)]
    arms = [k for k in ARMS
            if not args.arms or any(k.startswith(p) for p in args.arms)]

    print("signal or cost: is there direction in these entries, or is it chance?")
    print("pre-registration: research/registry/PREREG_SignalOrCost_2026-11-07.md")
    print("costs: FRICTIONLESS (zero spread/slip/commission/swap) -- a diagnostic")
    print("")
    print(str(len(arms)) + " arm(s) x " + str(len(eras)) + " era(s)")
    print("")

    specs = [(e[0], e[1], e[2], arms) for e in eras]
    pooled = {arm: [] for arm in arms}
    per_era = {arm: {} for arm in arms}
    t0 = time.time()
    with ProcessPoolExecutor(args.workers) as ex:
        for era, got in ex.map(job, *zip(*specs)):
            for arm, pls in got.items():
                pooled[arm] += pls
                per_era[arm][era] = stats(pls)
                print("  [%6.0fs] %-14s %-18s %5d trades  PF %.2f"
                      % (time.time() - t0, era, arm, len(pls),
                         per_era[arm][era]["pf"]), flush=True)

    print("")
    print("%-20s %7s %10s %6s %6s %9s %9s"
          % ("arm", "trades", "net $", "PF", "win%", "avg win", "avg loss"))
    print("-" * 72)
    report = {}
    for arm in arms:
        s = stats(pooled[arm])
        report[arm] = dict(s, per_era=per_era[arm])
        print("%-20s %7d %10.2f %6.2f %6.1f %9.2f %9.2f"
              % (arm, s["n"], s["net"], s["pf"], s["win"],
                 s["avg_win"], s["avg_loss"]))

    # ---- the pre-registered verdict ------------------------------------
    ctrl = [report[k]["pf"] for k in arms if k.startswith("D")]
    verdict = "incomplete -- not all arms ran"
    if "B real, gate off" in report and len(ctrl) >= 2:
        b = report["B real, gate off"]["pf"]
        lo, hi = min(ctrl), max(ctrl)
        print("")
        print("chance band from the control arms: PF %.2f to %.2f" % (lo, hi))
        print("the real entries, same timing, same caps:  PF %.2f" % b)
        if b >= 1.10 and b > hi:
            verdict = ("SIGNAL EXISTS -- entries carry direction; costs are the "
                       "binding constraint and tuning is a real lever")
        elif lo <= b <= hi:
            verdict = ("NO SIGNAL -- the real entries fall inside the chance "
                       "band. No stop/target/filter tuning can manufacture an edge")
        elif b > hi:
            verdict = ("WEAK -- above chance but PF %.2f < 1.10 even at zero "
                       "cost; too thin to carry real costs" % b)
        else:
            verdict = "BELOW CHANCE -- the entries do worse than a coin flip"
        if "C inverted" in report and report["C inverted"]["pf"] - b >= 0.10:
            verdict += " | ANTI-SIGNAL: inverting beats the real direction"
    report["verdict"] = verdict
    print("")
    print("VERDICT (criteria fixed before the run): " + verdict)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(report, open(OUT, "w"), indent=1, default=str)
    print("")
    print("written to " + OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
