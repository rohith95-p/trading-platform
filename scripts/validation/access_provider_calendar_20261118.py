"""One frozen Exness-calendar sensitivity; preserve primary lifecycle result.

The November3 notice is historical calendar ASSUMPTION for Jul–Oct; never Atlas
hours. Real observed minutes only; missing active/holiday minutes still refuse.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np

from scripts.validation.access_lifecycle_20261118 import (
    START, END, ROOT, LifecyclePolicy, LifecycleEngine, IndeterminatePath, serial, digest,
)
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.research.access_rules_20261118 import PROFILE

OUT = ROOT / "research" / "results" / "access_provider_calendar_2026-11-18"
SOURCE_URL = "https://get.exness.help/hc/en-us/articles/31342732737180-Trading-Hours-Update-End-of-US-Daylight-Saving-Time-01-Nov-2026"


def market_state(ts):
    """Published SUMMER XAUUSD schedule, applied only inside preregistered dates."""
    moment = datetime.fromtimestamp(int(ts), timezone.utc)
    day, second = moment.weekday(), int(ts) % 86400
    if day == 5:
        return "closed"
    if day == 6:
        if second < 22*3600 + 90:
            return "closed"
        return "close_only" if second < 22*3600 + 300 else "open"
    if day == 4:
        return "open" if second < 20*3600 + 58*60 else "closed"
    if second < 20*3600 + 58*60 or second >= 22*3600 + 120:
        return "open"
    return "closed" if second < 22*3600 + 30 else "close_only"


def quote_minute_expected(ts):
    return market_state(ts) != "closed" or market_state(ts+59) != "closed"


def scheduled_closed_gap(start, end):
    return all(not quote_minute_expected(ts) for ts in range(int(start), int(end), 60))


class CalendarPolicy(LifecyclePolicy):
    def observe(self, engine, ts):
        ts = int(ts)
        sample = engine.equity_samples[-1]
        if sample["phase"] == "open" and ts > self.last_seen:
            if not scheduled_closed_gap(self.last_seen, ts):
                self.stop_indeterminate(ts, "unverified_active_or_holiday_quote_gap")
            self.events.append({"time": ts, "kind": "calendar_assumed_closed_gap",
                                "from": self.last_seen, "to": ts, "open_positions": self.last_positions,
                                "no_interpolated_marks": True})
            # Bypass ONLY the primary policy's blanket >60s gap refusal; its
            # real UTC ledger clock remains unchanged and still requires actual
            # midnight quotes for exposure. No synthetic equity is supplied.
            self.last_seen = ts-60
        return super().observe(engine, ts)


class CalendarEngine(LifecycleEngine):
    def __init__(self, *args, **kwargs):
        self.scheduled_partial_blocks = []
        self.close_only_entry_blocks = 0
        super().__init__(*args, **kwargs)

    def _m1_slice(self, start, end):
        # Call the real engine slice, not the primary all-partial refusal hook.
        observed = BacktestEngine._m1_slice(self, start, end)
        actual = set() if observed is None else set(int(ts) for ts in observed["time"])
        missing = [ts for ts in range(start, end, 60) if ts not in actual]
        unexpected = [ts for ts in missing if quote_minute_expected(ts)]
        outside = [ts for ts in actual if not quote_minute_expected(ts)]
        if unexpected:
            self.lifecycle_policy.events.append({"time": start, "kind": "unexpected_missing_quote_minutes", "minutes": unexpected})
            self.lifecycle_policy.stop_indeterminate(start, "missing_active_or_close_only_minutes_not_explained_by_calendar")
        if outside:
            self.lifecycle_policy.stop_indeterminate(start, "observed_quotes_contradict_assumed_provider_clock_or_calendar")
        if missing:
            self.scheduled_partial_blocks.append({"start": start, "end": end, "missing_closed_minutes": len(missing),
                                                   "observed_minutes": len(actual), "open_positions": len(self.positions)})
        # Empty observed arrays cause zero engine minute iterations. None would
        # trigger a coarse M15 substitution and is NEVER returned here.
        return self.m1[:0] if observed is None else observed

    def _open(self, *args, **kwargs):
        ts = kwargs.get("ts", args[4] if len(args) > 4 else None)
        if ts is None or market_state(ts) != "open":
            self.close_only_entry_blocks += 1
            return None
        return super()._open(*args, **kwargs)


def source_provenance(bars):
    rows = []
    for folder in ("research/data", "research/data_2026-10-30", "research/data/broker_archive"):
        manifest = ROOT / folder / "XAUUSDm_M1.manifest.json"
        array = ROOT / folder / "XAUUSDm_M1.npy"
        if not manifest.exists() or not array.exists():
            continue
        doc = json.loads(manifest.read_text(encoding="utf-8-sig"))
        data = np.load(array, mmap_mode="r")
        actual = hashlib.sha256(data.tobytes()).hexdigest()
        rows.append({"manifest": str(manifest.relative_to(ROOT)), "manifest_sha256": digest(manifest),
                     "server": doc.get("server"), "symbol": doc.get("symbol"),
                     "declared_first_time": doc.get("first_time"), "declared_last_time": doc.get("last_time"),
                     "actual_first_epoch": int(data["time"][0]), "actual_last_epoch": int(data["time"][-1]),
                     "content_sha256": actual, "declared_content_sha256": doc.get("sha256"),
                     "content_hash_matches": actual == doc.get("sha256"),
                     "clock": "UTC according to loader/acquisition metadata; no new live terminal check"})
    if not rows or any(not row["content_hash_matches"] or row["server"] != "Exness-MT5Trial11" for row in rows):
        raise ValueError("Provider identity/content provenance not verified for this fixed sensitivity")
    return rows


def run_phase(bars, phase, start, end):
    from src.backtesting.costs import SCENARIOS
    from src.strategies.portfolio_atlas import PORTFOLIO
    with gzip.open(OUT / f"{phase}_observations.csv.gz", "wt", newline="", encoding="utf-8") as stream:
        trace = csv.writer(stream)
        trace.writerow(("time", "mark_kind", "balance", "net_liquidation_equity", "daily_floor", "trailing_floor", "positions", "status"))
        policy = CalendarPolicy(phase, start, trace=trace)
        config = EngineConfig.live_parity_preset(
            starting_balance=5000., fixed_lots=.02, sizing_mode="fixed", max_concurrent=3,
            max_same_direction=3, history_bars=7500, protect_profit=False, m1_policy="coarse",
            leverage=100. if phase == "evaluation" else 50., entry_delay_sec=0, record_equity_samples=True)
        engine = CalendarEngine(bars, SCENARIOS["realistic_ecn"], config, lifecycle_policy=policy)
        try:
            engine.run([cls() for cls in PORTFOLIO], start, end, account_policy=policy)
        except IndeterminatePath:
            pass
        result = policy.summary(engine)
        result.update(config=config.as_dict(), diagnostics=engine.diag, total_engine_marks=engine.total_marks,
                      scheduled_partial_blocks=engine.scheduled_partial_blocks,
                      close_only_entry_blocks=engine.close_only_entry_blocks,
                      no_M15_price_fills=int(engine.diag["bars_without_m1"]) == 0,
                      cost=asdict(SCENARIOS["realistic_ecn"]), data_hash=bars.hash_key())
        (OUT / f"{phase}.json").write_text(json.dumps(result, default=serial, indent=2))
        (OUT / f"{phase}_trades.json").write_text(json.dumps([asdict(t) for t in engine.trades], default=serial, indent=2))
        return result


def main():
    os.environ.update(ULTRA_TRADE_24H="1", ULTRA_DISABLE_ALERTS="1", ULTRA_NO_TRIAL_LEDGER="1")
    from src.backtesting.master import load_master
    OUT.mkdir(parents=True, exist_ok=True)
    protocol = ROOT / "research/registry/PREREG_AccessProviderCalendar_2026-11-18.md"
    protocol_commit = subprocess.run(["git", "log", "--diff-filter=A", "--format=%H", "--", str(protocol)], capture_output=True, text=True, check=True).stdout.strip()
    if not protocol_commit:
        raise ValueError("Committed preregistration required")
    bars = load_master(("M15", "M1", "D1"), start=START, end=END)
    provenance = source_provenance(bars)
    phases = [run_phase(bars, "evaluation", START, END)]
    if phases[0]["status"] == "passed":
        funded_start = (phases[0]["finished_at"]//900+1)*900
        if funded_start < END:
            phases.append(run_phase(bars, "funded", funded_start, END))
    result = {"kind": "provider_calendar_assumed_engineering_sensitivity", "start": START, "end_exclusive": END,
              "protocol_commit": protocol_commit, "protocol_sha256": digest(protocol),
              "runner_sha256": digest(__file__), "primary_runner_sha256": digest(ROOT/"scripts/validation/access_lifecycle_20261118.py"),
              "engine_sha256": digest(ROOT/"src/backtesting/engine.py"), "ledger_sha256": digest(ROOT/"src/research/access_rules_20261118.py"),
              "source_provenance": provenance, "profile": asdict(PROFILE), "phases": phases,
              "calendar_evidence": {"url": SOURCE_URL, "published_update": "2026-11-03T09:45", "retrieved_date": "2026-11-18",
                                    "historical_July_October_schedule_verified": False,
                                    "interpretation": "Published then-current summer Exness XAUUSD schedule assumed for these earlier Exness demo quotes; NOT Atlas hours"},
              "actual_cash_received": 0,
              "approval_scenario": "conditional verified KYC and immediate explicit approval at flat eligible request; never actual receipt"}
    (OUT / "summary.json").write_text(json.dumps(result, default=serial, indent=2))
    print(json.dumps({"phases": [{k: phase[k] for k in ("phase", "status", "reason", "trades", "net_trade_cash", "ledger_balance", "finished_at")} for phase in phases], "actual_cash_received": 0}))


if __name__ == "__main__":
    main()


