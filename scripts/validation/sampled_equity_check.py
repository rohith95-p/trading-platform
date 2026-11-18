"""Independent sampled mark arithmetic; does not import the backtest engine."""
from math import isclose

import numpy as np

from scripts.validation.execution_audit_helpers import swap_charge


def verify_samples(samples, trades, m1, costs, spec, start_balance, reported_dd):
    """Reconcile no-cashflow benchmark samples to input quotes and trade records.

    This verifies sampled arithmetic and observed quote provenance, not tick
    ordering, actual ask prices or independent production signal equivalence.
    """
    errors = []
    tickets = {int(t["ticket"]): t for t in trades}
    rows = {int(row["time"]): row for row in m1}
    point = spec["point"]
    value = spec["trade_tick_value"] / spec["trade_tick_size"]
    previous = None
    for i, sample in enumerate(samples):
        ts, phase = sample["time"], sample["phase"]
        if previous is not None and ts < previous:
            errors.append([i, "time_order"])
        previous = ts
        origin = ts - 60 if phase == "interval_end" else ts
        if phase == "final_settlement":
            bid, ask = samples[i-1]["bid"], samples[i-1]["ask"]
        elif origin in rows:
            row = rows[origin]
            bid = float(row["close"] if phase == "interval_end" else row["open"])
            spread = float(row["spread"])
            if costs.get("spread_source", "bar") != "bar" or not np.isfinite(spread) or spread <= 0:
                spread = costs["fixed_spread_points"]
            ask = bid + spread * point * costs.get("spread_multiplier", 1.)
        else:
            errors.append([i, "quote_missing"])
            continue
        expected = {"bid": bid, "ask": ask}
        floating, swaps, reserve = 0., 0., 0.
        active = {int(p["ticket"]) for p in sample["positions"]}
        for position in sample["positions"]:
            trade = tickets.get(int(position["ticket"]))
            if trade is None or any(position[key] != trade[key] for key in
                                    ("is_buy", "lots", "entry_time", "entry_price")):
                errors.append([i, "position_trade_identity"])
                continue
            mark = bid if position["is_buy"] else ask
            pnl = (mark-position["entry_price"]) * (1 if position["is_buy"] else -1) * value * position["lots"]
            swap = swap_charge({**trade, "exit_time": ts}, costs, point, value)
            commission = costs.get("commission_per_lot_roundtrip", 0.) * position["lots"]
            for key, expected_value in (("mark_price", mark), ("floating_pl", pnl),
                                        ("accrued_swap", swap), ("pending_commission", commission)):
                if not isclose(position[key], expected_value, abs_tol=1e-7):
                    errors.append([i, "position_"+key])
            floating += pnl
            swaps += swap
            reserve += commission
        realized = []
        for trade in trades:
            ex, en = trade["exit_time"], trade["entry_time"]
            if phase == "final_settlement":
                settled = True
            elif phase == "interval_end":
                settled = ex < ts and trade["exit_reason"] != "END_OF_DATA"
            elif phase == "open":
                settled = ex < ts
            else:
                settled = (ex < ts or (ex == ts and int(trade["ticket"]) not in active
                           and trade["exit_reason"] != "END_OF_DATA"
                           and (en < ts or trade["exit_reason"] not in ("SL", "TP"))))
            if settled:
                realized.append(trade["net_pl"])
        cash = start_balance + sum(realized)
        expected.update(balance=cash, floating_pl=floating, accrued_swap=swaps,
                        pending_commission=reserve, gross_equity=cash+floating,
                        net_liquidation_equity=cash+floating+swaps-reserve)
        for key, expected_value in expected.items():
            if not isclose(sample[key], expected_value, abs_tol=1e-7):
                errors.append([i, key])
    recomputed = {}
    for key in ("gross_equity", "net_liquidation_equity"):
        series = np.array([start_balance] + [s[key] for s in samples], dtype=float)
        peak = np.maximum.accumulate(series)
        dd = peak-series
        pct = np.divide(dd, peak, out=np.zeros_like(dd), where=peak > 0) * 100.
        recomputed[key] = {"maximum_usd": float(dd.max()), "maximum_pct": float(pct.max())}
        for field, value_ in recomputed[key].items():
            if not isclose(value_, reported_dd[key][field], abs_tol=1e-7):
                errors.append([-1, key+"_"+field])
    return {"samples": len(samples), "trades": len(trades), "errors": len(errors),
            "examples": errors[:20], "drawdown": recomputed,
            "scope": "no-cashflow M1 mark arithmetic; not real-tick or signal validation"}
