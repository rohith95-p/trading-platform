"""Is the engine wrong in my favour, or against me?

Pre-registered: research/registry/PREREG_BiasAudit_2026-11-09.md
Run in the direction that can falsify the project's negative verdict. The bar was
set before this ran: if GENEROUS reaches PF >= 1.15 the engine was the problem.

    python -I scripts/validation/bias_audit.py
    python -I scripts/validation/bias_audit.py --live-only
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

os.environ["ULTRA_TRADE_24H"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUT = os.path.join("research", "registry", "bias_audit_2026-11-09.json")


def utc(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())


ERAS = [("e1", utc(2004, 7, 1), utc(2008, 1, 1)),
        ("e2", utc(2008, 1, 1), utc(2012, 1, 1)),
        ("e3", utc(2012, 1, 1), utc(2016, 1, 1)),
        ("e4", utc(2016, 1, 1), utc(2020, 1, 1)),
        ("e5", utc(2020, 1, 1), utc(2022, 8, 1))]

# ambiguity resolution, gapped-stop fills
ARMS = {
    "BASE     (as published)": ("sl_first", False),
    "GENEROUS (tp first)": ("tp_first", False),
    "HARSH    (gap fills)": ("sl_first", True),
}


def cfg_for(arm, start):
    from src.backtesting.engine import EngineConfig
    res, gap = ARMS[arm]
    return EngineConfig.live_parity_preset(
        sizing_mode="fixed", fixed_lots=0.02, starting_balance=start,
        max_concurrent=3, max_same_direction=3, history_bars=7500,
        protect_profit=False, m1_policy="skip",
        ambiguous_resolution=res, gap_fill_stops=gap)


def job(arm, era, a, b):
    from src.backtesting.costs import SCENARIOS
    from src.backtesting.engine import BacktestEngine
    from src.backtesting.master import load_master
    from src.strategies.portfolio_atlas import PORTFOLIO

    bars = load_master(("M15", "M1", "D1"), start=a, end=b)
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"],
                         config=cfg_for(arm, 5000.0))
    res = eng.run([c() for c in PORTFOLIO], a, b)
    d = eng.diag
    rows = [dict(net=float(t.net_pl), amb=bool(t.intrabar_ambiguous),
                 swap=float(t.swap), nights=int(t.nights_held),
                 is_buy=bool(t.is_buy), mins=int(t.minutes_open),
                 reason=t.exit_reason)
            for t in res.trades]
    diag = {k: d.get(k, 0) for k in
            ("ambiguous_bars", "ambiguous_given_to_tp", "gapped_stops",
             "gapped_stop_extra_usd", "bars_skipped_no_m1")}
    return arm, era, rows, diag


def pf(pls):
    a = np.asarray(pls, dtype=float)
    if not len(a):
        return 0.0
    gl = float(-a[a < 0].sum())
    return float(a[a > 0].sum() / gl) if gl > 0 else float("inf")


def live_reconcile():
    """Replay the only month the current portfolio ever traded for real."""
    from src.backtesting.costs import SCENARIOS
    from src.backtesting.engine import BacktestEngine
    from src.backtesting.master import load_master
    from src.strategies.portfolio_atlas import PORTFOLIO

    a, b = utc(2026, 10, 1), utc(2026, 11, 1)
    bars = load_master(("M15", "M1", "D1"), start=a, end=b)
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"],
                         config=cfg_for("BASE     (as published)", 5000.0))
    res = eng.run([c() for c in PORTFOLIO], a, b)

    # The broker's own ledger, read read-only from MT5 on 2026-11-09.
    broker = [("2026-10-30", 7320, "SELL", 3987.06, 3960.39, 53.33),
              ("2026-10-30", 7324, "SELL", None, 3931.854, 59.12)]
    print("\n" + "=" * 86)
    print("LIVE RECONCILIATION -- October 2026, the only month the live 4 legs traded")
    print("=" * 86)
    print("broker's actual fills:")
    for d, mg, side, ep, xp, net in broker:
        print("  %s magic %d %s entry %s exit %.3f  net $%+.2f"
              % (d, mg, side, ("%.2f" % ep) if ep else "   ?  ", xp, net))
    print("\nengine's replay of the same month:")
    if not res.trades:
        print("  (engine produced NO trades)")
    for t in res.trades:
        print("  %s magic?-%-26s %s entry %.3f exit %.3f  net $%+.2f  %s"
              % (dt.datetime.fromtimestamp(t.entry_time, dt.timezone.utc)
                 .strftime("%Y-%m-%d %H:%M"), t.strategy,
                 "BUY " if t.is_buy else "SELL", t.entry_price, t.exit_price,
                 t.net_pl, t.exit_reason))
    eng_net = sum(t.net_pl for t in res.trades)
    bro_net = sum(x[5] for x in broker)
    print("\n  engine net $%+.2f over %d trades   broker net $%+.2f over %d trades"
          % (eng_net, len(res.trades), bro_net, len(broker)))
    if res.trades:
        print("  engine minus broker: $%+.2f  (negative = the engine is pessimistic)"
              % (eng_net - bro_net))
    return dict(engine_net=round(eng_net, 2), engine_trades=len(res.trades),
                broker_net=round(bro_net, 2), broker_trades=len(broker))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live-only", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    report = {}
    if not args.live_only:
        print("BIAS AUDIT -- bounding the engine's two known intrabar biases")
        print("pre-registration: research/registry/PREREG_BiasAudit_2026-11-09.md")
        print("bar set before the run: GENEROUS PF >= 1.15 means the engine was "
              "the problem\n")
        specs = [(arm, e[0], e[1], e[2]) for arm in ARMS for e in ERAS]
        pooled = {a: [] for a in ARMS}
        diags = {a: {} for a in ARMS}
        with ProcessPoolExecutor(args.workers) as ex:
            for arm, era, rows, diag in ex.map(job, *zip(*specs)):
                pooled[arm] += rows
                for k, v in diag.items():
                    diags[arm][k] = diags[arm].get(k, 0) + v
                print("  done %-24s %s  %4d trades" % (arm, era, len(rows)),
                      flush=True)

        print("\n%-24s %7s %10s %6s %7s" % ("arm", "trades", "net $", "PF", "win%"))
        print("-" * 60)
        for arm in ARMS:
            pls = [r["net"] for r in pooled[arm]]
            a = np.asarray(pls, dtype=float)
            print("%-24s %7d %10.2f %6.2f %7.1f"
                  % (arm, len(a), a.sum(), pf(pls), 100 * (a > 0).mean()))
            report[arm] = dict(trades=len(a), net=round(float(a.sum()), 2),
                               pf=round(pf(pls), 3),
                               win=round(100 * float((a > 0).mean()), 1),
                               diag=diags[arm])

        base = pooled["BASE     (as published)"]
        amb = sum(1 for r in base if r["amb"])
        print("\nsize of each bias, measured:")
        print("  trades flagged intrabar-ambiguous : %d of %d (%.1f%%)"
              % (amb, len(base), 100.0 * amb / max(1, len(base))))
        print("  ambiguous M1 bars seen            : %d"
              % diags["BASE     (as published)"]["ambiguous_bars"])
        print("  ambiguous bars handed to TP       : %d"
              % diags["GENEROUS (tp first)"]["ambiguous_given_to_tp"])
        print("  stops that had gapped through     : %d"
              % diags["HARSH    (gap fills)"]["gapped_stops"])
        print("  extra loss when gaps are honest   : $%.2f"
              % diags["HARSH    (gap fills)"]["gapped_stop_extra_usd"])

        # swap sanity
        shorts_paying = [r for r in base if not r["is_buy"] and r["swap"] != 0]
        intraday_paying = [r for r in base if r["nights"] == 0 and r["swap"] != 0]
        print("\nswap sanity:")
        print("  shorts charged swap (should be 0) : %d" % len(shorts_paying))
        print("  0-night trades charged swap (0)   : %d" % len(intraday_paying))
        print("  total swap paid                   : $%.2f"
              % sum(r["swap"] for r in base))
        report["swap_check"] = dict(shorts_paying=len(shorts_paying),
                                    intraday_paying=len(intraday_paying),
                                    total=round(sum(r["swap"] for r in base), 2))

        gen = report["GENEROUS (tp first)"]["pf"]
        print("")
        if gen >= 1.15:
            v = ("ENGINE WAS THE PROBLEM -- the negative verdict is retracted; "
                 "the four legs go back on the table")
        elif gen >= 1.00:
            v = ("MATERIAL BUT NOT SUFFICIENT -- the legs are still not "
                 "profitable, but my stated margin was overstated")
        else:
            v = ("NEGATIVE VERDICT ROBUST -- even the most favourable reading the "
                 "data allows stays below breakeven")
        report["verdict"] = v
        print("VERDICT (bar set before the run): " + v)

    report["live"] = live_reconcile()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(report, open(OUT, "w"), indent=1, default=str)
    print("\nwritten to %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
