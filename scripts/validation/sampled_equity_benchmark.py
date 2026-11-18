"""Fixed pre-holdout portfolio engineering replay; never strategy acceptance."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["ULTRA_TRADE_24H"] = "1"
os.environ["ULTRA_DISABLE_ALERTS"] = "1"

from src.backtesting.costs import SCENARIOS
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.master import load_master
from src.strategies.portfolio_atlas import PORTFOLIO
from scripts.validation.execution_audit_helpers import swap_charge
from scripts.validation.sampled_equity_check import verify_samples


def utc(*args):
    return int(datetime(*args, tzinfo=timezone.utc).timestamp())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    os.chdir(ROOT)
    output = ROOT / "research/results/sampled_equity_2026-11-18"
    if (output / "benchmark.json").exists():
        raise RuntimeError("Frozen benchmark already exists; do not silently overwrite evidence")
    output.mkdir(parents=True, exist_ok=True)
    start, end = utc(2026, 9, 1), utc(2026, 9, 15)
    paths = {Path(inspect.getfile(cls)).resolve() for cls in PORTFOLIO}
    paths.update(ROOT / path for path in (
        "src/strategies/base_strategy.py", "src/strategies/portfolio_atlas.py",
        "src/backtesting/engine.py", "src/backtesting/costs.py", "src/backtesting/data.py",
        "src/backtesting/master.py", "src/core/risk_manager.py",
        "scripts/validation/sampled_equity_benchmark.py",
        "scripts/validation/sampled_equity_check.py"))
    source_hashes = {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(paths)}
    print("Loading fixed 2026-09-01 to 2026-09-15 pre-holdout cache", flush=True)
    bars = load_master(("M15", "M1", "D1"), start=start, end=end)
    cfg = EngineConfig(symbol="XAUUSDm", starting_balance=5000., sizing_mode="fixed",
                       fixed_lots=.02, max_concurrent=3, max_same_direction=3,
                       history_bars=7500, live_exec_order=True, entry_delay_sec=0,
                       protect_profit=False, enable_trailing=False, enable_pyramiding=False,
                       gap_fill_stops=True, causal_minute_order=True, m1_policy="skip",
                       record_equity_samples=True)
    costs = SCENARIOS["realistic_ecn"]
    engine = BacktestEngine(bars, costs, cfg)
    result = engine.run([cls() for cls in PORTFOLIO], start, end)
    trades = [dataclasses.asdict(trade) for trade in result.trades]
    print(f"Replayed {len(trades)} trades and {len(result.equity_samples)} samples", flush=True)
    audit = verify_samples(result.equity_samples, trades, bars.m1, dataclasses.asdict(costs),
                           dataclasses.asdict(bars.spec), cfg.starting_balance,
                           result.diagnostics["sampled_drawdown"])
    trade_errors = []
    balance = cfg.starting_balance
    value = bars.spec.trade_tick_value / bars.spec.trade_tick_size
    for trade in trades:
        gross = ((trade["exit_price"]-trade["entry_price"]) * trade["lots"] * value
                 * (1 if trade["is_buy"] else -1))
        commission = costs.commission_per_lot_roundtrip * trade["lots"]
        swap = swap_charge(trade, dataclasses.asdict(costs), bars.spec.point, value)
        net = gross-commission+swap
        balance += net
        for key, expected in (("gross_pl", gross), ("commission", commission),
                               ("swap", swap), ("net_pl", net), ("balance_after", balance)):
            if abs(trade[key]-expected) > 1e-7:
                trade_errors.append([trade["ticket"], key])
    audit["trade_arithmetic_errors"] = trade_errors
    audit["source_files_unchanged_during_run"] = all(digest(ROOT/path) == sha for path, sha in source_hashes.items())
    winners = sum(t["net_pl"] for t in trades if t["net_pl"] > 0)
    losers = -sum(t["net_pl"] for t in trades if t["net_pl"] < 0)
    closed_peak = cfg.starting_balance
    closed_dd = 0.
    for trade in trades:
        closed_peak = max(closed_peak, trade["balance_after"])
        closed_dd = max(closed_dd, closed_peak-trade["balance_after"])
    payload = {"purpose": "engineering verification, not candidate qualification",
               "window_utc": ["2026-09-01T00:00:00Z", "2026-09-15T00:00:00Z"],
               "window_end_exclusive": True, "holdout_accessed": False,
               "parent_commit_at_run": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
               "code_sha256": source_hashes, "data_hash": result.data_hash,
               "config": result.config, "cost_model": dataclasses.asdict(costs),
               "symbol_spec": dataclasses.asdict(bars.spec), "diagnostics": result.diagnostics,
               "summary": {"trades": len(trades), "net_pl": sum(t["net_pl"] for t in trades),
                           "profit_factor": winners/losers if losers else None,
                           "closed_balance_max_drawdown_usd": closed_dd,
                           "sampled_drawdown": result.diagnostics["sampled_drawdown"]},
               "input_lengths_including_warmup": {"m1": len(bars.m1), "m15": len(bars.m15), "d1": len(bars.d1)},
               "audit": audit, "trades": trades,
               "limitations": ["short previously explored window; no independent alpha claim",
                               "M1 open/end samples miss intraminute adverse equity",
                               "ask reconstructed from bid plus bar spread",
                               "pending commission reserve and swap are configured assumptions",
                               "skip policy can censor missing-minute exposure",
                               "no full Atlas evaluation/funded/payout wrapper",
                               "native MT5/tick/demo execution reconciliation not performed"]}
    with gzip.open(output/"samples.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(result.equity_samples, stream, separators=(",", ":"), allow_nan=False)
    payload["samples_sha256"] = digest(output/"samples.json.gz")
    (output/"benchmark.json").write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2), flush=True)
    print(json.dumps(audit, indent=2), flush=True)
    if audit["errors"] or trade_errors or not audit["source_files_unchanged_during_run"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
