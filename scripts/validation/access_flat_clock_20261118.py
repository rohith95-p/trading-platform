"""Final predeclared flat/inert-clock coverage sensitivity, not a strategy rescue."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import csv
import gzip
import json
import os
from pathlib import Path
import subprocess

import numpy as np

from scripts.validation.access_lifecycle_20261118 import (
    START, END, ROOT, LifecyclePolicy, IndeterminatePath, serial, digest,
)
from scripts.validation.access_provider_calendar_20261118 import (
    CalendarPolicy, CalendarEngine, market_state, quote_minute_expected, scheduled_closed_gap,
    source_provenance, SOURCE_URL,
)
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.research.access_rules_20261118 import PROFILE

OUT = ROOT / "research/results/access_flat_clock_2026-11-18"
LOCK = ROOT / "research/registry/access_flat_clock_source_lock_20261118.json"
EXPECTED_NAMES = ("AsianRangeFilteredV6", "AsianBreakoutV6", "LondonMomentumTightV6", "NYSessionReversalV6")


def verify_source_lock():
    recorded = json.loads(LOCK.read_text())
    changed = [path for path, sha in recorded.items() if digest(ROOT/path) != sha]
    if changed:
        raise ValueError("Frozen source changed: " + ", ".join(changed))
    from src.strategies.portfolio_atlas import PORTFOLIO
    if tuple(cls.__name__ for cls in PORTFOLIO) != EXPECTED_NAMES:
        raise ValueError("Fixed four-leg identity changed")
    for cls in PORTFOLIO:
        strategy = cls()
        if not strategy.execute_immediately or not strategy.edge_trigger or strategy.check_pending_confirmation(None) is not None:
            raise ValueError("Deferred or non-immediate strategy invalidates entry-impossibility proof")
    return recorded


def candidate_signal_clock(bar_time):
    second = int(bar_time) % 86400
    return second == 25200 or 43200 <= second < 57600


def flat_inert_proof(engine, missing, *, block_start):
    if engine.positions or engine.lifecycle_policy.last_positions or not missing:
        return None
    policy = engine.lifecycle_policy
    if policy.ledger.pending is not None or len(engine.trades) != policy.seen:
        return None
    if (engine.cfg.enable_pyramiding or not engine.cfg.live_exec_order or engine.cfg.entry_delay_sec
            or engine.cfg.resignal_interval_sec != 300 or not engine.cfg.dedup_per_candle):
        return None
    missing = [int(ts) for ts in missing]
    days = {ts//86400 for ts in missing}
    if len(days) != 1 or any(not 16*3600+30*60 <= ts%86400 < 23*3600+45*60 for ts in missing):
        return None
    # Retain broker-native aggregate information; never make a missing M15 bar.
    index = int(np.searchsorted(engine._m15_t, block_start))
    if index <= 0 or index >= len(engine.m15) or int(engine._m15_t[index]) != block_start:
        return None
    row = engine.m15[index]
    o,h,l,c = [float(row[name]) for name in ("open","high","low","close")]
    if not all(np.isfinite(value) and value > 0 for value in (o,h,l,c)) or not l <= min(o,c) <= max(o,c) <= h:
        return None
    cutoff = int(engine._m15_t[index-1])+900
    view = engine._view(engine.m15,engine._m15_t,cutoff,engine.cfg.history_bars,900)
    if view is None or len(view)<2:
        return None
    signal_bar = int(view["time"][-2])
    if signal_bar//86400 != block_start//86400 or candidate_signal_clock(signal_bar):
        return None
    return {"kind":"proven_flat_inert_clock_gap", "missing_minutes":missing,
            "block_start":int(block_start), "actual_signal_bar":signal_bar,
            "known_positions_before":0,"known_positions_now":0,
            "entry_impossibility":"frozen four hard signal clocks; no pending confirmations/pyramiding; reevaluation precedes entries",
            "broker_M15_aggregate_retained":True,"no_prices_invented":True}


class FlatClockPolicy(CalendarPolicy):
    def observe(self, engine, ts):
        ts = int(ts)
        sample = engine.equity_samples[-1]
        if sample["phase"] == "open" and ts > self.last_seen and not scheduled_closed_gap(self.last_seen,ts):
            # A missing M15 candidate block must not silently discard quotes that
            # actually exist in the M1 input, even when an account is flat.
            inside = engine.m1[(engine.m1["time"]>=self.last_seen)&(engine.m1["time"]<ts)]
            unknown = [minute for minute in range(self.last_seen,ts,60) if quote_minute_expected(minute)]
            proof = None if len(inside) else flat_inert_proof(engine,unknown,block_start=engine.current_block_start)
            if proof is None:
                self.stop_indeterminate(ts,"gap_not_proven_flat_inert_or_available_quotes_were_skipped")
            proof.update(time=ts,from_time=self.last_seen,to_time=ts)
            self.events.append(proof)
            self.last_seen=ts-60
            return LifecyclePolicy.observe(self,engine,ts)
        return super().observe(engine,ts)


class FlatClockEngine(CalendarEngine):
    def __init__(self,*args,**kwargs):
        self.flat_inert_blocks=[]
        self.current_block_start=None
        super().__init__(*args,**kwargs)

    def _m1_slice(self,start,end):
        self.current_block_start=int(start)
        observed=BacktestEngine._m1_slice(self,start,end)
        actual=set() if observed is None else set(int(ts) for ts in observed["time"])
        missing=[ts for ts in range(start,end,60) if ts not in actual]
        unexplained=[ts for ts in missing if quote_minute_expected(ts)]
        if any(not quote_minute_expected(ts) for ts in actual):
            self.lifecycle_policy.stop_indeterminate(start,"observed_quotes_contradict_assumed_provider_clock_or_calendar")
        if unexplained:
            proof=flat_inert_proof(self,unexplained,block_start=start)
            if proof is None:
                self.lifecycle_policy.events.append({"time":start,"kind":"unsupported_missing_minutes","minutes":unexplained})
                self.lifecycle_policy.stop_indeterminate(start,"missing_minutes_not_proven_flat_entry_impossible")
            self.flat_inert_blocks.append(proof)
        if missing:
            self.scheduled_partial_blocks.append({"start":start,"end":end,
                  "missing_closed_minutes":len(missing)-len(unexplained),
                  "unobserved_flat_inert_minutes":len(unexplained),"observed_minutes":len(actual),
                  "open_positions":len(self.positions)})
        return self.m1[:0] if observed is None else observed


def run_phase(bars,phase,start,end):
    from src.backtesting.costs import SCENARIOS
    from src.strategies.portfolio_atlas import PORTFOLIO
    with gzip.open(OUT/f"{phase}_observations.csv.gz","wt",newline="",encoding="utf-8") as stream:
        trace=csv.writer(stream)
        trace.writerow(("time","mark_kind","balance","net_liquidation_equity","daily_floor","trailing_floor","positions","status"))
        policy=FlatClockPolicy(phase,start,trace=trace)
        config=EngineConfig.live_parity_preset(starting_balance=5000.,fixed_lots=.02,sizing_mode="fixed",
            max_concurrent=3,max_same_direction=3,history_bars=7500,protect_profit=False,m1_policy="coarse",
            leverage=100. if phase=="evaluation" else 50.,entry_delay_sec=0,record_equity_samples=True)
        engine=FlatClockEngine(bars,SCENARIOS['realistic_ecn'],config,lifecycle_policy=policy)
        try:
            engine.run([cls() for cls in PORTFOLIO],start,end,account_policy=policy)
        except IndeterminatePath:
            pass
        result=policy.summary(engine)
        result.update(config=config.as_dict(),diagnostics=engine.diag,total_engine_marks=engine.total_marks,
                      scheduled_partial_blocks=engine.scheduled_partial_blocks,flat_inert_blocks=engine.flat_inert_blocks,
                      close_only_entry_blocks=engine.close_only_entry_blocks,
                      no_M15_price_fills=int(engine.diag['bars_without_m1'])==0,
                      cost=asdict(SCENARIOS['realistic_ecn']),data_hash=bars.hash_key())
        (OUT/f"{phase}.json").write_text(json.dumps(result,default=serial,indent=2))
        (OUT/f"{phase}_trades.json").write_text(json.dumps([asdict(t) for t in engine.trades],default=serial,indent=2))
        return result


def main():
    os.environ.update(ULTRA_TRADE_24H='1',ULTRA_DISABLE_ALERTS='1',ULTRA_NO_TRIAL_LEDGER='1')
    locked=verify_source_lock()
    from src.backtesting.master import load_master
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=ROOT/'research/registry/PREREG_AccessFlatClock_2026-11-18.md'
    pc=subprocess.run(['git','log','--diff-filter=A','--format=%H','--',str(protocol)],capture_output=True,text=True,check=True).stdout.strip()
    if not pc:
        raise ValueError('Committed pre-registration required')
    bars=load_master(('M15','M1','D1'),start=START,end=END)
    provenance=source_provenance(bars)
    phases=[run_phase(bars,'evaluation',START,END)]
    if phases[0]['status']=='passed':
        later=(phases[0]['finished_at']//900+1)*900
        if later<END:
            phases.append(run_phase(bars,'funded',later,END))
    result={'kind':'final_flat_inert_clock_engineering_sensitivity','start':START,'end_exclusive':END,
            'protocol_commit':pc,'protocol_sha256':digest(protocol),'source_lock':locked,
            'runner_sha256':digest(__file__),'engine_sha256':digest(ROOT/'src/backtesting/engine.py'),
            'ledger_sha256':digest(ROOT/'src/research/access_rules_20261118.py'),
            'profile':asdict(PROFILE),'source_provenance':provenance,'phases':phases,
            'actual_cash_received':0,'historical_provider_calendar_assumption':SOURCE_URL,
            'approval_scenario':'Conditional verified KYC and immediate explicitly supplied approval; actual receipts zero',
            'no_independent_strategy_acceptance':True}
    (OUT/'summary.json').write_text(json.dumps(result,default=serial,indent=2))
    print(json.dumps({'phases':[{k:p[k] for k in ('phase','status','reason','trades','net_trade_cash','ledger_balance','finished_at')} for p in phases],
                      'actual_cash_received':0}))


if __name__=='__main__':
    main()
