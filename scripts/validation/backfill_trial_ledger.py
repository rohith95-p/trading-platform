"""Backfill the trial ledger from what the registry can actually document.

The trial ledger (src/research/ledger.py) records every backtest from
2026-11-09 onward. Everything before that is only recoverable from the JSON
result files in research/registry/, and those saved **summary statistics, not
return series** -- which is exactly the gap that made the effective-trial
correction impossible on 2026-11-09.

So these records are deliberately marked `backfilled` with an empty series. They
make N honest; they cannot make k_eff computable. `ledger.effective_trials` will
keep refusing until enough post-ledger trials exist with series saved, and that
refusal is correct.

Idempotent: re-running adds nothing, because each trial's id is a hash of its
own configuration.

    python -I scripts/validation/backfill_trial_ledger.py
    python -I scripts/validation/backfill_trial_ledger.py --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.pop("ULTRA_NO_TRIAL_LEDGER", None)

from src.research import ledger as L  # noqa: E402

REG = os.path.join("research", "registry")


def utc(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())


# Windows named in the pre-registrations, so backfilled trials carry the right one.
W_SELECT = (utc(2004, 7, 1), utc(2016, 1, 1))
W_CONFIRM = (utc(2016, 1, 1), utc(2022, 8, 1))
W_HOLDOUT = (utc(2004, 7, 1), utc(2022, 8, 1))
W_2016_2022 = W_CONFIRM


def load(name):
    p = os.path.join(REG, name)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def plan():
    """[(strategies, window, cost, purpose, note, reported)] from the registry."""
    out = []

    d = load("entry_search_select_2026-11-07.json")
    if d and isinstance(d.get("real"), dict):
        for cid, st in d["real"].items():
            out.append(([cid], W_SELECT, "realistic_ecn", "select",
                        "PREREG_EntrySearch_2026-11-07 SELECT", st))

    d = load("entry_search_confirm_2026-11-07.json")
    if d and isinstance(d.get("real"), dict):
        for cid, st in d["real"].items():
            out.append(([cid], W_CONFIRM, "realistic_ecn", "confirm",
                        "PREREG_EntrySearch_2026-11-07 CONFIRM", st))

    d = load("vol_timing_test_2026-11-09.json")
    if d and isinstance(d.get("results"), dict):
        for key, st in d["results"].items():
            out.append(([key], W_2016_2022, "realistic_ecn", "test",
                        "PREREG_VolTiming_2026-11-09 TEST", st))

    d = load("signal_or_cost_2026-11-07.json")
    if d:
        for key, st in d.items():
            if isinstance(st, dict) and "pf" in st:
                out.append(([key], W_HOLDOUT, "frictionless", "diagnostic",
                            "PREREG_SignalOrCost_2026-11-07", st))

    d = load("eighteen_year_holdout_2026-11-07.json")
    if d:
        for key, st in d.items():
            if isinstance(st, dict) and "pf" in st and not key.startswith("leg_"):
                out.append((["PORTFOLIO_ATLAS_4LEG @" + key], W_HOLDOUT,
                            "realistic_ecn", "judge",
                            "PREREG_EighteenYearHoldout_2026-11-07", st))

    d = load("bias_audit_2026-11-09.json")
    if d:
        for key, st in d.items():
            if isinstance(st, dict) and "pf" in st:
                out.append((["PORTFOLIO_ATLAS_4LEG @" + key], W_HOLDOUT,
                            "realistic_ecn", "diagnostic",
                            "PREREG_BiasAudit_2026-11-09", st))
    return out


# Trials this project certainly ran but which cannot be itemised: the result
# files kept only aggregates. Counted in the report as a floor, never written as
# fake individual records.
UNDOCUMENTED = [
    (48, "48-strategy Atlas candidate screen, 2026-10-29 (DECISIONS.md)"),
    (60, "stop/target sweep, 60 combinations on DEV+TEST (portfolio_atlas.py)"),
    (22, "liquidity-sweep reversal family, ~22 variations (HYP-070)"),
    (9, "three TradingView indicator strategies x fixed SL/TP sets (#646-654)"),
    (16, "hour-of-day cuts, session timing study 2026-10-19"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = plan()
    print("backfill candidates found in research/registry/: %d" % len(rows))
    before = L.count_trials()
    print("trials already in the ledger: %d\n" % before)

    added = 0
    for strategies, window, cost, purpose, note, st in rows:
        if args.dry_run:
            print("  would record %-34s %-10s %s" % (strategies[0][:34], purpose, note))
            continue
        tid = L.record_trial(
            strategies=strategies, window=window, pls=[], cost=cost,
            purpose=purpose, note=note,
            extra={"backfilled": True,
                   "series_retained": False,
                   "reported_trades": st.get("n") or st.get("trades"),
                   "reported_pf": st.get("pf") or st.get("profit_factor"),
                   "reported_net": st.get("net"),
                   "reported_win_pct": st.get("win") or st.get("win_rate")})
        if tid:
            added += 1

    after = L.count_trials()
    print("\nrecorded %d new, ledger now holds %d documented trials"
          % (after - before, after))

    floor = sum(n for n, _ in UNDOCUMENTED)
    print("\nnot itemisable (result files kept only aggregates):")
    for n, what in UNDOCUMENTED:
        print("   %4d  %s" % (n, what))
    print("   ----")
    print("   %4d  floor for pre-ledger trials" % floor)
    print("\nHONEST TRIAL COUNT: at least %d (%d documented + %d aggregate-only)"
          % (after + floor, after, floor))

    eff = L.effective_trials()
    print("\neffective-trial correction: %s"
          % (eff.get("note") or ("k_eff = %s" % eff.get("k_eff"))))
    print("(expected: refused. Backfilled trials have no series, which is the "
          "gap that caused this whole problem.)")

    backfill_windows(args.dry_run)
    print("\n" + L.spend_report())
    return 0


# Which windows this project has already decided on, from the pre-registrations.
# Guarded on (window, purpose) so re-running the backfill adds nothing.
WINDOW_SPENDS = [
    ("2004-2016", W_SELECT, "select",
     "PREREG_EntrySearch_2026-11-07: 21 candidates ranked here"),
    ("2016-2022", W_CONFIRM, "confirm",
     "PREREG_EntrySearch_2026-11-07: 2 finalists judged here"),
    ("2016-2022", W_CONFIRM, "test",
     "PREREG_VolTiming_2026-11-09: 16 arms judged here"),
    ("2004-2022", W_HOLDOUT, "judge",
     "PREREG_EighteenYearHoldout_2026-11-07: the live 4 legs judged here"),
    ("2022-2026", (utc(2022, 8, 1), utc(2026, 11, 1)), "select",
     "48-strategy screen + 60-cell stop/target sweep + 8 closed hypotheses"),
]


def backfill_windows(dry_run: bool) -> None:
    print("\nwindow spends:")
    for name, (a, b), purpose, reason in WINDOW_SPENDS:
        already = [h for h in L.window_history(name)
                   if h.get("purpose") == purpose]
        if already:
            print("   %-12s %-10s already recorded" % (name, purpose))
            continue
        if dry_run:
            print("   %-12s %-10s would record" % (name, purpose))
            continue
        # allow_respend because the history being recorded genuinely contains
        # repeat decisions on 2016-2022 and 2022-2026. Hiding that would defeat
        # the purpose of the ledger.
        L.spend_window(name, a, b, purpose, allow_respend=True,
                       reason="backfilled 2026-11-09 from the registry: " + reason)
        print("   %-12s %-10s recorded" % (name, purpose))


if __name__ == "__main__":
    raise SystemExit(main())
