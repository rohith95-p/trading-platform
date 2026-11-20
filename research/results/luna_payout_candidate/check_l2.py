"""Reconcile native Luna deals and inspect the first evaluation attempt tick by tick."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from scripts.research.luna_six_month_audit import portfolio_states, read_report, stamp
from src.backtesting.metrics import closed_balance_metrics, drop_best_worst, monte_carlo_paths, pnl_ratios


def check(report, cache, start, end, *, allowed_tick_count_delta=0, phase="evaluation"):
    metrics, deals = read_report(report)
    times, longs, shorts, cash, balances = portfolio_states(deals)
    assert deals and {row["symbol"] for row in deals} == {"XAUUSDm.L48"}
    realized = [d["profit"] + d["swap"] + d["fee"] for d in deals if d["action"] == "out"]
    entries = [d for d in deals if d["action"] == "in"]
    target = next((d for d in deals if d["action"] == "out" and d["balance"] >= 5150), None)
    funded = phase == "funded"
    events = {"target": stamp(target["ts"] * 1000)} if target and not funded else {}
    crossings = {}
    opened = [pd.Timestamp(d["ts"], unit="s", tz="UTC") for d in entries]
    for first, second in zip([start, *opened], [*opened, end]):
        if second - first >= pd.Timedelta(days=30):
            events["inactivity"] = (first + pd.Timedelta(days=30)).isoformat()
            break
    peak = previous = anchor = 5000.
    worst_floating = 0.
    worst_daily = 0.
    max_volume = 0.
    last_day = None
    tick_count = 0
    money_days = {}
    for d in deals:
        day = stamp(d["ts"] * 1000)[:10]
        money_days[day] = money_days.get(day, 0.) + d["profit"] + d["swap"] + d["fee"]
    for month in pd.period_range(start.strftime("%Y-%m"), (end - pd.Timedelta(seconds=1)).strftime("%Y-%m"), freq="M"):
        number = month.ordinal - pd.Period("2022-09", "M").ordinal + 1
        feed = np.memmap(cache / f"ticks{number}.bin", mode="r",
                         dtype=[("ms", "<i8"), ("bid", "<f8"), ("ask", "<f8")])
        lo_ms = int(start.timestamp() * 1000)
        hi_ms = int(end.timestamp() * 1000)
        first, last = feed["ms"].searchsorted([lo_ms, hi_ms], side="left")
        for i in range(first, last, 250000):
            q = feed[i:min(i+250000, last)]
            t = q["ms"]
            ix = times.searchsorted(t, side="right") - 1
            eq = cash[ix] + longs[ix] * q["bid"] - shorts[ix] * q["ask"]
            tick_count += len(t)
            worst_floating = max(worst_floating, float((balances[ix] - eq).max()))
            max_volume = max(max_volume, float((longs[ix] + shorts[ix]).max()) / 100.)
            parts = np.r_[0, np.flatnonzero(np.diff(t // 86400000)) + 1, len(t)]
            for lo, hi in zip(parts[:-1], parts[1:]):
                day = t[lo] // 86400000
                if last_day != day:
                    anchor, last_day = previous, day
                e = eq[lo:hi]
                peaks = np.maximum.accumulate(np.maximum(peak, e))
                checks = [("daily", e < anchor * (.97 if funded else .95)),
                          ("trailing", e < peaks * (.94 if funded else .90))]
                if funded:
                    checks.append(("protector", balances[ix[lo:hi]] - e >= 100))
                for label, mask in checks:
                    if label not in events and mask.any():
                        offset = int(mask.argmax())
                        quote = lo + offset
                        events[label] = stamp(t[quote])
                        crossings[label] = dict(equity=float(e[offset]), balance=float(balances[ix[quote]]),
                                                reference_equity=float(anchor), peak_equity=float(peaks[offset]))
                worst_daily = max(worst_daily, anchor - float(e.min()))
                peak, previous = float(peaks[-1]), float(e[-1])
    assert abs(tick_count - int(metrics["Ticks"].replace(" ", ""))) <= allowed_tick_count_delta, (
        tick_count, metrics["Ticks"]
    )
    assert abs(float(metrics["Total Net Profit"].replace(" ", "")) - deals[-1]["balance"] + 5000.) < .01
    # The project measures these ratios on closed-trade P&L. Grid entries can
    # share the same basket; iid reshuffling is a descriptive sensitivity only.
    closures = [d for d in deals if d["action"] == "out"]
    samples = [SimpleNamespace(net_pl=pnl, entry_time=int(d["ts"]), exit_time=int(d["ts"]))
               for pnl, d in zip(realized, closures)]
    ratios = pnl_ratios(realized)
    risk = dict(closed_trades=ratios, omega_at_zero=ratios["profit_factor"],
                closed_balance=closed_balance_metrics(samples, [], 5000., start_ts=start.timestamp(),
                                                      end_ts=end.timestamp()),
                shuffled_closed_trades=monte_carlo_paths(samples, 5000.), ablation=drop_best_worst(samples))
    return dict(metrics=metrics, evaluation_first_event=min(events, key=lambda k: events[k], default="pending"),
                events=events, crossings=crossings, max_floating_loss=round(worst_floating, 2), max_daily_loss=round(worst_daily, 2),
                max_open_lots=round(max_volume, 2), max_order_lots=max(d["volume"] for d in entries),
                months=str(start.date()) + " to " + str(end.date()) + " exclusive",
                tick_count=tick_count, wins=sum(x > 0 for x in realized),
                trade_expectancy=round(sum(realized)/len(realized), 3),
                pnl_without_best=round(sum(realized)-max(realized), 2),
                full_window_days_at_least_25_before_deductions=sum(round(v, 2) >= 25 for v in money_days.values()),
                risk_metrics=risk, deals=deals)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("report", "cache", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("start")
    parser.add_argument("end")
    args = parser.parse_args()
    result = check(args.report, args.cache, pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC"))
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "deals"}, indent=2))
