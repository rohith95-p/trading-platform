"""Weekly paper-test review -- REAL_MONEY_READINESS.md I.9 + VI.1 + VI.3.

I.9's pass condition is "live-demo PF within 20% of backtest PF" over an 8-week
frozen-config run. That comparison was never automatable because nothing wrote
a machine-readable live record (trade_ledger.jsonl was dead) and nothing ran
the backtest over the matching date range. This does both:

  1. Pulls ACTUAL executed trades from the MT5 account (by portfolio_v4 magic
     numbers) for the period -- the broker's own deal history, not our logs,
     because the broker is the authority on what really filled.
  2. Runs the backtest over the identical date range at the live config.
  3. Compares them, and applies VI.3's divergence tripwire.

    python -m scripts.paper_test_review                # since paper test start
    python -m scripts.paper_test_review 2026-09-08 2026-09-15
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np

IST = timezone(timedelta(hours=5, minutes=30))
FREEZE_PATH = os.path.join("research", "paper_test_freeze.json")

# Live PORTFOLIO_V4 (2026-09-09, 3 legs) + the benched legs kept so an
# unexpected fill under an old magic still shows up in the review.
PORTFOLIO_MAGICS = {3012: "EMASTACK_LONDON_TIGHT",
                    3013: "FVG_NY_TIGHT",
                    3022: "FVG_NY_SWEEP_OR_VOID",
                    3011: "SQUEEZE_ASIA (benched)",
                    3014: "RANGEREJECTION_NY_TIGHT (benched)"}

# I.9 / VI.3 thresholds
PF_DIVERGENCE_TOLERANCE = 0.20   # live PF within 20% of backtest PF
TRIPWIRE_PAUSE_PF = 1.0          # rolling 30-trade live PF below this -> pause
TRIPWIRE_STOP_PF = 0.8           # below this -> full stop, re-validate


def _pf(pls: List[float]) -> float:
    arr = np.array(pls, dtype=float)
    if not len(arr):
        return 0.0
    w, l = arr[arr > 0], arr[arr < 0]
    return float(w.sum() / -l.sum()) if len(l) else float("inf")


def _summarise(pls: List[float]) -> Dict:
    arr = np.array(pls, dtype=float)
    if not len(arr):
        return dict(n=0, pf=0.0, net=0.0, win_rate=0.0)
    w = arr[arr > 0]
    return dict(n=int(len(arr)), pf=round(_pf(pls), 3), net=round(float(arr.sum()), 2),
                win_rate=round(float(len(w) / len(arr) * 100), 1))


def live_trades(start: datetime, end: datetime) -> List[Dict]:
    """Closed portfolio_v4 deals straight from the broker."""
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
    try:
        deals = mt5.history_deals_get(start, end) or []
        out = []
        for d in deals:
            if d.symbol != "XAUUSDm" or d.magic not in PORTFOLIO_MAGICS:
                continue
            if d.entry != 1:      # entry==1 is the closing deal, which carries P&L
                continue
            out.append(dict(ticket=d.ticket, magic=d.magic,
                            strategy=PORTFOLIO_MAGICS[d.magic],
                            profit=float(d.profit) + float(d.swap) + float(d.commission),
                            time=int(d.time)))
        return out
    finally:
        mt5.shutdown()


def backtest_trades(start: datetime, end: datetime) -> List[Dict]:
    """The same window through the engine at the CURRENT live config."""
    from src.backtesting.data import load_bars
    from src.backtesting.engine import BacktestEngine
    from src.backtesting.costs import SCENARIOS
    from src.strategies.portfolio_v4 import PORTFOLIO_V4
    from scripts.validation.part1_suite import live_config

    bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1", "H4"))
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic"], config=live_config())
    res = eng.run([c() for c in PORTFOLIO_V4],
                  start_ts=int(start.timestamp()), end_ts=int(end.timestamp()))
    return [dict(strategy=t.strategy, profit=float(t.net_pl), time=int(t.exit_time))
            for t in res.trades]


def freeze_record() -> Optional[Dict]:
    try:
        with open(FREEZE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def review(start: datetime, end: datetime) -> Dict:
    print(f"PAPER TEST REVIEW  {start:%Y-%m-%d} -> {end:%Y-%m-%d} (IST)\n")

    fz = freeze_record()
    if fz:
        print(f"Frozen config: {fz.get('fingerprint')}  (frozen {fz.get('frozen_at')})")
        try:
            from src.core.system_config import SystemConfig
            now_fp = SystemConfig.from_live().fingerprint()
            if now_fp != fz.get("fingerprint"):
                print(f"  *** CONFIG DRIFT: live is now {now_fp}, the test was frozen at "
                      f"{fz.get('fingerprint')}. The 8-week clock must restart. ***")
            else:
                print("  config unchanged since freeze -- clock still valid")
        except Exception as e:
            print(f"  (could not verify live fingerprint: {e})")
        print()

    try:
        live = live_trades(start, end)
    except Exception as e:
        print(f"Could not read live trades: {e}")
        live = []
    bt = backtest_trades(start, end)

    live_s = _summarise([t["profit"] for t in live])
    bt_s = _summarise([t["profit"] for t in bt])

    print(f"{'':14s} {'trades':>7} {'PF':>8} {'net$':>10} {'WR%':>7}")
    print(f"{'LIVE (demo)':14s} {live_s['n']:>7} {live_s['pf']:>8} {live_s['net']:>10} {live_s['win_rate']:>7}")
    print(f"{'BACKTEST':14s} {bt_s['n']:>7} {bt_s['pf']:>8} {bt_s['net']:>10} {bt_s['win_rate']:>7}")

    verdict = {}
    if live_s["n"] and bt_s["pf"]:
        div = abs(live_s["pf"] - bt_s["pf"]) / bt_s["pf"]
        ok = div <= PF_DIVERGENCE_TOLERANCE
        verdict["pf_divergence"] = round(div, 4)
        verdict["within_tolerance"] = bool(ok)
        print(f"\nI.9 divergence: {div:.1%} (bar: <= {PF_DIVERGENCE_TOLERANCE:.0%}) -> "
              f"{'PASS' if ok else 'FAIL'}")
    else:
        print("\nI.9 divergence: not computable yet (need live trades)")

    # VI.3 tripwire on the rolling 30 live trades
    if live:
        recent = [t["profit"] for t in sorted(live, key=lambda x: x["time"])][-30:]
        r_pf = _pf(recent)
        verdict["rolling30_pf"] = round(r_pf, 3)
        if len(recent) >= 30:
            if r_pf < TRIPWIRE_STOP_PF:
                state = "FULL STOP -- treat as edge decay, re-validate"
            elif r_pf < TRIPWIRE_PAUSE_PF:
                state = "PAUSE new entries, investigate"
            else:
                state = "OK"
            print(f"VI.3 tripwire: rolling-30 live PF = {r_pf:.3f} -> {state}")
            verdict["tripwire"] = state
        else:
            print(f"VI.3 tripwire: only {len(recent)} live trades, needs 30")

    per_leg = {}
    for name in PORTFOLIO_MAGICS.values():
        lp = [t["profit"] for t in live if t["strategy"] == name]
        bp = [t["profit"] for t in bt if t["strategy"] == name]
        if lp or bp:
            per_leg[name] = dict(live=_summarise(lp), backtest=_summarise(bp))
    if per_leg:
        print("\nper leg (live vs backtest):")
        for name, d in per_leg.items():
            print(f"  {name:26s} live n={d['live']['n']:3d} PF={d['live']['pf']:<6} "
                  f"| bt n={d['backtest']['n']:3d} PF={d['backtest']['pf']}")

    out = dict(window=[start.isoformat(), end.isoformat()], live=live_s,
               backtest=bt_s, verdict=verdict, per_leg=per_leg)
    os.makedirs("research/validation", exist_ok=True)
    path = f"research/validation/paper_review_{start:%Y%m%d}_{end:%Y%m%d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n--> {path}")
    return out


if __name__ == "__main__":
    if len(sys.argv) == 3:
        s = datetime.strptime(sys.argv[1], "%Y-%m-%d").replace(tzinfo=IST)
        e = datetime.strptime(sys.argv[2], "%Y-%m-%d").replace(tzinfo=IST)
    else:
        fz = freeze_record()
        if fz and fz.get("frozen_at"):
            s = datetime.fromisoformat(fz["frozen_at"]).astimezone(IST)
        else:
            s = datetime.now(IST) - timedelta(days=7)
        e = datetime.now(IST)
    review(s, e)
