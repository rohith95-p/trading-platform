"""Is the breakout-timing payoff real, and is it big enough to trade?

Pre-registered: research/registry/PREREG_VolTiming_2026-11-09.md
Read that first. It records, before this ran, that the effect is expected to be
REAL BUT TOO SMALL -- worth ~2-3 points of win rate against a ~4.3-4.9 point bar --
and that the gate is deliberately not lowered to fit it.

    python -I scripts/validation/vol_timing.py --stage test
    python -I scripts/validation/vol_timing.py --stage confirm
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

SIGNALS = ["DONCH20_S6_T10", "DONCH20_S8_T16"]
MODES = ["as_is", "long_only", "short_only", "force_short", "force_long"]
CONTROL_SEEDS = (1, 2, 3)

GATE = dict(min_trades=150, min_pf=1.15)


def utc(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())


STAGES = {
    # control arms were never run on 2016-2022, so every mode but as_is is unobserved
    "test": [("2016-2020", utc(2016, 1, 1), utc(2020, 1, 1)),
             ("2020-2022", utc(2020, 1, 1), utc(2022, 8, 1))],
    # completely unspent; touched only if TEST passes
    "confirm": [("2022-2024", utc(2022, 8, 1), utc(2024, 8, 1)),
                ("2024-2026", utc(2024, 8, 1), utc(2026, 11, 1))],
}


def out_path(stage):
    return os.path.join(REG, "vol_timing_%s_2026-11-09.json" % stage)


# -- direction transforms -------------------------------------------------
# Both engine traps apply (see signal_or_cost.py): keep __module__ so the engine
# patches the right module's clock stub, and keep *args because the engine calls
# evaluate(m15, m5) while BaseStrategy documents evaluate(rates).
def _as(sig, is_buy):
    return replace(sig, is_buy=is_buy, direction=0 if is_buy else 1)


def _coin(seed, magic, ts):
    key = str(seed) + ":" + str(magic) + ":" + str(ts)
    return bool(hashlib.blake2b(key.encode(), digest_size=8).digest()[0] & 1)


def build(make, mode, seed):
    inst = make()
    if mode == "as_is":
        return inst
    cls = type(inst)

    class Arm(cls):
        def _twist(self, sig, rates):
            if sig is None:
                return sig
            if mode == "long_only":
                return sig if sig.is_buy else None
            if mode == "short_only":
                return None if sig.is_buy else sig
            if mode == "force_short":
                return _as(sig, False)
            if mode == "force_long":
                return _as(sig, True)
            if mode == "coin":
                return _as(sig, _coin(seed, self.magic, int(rates[-1]["time"])))
            raise ValueError("unknown mode " + mode)

        def evaluate(self, *a, **kw):
            return self._twist(super().evaluate(*a, **kw), a[0])

    Arm.__name__ = cls.__name__
    Arm.__module__ = cls.__module__
    return Arm(sl_atr_mult=inst.sl_atr_mult, tp_atr_mult=inst.tp_atr_mult,
               magic=inst.magic)


def stats(pls, nights=None):
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


def job(era, a, b, specs):
    from src.backtesting.costs import SCENARIOS
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.master import load_master
    from src.strategies.search_candidates import candidates

    factory = dict(candidates())
    bars = load_master(("M15", "M1", "D1"), start=a, end=b)
    out = {}
    for sid, mode, seed in specs:
        cfg = EngineConfig.live_parity_preset(
            sizing_mode="fixed", fixed_lots=0.02, starting_balance=5000.0,
            max_concurrent=3, max_same_direction=3, history_bars=7500,
            protect_profit=False, m1_policy="skip", enable_d1_bias_gate=False)
        eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg)
        res = eng.run([build(factory[sid], mode, seed)], a, b)
        out["%s|%s|%d" % (sid, mode, seed)] = [
            dict(net=float(t.net_pl),
                 hours=round((int(t.exit_time) - int(t.entry_time)) / 3600.0, 2))
            for t in res.trades]
    return era, out


def run(stage, specs, workers):
    windows = STAGES[stage]
    t0 = time.time()
    pooled = {}
    with ProcessPoolExecutor(min(workers, len(windows))) as ex:
        args = [(w[0], w[1], w[2], specs) for w in windows]
        for era, got in ex.map(job, *zip(*args)):
            for k, rows in got.items():
                pooled.setdefault(k, []).extend(rows)
            print("  [%5.0fs] %s done (%d arms)" % (time.time() - t0, era, len(got)),
                  flush=True)
    return pooled


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", required=True, choices=list(STAGES))
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    stage = args.stage

    if stage == "confirm":
        p = out_path("test")
        if not os.path.exists(p):
            print("run --stage test first")
            return 2
        adv = json.load(open(p))["advancing"]
        if not adv:
            print("nothing advanced from TEST -- per the pre-registration, stop here.")
            return 0
        sid, mode = adv[0].split("|")[:2]
        signals, modes = [sid], [mode]
    else:
        signals, modes = SIGNALS, MODES

    print("VOL TIMING -- stage %s" % stage.upper())
    print("pre-registration: research/registry/PREREG_VolTiming_2026-11-09.md")
    print("windows: " + ", ".join(w[0] for w in STAGES[stage]))
    print("gate: >=%d trades, PF >=%.2f, above its own coin-flip max\n"
          % (GATE["min_trades"], GATE["min_pf"]))

    specs = [(s, m, 0) for s in signals for m in modes]
    specs += [(s, "coin", k) for s in signals for k in CONTROL_SEEDS]
    pooled = run(stage, specs, args.workers)

    res = {k: stats([r["net"] for r in v]) for k, v in pooled.items()}
    hours = {k: (float(np.mean([r["hours"] for r in v])) if v else 0.0)
             for k, v in pooled.items()}

    print("\n%-34s %7s %10s %6s %6s %9s %9s %8s" % (
        "arm", "trades", "net $", "PF", "win%", "avg win", "avg loss", "avg hrs"))
    print("-" * 96)
    for k in sorted(res, key=lambda j: -res[j]["pf"]):
        s = res[k]
        print("%-34s %7d %10.2f %6.2f %6.1f %9.2f %9.2f %8.1f" % (
            k, s["n"], s["net"], s["pf"], s["win"], s["avg_win"], s["avg_loss"],
            hours[k]))

    print("")
    bands = {}
    passed = []
    for s in signals:
        band = [res["%s|coin|%d" % (s, k)]["pf"] for k in CONTROL_SEEDS]
        bands[s] = band
        print("%s coin-flip band: %.2f-%.2f (mean %.3f)"
              % (s, min(band), max(band), sum(band) / len(band)))
        for m in modes:
            key = "%s|%s|0" % (s, m)
            st = res[key]
            ok = (st["n"] >= GATE["min_trades"] and st["pf"] >= GATE["min_pf"]
                  and st["pf"] > max(band))
            why = []
            if st["n"] < GATE["min_trades"]:
                why.append("only %d trades" % st["n"])
            if st["pf"] < GATE["min_pf"]:
                why.append("PF %.2f < %.2f" % (st["pf"], GATE["min_pf"]))
            if st["pf"] <= max(band):
                why.append("not above chance %.2f" % max(band))
            print("   %-14s %s" % (m, "PASS" if ok else "fail: " + ", ".join(why)))
            if ok:
                passed.append(key)

    passed.sort(key=lambda k: -res[k]["pf"])
    advancing = passed[:1] if stage == "test" else passed

    json.dump(dict(stage=stage, gate=GATE, results=res, avg_hours=hours,
                   bands=bands, passed=passed, advancing=advancing),
              open(out_path(stage), "w"), indent=1, default=str)

    print("")
    if not passed:
        print("RESULT: nothing clears the gate at %s." % stage.upper())
        if stage == "test":
            print("Per the pre-registration, the volatility-timing idea is CLOSED,")
            print("and with it the signal-search route to a funded account.")
    else:
        print("RESULT: %s clears %s. advancing: %s"
              % (", ".join(passed), stage.upper(), advancing))
    print("\nwritten to %s" % out_path(stage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
