"""Frozen four-lag forecasts of XAUUSD return and absolute return."""
from pathlib import Path
import hashlib
import json

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from src.backtesting.master import HOLDOUT_FROM, load_master


def samples(bars):
    """End timestamp, returns oldest first, next close-to-close dollar move."""
    times = sliding_window_view(bars["time"].astype("int64"), 6)
    closes = sliding_window_view(bars["close"].astype(float), 6)
    keep = (np.diff(times, axis=1) == 900).all(axis=1)
    keep &= (np.isfinite(closes) & (closes > 0)).all(axis=1)
    keep &= times[:, -1] + 900 < HOLDOUT_FROM
    px = closes[keep]
    return (times[keep, -1] + 900).astype("datetime64[s]"), np.diff(np.log(px), axis=1)*1e4, px[:, -1]-px[:, -2]


def bootstrap_gain(loss_gain, dates):
    months, groups = np.unique(dates.astype("datetime64[M]"), return_inverse=True)
    counts = np.bincount(groups)
    sums = np.bincount(groups, weights=loss_gain)
    choices = np.random.default_rng(20261118).integers(len(months), size=(1999, len(months)))
    draws = sums[choices].sum(axis=1) / counts[choices].sum(axis=1)
    return np.quantile(draws, [.025, .975]).tolist()


def model(values, dates, moves, magnitude):
    if magnitude:
        values = np.abs(values)
    # Columns use lag 1 through lag 4. Target is the following completed return.
    design = np.column_stack((np.ones(len(values)), values[:, 3::-1]))
    target = values[:, -1]
    years = dates.astype("datetime64[Y]").astype(int) + 1970
    train = (years >= 2004) & (years <= 2018)
    weights, _, rank, _ = np.linalg.lstsq(design[train], target[train], rcond=None)
    if rank != design.shape[1]:
        raise ValueError("Singular training design")
    baseline = float(target[train].mean())
    output = dict(train_observations=int(train.sum()), coefficients_intercept_then_lags=weights.tolist(),
                  constant_forecast_bps=baseline, periods={})
    for first, last in [(2019, 2024), (2025, 2025), (2026, 2026)]:
        select = (years >= first) & (years <= last)
        y, ts = target[select], dates[select]
        pred = design[select] @ weights
        reference_loss = (y-baseline)**2
        loss = (y-pred)**2
        gain = reference_loss-loss
        result = dict(n=len(y), first_close_utc=str(ts[0]), last_close_utc=str(ts[-1]),
                      months=len(np.unique(ts.astype("datetime64[M]"))),
                      baseline_mse_bps2=float(reference_loss.mean()), model_mse_bps2=float(loss.mean()),
                      mse_reduction_pct=float(100 * gain.mean() / reference_loss.mean()),
                      gain_bps2=float(gain.mean()), gain_ci95=bootstrap_gain(gain, ts))
        if not magnitude:
            result.update(direction_accuracy_pct=float(100*np.mean(np.sign(y)==np.sign(pred))),
                          baseline_direction_accuracy_pct=float(100*np.mean(np.sign(y)==np.sign(baseline))),
                          flat_targets=int(np.count_nonzero(y==0)),
                          forecast_signed_gross_move_usd_oz=float(np.mean(np.sign(pred)*moves[select])))
        output["periods"][str(first)] = result
    p = output["periods"]
    output["meets_broad_improvement_criterion"] = bool(all(v["mse_reduction_pct"] > 0 for v in p.values())
            and all(p[k]["gain_ci95"][0] > 0 for k in ("2019", "2025")))
    return output


def main():
    master = load_master(("M15",), end=HOLDOUT_FROM)
    bars = master.m15
    dates, values, moves = samples(bars)
    result = dict(protocol_commit="a99ffda", master_provenance=master.provenance,
                  bars_sha256=hashlib.sha256(bars.tobytes()).hexdigest(), input_bars=len(bars),
                  signed=model(values, dates, moves, False), absolute=model(values, dates, moves, True))
    output = Path(__file__).resolve().parents[2] / "research/results/gold_m15_forecast_2026-11-18.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
