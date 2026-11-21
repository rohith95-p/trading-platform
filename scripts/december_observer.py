"""Observe the frozen two-strategy demo candidate through the MT5 read API."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time

import numpy as np
import psutil

from scripts.demo_preflight import ReadOnlyTerminal
from scripts.validation.mt5_demo_tick_capture import TICK_DTYPE, validate_quotes
from src.strategies.asian_range_filtered import AsianRangeFilteredV6
from src.strategies.london_momentum_tight import LondonMomentumTightV6


SYMBOL = "XAUUSDm"
SCAN_MINUTES = {435: AsianRangeFilteredV6, 735: LondonMomentumTightV6}
HOUR = 3600
START = int(datetime(2026, 11, 20, 18, 30, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 12, 15, 18, 30, tzinfo=timezone.utc).timestamp())
CAPTURE_START = START // HOUR * HOUR
CAPTURE_END = (END + HOUR - 1) // HOUR * HOUR


def capture_hour(api, directory, start, ticks_all):
    """Save exactly one completed UTC hour with original tick ordering."""
    end = start + HOUR
    raw = api.copy_ticks_range(SYMBOL, datetime.fromtimestamp(start, timezone.utc),
                               datetime.fromtimestamp(end, timezone.utc), ticks_all)
    if raw is None:
        raise ValueError("tick history unavailable")
    if not set(TICK_DTYPE.names).issubset(raw.dtype.names or ()):
        raise ValueError("tick history fields unavailable")
    times = raw["time_msc"]
    if ((times < start * 1000) | (times > end * 1000)).any():
        raise ValueError("tick history outside requested hour")
    selected = raw[times < end * 1000]
    rows = np.empty(len(selected), dtype=TICK_DTYPE)
    for field in TICK_DTYPE.names:
        rows[field] = selected[field]
    if len(rows):
        validate_quotes(rows, start * 1000, end * 1000)
    temporary = directory / f"{start}.tmp"
    with temporary.open("wb") as stream:
        np.save(stream, rows, allow_pickle=False)
    temporary.replace(directory / f"{start}.npy")
    return len(rows)


def valid_rates(rates, length):
    if rates is None or len(rates) != length or not rates.dtype.names:
        return False
    required = {"time", "open", "high", "low", "close", "tick_volume"}
    if not required.issubset(rates.dtype.names):
        return False
    columns = [rates[name] for name in required]
    return (
        all(np.isfinite(column).all() for column in columns)
        and all((rates[name] > 0).all() for name in ("open", "high", "low", "close"))
        and (rates["tick_volume"] >= 0).all()
        and (np.diff(rates["time"]) > 0).all()
        and (rates["high"] >= np.maximum(rates["open"], rates["close"])).all()
        and (rates["low"] <= np.minimum(rates["open"], rates["close"])).all()
    )


def inspect(api, now, expected_login, expected_server, m15, d1):
    account, terminal = api.account_info(), api.terminal_info()
    if not account or not terminal or not terminal.connected:
        return {"status": "terminal_unavailable"}
    if account.trade_mode != 0 or account.login != expected_login or account.server != expected_server:
        return {"status": "demo_identity_mismatch"}
    if account.margin_mode != 2 or account.currency != "USD":
        return {"status": "contract_profile_mismatch"}
    positions, orders = api.positions_get(), api.orders_get()
    if positions is None or orders is None:
        return {"status": "exposure_query_unavailable"}
    quote, spec = api.symbol_info_tick(SYMBOL), api.symbol_info(SYMBOL)
    result = {"status": "observing", "demo_verified": True, "leverage": account.leverage,
              "positions": len(positions), "pending_orders": len(orders),
              "expected_funded_leverage": 50, "orders_enabled": False}
    if not quote or not spec or not all(
        math.isfinite(x) and x > 0 for x in (quote.bid, quote.ask, spec.point)
    ) or quote.ask < quote.bid:
        return {**result, "status": "quote_unavailable"}
    age = now.timestamp() - quote.time_msc / 1000
    if not 0 <= age <= 120:
        return {**result, "status": "quote_stale_or_clock_mismatch", "quote_age_seconds": round(age, 1)}
    result["quote_age_seconds"] = round(age, 1)
    if not START <= now.timestamp() < END:
        return result
    result.update(bid=quote.bid, ask=quote.ask)
    minute = now.hour * 60 + now.minute
    target = minute - minute % 15
    if now.weekday() >= 5 or target not in SCAN_MINUTES:
        return result
    expected = int(now.timestamp()) // 900 * 900
    rates = api.copy_rates_from_pos(SYMBOL, m15, 0, 7500)
    daily = api.copy_rates_from_pos(SYMBOL, d1, 0, 50)
    if not valid_rates(rates, 7500) or not valid_rates(daily, 50):
        return {**result, "status": "missing_or_invalid_history", "signal_block": expected}
    day = expected // 86400 * 86400
    if list(rates["time"][-2:]) != [expected - 900, expected] or daily["time"][-1] != day:
        return {**result, "status": "bar_clock_or_coverage_mismatch", "signal_block": expected}
    window_start = day if target == 435 else day + 420 * 60
    window_end = day + 360 * 60 if target == 435 else day + 720 * 60
    session_bars = rates["time"][(rates["time"] >= window_start) & (rates["time"] < window_end)]
    if not np.array_equal(session_bars, np.arange(window_start, window_end, 900)):
        return {**result, "status": "missing_session_bars", "signal_block": expected}
    signal = SCAN_MINUTES[target]().evaluate(rates)
    return {**result, "signal_block": expected, "raw_strategy_signal": signal.direction_str if signal else None,
            "strategy": SCAN_MINUTES[target].__name__}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--terminal", type=Path, required=True)
    p.add_argument("--expected-login", type=int, required=True)
    p.add_argument("--expected-server", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--once", action="store_true")
    args = p.parse_args()
    requested = os.path.normcase(str(args.terminal.resolve()))
    if not any(os.path.normcase(proc.info["exe"] or "") == requested
               for proc in psutil.process_iter(["exe"], ad_value="")):
        raise SystemExit("The selected MT5 terminal must already be running")
    import MetaTrader5 as mt5

    api = ReadOnlyTerminal(mt5)
    args.output.mkdir(parents=True, exist_ok=True)
    ticks = args.output / "ticks"
    ticks.mkdir(exist_ok=True)
    collected = {int(p.stem) for p in ticks.glob("*.npy") if p.stem.isdigit()}
    next_hour = CAPTURE_START
    if not api.initialize(str(args.terminal.resolve()), timeout=5000):
        raise SystemExit("The selected MT5 terminal refused a read-only connection")
    try:
        while True:
            now = datetime.now(timezone.utc)
            try:
                event = inspect(api, now, args.expected_login, args.expected_server,
                                mt5.TIMEFRAME_M15, mt5.TIMEFRAME_D1)
                for _ in range(6):
                    if next_hour + HOUR > min(int(now.timestamp()), CAPTURE_END) or not event.get("demo_verified"):
                        break
                    if next_hour not in collected:
                        event.update(captured_hour=next_hour,
                                     captured_ticks=capture_hour(api, ticks, next_hour, mt5.COPY_TICKS_ALL))
                    next_hour += HOUR
            except (RuntimeError, OSError, ValueError, TypeError, AttributeError) as error:
                event = {"status": "observation_error", "error_type": type(error).__name__,
                         "retry_from_hour": next_hour}
            event.update(timestamp=now.isoformat(), mode="read_only", orders_enabled=False)
            line = json.dumps(event, allow_nan=False) + "\n"
            with (args.output / "observations.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(line)
            pending = args.output / "status.tmp"
            pending.write_text(line, encoding="utf-8")
            pending.replace(args.output / "status.json")
            if args.once or event["status"] == "demo_identity_mismatch":
                print(line.strip())
                return 1 if event["status"] in {"demo_identity_mismatch", "terminal_unavailable"} else 0
            time.sleep(60 - time.time() % 60)
    finally:
        api.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
