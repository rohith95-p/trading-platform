"""Evaluate one frozen London signal and reconcile fills against Aurum v2."""
from collections import Counter
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd

if __name__ == "__main__":
    os.environ.update(ULTRA_DISABLE_ALERTS="1", ULTRA_TRADE_24H="1", ULTRA_NO_TRIAL_LEDGER="1")

from scripts.research.fomc_shock_propagation import event_bars, replay_one
from scripts.research.london_absorption_data import ARCHIVE, CACHE
from src.backtesting import master
from src.backtesting.costs import SCENARIOS

REVIEW = Path("research/external_review_20261120")
OUT = Path("research/registry/london_quote_absorption.json")


def absorption(w):
    """Return signed trade direction using only the 45 completed minutes."""
    first = (w["bid_open"][::15] + w["ask_open"][::15]) / 2
    last = (w["bid_close"][14::15] + w["ask_close"][14::15]) / 2
    a, b, c = last - first
    count = w["quotes"].reshape(3, 15).sum(axis=1)
    if a * b > 0 and count[1] >= 1.5 * count[0] and abs(b) <= abs(a) / 2 and b * c < 0 and abs(c) >= abs(b) / 2:
        return int(np.sign(c))
    return 0


def monthly_source(q, history, point):
    dtype = np.load("research/data/XAUUSDm_M1.npy", mmap_mode="r").dtype
    minute = np.zeros(len(q), dtype=dtype)
    minute["time"] = q["time"]
    minute["spread"] = np.rint((q["ask_open"] - q["bid_open"]) / point)
    minute["tick_volume"] = q["quotes"]
    for k in ["open", "high", "low", "close"]:
        minute[k] = q["bid_" + k]
    starts = np.where(minute["time"] % 900 == 0)[0]
    starts = starts[starts + 14 < len(minute)]
    starts = starts[minute["time"][starts + 14] - minute["time"][starts] == 840]
    quarter = minute[starts].copy()
    blocks = minute[starts[:, None] + np.arange(15)]
    quarter["high"] = blocks["high"].max(axis=1)
    quarter["low"] = blocks["low"].min(axis=1)
    quarter["close"] = blocks["close"][:, -1]
    quarter["tick_volume"] = blocks["tick_volume"].sum(axis=1)
    if history is not None:
        quarter = np.concatenate([history, quarter])
    folder = CACHE / "engine_source"
    folder.mkdir(parents=True, exist_ok=True)
    for tf, data in (("M1", minute), ("M15", quarter)):
        path = folder / ("XAUUSDm_" + tf)
        np.save(path, data)
        path.with_suffix(".manifest.json").write_text(json.dumps(dict(
            symbol="XAUUSDm", timeframe=tf, bars=len(data), sha256=hashlib.sha256(data.tobytes()).hexdigest())))
    source = master.Source("ExnessStandard", str(folder), ("M1", "M15"), 0, master.HOLDOUT_FROM)
    with patch.object(master, "MASTER_SOURCES", (source,)):
        bars = master.load_master(("M15", "M1"), use_cache=False)
    return bars, quarter[-350:].copy()


def external(w, trade, point):
    from aurum.data.schema import make_bars
    from aurum.execution.simulator import ExecutionSimulator
    from aurum.execution.costs import CostModel
    spread = w["spread"] * point
    mid = pd.DataFrame({k: w[k] + spread / 2 for k in ("open", "high", "low", "close")},
                       index=pd.to_datetime(w["time"], unit="s", utc=True))
    mid["spread"] = spread
    costs = CostModel(min_spread=0, slippage_fixed=.020, slippage_range_frac=0, commission_per_lot=1.75)
    sim = ExecutionSimulator(make_bars(mid, "M1"), costs=costs, initial_equity=5000)
    side = 1 if trade.is_buy else -1
    for i in range(1, len(w)):
        if i == 61:
            sim.step(0)
            break
        shift = side * spread[i] / 2
        step = sim.step(side * .02, stop_price=trade.initial_sl + shift, take_profit=trade.tp + shift)
        if step.exit_reason:
            break
    return sim.equity - 5000


def pullback(bars, entry, allow_maintenance):
    end = bars.m15["time"].searchsorted(entry)
    w = bars.m15[end-60:end]
    if len(w) != 60 or w["time"][-1] != entry - 900:
        return 0
    if np.max(np.diff(w["time"])) > (7200 if allow_maintenance else 900):
        return 0
    close = pd.Series(w["close"])
    fast = close.ewm(span=8, adjust=False).mean()
    slow = close.ewm(span=21, adjust=False).mean()
    side = int(np.sign(fast.iloc[-1] - slow.iloc[-1]))
    distance = side * (close - fast)
    return side if distance.iloc[-2] <= 0 < distance.iloc[-1] else 0


def main(public_pullback=False, allow_maintenance=False):
    sys.path.insert(0, str((REVIEW / "aurum").resolve()))
    base = SCENARIOS["realistic_ecn"]
    stress = replace(base, spread_multiplier=2., slippage_points=60.)
    months = sorted((CACHE / "payload/standard_m1").glob("*.npy")) + sorted((ARCHIVE / "payload/standard_m1").glob("2026-*.npy"))
    assert len(months) == 82
    totals = Counter()
    records = []
    history = None
    for path in months:
        if path.stem == "2026-01":
            history = None
        if hashlib.sha256(path.read_bytes()).hexdigest() != json.loads(path.with_suffix(".json").read_text())["sha256"]:
            raise ValueError(f"Unverified minute file {path}")
        q = np.load(path)
        point = master.master_spec().point
        bars, history = monthly_source(q, history, point)
        t = q["time"]
        clock = pd.to_datetime(t, unit="s", utc=True).tz_convert("Europe/London")
        entries = np.flatnonzero((clock.hour == 10) & (clock.minute == 0) & (clock.weekday < 5))
        for i in entries:
            entry = int(t[i])
            if i < 45 or not np.array_equal(t[i-45:i+62], entry + 60 * np.arange(-45, 62)):
                totals["missing minute window"] += 1
                continue
            if bars.m15["time"].searchsorted(entry) < 260:
                totals["missing warmup"] += 1
                continue
            direction = pullback(bars, entry, allow_maintenance) if public_pullback else absorption(q[i-45:i])
            if not direction:
                totals["no signal"] += 1
                continue
            sample = event_bars(bars, entry)
            row = dict(date=str(clock[i].date()), side=direction)
            for key, cost, side in (("base", base, direction), ("stress", stress, direction), ("control", base, -direction)):
                feature = dict(direction=side, latest_feature_close_time=entry)
                result, _ = replay_one(sample, entry-2700, feature, cost, 5000, "candidate")
                if not result.trades:
                    row[key] = None
                    continue
                trade, = result.trades
                row[key] = trade.net_pl
                if key == "base":
                    row.update(entry=trade.entry_price, exit=trade.exit_price, stop=trade.initial_sl,
                               target=trade.tp, reason=trade.exit_reason,
                               aurum=external(bars.m1[i-1:i+61], trade, point))
            records.append(row)
    output = OUT.with_name("public_gold_pullback.json") if public_pullback else OUT
    if allow_maintenance:
        output = OUT.with_name("public_gold_pullback_sessions.json")
    output.write_text(json.dumps(dict(counts=totals, records=records), indent=2))


if __name__ == "__main__":
    main(public_pullback="--public-pullback" in sys.argv, allow_maintenance="--maintenance" in sys.argv)
