"""Independent quote replay versus the real M1 engine on frozen engineering orders.

Default mode is explicitly SYNTHETIC. --ticks consumes a validated saved historical
capture; it never connects to a terminal and never infers alpha from fixture P&L.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.validation.mt5_demo_tick_capture import TICK_DTYPE, validate_quotes

START = int(datetime(2025, 1, 6, 12, tzinfo=timezone.utc).timestamp())
END = START+3600


def offline_quotes():
    """Toy quotes with known target/stop order and a short-side ask-only spike."""
    rows = [(1000*(START+60*minute), 2000., 2000.2) for minute in range(60)]
    rows.extend([(1000*(START+900)+200, 2002., 2002.2),
                 (1000*(START+900)+300, 1998., 1998.2),
                 (1000*(START+900)+400, 2000., 2000.2),
                 (1000*(START+1800)+200, 2000.5, 2001.5),
                 (1000*(START+1800)+300, 1998., 1998.2),
                 (1000*(START+1800)+400, 2000., 2000.2)])
    # Sorting constructs this artificial fixture only. Capture validation never
    # sorts real observations or discards duplicate timestamp order.
    return np.array(sorted(rows), dtype=TICK_DTYPE)


def tick_replay(ticks, *, signal_ms, is_buy, lots=.02, stop_distance=1., target_distance=1.5,
                slip=.02, commission_roundtrip_per_lot=3.5, balance=5000.):
    """Independent ordered-quote arithmetic, no engine protective/fill imports."""
    eligible = ticks[ticks["time_msc"] >= signal_ms]
    if not len(eligible):
        raise ValueError("No quote at or after frozen order timestamp")
    first = eligible[0]
    direction = 1 if is_buy else -1
    entry = float(first["ask"] if is_buy else first["bid"]) + direction*slip
    stop, target = entry-direction*stop_distance, entry+direction*target_distance
    commission = commission_roundtrip_per_lot*lots
    net_samples = [balance]
    closed = False
    trade = {}
    for quote in eligible:
        mark = float(quote["bid"] if is_buy else quote["ask"])
        stop_hit = mark <= stop if is_buy else mark >= stop
        target_hit = mark >= target if is_buy else mark <= target
        if not closed and (stop_hit or target_hit):
            reason = "SL" if stop_hit else "TP"
            fill = mark-direction*slip if stop_hit else target
            net = (fill-entry)*direction*100.*lots-commission
            trade = {"is_buy": is_buy, "lots": lots, "entry_time_ms": int(first["time_msc"]),
                     "exit_time_ms": int(quote["time_msc"]), "entry_price": entry,
                     "exit_price": fill, "sl": stop, "tp": target, "exit_reason": reason,
                     "commission": commission, "net_pl": net}
            closed = True
        if closed:
            equity = balance+trade["net_pl"]
        else:
            equity = balance+(mark-entry)*direction*100.*lots-commission
        net_samples.append(equity)
    if not closed:
        quote = eligible[-1]
        mark = float(quote["bid"] if is_buy else quote["ask"])
        fill = mark-direction*slip
        net = (fill-entry)*direction*100.*lots-commission
        trade = {"is_buy": is_buy, "lots": lots, "entry_time_ms": int(first["time_msc"]),
                 "exit_time_ms": int(quote["time_msc"]), "entry_price": entry,
                 "exit_price": fill, "sl": stop, "tp": target, "exit_reason": "END_OF_QUOTES",
                 "commission": commission, "net_pl": net}
        net_samples.append(balance+net)
    series = np.array(net_samples)
    peak = np.maximum.accumulate(series)
    return {"trade": trade, "quote_count": len(eligible),
            "observed_quote_net_liquidation_max_drawdown_usd": float(np.max(peak-series)),
            "scope": "observed bid/ask quotes, assumed constant slip/fees, no queue or broker fills"}


def minute_replay(ticks, *, signal_ts, is_buy):
    """Use actual BacktestEngine, with frozen non-alpha order/stop test doubles."""
    from src.backtesting.costs import SCENARIOS
    from src.backtesting.data import BarSet, SymbolSpec
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.core.risk_manager import StopLevels
    from src.strategies.base_strategy import Signal
    dtype = [("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
             ("close", "f8"), ("spread", "i4"), ("tick_volume", "i8"), ("real_volume", "i8")]
    minute = np.zeros(60, dtype=dtype)
    for i, ts in enumerate(range(START, END, 60)):
        rows = ticks[(ticks["time_msc"] >= ts*1000) & (ticks["time_msc"] < (ts+60)*1000)]
        if not len(rows):
            raise ValueError("Fixture M1 missing quotes; never pad")
        minute[i] = (ts, rows["bid"][0], rows["bid"].max(), rows["bid"].min(),
                     rows["bid"][-1], round((rows["ask"][0]-rows["bid"][0])/.001), len(rows), 0)
    m15 = np.zeros(4, dtype=dtype)
    for i in range(4):
        rows = minute[i*15:(i+1)*15]
        m15[i] = (rows["time"][0], rows["open"][0], rows["high"].max(), rows["low"].min(),
                  rows["close"][-1], rows["spread"][0], rows["tick_volume"].sum(), 0)
    spec = SymbolSpec("XAUUSDm", 3, .001, .001, .1, .01, 200., .01, 100.)
    bars = BarSet("XAUUSDm", m15, None, minute, None, spec, {})
    class FrozenOrder:
        name = "EXECUTION_FIXTURE"
        magic = 990099
        skip_d1_gate = True
        def evaluate(self, m15_rates, m5_rates=None):
            if int(m15_rates["time"][-1]) == signal_ts:
                return Signal(direction=0 if is_buy else 1, strategy_name=self.name,
                              magic=self.magic, is_buy=is_buy)
            return None
    class FixtureEngine(BacktestEngine):
        def _make_risk_manager(self):
            manager, module = super()._make_risk_manager()
            def fixed_stops(price, buy, *args, **kwargs):
                direction = 1 if buy else -1
                return StopLevels(price-direction, price+direction*1.5, 1., 1.5, 0., 0., 1., 1.)
            manager.calculate_atr_stops = fixed_stops
            return manager, module
    cfg = EngineConfig(symbol="XAUUSDm", starting_balance=5000., sizing_mode="fixed", fixed_lots=.02,
                       warmup_bars=0, history_bars=2, enable_d1_bias_gate=False,
                       enable_consolidation_exit=False, enable_trailing=False, enable_pyramiding=False,
                       live_exec_order=True, entry_delay_sec=0, record_equity_samples=True,
                       daily_loss_limit_mode="off", spread_gate_points=10000., m1_policy="require")
    result = FixtureEngine(bars, SCENARIOS["realistic_ecn"], cfg).run([FrozenOrder()], START+900, END)
    if len(result.trades) != 1:
        raise ValueError(f"Expected one frozen order, got {len(result.trades)}")
    return {"trade": asdict(result.trades[0]), "config": result.config, "diagnostics": result.diagnostics,
            "fixture_bar_hash": bars.hash_key(),
            "scope": "actual M1 engine; tick-derived bid OHLC and opening spread; no alpha signal"}


def compare(ticks, label):
    validate_quotes(ticks, START*1000, END*1000)
    output = {"data_kind": label, "historical_verification": False,
              "window_utc": ["2025-01-06T12:00:00Z", "2025-01-06T13:00:00Z"], "ticks": len(ticks),
              "fixtures": [], "orders_sent": 0, "holdout_accessed": False,
              "limitations": ["frozen engineering orders are not a trading strategy",
                              "provider quotes are not intended broker fills",
                              "constant adverse slippage/commission remain assumptions",
                              "minute replay reconstructs ask from opening spread",
                              "no queue, liquidity depth or market impact simulation"]}
    for is_buy, offset in ((True, 900), (False, 1800)):
        tick = tick_replay(ticks, signal_ms=(START+offset)*1000, is_buy=is_buy)
        minute = minute_replay(ticks, signal_ts=START+offset, is_buy=is_buy)
        a, b = tick["trade"], minute["trade"]
        output["fixtures"].append({"direction": "BUY" if is_buy else "SELL", "tick": tick,
                                   "minute": minute,
                                   "comparison": {"entry_count_tick": 1, "entry_count_m1": 1,
                                                  "exit_reason_equal": a["exit_reason"] == b["exit_reason"],
                                                  "entry_price_m1_minus_tick": b["entry_price"]-a["entry_price"],
                                                  "exit_price_m1_minus_tick": b["exit_price"]-a["exit_price"],
                                                  "exit_time_m1_label_minus_tick_ms": b["exit_time"]*1000-a["exit_time_ms"],
                                                  "net_pl_m1_minus_tick": b["net_pl"]-a["net_pl"]}})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticks", type=Path, help="Saved validated historical .npy capture; default synthetic")
    parser.add_argument("--out", type=Path, default=Path("research/results/tick_reconciliation_2026-11-18"))
    args = parser.parse_args()
    if (args.out/"comparison.json").exists():
        raise RuntimeError("Refusing to overwrite frozen evidence")
    ticks = np.load(args.ticks, allow_pickle=False) if args.ticks else offline_quotes()
    result = compare(ticks, "historical_capture_provenance_requires_manifest" if args.ticks else "synthetic_offline_fixture")
    result["historical_verification"] = False  # never certify source merely because a path was supplied
    result["source_provenance"] = str(args.ticks) if args.ticks else "programmed toy quotes, NOT historical gold prices"
    result["code_sha256"] = {str(Path(__file__).name): hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.out.mkdir(parents=True, exist_ok=True)
    np.save(args.out/"input_quotes.npy", ticks, allow_pickle=False)
    result["input_sha256"] = hashlib.sha256((args.out/"input_quotes.npy").read_bytes()).hexdigest()
    (args.out/"comparison.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"data_kind": result["data_kind"], "historical_verification": result["historical_verification"],
                      "comparisons": [f["comparison"] for f in result["fixtures"]]}, indent=2))


if __name__ == "__main__":
    main()
