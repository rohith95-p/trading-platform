"""Preregistered XAUUSD FOMC strategy experiment using BacktestEngine.

Official USMPD calendar metadata only. Retrospective macro surprise/asset-return
columns never become features. Production modules/settings are not modified.
"""
from dataclasses import asdict, replace
from datetime import datetime, timedelta
import hashlib
import gzip
import json
import os
from pathlib import Path
import subprocess
import urllib.request
from xml.etree import ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# market_hours freezes this environment at import. Only the separately launched
# research runner lifts the owner's live night window; importing research helpers
# into tests/application code must not change process settings.
if __name__ == "__main__":
    os.environ["ULTRA_TRADE_24H"] = "1"
    os.environ["ULTRA_DISABLE_ALERTS"] = "1"
    os.environ["ULTRA_NO_TRIAL_LEDGER"] = "1"

from src.backtesting.costs import SCENARIOS
from src.backtesting.data import BarSet
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.master import load_master
from src.backtesting.metrics import summarize, monte_carlo_paths, drop_best_worst
from src.strategies.base_strategy import Signal


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "research/sources/fomc_usmpd_20261118"
OUT = ROOT / "research/results/finalization_2026-11-18/fomc_shock_propagation.json"
PROTOCOL = ROOT / "research/registry/PREREG_FOMCShockPropagation_2026-11-18.md"
URL = "https://www.frbsf.org/wp-content/uploads/USMPD.xlsx"
USMPD_SHA = "2b91297c42cf692dd74f65eabf7ee97f81d452676e23fa02edb222bfa60f0d0a"
NY = ZoneInfo("America/New_York")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calendar():
    """Mechanical XML metadata extraction; no workbook formulas or model fit."""
    SOURCE.mkdir(parents=True, exist_ok=True)
    path = SOURCE / "USMPD.xlsx"
    if not path.exists():
        path.write_bytes(urllib.request.urlopen(URL, timeout=30).read())
    if sha(path) != USMPD_SHA:
        raise ValueError("USMPD version changed; do not silently replace calendar snapshot")
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    records, excluded = [], []
    with zipfile.ZipFile(path) as book:
        strings = []
        if "xl/sharedStrings.xml" in book.namelist():
            strings = ["".join(e.itertext()) for e in ET.fromstring(book.read("xl/sharedStrings.xml"))]
        rows = ET.fromstring(book.read("xl/worksheets/sheet2.xml")).find("s:sheetData", ns)
        for row in list(rows)[1:]:
            meta = {}
            for cell in row:
                col = "".join(c for c in cell.get("r", "") if c.isalpha())
                if col not in {"A", "B", "C", "D"}:
                    continue  # Ignore every retrospective rate/asset return.
                if cell.get("t") == "inlineStr":
                    value = "".join(cell.find("s:is", ns).itertext())
                else:
                    node = cell.find("s:v", ns)
                    value = "" if node is None else node.text
                    if cell.get("t") == "s":
                        value = strings[int(value)]
                meta[col] = value
            local = datetime(1899, 12, 30) + timedelta(seconds=round(float(meta["B"]) * 86400))
            if not 2016 <= local.year <= 2025:
                continue
            event = dict(date=local.date().isoformat(), local_time=local.isoformat(),
                         event_time=int(local.replace(tzinfo=NY).timestamp()),
                         source_url=URL, sep=bool(int(float(meta["C"]))),
                         unscheduled=bool(int(float(meta["D"]))))
            if event["unscheduled"] or local.hour != 14 or local.minute != 0:
                excluded.append(dict(**event, reason="not_scheduled_1400_statement"))
            else:
                records.append(event)
    records.sort(key=lambda e: e["event_time"])
    if len({e["event_time"] for e in records}) != len(records):
        raise ValueError("duplicate statement timestamps")
    payload = dict(source_url=URL, workbook_sha256=sha(path), downloaded_metadata_version="2026-10-30",
                   timezone="Eastern Time in source; America/New_York conversion", records=records,
                   excluded=excluded, excluded_financial_columns="All columns E onward; not features",
                   availability="Calendar is retrospective historical metadata. Gold response is observed causally; published surprise series is not presumed historically available.")
    (SOURCE / "calendar.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def signal_features(window, release):
    """Only supplied completed M1 observations before release+30m are read."""
    wanted = release - 3600 + np.arange(90) * 60
    if len(window) != 90 or not np.array_equal(window["time"], wanted):
        raise ValueError("incomplete pre-risk/shock feature window")
    if (np.any(~np.isfinite(window["open"])) or np.any(~np.isfinite(window["close"]))
            or np.any(window["open"] <= 0) or np.any(window["close"] <= 0)):
        raise ValueError("invalid feature prices")
    pre = np.log(window["close"][:60] / window["open"][:60])
    scale = float(np.sqrt(np.mean(pre ** 2)) * np.sqrt(30))
    shock = float(np.log(window["close"][89] / window["open"][60]))
    normalized = shock / scale if scale > 0 else None
    return dict(pre_risk_30m=scale, shock_log_return=shock, shock_z=normalized,
                direction=1 if shock > 0 else -1 if shock < 0 else 0,
                candidate=bool(normalized is not None and np.isfinite(normalized) and abs(normalized) > 2),
                latest_feature_close_time=release + 1800)


class FOMCShockStrategy:
    name = "EXPERIMENTAL_FOMC_NORMALIZED_SHOCK_20261118"
    magic = 991118
    sl_atr_mult = 2.0
    tp_atr_mult = 4.0

    def __init__(self, entry, feature, side=None):
        self.entry = int(entry)
        self.feature = dict(feature)
        self.side = side if side is not None else feature["direction"]
        self.now = None

    def evaluate(self, m15, m5=None):
        if self.now != self.entry or self.side not in (-1, 1):
            return None
        if self.feature["latest_feature_close_time"] > self.now:
            raise ValueError("feature used before available")
        return Signal(direction=0 if self.side > 0 else 1, strategy_name=self.name,
                      magic=self.magic, is_buy=self.side > 0)


class ClosedATRResearchEngine(BacktestEngine):
    """Use original production RiskManager formula on closed bars only."""
    def _make_risk_manager(self):
        rm, module = super()._make_risk_manager()
        original = rm.calculate_atr_stops

        def closed(price, is_buy, rates, multiplier=None, tp_multiplier=None):
            return original(price, is_buy, rates[:-1], multiplier, tp_multiplier)

        rm.calculate_atr_stops = closed
        return rm, module


class OpeningClockAndTimeExit:
    def __init__(self, strategy, exit_at):
        self.strategy = strategy
        self.exit_at = exit_at

    def observe(self, engine, ts):
        sample = engine.equity_samples[-1]
        if sample["phase"] != "open" or sample["time"] != ts:
            return False
        self.strategy.now = ts
        if ts >= self.exit_at:
            for pos in list(engine.positions):
                px = sample["bid"] if pos.is_buy else sample["ask"]
                px -= (1 if pos.is_buy else -1) * engine.cost.slip(engine.spec.point)
                engine._close(pos, px, ts, "FOMC_FIXED_TIME")
            return True
        return False


def event_bars(master, entry):
    t = master.m15["time"]
    left = max(0, int(np.searchsorted(t, entry)) - 350)
    right = int(np.searchsorted(t, entry + 2 * 3600, side="right"))
    m15 = master.m15[left:right].copy()
    m1 = master.m1[(master.m1["time"] >= entry) & (master.m1["time"] < entry + 2 * 3600)].copy()
    return BarSet(master.symbol, m15, None, m1, None, master.spec, master.manifests)


def replay_one(bars, release, feature, cost, balance, arm, delay=0):
    base_entry = release + 45 * 60
    entry = base_entry + delay
    side = 1 if arm == "buy_control" else -1 if arm == "sell_control" else feature["direction"]
    strategy = FOMCShockStrategy(entry, feature, side)
    cfg = EngineConfig(starting_balance=balance, sizing_mode="fixed", fixed_lots=.02,
                       max_concurrent=1, max_same_direction=1, enable_d1_bias_gate=False,
                       enable_consolidation_exit=False, enable_trailing=False, enable_pyramiding=False,
                       daily_loss_limit_mode="off", history_bars=250, warmup_bars=260,
                       resignal_interval_sec=60, record_equity_samples=True,
                       spread_gate_points=100000., spread_gate_blocks_management=False,
                       leverage=50., m1_policy="require", causal_minute_order=True,
                       entry_delay_sec=0)
    engine = ClosedATRResearchEngine(bars, cost, cfg)
    policy = OpeningClockAndTimeExit(strategy, release + 105 * 60)
    result = engine.run([strategy], base_entry, release + 106 * 60, account_policy=policy)
    if any(t.entry_time != entry for t in result.trades):
        raise AssertionError("unexpected entry timestamp")
    if result.diagnostics["exits_unchecked_no_m1"]:
        raise AssertionError("unresolved minute exit")
    return result, engine.balance


def block_mean(values, times, multiplier=4):
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return dict(mean=float(values.mean()) if len(values) else None, ci95=None, p_bonferroni4=None)
    quarters = pd.to_datetime(times, unit="s", utc=True).tz_localize(None).to_period("Q").astype(str)
    group = pd.factorize(quarters)[0]
    sums = np.bincount(group, weights=values)
    counts = np.bincount(group).astype(float)
    rng = np.random.default_rng(20261118)
    pick = rng.integers(0, len(counts), (1999, len(counts)))
    boot = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    mean = float(values.mean())
    p = (1 + np.sum(np.abs(boot - mean) >= abs(mean))) / 2000
    return dict(mean=mean, ci95=np.quantile(boot, [.025, .975]).tolist(),
                p_bonferroni4=float(min(1, multiplier * p)), quarters=len(counts), bootstrap_draws=1999)


def metrics(trades, equity, first, last):
    if not trades:
        return dict(trades=0, net_pl=0., profit_factor=None, expectancy=None,
                    max_sampled_net_liquidation_dd_pct=0.)
    stats = summarize(trades, [], 5000.).to_dict()
    cash = np.array([x.net_pl for x in trades])
    values = np.array([5000., *[x["net_liquidation_equity"] for x in equity]])
    peaks = np.maximum.accumulate(values)
    stats["max_sampled_net_liquidation_dd_pct"] = float(np.max((peaks - values) / peaks) * 100)
    stats["quarter_cluster_mean"] = block_mean(cash, [x.exit_time for x in trades])
    stats["drop_best_worst"] = drop_best_worst(trades)
    stats["trade_permutation_mc"] = monte_carlo_paths(trades, 5000., n=1999, seed=20261118)
    daily = pd.Series(cash, index=pd.to_datetime([t.exit_time for t in trades], unit="s", utc=True).normalize()).groupby(level=0).sum()
    daily = daily.reindex(pd.date_range(f"{first}-01-01", f"{last}-12-31", freq="B", tz="UTC"), fill_value=0.) / 5000.
    stats["weekday_daily_sharpe_252"] = float(np.sqrt(252) * daily.mean() / daily.std(ddof=1)) if daily.std() else None
    downside = np.sqrt(np.mean(np.minimum(daily, 0.) ** 2))
    stats["weekday_daily_sortino_252"] = float(np.sqrt(252) * daily.mean() / downside) if downside else None
    stats["annual_net"] = {str(y): float(sum(t.net_pl for t in trades if datetime.fromtimestamp(t.exit_time, tz=NY).year == y)) for y in range(first, last + 1)}
    stats["long_short"] = {side: dict(n=sum(t.is_buy == buy for t in trades), net=float(sum(t.net_pl for t in trades if t.is_buy == buy))) for side, buy in (("long", True), ("short", False))}
    stats["uncertainty_limits"] = "Explored eras; event dependence; sampled minute equity not intratick max; permutation preserves final total; no verified account-rule violation probability. PBO/DSR not fabricated from incomplete historical trial matrix."
    return stats


def main():
    os.environ["ULTRA_DISABLE_ALERTS"] = "1"
    os.environ["ULTRA_NO_TRIAL_LEDGER"] = "1"
    os.environ["ULTRA_TRADE_24H"] = "1"
    relative = str(PROTOCOL.relative_to(ROOT)).replace("\\", "/")
    if subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT) != PROTOCOL.read_bytes().replace(b"\r\n", b"\n"):
        raise ValueError("protocol must be committed")
    events = calendar()
    master = load_master(("M15", "M1"), start=int(pd.Timestamp("2015-12-01", tz="UTC").timestamp()),
                         end=int(pd.Timestamp("2026-01-01", tz="UTC").timestamp()), use_cache=False)
    included, excluded = [], []
    for event in events["records"]:
        ts = event["event_time"]
        lo, hi = np.searchsorted(master.m1["time"], [ts - 3600, ts + 2 * 3600])
        window = master.m1[lo:hi]
        if len(window) != 180 or not np.array_equal(window["time"], ts - 3600 + np.arange(180) * 60):
            excluded.append(dict(**event, reason="incomplete_1300_1559_M1"))
            continue
        feature = signal_features(window[:90], ts)
        if not feature["direction"] or feature["pre_risk_30m"] <= 0:
            excluded.append(dict(**event, reason="zero_or_invalid_risk_shock"))
            continue
        included.append(dict(**event, feature=feature))
    base = SCENARIOS["realistic_ecn"]
    scenarios = {"base": (base, 0), "stress": (replace(base, spread_multiplier=2., slippage_points=60.), 0),
                 "delay60": (base, 60)}
    report = dict(protocol_sha256=sha(PROTOCOL), runner_sha256=sha(Path(__file__)),
                  engine_sha256=sha(ROOT / "src/backtesting/engine.py"),
                  protocol_commit="532351c", implementation_amendment="3471bf1",
                  git_head_before_run=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                  calendar=events, input_master_hash=master.hash_key(), input_provenance=master.provenance,
                  input_m15_sha256=hashlib.sha256(master.m15.tobytes()).hexdigest(),
                  input_m1_sha256=hashlib.sha256(master.m1.tobytes()).hexdigest(),
                  included_events=included, excluded_events=excluded, results={}, promoted=False,
                  classification="experimental_engine_candidate_no_independent_holdout_or_Atlas_qualification")
    for era, first, last in (("2016_2021", 2016, 2021), ("2022_2025", 2022, 2025)):
        selected = [e for e in included if first <= int(e["date"][:4]) <= last]
        candidate_events = [e for e in selected if e["feature"]["candidate"]]
        for scenario, (cost, delay) in scenarios.items():
            for arm in ("candidate", "unfiltered_follow", "buy_control", "sell_control"):
                balance, trades, marks, diagnostics, event_cash = 5000., [], [], [], []
                for event in (selected if arm == "unfiltered_follow" else candidate_events):
                    bars = event_bars(master, event["event_time"] + 45 * 60)
                    result, balance = replay_one(bars, event["event_time"], event["feature"], cost, balance, arm, delay)
                    trades.extend(result.trades)
                    marks.extend(result.equity_samples)
                    diagnostics.append(dict(date=event["date"], **result.diagnostics))
                    event_cash.append(dict(event_time=event["event_time"], net=float(sum(t.net_pl for t in result.trades)), trades=len(result.trades)))
                stats = metrics(trades, marks, first, last)
                key = f"{era}/{scenario}/{arm}"
                report["results"][key] = dict(stats=stats, trades=[asdict(t) for t in trades], equity_samples=marks,
                    diagnostics=diagnostics, event_cash=event_cash, cost=cost.descriptor(), additional_delay_seconds=delay,
                    intended_events=len(selected if arm == "unfiltered_follow" else candidate_events))
                print(key, stats["trades"], stats["net_pl"], stats["profit_factor"], flush=True)
    for era in ("2016_2021", "2022_2025"):
        arms = {k: report["results"][f"{era}/base/{k}"]["event_cash"] for k in ("candidate", "buy_control", "sell_control")}
        delta = np.array([c["net"] - (b["net"] + s["net"]) / 2 for c, b, s in zip(arms["candidate"], arms["buy_control"], arms["sell_control"])])
        report["results"][f"{era}/base/candidate"]["stats"]["versus_balanced_direction"] = block_mean(delta, [e["event_time"] for e in arms["candidate"]])
    bases = [report["results"][f"{era}/base/candidate"]["stats"] for era in ("2016_2021", "2022_2025")]
    pooled = [t for era in ("2016_2021", "2022_2025") for t in report["results"][f"{era}/base/candidate"]["trades"]]
    pooled_mean = block_mean([t["net_pl"] for t in pooled], [t["exit_time"] for t in pooled])
    gates = dict(sample_at_least_30_each_era=all(s["trades"] >= 30 for s in bases),
                 positive_net_and_pf_each_era=all(s["net_pl"] > 0 and s["profit_factor"] is not None and s["profit_factor"] >= 1.2 for s in bases),
                 positive_pooled_mean_lower_ci=pooled_mean["ci95"] is not None and pooled_mean["ci95"][0] > 0,
                 exceeds_direction_controls_each_era=all(s["versus_balanced_direction"]["ci95"] is not None and s["versus_balanced_direction"]["ci95"][0] > 0 and s["versus_balanced_direction"]["p_bonferroni4"] < .05 for s in bases),
                 sampled_dd_below_3_6pct_each_era=all(s["max_sampled_net_liquidation_dd_pct"] < 3.6 for s in bases),
                 stress_and_delay_positive_pooled=all(sum(report["results"][f"{era}/{scenario}/candidate"]["stats"]["net_pl"] for era in ("2016_2021", "2022_2025")) > 0 for scenario in ("stress", "delay60")),
                 drop_best_positive_pooled=bool(pooled and sum(t["net_pl"] for t in pooled) - max(t["net_pl"] for t in pooled) > 0))
    report["gates"] = gates
    report["pooled_candidate_mean"] = pooled_mean
    report["promoted"] = all(gates.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    def clean(x):
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        if isinstance(x, (float, np.floating)) and not np.isfinite(x):
            return None
        return x.item() if hasattr(x, "item") else x
    full = clean(report)
    full_path = OUT.with_suffix(".json.gz")
    with gzip.open(full_path, "wt", encoding="utf-8") as stream:
        json.dump(full, stream, allow_nan=False)
    for key, result in full["results"].items():
        samples = result.pop("equity_samples")
        result["equity_samples_archive"] = dict(path=str(full_path.relative_to(ROOT)),
            result_key=key, rows=len(samples), archive_sha256=sha(full_path))
    OUT.write_text(json.dumps(full, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("GATES", json.dumps(gates), flush=True)


if __name__ == "__main__":
    main()
