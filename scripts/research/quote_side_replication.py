"""Fixed preregistered quote-side conditional-outcome study, not a backtest.

No orders, positions, stops, account returns, PF or strategy qualification. This
source-forensics exception reads explicitly requested independent quote data;
it does not replace master data or bypass BacktestEngine for a strategy test.
"""
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "research/data/dukascopy_2025/XAUUSD_M1_bidask.npy"
EXPECTED_SHA = "71b2a48870e0b53bf8e634fb3ebc8589dd88d44a828559e618d2b0dd104328f8"
PROTOCOL = ROOT / "research/registry/PREREG_QuoteSideReplication_2026-11-18.md"
OUTPUT = ROOT / "research/results/finalization_2026-11-18/quote_side_replication.json"
REPORT = ROOT / "research/QUOTE_SIDE_REPLICATION.md"
START = 1735689600
END = 1767225600


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(a):
    needed = {"time", *(f"{side}_{field}" for side in ("bid", "ask")
                         for field in ("open", "high", "low", "close"))}
    if not needed <= set(a.dtype.names or ()):
        raise ValueError("quote side fields missing")
    t = a["time"]
    if np.any(t % 60) or np.any(np.diff(t) <= 0):
        raise ValueError("timestamps must be unique increasing minute boundaries")
    for side in ("bid", "ask"):
        x = {name: a[f"{side}_{name}"] for name in ("open", "high", "low", "close")}
        if any(np.any(~np.isfinite(v) | (v <= 0)) for v in x.values()):
            raise ValueError("invalid quote price")
        if np.any(x["low"] > np.minimum(x["open"], x["close"])) or np.any(
                x["high"] < np.maximum(x["open"], x["close"])) or np.any(x["low"] > x["high"]):
            raise ValueError("invalid quote OHLC")
    if any(np.any(a[f"ask_{f}"] < a[f"bid_{f}"]) for f in ("open", "high", "low", "close")):
        raise ValueError("crossed quote fields")


def aggregate(a, step):
    if step == 60:
        return a.copy()
    if step != 900:
        raise ValueError("only preregistered resolutions allowed")
    t = a["time"].astype(np.int64)
    starts = np.flatnonzero(t % step == 0)
    starts = starts[starts + 14 < len(a)]
    valid = np.array([np.all(np.diff(t[i:i + 15]) == 60) for i in starts])
    starts = starts[valid]
    result = np.empty(len(starts), dtype=a.dtype)
    for field in a.dtype.names:
        if field == "time":
            result[field] = t[starts]
        elif field.endswith("_open"):
            result[field] = a[field][starts]
        elif field.endswith("_close"):
            result[field] = a[field][starts + 14]
        elif field.endswith("_high"):
            result[field] = np.array([np.max(a[field][i:i + 15]) for i in starts])
        elif field.endswith("_low"):
            result[field] = np.array([np.min(a[field][i:i + 15]) for i in starts])
        else:
            raise ValueError("unexpected field: " + field)
    return result


def features(a, step):
    c = (a["bid_close"] + a["ask_close"]) / 2
    returns = np.full(len(a), np.nan)
    good = np.diff(a["time"]) == step
    returns[1:] = np.where(good, np.log(c[1:] / c[:-1]), np.nan)
    observed = pd.Series(returns).dropna()
    rms = observed.pow(2).rolling(60, min_periods=60).mean().pow(.5).shift(1).reindex(range(len(a))).to_numpy()
    return returns, rms


def outcomes(a, minute_times, step):
    """Per-signal descriptive endpoints, never a realized portfolio ledger."""
    t = a["time"].astype(np.int64)
    r, rms = features(a, step)
    valid = np.zeros(len(a), dtype=bool)
    eligible = np.flatnonzero(np.isfinite(r) & np.isfinite(rms) & (r != 0))
    eligible = eligible[eligible + 2 < len(a)]
    direction = -np.sign(r)
    reference = np.full(len(a), np.nan)
    mid_move = reference.copy()
    spread_cost = reference.copy()
    side_move = reference.copy()
    mid_close = (a["bid_close"] + a["ask_close"]) / 2
    mid_open = (a["bid_open"] + a["ask_open"]) / 2
    opening_spread = a["ask_open"] - a["bid_open"]
    for i in eligible:
        if t[i + 1] != t[i] + step or t[i + 2] != t[i] + 2 * step:
            continue
        entry, exit_ = t[i + 1], t[i + 2]
        left, right = np.searchsorted(minute_times, [entry, exit_])
        if right >= len(minute_times) or minute_times[right] != exit_:
            continue
        path = minute_times[left:right + 1]
        if len(path) != step // 60 + 1 or np.any(np.diff(path) != 60):
            continue
        if entry < START or exit_ >= END:
            continue
        valid[i] = True
        reference[i] = direction[i] * (mid_close[i + 1] - mid_close[i])
        mid_move[i] = direction[i] * (mid_open[i + 2] - mid_open[i + 1])
        spread_cost[i] = (opening_spread[i + 1] + opening_spread[i + 2]) / 2
        side_move[i] = (a["bid_open"][i + 2] - a["ask_open"][i + 1] if direction[i] > 0
                        else a["bid_open"][i + 1] - a["ask_open"][i + 2])
    if valid.any() and not np.allclose(side_move[valid], mid_move[valid] - spread_cost[valid], atol=1e-10):
        raise AssertionError("quote side reconciliation failed")
    return dict(time=t, return_=r, rms=rms, direction=direction, valid=valid,
                extreme=valid & (np.abs(r) > 2 * rms), reference=reference,
                mid=mid_move, spread=spread_cost, side=side_move)


def match_controls(x, step):
    history = defaultdict(lambda: deque(maxlen=20))
    matched, controls = [], []
    for i in np.flatnonzero(x["valid"]):
        stamp = int(x["time"][i] + step)
        date = pd.Timestamp(stamp, unit="s", tz="UTC")
        key = (date.strftime("%Y-%m"), date.hour, int(np.sign(x["return_"][i])))
        if x["extreme"][i]:
            for j in reversed(history[key]):
                if stamp - int(x["time"][j] + step) > 7 * 86400:
                    continue
                if .5 * x["rms"][i] <= x["rms"][j] <= 2 * x["rms"][i]:
                    matched.append(i)
                    controls.append(j)
                    break
        else:
            history[key].append(i)
    return np.array(matched, dtype=int), np.array(controls, dtype=int)


def uncertainty(values, times):
    if not len(values):
        return dict(n=0, mean=None, ci95=None, utc_weeks=0, p_centered=None, p_bonferroni4=None)
    # Fixed Monday-anchored UTC calendar weeks, not exchange sessions.
    weeks = (times.astype(np.int64) + 3 * 86400) // (7 * 86400)
    unique, group = np.unique(weeks, return_inverse=True)
    counts = np.bincount(group).astype(float)
    sums = np.bincount(group, weights=values)
    mean = float(values.mean())
    rng = np.random.default_rng(20261118)
    choices = rng.integers(0, len(unique), size=(1999, len(unique)))
    boot = sums[choices].sum(axis=1) / counts[choices].sum(axis=1)
    centered = boot - mean
    p = float((1 + np.sum(np.abs(centered) >= abs(mean))) / (len(boot) + 1))
    return dict(n=len(values), mean=mean, ci95=np.quantile(boot, [.025, .975]).tolist(),
                utc_weeks=len(unique), p_centered=p, p_bonferroni4=min(1., 4 * p),
                bootstrap_draws=1999, limitation="One explored calendar year; resampled weeks not independent prospective trials.")


def study(a, step):
    bars = aggregate(a, step)
    x = outcomes(bars, a["time"].astype(np.int64), step)
    event = np.flatnonzero(x["extreme"])
    paired, controls = match_controls(x, step)
    default = x["side"] - .035 - .04
    primary = uncertainty(default[event], x["time"][event] + step)
    difference = uncertainty(default[paired] - default[controls], x["time"][paired] + step)
    costs = []
    for multiplier in (1., 1.5, 2.):
        for slippage in (0., .04, .10):
            samples = x["mid"][event] - multiplier * x["spread"][event] - .035 - slippage
            costs.append(dict(spread_multiplier=multiplier, round_trip_slippage=slippage,
                              commission=.035, mean=float(samples.mean()) if len(samples) else None))
    months = {}
    for month in range(1, 13):
        e = event[pd.to_datetime(x["time"][event], unit="s", utc=True).month == month]
        months[str(month)] = dict(n=len(e), default_net_mean=float(default[e].mean()) if len(e) else None)
    reused = Counter(controls.tolist())
    return dict(resolution_seconds=step, complete_bars=len(bars), valid_endpoint_observations=int(x["valid"].sum()),
                extreme_events=len(event), matched_events=len(paired), unique_controls=len(reused),
                max_control_reuse=max(reused.values(), default=0), reference_move_mean=float(x["reference"][event].mean()),
                causal_mid_open_mean=float(x["mid"][event].mean()), quote_side_mean=float(x["side"][event].mean()),
                observed_endpoint_spread_hurdle_mean=float(x["spread"][event].mean()),
                same_timestamp_balanced_side_default_mean=float((-x["spread"][event] - .075).mean()),
                matched_ordinary_default_mean=float(default[controls].mean()) if len(controls) else None,
                primary_default_net=primary, primary_matched_difference=difference,
                default_spread_multiple=1., default_commission=.035, default_slippage=.04,
                cost_stress=costs, months=months,
                promoted=False, classification="mechanism_quote_hurdle_only_not_strategy_or_account_simulation")


def main():
    protocol_rel = str(PROTOCOL.relative_to(ROOT)).replace("\\", "/")
    frozen = subprocess.check_output(["git", "show", f"HEAD:{protocol_rel}"], cwd=ROOT)
    if frozen != PROTOCOL.read_bytes().replace(b"\r\n", b"\n"):
        raise ValueError("protocol must be committed unchanged before computation")
    if sha(SOURCE) != EXPECTED_SHA:
        raise ValueError("input hash differs from preregistration")
    a = np.load(SOURCE, allow_pickle=False)
    validate(a)
    if np.any(a["time"] >= END):
        raise ValueError("input crosses frozen study boundary")
    payload = dict(protocol_sha256=sha(PROTOCOL), script_sha256=sha(Path(__file__)), input_sha256=sha(SOURCE),
                   git_head_before_eval=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   input_rows=len(a), sample="2025 endpoints only; December2024 warmup; not untouched",
                   studies={label: study(a, step) for label, step in (("M1", 60), ("M15", 900))},
                   caveats=["Separate minute Bid/Ask aggregates are not certified synchronous ticks.",
                            "No broker fills, actual slippage or Atlas fees observed.",
                            "Overlapping event outcomes and reused controls are not an attainable portfolio.",
                            "No financing, barriers, account rules or strategy qualification tested."])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Quote-side replication of extreme-return reversal", "", "Fixed preregistered mechanism study on the saved independent-source Dukascopy bid/ask2025 snapshot. **No strategy, account or payout result is claimed.** November2026 holdout untouched. Previously researched2025 is exploratory replication, not independent temporal confirmation.", "",
             "| Resolution | Extreme observations | Reference reversal $/oz | Causal mid-open outcome $/oz | Observed quote-side outcome $/oz | Default after-friction mean [95% interval] $/oz |",
             "|---|---:|---:|---:|---:|---|"]
    for label, d in payload["studies"].items():
        primary = d["primary_default_net"]
        lines.append(f"| {label} | {d['extreme_events']:,} | {d['reference_move_mean']:.5f} | {d['causal_mid_open_mean']:.5f} | {d['quote_side_mean']:.5f} | {primary['mean']:.5f} [{primary['ci95'][0]:.5f}, {primary['ci95'][1]:.5f}] |")
    lines += ["", "Default friction is observed endpoint spreads plus assumed$0.035/oz commission and$0.04/oz round-trip adverse slippage. The nine fixed spread/slippage stress combinations, month counts/means, matched-control comparisons, weekly bootstrap uncertainty and hashes are in `results/finalization_2026-11-18/quote_side_replication.json`.", "",
              "## Controls and uncertainty", ""]
    for label, d in payload["studies"].items():
        p = d["primary_default_net"]
        delta = d["primary_matched_difference"]
        lines.append(f"- {label}: {d['matched_events']} matched observations, {d['unique_controls']} unique prior controls, maximum reuse{d['max_control_reuse']}. Matched extreme-minus-ordinary default mean{delta['mean']:.5f} $/oz, interval{delta['ci95']}; Bonferroni4 p={delta['p_bonferroni4']:.4f}. Default event mean uses{p['utc_weeks']} UTC-week clusters; Bonferroni4 p={p['p_bonferroni4']:.4f}. Balanced-direction same-time default outcome={d['same_timestamp_balanced_side_default_mean']:.5f} $/oz.")
    lines += ["", "A significant negative default mean is evidence against economic feasibility, not evidence of a profitable inverted strategy. Comparing extremes to ordinary observations can detect relative information while absolute outcomes remain negative. No threshold, holding interval or cost assumption is tuned to rescue the result.", "",
              "## Causality and limitations", "", "Signals use completed mid-close returns and only previous60 valid-return RMS. Endpoints begin at the next quote open and end exactly one interval later. Missing boundary/intervening minutes are excluded rather than filled. Bid/ask side marking reconciles independently with mid movement minus endpoint half-spread sum. Matched controls are prior observations with the same month, UTC hour and return sign and comparable lagged volatility; their outcomes never select them. Overlap and reused controls limit independence even with week clustering. Separate bid/ask minute aggregates do not prove synchronous tick quotes or obtainable fills. Financing, latency beyond assumed slippage, stop execution, account constraints and Atlas contract verification remain outside scope.", "",
              "## Decision", "", "This study does not promote a strategy. Consult every fixed cost cell and primary interval in the machine-readable artifact before proposing a separately committed BacktestEngine candidate. No PF, account drawdown or payout rate has been manufactured for these descriptive event outcomes.", "",
              "Reproduce: `.\\venv\\Scripts\\python.exe -m scripts.research.quote_side_replication`. Protocol: `registry/PREREG_QuoteSideReplication_2026-11-18.md`."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for label, d in payload["studies"].items():
        print(label, json.dumps(d["primary_default_net"]), flush=True)


if __name__ == "__main__":
    main()
