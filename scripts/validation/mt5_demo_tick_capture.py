"""Read-only historical MT5 quote capture, pinned to an explicitly named demo.

This module never logs in, changes terminal settings, selects symbols, or sends
orders. Importing it does not import/connect MetaTrader5. Historical output is
strictly before the existing 2026-11-01 holdout and at most one UTC day.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import numpy as np

HOLDOUT_MS = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()*1000)
TICK_DTYPE = np.dtype([("time_msc", "i8"), ("bid", "f8"), ("ask", "f8")])


def validate_quotes(ticks, start_ms, end_ms):
    if not len(ticks):
        raise ValueError("No tick observations; empty capture is not verification")
    if not {"time_msc", "bid", "ask"}.issubset(ticks.dtype.names or ()):
        raise ValueError("Timestamped bid/ask quote fields required")
    times = ticks["time_msc"]
    if np.any(times < start_ms) or np.any(times >= end_ms):
        raise ValueError("Quote timestamp outside requested half-open interval")
    if np.any(np.diff(times) < 0):
        raise ValueError("Tick order is not monotonic; do not sort away feed defects")
    if not np.isfinite(ticks["bid"]).all() or not np.isfinite(ticks["ask"]).all():
        raise ValueError("Nonfinite quote")
    if np.any(ticks["bid"] <= 0) or np.any(ticks["ask"] < ticks["bid"]):
        raise ValueError("Nonpositive or crossed bid/ask quote")


def validate_window(start, end):
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Explicit timezone required; use UTC Z suffix")
    lo, hi = int(start.timestamp()*1000), int(end.timestamp()*1000)
    if not 0 < hi-lo <= 86400*1000 or hi > HOLDOUT_MS:
        raise ValueError("Require positive <=24h window entirely before the holdout")
    return lo, hi


def require_demo(api, expected_login, expected_server):
    account = api.account_info()
    if expected_login <= 0 or not expected_server:
        raise ValueError("Explicit positive expected login and exact demo server required")
    if (account is None or account.trade_mode != api.ACCOUNT_TRADE_MODE_DEMO
            or int(account.login) != expected_login or account.server != expected_server):
        raise RuntimeError("Connected account is not the explicitly pinned demo identity")
    return account


def require_running_terminal(terminal_path, processes):
    """Never let initialize launch an unknown terminal and its attached EAs."""
    expected = os.path.normcase(os.path.abspath(terminal_path))
    if not any(record.get("exe") and
               os.path.normcase(os.path.abspath(record["exe"])) == expected for record in processes):
        raise RuntimeError("Open the intended demo terminal manually first; capture will not launch one")


def capture(api, *, expected_login, expected_server, symbol, start, end):
    lo, hi = validate_window(start, end)
    if symbol not in ("XAUUSD", "XAUUSDm"):
        raise ValueError("Only XAUUSD / XAUUSDm capture is allowed")
    account = require_demo(api, expected_login, expected_server)
    info = api.symbol_info(symbol)
    if info is None:
        raise RuntimeError("Symbol unavailable; configure intended demo terminal manually")
    raw = api.copy_ticks_range(symbol, start.astimezone(timezone.utc),
                               end.astimezone(timezone.utc), api.COPY_TICKS_ALL)
    require_demo(api, expected_login, expected_server)  # account switching fails closed
    if raw is None:
        raise RuntimeError("Historical tick capture failed")
    if not {"time_msc", "bid", "ask"}.issubset(raw.dtype.names or ()):
        raise ValueError("Terminal did not supply millisecond bid/ask quotes")
    if np.any(raw["time_msc"] < lo) or np.any(raw["time_msc"] > hi):
        raise ValueError("Terminal returned quotes outside requested boundaries; verify server time")
    # MT5 range end may be inclusive. Enforce our declared exclusive boundary;
    # record boundary clipping without deleting malformed observations inside it.
    keep = (raw["time_msc"] >= lo) & (raw["time_msc"] < hi)
    ticks = np.empty(int(keep.sum()), dtype=TICK_DTYPE)
    for key in TICK_DTYPE.names:
        ticks[key] = raw[key][keep]
    validate_quotes(ticks, lo, hi)
    spec_fields = ("digits", "point", "trade_tick_size", "trade_tick_value",
                   "trade_contract_size", "volume_min", "volume_max", "volume_step")
    metadata = {"source": "MT5 read-only historical demo quotes", "symbol": symbol,
                "identity_verified_demo": True,
                "identity_sha256": hashlib.sha256(f"{account.login}@{account.server}".encode()).hexdigest(),
                "server": account.server, "start_ms": lo, "end_ms_exclusive": hi,
                "rows": len(ticks), "raw_rows": len(raw), "boundary_rows_excluded": int((~keep).sum()),
                "spec_observed_at_capture_not_historical": {key: getattr(info, key, None) for key in spec_fields},
                "first_ms": int(ticks["time_msc"][0]), "last_ms": int(ticks["time_msc"][-1]),
                "duplicate_timestamp_rows": int(np.sum(np.diff(ticks["time_msc"]) == 0)),
                "largest_observed_gap_ms": int(np.diff(ticks["time_msc"]).max()) if len(ticks) > 1 else None,
                "orders_sent": 0, "holdout_accessed": False,
                "limitations": "Quote availability, timestamp convention and broker history completeness require reconciliation; current contract spec is not historical fee calibration."}
    return ticks, metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-login", type=int, required=True)
    parser.add_argument("--expected-server", required=True)
    parser.add_argument("--symbol", choices=("XAUUSD", "XAUUSDm"), default="XAUUSDm")
    parser.add_argument("--terminal-path", type=Path, required=True, help="Executable of an already-running intended demo terminal")
    parser.add_argument("--start", required=True, help="UTC ISO timestamp, e.g. 2025-01-06T12:00:00Z")
    parser.add_argument("--end", required=True, help="Exclusive UTC ISO timestamp")
    parser.add_argument("--out", type=Path, required=True, help="New .npy path; refuses overwrites")
    args = parser.parse_args()
    start, end = [datetime.fromisoformat(x.replace("Z", "+00:00")) for x in (args.start, args.end)]
    validate_window(start, end)
    if args.out.suffix != ".npy" or args.out.exists() or args.out.with_suffix(".json").exists():
        raise ValueError("New .npy and manifest paths required")
    import psutil
    running = []
    for process in psutil.process_iter(["exe"]):
        try:
            running.append(process.info)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    require_running_terminal(args.terminal_path, running)
    import MetaTrader5 as mt5  # deferred; importing/testing the module never connects
    if not mt5.initialize(str(args.terminal_path)):
        raise RuntimeError("Cannot attach to the intended demo MT5 terminal")
    try:
        ticks, metadata = capture(mt5, expected_login=args.expected_login,
                                  expected_server=args.expected_server, symbol=args.symbol,
                                  start=start, end=end)
    finally:
        mt5.shutdown()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("xb") as stream:
        np.save(stream, ticks, allow_pickle=False)
    metadata["sha256"] = hashlib.sha256(args.out.read_bytes()).hexdigest()
    with args.out.with_suffix(".json").open("x", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
