"""One preregistered short-gold auction study. Run with python -m scripts.research.treasury_auction_gold."""
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

if __name__ == "__main__":
    os.environ.update(ULTRA_TRADE_24H="1", ULTRA_DISABLE_ALERTS="1", ULTRA_NO_TRIAL_LEDGER="1")

import numpy as np
import requests
from scripts.research.fomc_shock_propagation import ClosedATRResearchEngine, block_mean
from src.backtesting.costs import SCENARIOS
from src.backtesting.data import BarSet
from src.backtesting.engine import EngineConfig
from src.backtesting.master import load_master, M1_HOLE
from src.backtesting.metrics import summarize
from src.strategies.base_strategy import Signal

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/results/treasury_auction_gold_2026-11-18"
URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
NY = ZoneInfo("America/New_York")
PERIODS = [(2010, 2018), (2019, 2024), (2025, 2025), (2026, 2026)]


def clock(day):
    return int(datetime.combine(day, time(11, 45), NY).timestamp())


def calendar():
    path = OUT / "calendar.json"
    if not path.exists():
        fields = ("auction_date,announcemt_date,security_type,original_security_term,"
                  "inflation_index_security,floating_rate,closing_time_comp,cusip")
        params = {"fields": fields, "sort": "auction_date,cusip", "page[size]": "1000",
                  "filter": "original_security_term:eq:10-Year,auction_date:gte:2010-01-01,auction_date:lt:2026-11-01"}
        response = requests.get(URL, params=params, timeout=45)
        response.raise_for_status()
        payload = response.json()
        if len(payload["data"]) != int(payload["meta"]["total-count"]):
            raise ValueError("Incomplete Treasury response")
        path.write_text(json.dumps(dict(url=response.url, rows=payload["data"]), indent=2), encoding="utf-8")
    rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
    dates = []
    for r in rows:
        if (r["security_type"], r["original_security_term"], r["inflation_index_security"],
            r["floating_rate"], r["closing_time_comp"]) != ("Note", "10-Year", "No", "No", "01:00 PM"):
            continue
        day = date.fromisoformat(r["auction_date"])
        if date.fromisoformat(r["announcemt_date"]) >= day or day in dates:
            raise ValueError(f"Ambiguous schedule for {day}")
        dates.append(day)
    return sorted(dates)


def bars_for(master, ts):
    end = ts + 3600
    if M1_HOLE[0] <= end and ts < M1_HOLE[1]:
        return None, "declared M1 hole"
    t15 = master.m15["time"]
    lo, hi = np.searchsorted(t15, [ts, end + 900])
    if lo < 261 or not np.array_equal(t15[lo-16:hi], np.arange(ts-16*900, end+900, 900)):
        return None, "missing M15 warmup or window"
    # Strict engine requires the complete 15-minute bucket containing the exit.
    a, b = np.searchsorted(master.m1["time"], [ts, end+900])
    m1 = master.m1[a:b]
    if not np.array_equal(m1["time"], np.arange(ts, end+900, 60)):
        return None, "missing M1 execution bucket"
    return BarSet(master.symbol, master.m15[lo-261:hi], None, m1, None, master.spec, master.manifests), None


class ScheduledShort:
    name = "RESEARCH_TEN_YEAR_AUCTION_GOLD"
    magic = 991119
    sl_atr_mult = 2.
    tp_atr_mult = 4.

    def __init__(self, entry):
        self.entry = entry
        self.now = None

    def observe(self, engine, ts):
        mark = engine.equity_samples[-1]
        if mark["phase"] != "open":
            return False
        self.now = ts
        if ts != self.entry + 3600:
            return False
        for position in list(engine.positions):
            engine._close(position, mark["ask"] + engine.cost.slip(engine.spec.point), ts, "PRE_AUCTION_TIME")
        return True

    def evaluate(self, m15, m5=None):
        if self.now == self.entry:
            return Signal(direction=1, strategy_name=self.name, magic=self.magic, is_buy=False)
        return None


def replay(bars, ts, balance, cost):
    strategy = ScheduledShort(ts)
    cfg = EngineConfig(starting_balance=balance, sizing_mode="fixed", fixed_lots=.02,
                       max_concurrent=1, max_same_direction=1, enable_d1_bias_gate=False,
                       enable_consolidation_exit=False, enable_trailing=False, enable_pyramiding=False,
                       daily_loss_limit_mode="off", history_bars=250, warmup_bars=260,
                       record_equity_samples=True, resignal_interval_sec=60,
                       spread_gate_points=100000., spread_gate_blocks_management=False,
                       leverage=50., m1_policy="require", causal_minute_order=True, entry_delay_sec=0)
    engine = ClosedATRResearchEngine(bars, cost, cfg)
    result = engine.run([strategy], ts, ts+3660, account_policy=strategy)
    if len(result.trades) != 1 or result.diagnostics["exits_unchecked_no_m1"]:
        raise ValueError(f"Unresolved trade {ts}: {result.diagnostics}")
    trade = result.trades[0]
    if trade.is_buy or trade.entry_time != ts or not ts <= trade.exit_time <= ts+3600 or trade.lots != .02:
        raise AssertionError("Trade outside fixed rule")
    net = (trade.entry_price - trade.exit_price)*bars.spec.contract_size*.02 - trade.commission
    if not np.isclose(trade.net_pl, net) or not np.isclose(engine.balance, balance+net):
        raise AssertionError("Fill economics do not reconcile")
    return trade, [m["net_liquidation_equity"] for m in result.equity_samples] + [engine.balance]


def statistics(trades, marks, first, last, control):
    # January auctions can have their matched control in the previous December.
    offset = timedelta(days=7 if control else 0)
    start = clock(date(first, 1, 1) - offset)
    end = clock((date(2026, 11, 1) if last == 2026 else date(last+1, 1, 1)) - offset)
    stats = summarize(trades, [], 5000., start_ts=start, end_ts=end).to_dict()
    cash = [t.net_pl for t in trades]
    peaks = np.maximum.accumulate(marks)
    stats.update(sampled_drawdown_pct=float(np.max((peaks-marks)/peaks)*100),
                 net_after_best_removed=sum(cash)-max(cash) if cash else None,
                 annual_net_by_auction_year={str(y): sum(t.net_pl for t in trades if
                             (datetime.fromtimestamp(t.entry_time, NY).date() + offset).year == y)
                             for y in range(first, last+1)})
    return stats


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    days = calendar()
    master = load_master(("M15", "M1"), start=clock(date(2009, 12, 1)), end=clock(date(2026, 11, 1)))
    base = SCENARIOS["realistic_ecn"]
    report = dict(protocol_commit="138aad2", master_hash=master.hash_key(), provenance=master.provenance,
                  calendar_sha256=hashlib.sha256((OUT/"calendar.json").read_bytes()).hexdigest(),
                  base_cost=base.descriptor(), scheduled=len(days), omitted=[], periods={})
    pairs = []
    for day in days:
        control = day-timedelta(days=7)
        dates = [day, control]
        bars = [bars_for(master, clock(d)) for d in dates]
        reasons = [reason for _, reason in bars]
        if control in days:
            reasons[1] = "control also an auction"
        if any(reasons):
            report["omitted"].append(dict(auction=str(day), control=str(control), reasons=reasons))
        else:
            pairs.append((day, [(b, clock(d)) for (b, _), d in zip(bars, dates)]))
    for first, last in PERIODS:
        sample = [p for d, p in pairs if first <= d.year <= last]
        arms = []
        period = {}
        for i, label in enumerate(("auction", "prior_week")):
            trades, marks = [], [5000.]
            for pair in sample:
                trade, path = replay(*pair[i], marks[-1], base)
                trades.append(trade)
                marks.extend(path)
            period[label] = dict(stats=statistics(trades, marks, first, last, control=i == 1),
                                 trades=list(map(asdict, trades)))
            arms.append(trades)
        diff = [a.net_pl-b.net_pl for a, b in zip(*arms)]
        advantage = block_mean(diff, [a.entry_time for a in arms[0]], multiplier=1)
        advantage["p_unadjusted"] = advantage.pop("p_bonferroni4")
        period["paired_advantage_usd"] = advantage
        report["periods"][f"{first}-{last}"] = period
    periods = list(report["periods"].values())
    def primary_pass(p):
        s = p["auction"]["stats"]
        ci = p["paired_advantage_usd"]["ci95"]
        return bool(s["trades"] >= 30 and s["profit_factor"] is not None and s["profit_factor"] >= 1.3
                    and s["net_after_best_removed"] > 0 and ci and ci[0] > 0)
    later = [p["auction"]["stats"] for p in periods[2:]]
    report["base_pass"] = (all(primary_pass(p) for p in periods[:2]) and sum(s["trades"] for s in later) >= 10
                           and sum(s["net_pl"] for s in later) > 0)
    if report["base_pass"]:
        stress = replace(base, spread_multiplier=2., slippage_points=60.)
        bal = 5000.
        rows = []
        for day, pair in pairs:
            t, path = replay(*pair[0], bal, stress)
            rows.append(asdict(t))
            bal = path[-1]
        report["stress"] = dict(cost=stress.descriptor(), trades=rows, net=bal-5000.)
    (OUT/"backtest.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
