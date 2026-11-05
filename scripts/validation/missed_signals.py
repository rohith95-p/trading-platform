"""Every signal the live legs allowed, against every order the account actually got.

The question this answers: has the bot ever been handed a tradeable signal and
failed to place the order? That happened on 2026-11-03 and was only found by
hand. This finds all of them.

For each candle in the window it runs the four live strategy objects on exactly
the bars they would have seen, applies the daily trend gate as it stood that day,
applies the Highlander rule (one order per candle), and then looks for a matching
entry deal on the account. An allowed signal with no deal is a miss.

    python -I scripts/validation/missed_signals.py --days 14

Read-only: it places nothing and writes nothing but its own report.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUT = os.path.join("research", "results", "missed_signals.json")
IST = dt.timedelta(hours=5, minutes=30)


def live_from(class_name: str) -> int:
    """When this leg first entered the live portfolio, from git.

    Without this the audit replays TODAY's four legs over history and reports
    every signal from before a leg existed as a missed trade. London Momentum
    and NY Session Reversal only joined on 2026-10-29; three of the four "misses"
    in the first run of this script were signals from before that.

    The commit time is an upper bound on when the leg could have been trading --
    the VPS is updated after a commit, never before it -- which is all this
    needs to be safe.
    """
    import subprocess

    out = subprocess.run(
        ["git", "log", "--reverse", "--format=%ct", "-S", class_name, "--",
         "src/strategies/portfolio_atlas.py"],
        capture_output=True, text=True).stdout.split()
    return int(out[0]) if out else 0


def ema(x, period):
    out = np.full(len(x), np.nan, dtype=float)
    if len(x) >= period:
        k = 2.0 / (period + 1.0)
        out[period - 1] = np.mean(x[:period])
        for i in range(period, len(x)):
            out[i] = (x[i] - out[i - 1]) * k + out[i - 1]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--symbol", default=os.environ.get("ULTRA_SYMBOL", "XAUUSDm"))
    args = ap.parse_args()

    import MetaTrader5 as mt5

    from src.core import conviction
    from src.strategies.portfolio_atlas import PORTFOLIO

    if not mt5.initialize():
        print(f"MT5 initialize() failed: {mt5.last_error()}")
        return 1
    try:
        now = dt.datetime.now(dt.timezone.utc)
        start = now - dt.timedelta(days=args.days)
        # range requests, so the terminal downloads what it is missing
        m15 = mt5.copy_rates_range(args.symbol, mt5.TIMEFRAME_M15,
                                   start - dt.timedelta(days=45), now + dt.timedelta(hours=2))
        d1 = mt5.copy_rates_range(args.symbol, mt5.TIMEFRAME_D1,
                                  start - dt.timedelta(days=200), now + dt.timedelta(hours=2))
        if m15 is None or len(m15) < 300 or d1 is None or len(d1) < 21:
            print("not enough history; open an XAUUSDm chart in MT5 and retry")
            return 1

        deals = mt5.history_deals_get(int(start.timestamp()) - 86400,
                                      int(now.timestamp()) + 3600) or []
        entries = [d for d in deals if d.symbol == args.symbol and d.entry == 0]
        print(f"account: {len(entries)} entry deals in the window")
        # the candle each entry belongs to
        by_candle = {}
        for d in entries:
            by_candle.setdefault((int(d.magic), int(d.time) // 900 * 900), d)

        strategies = [c() for c in PORTFOLIO]
        since = {}
        print("each leg's earliest possible live date (first commit into the portfolio):")
        for c in PORTFOLIO:
            inst = c()
            ts = live_from(c.__name__)
            since[inst.name] = ts
            print(f"   {inst.name:26s} "
                  f"{dt.datetime.utcfromtimestamp(ts):%Y-%m-%d %H:%M} UTC" if ts
                  else f"   {inst.name:26s} unknown")
        print()
        t = m15["time"].astype(np.int64)
        dt1 = d1["time"].astype(np.int64)
        d1c = d1["close"].astype(float)

        def gate_for(day: int):
            prior = np.nonzero(dt1 // 86400 < day)[0]
            if len(prior) < 20:
                return None
            cc = d1c[: prior[-1] + 1]
            e = ema(cc, 20)
            if np.isnan(e[-1]):
                return None
            return "BULLISH" if cc[-1] > e[-1] else "BEARISH"

        rows, misses = [], []
        first = int(start.timestamp())
        for i in range(250, len(t) - 1):
            if t[i] < first:
                continue
            gate = gate_for(int(t[i]) // 86400)
            view = m15[: i + 2]
            fired = []
            for s in strategies:
                try:
                    sig = s.evaluate(view, None)
                except Exception:
                    continue
                if sig is None:
                    continue
                if int(t[i]) < since.get(s.name, 0):
                    rows.append(dict(candle=int(t[i]), strategy=s.name,
                                     side="BUY" if sig.is_buy else "SELL",
                                     gate=gate, outcome="not live yet"))
                    continue
                allowed = not ((sig.is_buy and gate == "BEARISH")
                               or (not sig.is_buy and gate == "BULLISH")
                               or gate is None)
                fired.append((s, sig, allowed))
            allowed_pairs = [(s, sig) for s, sig, ok in fired if ok]
            if not allowed_pairs:
                for s, sig, _ in fired:
                    rows.append(dict(candle=int(t[i]), strategy=s.name,
                                     side="BUY" if sig.is_buy else "SELL",
                                     gate=gate, outcome="blocked_by_gate"))
                continue
            # one order per candle, same rule the live loop uses
            (best_s, best_sig), losers = conviction.pick(allowed_pairs)
            for s, sig in losers:
                rows.append(dict(candle=int(t[i]), strategy=s.name,
                                 side="BUY" if sig.is_buy else "SELL",
                                 gate=gate, outcome="lost_highlander"))
            # the live loop fills on the NEXT candle's first minute
            fill_candle = int(t[i + 1])
            got = by_candle.get((int(best_s.magic), fill_candle))
            row = dict(candle=int(t[i]), fill_candle=fill_candle, strategy=best_s.name,
                       magic=int(best_s.magic), side="BUY" if best_sig.is_buy else "SELL",
                       gate=gate, outcome="traded" if got else "NO ORDER",
                       ticket=int(got.position_id) if got else None)
            rows.append(row)
            if not got:
                misses.append(row)

        print()
        hdr = f"{'candle (UTC)':17s} {'IST':6s} {'strategy':26s} {'side':4s} {'gate':8s} outcome"
        print(hdr)
        print("-" * len(hdr))
        for r in rows:
            c = dt.datetime.utcfromtimestamp(r["candle"])
            print(f"{c:%Y-%m-%d %H:%M}  {(c + IST):%H:%M}  {r['strategy']:26s} "
                  f"{r['side']:4s} {str(r['gate']):8s} {r['outcome']}"
                  + (f" #{r['ticket']}" if r.get("ticket") else ""))

        traded = [r for r in rows if r["outcome"] == "traded"]
        print(f"\nsignals that cleared every gate : {len(traded) + len(misses)}")
        print(f"  of those, orders on the account: {len(traded)}")
        print(f"  of those, MISSED               : {len(misses)}")
        for r in misses:
            c = dt.datetime.utcfromtimestamp(r["candle"])
            print(f"     MISSED {r['strategy']} {r['side']} on candle "
                  f"{c:%Y-%m-%d %H:%M} UTC ({(c + IST):%H:%M} IST)")
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(dict(generated_utc=now.strftime("%Y-%m-%d %H:%M:%S"), days=args.days,
                       rows=rows, misses=misses), open(OUT, "w"), indent=1)
        print(f"\nwritten to {OUT}")
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
