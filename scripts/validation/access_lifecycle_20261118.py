"""Pre-registered engineering coupling: real minute engine -> provisional Access ledger.

Not an independent strategy test, continuous-tick certificate or real payout claim.
See PREREG_AccessLifecycle_2026-11-18.md (committed before measurement).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np

from src.backtesting.engine import BacktestEngine, EngineConfig
from src.research.access_rules_20261118 import DAY, PROFILE, ExperimentalAccessLedger, amount

START = int(datetime(2026, 7, 6, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 10, 30, tzinfo=timezone.utc).timestamp())
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "results" / "access_lifecycle_2026-11-18"


class IndeterminatePath(RuntimeError):
    pass


def serial(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class LifecyclePolicy:
    def __init__(self, phase, opened_at, *, trace=None):
        self.ledger = ExperimentalAccessLedger(phase, opened_at, 5000)
        self.status, self.reason, self.finished_at = "active", None, None
        self.seen = 0
        self.last_seen = opened_at
        self.last_positions = 0
        self.trace = trace
        self.events = []
        self.resets = Counter()
        self.blocked_eligibility = Counter()
        self.conditional_settlements = []
        self.cash_reconciliation_max_error = 0.
        self.observations = 0
        self.minimum_equity = 5000.
        self.maximum_drawdown = 0.
        self.sample_peak = 5000.
        self.pending_midnight = None

    def stop_indeterminate(self, ts, reason):
        self.status, self.reason, self.finished_at = "indeterminate", reason, int(ts)
        self.events.append({"time": int(ts), "kind": "indeterminate", "reason": reason})
        raise IndeterminatePath(reason)

    def _advance(self, ts, *, flat, reset_equity=None):
        ledger = self.ledger
        if ts < ledger.last_at:
            self.stop_indeterminate(ts, "nonchronological_engine_cash_event")
        while ts // DAY > ledger.utc_day:
            midnight = (ledger.utc_day + 1) * DAY
            if flat:
                equity, method = ledger.balance, "proven_flat_cash"
            elif ts == midnight and reset_equity is not None:
                equity, method = amount(reset_equity), "exact_00utc_open_quote"
            else:
                self.stop_indeterminate(ts, "open_exposure_without_exact_midnight_quote")
            ledger.observe(midnight, equity, midnight_equity=equity)
            self.resets[method] += 1
            self.events.append({"time": midnight, "kind": "utc_reset", "evidence": method,
                                "equity": str(equity), "daily_floor": str(ledger.daily_floor)})
        # observe() or a booking call advances within this same UTC day.

    @staticmethod
    def net_equity(engine, ts):
        value = engine.balance + engine.floating_pl()
        for pos in engine.positions:
            value += engine.cost.swap(pos.lots, pos.is_buy, pos.entry_time, ts,
                                      engine.spec.point, engine.spec.value_per_price_unit_per_lot)
            value -= engine.cost.commission(pos.lots)
        return value

    def _book(self, engine):
        for trade in engine.trades[self.seen:]:
            ts = int(trade.exit_time)
            self._advance(ts, flat=self.last_positions == 0)
            self.ledger.record_closed_profit(ts, trade.net_pl)
            self.events.append({"time": ts, "kind": "closed_trade", "strategy": trade.strategy,
                                "net": trade.net_pl, "reason": trade.exit_reason})
        self.seen = len(engine.trades)
        difference = abs(float(self.ledger.balance) - engine.balance)
        self.cash_reconciliation_max_error = max(self.cash_reconciliation_max_error, difference)
        if difference > 1e-7:
            self.stop_indeterminate(int(self.last_seen), "engine_ledger_cash_does_not_reconcile")

    def _possible_intervention(self, engine, ts, sample):
        """Conservative OHLC envelope; do not invent the ordering of threshold hits."""
        if sample["phase"] != "interval_end":
            return
        start = ts - 60
        opening = next((row for row in reversed(engine.equity_samples)
                        if row["time"] == start and row["phase"] == "open_after_orders"), None)
        if not opening or not opening["positions"]:
            return
        index = int(np.searchsorted(engine.m1["time"], start))
        if index >= len(engine.m1) or int(engine.m1[index]["time"]) != start:
            self.stop_indeterminate(ts, "missing_exposed_minute_for_rule_envelope")
        bar = engine.m1[index]
        spread = float(bar["spread"]) if "spread" in bar.dtype.names else None
        lower = upper = float(opening["balance"])
        margin = 0.
        for pos in opening["positions"]:
            low, high = float(bar["low"]), float(bar["high"])
            value = engine.spec.value_per_price_unit_per_lot * pos["lots"]
            if pos["is_buy"]:
                lo, hi = (low-pos["entry_price"])*value, (high-pos["entry_price"])*value
            else:
                lo = (pos["entry_price"]-engine.cost.ask(high, engine.spec.point, spread))*value
                hi = (pos["entry_price"]-engine.cost.ask(low, engine.spec.point, spread))*value
            cost = pos["accrued_swap"] - pos["pending_commission"]
            lower += lo + cost
            upper += hi + cost
            margin += engine.margin_required(pos["lots"], pos["entry_price"])
        rate = PROFILE.evaluation_trailing if self.ledger.phase == "evaluation" else PROFILE.funded_trailing
        possible_floor = max(float(self.ledger.daily_floor), max(float(self.ledger.peak_equity), upper)*(1-float(rate)))
        if lower < possible_floor:
            self.stop_indeterminate(ts, "intraminute_envelope_can_cross_daily_or_trailing_floor")
        if self.ledger.phase == "funded":
            if lower-float(opening["balance"]) <= -float(PROFILE.protector*self.ledger.initial_balance):
                self.stop_indeterminate(ts, "intraminute_possible_protector_requires_actual_liquidation_fills")
            if lower <= 0 or margin/lower >= .8:
                self.stop_indeterminate(ts, "intraminute_possible_margin_intervention_requires_actual_fills")

    def observe(self, engine, ts):
        ts = int(ts)
        sample = engine.equity_samples[-1]
        if ts > self.last_seen + 60 and self.last_positions:
            self.stop_indeterminate(ts, "unobserved_quote_gap_with_open_exposure")
        self._possible_intervention(engine, ts, sample)
        if sample["phase"] == "open":
            self._advance(ts, flat=self.last_positions == 0,
                          reset_equity=sample["net_liquidation_equity"] if ts % DAY == 0 else None)
        self._book(engine)
        if sample["phase"] == "interval_end" and ts % DAY == 0 and engine.positions:
            # A23:59 close is not the00:00 opening quote. Wait for that exact
            # subsequent opening observation, otherwise the next call refuses.
            self.pending_midnight = ts
            self.last_seen, self.last_positions = ts, len(engine.positions)
            return False
        equity = self.net_equity(engine, ts)
        self._advance(ts, flat=not engine.positions)
        old_hits = self.ledger.protector_hits
        self.ledger.observe(ts, equity)
        self.pending_midnight = None
        self.last_seen, self.last_positions = ts, len(engine.positions)
        self.observations += 1
        self.minimum_equity = min(self.minimum_equity, equity)
        self.sample_peak = max(self.sample_peak, equity)
        self.maximum_drawdown = max(self.maximum_drawdown, self.sample_peak-equity)
        if self.trace:
            self.trace.writerow((ts, sample["phase"], float(self.ledger.balance), equity,
                                 float(self.ledger.daily_floor), float(self.ledger.trailing_floor),
                                 len(engine.positions), self.ledger.status))
        if self.ledger.protector_hits != old_hits:
            self.stop_indeterminate(ts, "observed_protector_requires_actual_liquidation_fills")
        if self.ledger.status == "breached":
            self.status, self.reason, self.finished_at = "breached", "observed_provisional_floor_breach", ts
            return True
        if self.ledger.evaluation_passed(open_positions=len(engine.positions)):
            self.status, self.finished_at = "passed", ts
            self.events.append({"time": ts, "kind": "flat_evaluation_pass", "balance": str(self.ledger.balance)})
            return True
        if self.ledger.phase == "funded" and not engine.positions:
            check = self.ledger.eligibility(ts, kyc_verified=True, open_positions=0)
            self.blocked_eligibility.update(check.reasons)
            if check.eligible:
                try:
                    request = self.ledger.request_payout(ts, 100, kyc_verified=True, open_positions=0)
                except ValueError:
                    self.blocked_eligibility["insufficient_gross_for_100_cash"] += 1
                else:
                    # Explicit favorable SCENARIO approval, never an actual receipt.
                    paid = self.ledger.settle_payout(ts, approved=True, open_positions=0)
                    engine.balance -= float(request["gross"])
                    engine.stub.balance = engine.balance
                    self.conditional_settlements.append(paid)
                    self.events.append({"time": ts, "kind": "conditional_instant_approval_settlement", **paid})
        return False

    def summary(self, engine):
        ledger = self.ledger
        kept = engine.trades[:self.seen]
        positives = sum(trade.net_pl for trade in kept if trade.net_pl > 0)
        losses = -sum(trade.net_pl for trade in kept if trade.net_pl < 0)
        return {
            "phase": ledger.phase, "status": self.status, "reason": self.reason,
            "opened_at": ledger.opened_at, "finished_at": self.finished_at,
            "ledger_balance": str(ledger.balance), "ledger_equity": str(ledger.equity),
            "peak_equity": str(ledger.peak_equity), "daily_floor": str(ledger.daily_floor),
            "trailing_floor": str(ledger.trailing_floor), "trades": len(kept),
            "net_trade_cash": sum(trade.net_pl for trade in kept),
            "profit_factor": positives/losses if losses else None,
            "sampled_max_drawdown_usd": self.maximum_drawdown,
            "minimum_sampled_net_liquidation_equity": self.minimum_equity,
            "observations": self.observations, "reset_evidence": dict(self.resets),
            "eligibility_block_observations": dict(self.blocked_eligibility),
            "conditional_settlements": self.conditional_settlements, "actual_receipts": 0,
            "actual_cash_received": 0, "protector_hits_observed": ledger.protector_hits,
            "cash_reconciliation_max_error": self.cash_reconciliation_max_error,
            "unledgered_terminal_settlements": [asdict(trade) for trade in engine.trades[self.seen:]],
            "open_positions_at_termination": len(engine.positions), "events": self.events,
        }


class LifecycleEngine(BacktestEngine):
    """Use the real engine; add fail-closed coverage guard and bounded mark cache."""
    def __init__(self, *args, lifecycle_policy, **kwargs):
        self.lifecycle_policy = lifecycle_policy
        self.total_marks = 0
        self.flat_coverage_exclusions = []
        super().__init__(*args, **kwargs)

    def _sample_equity(self, *args, **kwargs):
        super()._sample_equity(*args, **kwargs)
        self.total_marks += 1
        if len(self.equity_samples) > 6:
            del self.equity_samples[:-6]

    def _m1_slice(self, start, end):
        result = super()._m1_slice(start, end)
        complete = result is not None and np.array_equal(result["time"], np.arange(start, end, 60))
        if not complete:
            if self.positions:
                self.lifecycle_policy.stop_indeterminate(start, "missing_or_partial_M1_with_existing_exposure")
            self.flat_coverage_exclusions.append({"start": int(start), "end": int(end),
                                                  "observed_minutes": 0 if result is None else len(result)})
        return result


def run_phase(bars, phase, start, end, out):
    from src.backtesting.costs import SCENARIOS
    from src.strategies.portfolio_atlas import PORTFOLIO
    with gzip.open(out / f"{phase}_observations.csv.gz", "wt", newline="", encoding="utf-8") as stream:
        trace = csv.writer(stream)
        trace.writerow(("time", "mark_kind", "balance", "net_liquidation_equity", "daily_floor", "trailing_floor", "positions", "status"))
        policy = LifecyclePolicy(phase, start, trace=trace)
        config = EngineConfig.live_parity_preset(
            starting_balance=5000., fixed_lots=.02, sizing_mode="fixed",
            max_concurrent=3, max_same_direction=3, history_bars=7500,
            protect_profit=False, m1_policy="skip", leverage=100. if phase == "evaluation" else 50.,
            entry_delay_sec=0, record_equity_samples=True,
        )
        engine = LifecycleEngine(bars, SCENARIOS["realistic_ecn"], config, lifecycle_policy=policy)
        try:
            engine.run([cls() for cls in PORTFOLIO], start, end, account_policy=policy)
        except IndeterminatePath:
            pass
        result = policy.summary(engine)
        result.update(config=config.as_dict(), diagnostics=engine.diag,
                      total_engine_marks=engine.total_marks, flat_coverage_exclusions=engine.flat_coverage_exclusions,
                      cost=asdict(SCENARIOS["realistic_ecn"]), data_hash=bars.hash_key())
        (out / f"{phase}_trades.json").write_text(json.dumps([asdict(trade) for trade in engine.trades], default=serial, indent=2))
        (out / f"{phase}.json").write_text(json.dumps(result, default=serial, indent=2))
        return result


def main():
    os.environ.update(ULTRA_TRADE_24H="1", ULTRA_DISABLE_ALERTS="1", ULTRA_NO_TRIAL_LEDGER="1")
    from src.backtesting.master import load_master
    OUT.mkdir(parents=True, exist_ok=True)
    protocol = ROOT / "research" / "registry" / "PREREG_AccessLifecycle_2026-11-18.md"
    protocol_commit = subprocess.run(["git", "log", "--diff-filter=A", "--format=%H", "--", str(protocol)], capture_output=True, text=True, check=True).stdout.strip()
    if not protocol_commit:
        raise RuntimeError("Committed pre-registration required")
    bars = load_master(("M15", "M1", "D1"), start=START, end=END)
    results = [run_phase(bars, "evaluation", START, END, OUT)]
    if results[0]["status"] == "passed":
        next_start = (results[0]["finished_at"]//900+1)*900
        if next_start < END:
            results.append(run_phase(bars, "funded", next_start, END, OUT))
    payload = {"kind": "pre_explored_historical_engineering_replay", "start": START, "end_exclusive": END,
               "protocol_commit": protocol_commit, "protocol_sha256": digest(protocol),
               "runner_sha256": digest(__file__), "ledger_sha256": digest(ROOT/"src/research/access_rules_20261118.py"),
               "engine_sha256": digest(ROOT/"src/backtesting/engine.py"), "profile": asdict(PROFILE),
               "phases": results, "actual_cash_received": 0,
               "conditional_approval_assumption": "Verified KYC and instantaneous supplied approval at flat eligible request; no actual payout claim",
               "limitations": ["Selected portfolio and dates were previously explored; not independent edge evidence",
                               "Unknown activation fee and actual approval timing; evaluation fee not debited from account",
                               "News/short-trade deductions, inactivity and broker-native contract/financing not fully verified",
                               "Flat incomplete M15 blocks excluded retrospectively; different from causal live availability",
                               "Bid/ask reconstruction from bid OHLC/spread; no tick or broker parity certificate",
                               "Intraminute rule envelope may halt conservatively without proving a breach"]}
    (OUT/"summary.json").write_text(json.dumps(payload, default=serial, indent=2))
    print(json.dumps({"phases": [{key: phase[key] for key in ("phase", "status", "reason", "trades", "net_trade_cash", "ledger_balance", "finished_at")} for phase in results], "actual_cash_received": 0}))


if __name__ == "__main__":
    main()
