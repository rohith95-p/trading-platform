"""Independent arithmetic/first-hit check of saved FOMC engine trades.

Uses master data, never BacktestEngine fill/stop/cost functions. This checks the
declared bar model, not actual ticks, broker executions or account compliance.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtesting.master import load_master


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "research/results/finalization_2026-11-18/fomc_shock_propagation.json"


def independent_atr(a):
    tr = [float(a["high"][0] - a["low"][0])]
    for previous, current in zip(a[:-1], a[1:]):
        tr.append(max(float(current["high"] - current["low"]),
                      abs(float(current["high"] - previous["close"])),
                      abs(float(current["low"] - previous["close"]))))
    value = sum(tr[:14]) / 14
    for x in tr[14:]:
        value = (13 * value + x) / 14
    return value


def first_hit(rows, buy, sl, tp, deadline, point, multiple, slip):
    for row in rows:
        ts = int(row["time"])
        spread = (float(row["spread"]) or 260.) * point * multiple
        opening = float(row["open"]) + (0 if buy else spread)
        sl_open = opening <= sl if buy else opening >= sl
        tp_open = opening >= tp if buy else opening <= tp
        if sl_open:
            return ts, opening - slip if buy else opening + slip, "SL"
        if tp_open:
            return ts, tp, "TP"
        if ts == deadline:
            return ts, opening - slip if buy else opening + slip, "FOMC_FIXED_TIME"
        hit_sl = row["low"] <= sl if buy else row["high"] + spread >= sl
        hit_tp = row["high"] >= tp if buy else row["low"] + spread <= tp
        if hit_sl:
            return ts, sl - slip if buy else sl + slip, "SL"
        if hit_tp:
            return ts, tp, "TP"
    raise ValueError("no modeled exit by fixed deadline")


def main():
    report = json.loads(RESULT.read_text())
    bars = load_master(("M15", "M1"), start=int(pd.Timestamp("2015-12-01", tz="UTC").timestamp()),
                       end=int(pd.Timestamp("2026-01-01", tz="UTC").timestamp()), use_cache=False)
    if hashlib.sha256(bars.m1.tobytes()).hexdigest() != report["input_m1_sha256"]:
        raise ValueError("minute input changed")
    if hashlib.sha256(bars.m15.tobytes()).hexdigest() != report["input_m15_sha256"]:
        raise ValueError("M15 input changed")
    errors, checked, ambiguous = [], 0, 0
    point = bars.spec.point
    for name, result in report["results"].items():
        scenario = name.split("/")[1]
        multiplier, slip_points = (2., 60.) if scenario == "stress" else (1., 20.)
        slip = slip_points * point
        delay = result["additional_delay_seconds"]
        expected = {int(e["event_time"] + 45 * 60 + delay): e["event_time"] + 105 * 60 for e in result["event_cash"]}
        balance = 5000.
        for trade in result["trades"]:
            checked += 1
            entry = int(trade["entry_time"])
            if entry not in expected:
                errors.append(dict(result=name, entry=entry, error="entry_schedule"))
                continue
            deadline = expected[entry]
            left, right = np.searchsorted(bars.m1["time"], [entry, deadline])
            rows = bars.m1[left:right + 1]
            if not np.array_equal(rows["time"], np.arange(entry, deadline + 60, 60)):
                errors.append(dict(result=name, entry=entry, error="coverage"))
                continue
            buy = bool(trade["is_buy"])
            sign = 1 if buy else -1
            spread = (float(rows["spread"][0]) or 260.) * point * multiplier
            fill = float(rows["open"][0]) + (spread if buy else 0.) + sign * slip
            cutoff = entry - entry % 900
            closed_bars = bars.m15[bars.m15["time"] + 900 <= cutoff][-249:]
            atr = independent_atr(closed_bars)
            sl, tp = round(fill - sign * 2 * atr, 3), round(fill + sign * 4 * atr, 3)
            exit_ts, exit_px, reason = first_hit(rows, buy, sl, tp, deadline, point, multiplier, slip)
            gross = sign * (exit_px - fill) * bars.spec.value_per_price_unit_per_lot * trade["lots"]
            commission = 3.5 * trade["lots"]
            net = gross - commission  # Intraday event exposure never crosses UTC rollover.
            balance += net
            comparisons = dict(entry_price=fill, sl=sl, tp=tp, exit_price=exit_px,
                               gross_pl=gross, commission=commission, swap=0., net_pl=net, balance_after=balance)
            wrong = {field: dict(expected=value, actual=trade[field]) for field, value in comparisons.items()
                     if not np.isclose(value, trade[field], atol=1e-7, rtol=0)}
            if trade["exit_time"] != exit_ts or trade["exit_reason"] != reason:
                wrong["exit"] = dict(expected=[exit_ts, reason], actual=[trade["exit_time"], trade["exit_reason"]])
            if wrong:
                errors.append(dict(result=name, entry=entry, differences=wrong))
            ambiguous += bool(trade["intrabar_ambiguous"])
    output = dict(checked_scenario_trade_records=checked, errors=errors, ambiguous_scenario_records=ambiguous,
                  result_sha256=hashlib.sha256(RESULT.read_bytes()).hexdigest(),
                  auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  classification="Independent implementation of declared bar-model arithmetic; overlapping scenario records are not independent trades or broker/tick validation.")
    target = RESULT.with_name("fomc_shock_independent_audit.json")
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in output.items() if k != "errors"}), "errors", len(errors), flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
