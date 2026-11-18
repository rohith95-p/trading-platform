"""Pre-registered descriptive research; never a trade/execution simulator.

Run: venv/Scripts/python.exe -m scripts.research.market_atlas
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.backtesting.master import HOLDOUT_FROM, load_master

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/results/finalization_2026-11-18"
TF = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600, "H4": 14400, "D1": 86400}
SEED = 20261118


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def iso(t):
    return pd.Timestamp(int(t), unit="s", tz="UTC").isoformat()


def timestamp_column(frame):
    for col in ("time", "Date", "DATE", "date", "scheduled_utc", "timestamp", "datetime", "Unnamed: 0"):
        if col in frame:
            if col == "Unnamed: 0" and not frame[col].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}").all():
                continue
            if pd.api.types.is_numeric_dtype(frame[col]):
                return pd.to_datetime(frame[col], unit="s", utc=True, errors="coerce")
            return pd.to_datetime(frame[col], utc=True, errors="coerce", format="mixed")
    return None


def quality(frame, step=None):
    """No price summary is allowed on frozen observations."""
    stamp = timestamp_column(frame)
    out = {"rows": len(frame), "columns": list(frame.columns)}
    if stamp is not None:
        out.update(timestamp_invalid=int(stamp.isna().sum()),
                   duplicate_timestamps=int(stamp.dropna().duplicated().sum()),
                   timestamps_out_of_order=int((stamp.diff().dt.total_seconds() < 0).sum()),
                   first=str(stamp.min()), last=str(stamp.max()),
                   holdout_rows_excluded=int((stamp >= pd.Timestamp(HOLDOUT_FROM, unit="s", tz="UTC")).sum()))
        frame = frame.loc[stamp < pd.Timestamp(HOLDOUT_FROM, unit="s", tz="UTC")]
        times = stamp.loc[frame.index].dt.as_unit("s").astype("int64").to_numpy()
        gaps = np.diff(times)
        if len(gaps):
            out["largest_elapsed_gap_seconds"] = int(gaps.max())
            if step:
                ix = np.flatnonzero(gaps > step)
                top = ix[np.argsort(gaps[ix])[-5:][::-1]]
                out.update(adjacent_gaps_gt_step=int(len(ix)), off_grid_timestamps=int((times % step != 0).sum()),
                           largest_gaps=[{"after": iso(times[i]), "before": iso(times[i+1]),
                                          "elapsed_seconds": int(gaps[i])} for i in top])
    if stamp is None:
        out["status"] = "No recognized time column; only schema and row count available"
        return out
    out["analyzed_preholdout_rows"] = len(frame)
    if frame.empty:
        return out
    out["missing_values_preholdout"] = {str(k): int(v) for k, v in frame.isna().sum().items() if v}
    for prefix in ("", "bid_", "ask_"):
        cols = [prefix + x for x in ("open", "high", "low", "close")]
        if set(cols).issubset(frame.columns):
            o, h, l, c = (frame[k].to_numpy(float) for k in cols)
            bad = ~np.isfinite(o+h+l+c) | (l <= 0) | (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)
            out[prefix + "invalid_ohlc"] = int(bad.sum())
    if "spread" in frame:
        v = frame["spread"].to_numpy(float)
        out["spread_raw_points"] = {"zero_fraction": float(np.mean(v == 0)), "negative": int((v < 0).sum()),
                                     "quantiles": np.quantile(v, [.01, .5, .95, .99]).tolist()}
    if {"bid_open", "ask_open"}.issubset(frame.columns):
        d = frame.ask_open - frame.bid_open
        out["observed_open_spread_usd_quantiles"] = d.quantile([.01, .5, .95, .99]).to_dict()
        out["crossed_open_quotes"] = int((d < 0).sum())
    return out


def inventory():
    paths = sorted({p for directory in (ROOT / "research").glob("data*") if directory.is_dir()
                    for ext in ("*.npy", "*.csv") for p in directory.rglob(ext)} |
                   set((ROOT / "research/events").glob("*.csv")))
    results = []
    for path in paths:
        rec = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
        try:
            step = next((s for tf, s in TF.items() if path.stem.endswith("_"+tf)), None)
            if path.suffix == ".npy":
                a = np.load(path, mmap_mode="r", allow_pickle=False)
                rec["dtype"] = str(a.dtype)
                if a.dtype.names:
                    rec.update(quality(pd.DataFrame.from_records(a.reshape(-1)), step))
                    if a.ndim > 1:
                        rec["partition_shape"] = list(a.shape)
                        rec["partition_note"] = "Flattened event windows; overlap and ordering across partitions are expected, not a continuous tradable series."
                else:
                    rec.update(shape=list(a.shape), note="Nonstructured numeric array; no guessed schema")
            else:
                rec.update(quality(pd.read_csv(path), step))
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
        results.append(rec)
        print("inventory", rec["path"], flush=True)
    return results


def hour_from_m15(a):
    f = pd.DataFrame.from_records(a)
    f["bucket"] = f.time // 3600 * 3600
    g = f.groupby("bucket", sort=True)
    r = g.agg(time=("time", "min"), last=("time", "max"), count=("time", "size"),
              open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    r = r[(r["count"] == 4) & (r.time == r.index) & (r["last"] == r.index + 2700)]
    return r.drop(columns=["last", "count"]).to_records(index=False)


def clustered_effect(values, mask, months, contrast=None):
    """Monthly cluster bootstrap, with observation-weighted means and fixed seed."""
    good = np.isfinite(values) & mask
    other = np.zeros(len(values), bool) if contrast is None else np.isfinite(values) & contrast
    unique, ids = np.unique(months, return_inverse=True)
    n = np.bincount(ids[good], minlength=len(unique))
    sums = np.bincount(ids[good], weights=values[good], minlength=len(unique))
    nb = np.bincount(ids[other], minlength=len(unique))
    sb = np.bincount(ids[other], weights=values[other], minlength=len(unique))
    if n.sum() == 0 or (contrast is not None and nb.sum() == 0):
        return {"observations": int(n.sum()), "status": "insufficient"}
    estimate = sums.sum()/n.sum() - (sb.sum()/nb.sum() if contrast is not None else 0)
    rng = np.random.default_rng(SEED)
    ix = rng.integers(0, len(unique), size=(999, len(unique)))
    with np.errstate(invalid="ignore", divide="ignore"):
        boot = sums[ix].sum(1)/n[ix].sum(1)
        if contrast is not None:
            boot -= sb[ix].sum(1)/nb[ix].sum(1)
    boot = boot[np.isfinite(boot)]
    p = (1+np.count_nonzero(np.abs(boot-estimate) >= abs(estimate)))/(1+len(boot))
    return {"observations": int(n.sum()), "comparison_observations": int(nb.sum()),
            "months": len(unique), "estimate_log_return": float(estimate),
            "ci95": np.quantile(boot, [.025, .975]).tolist(), "p_centered_bootstrap": float(p),
            "p_bonferroni18": float(min(1, 18*p)), "bootstrap_replicates": len(boot)}


def return_features(a, step):
    t = a["time"].astype(np.int64)
    c = a["close"].astype(float)
    r = np.full(len(a), np.nan)
    valid = (np.diff(t) == step) & (c[1:] > 0) & (c[:-1] > 0)
    r[1:] = np.where(valid, np.log(c[1:]/c[:-1]), np.nan)
    # Previous60 valid adjacent returns; never insert a return across a gap.
    observed = pd.Series(r).dropna()
    scale = observed.pow(2).rolling(60, min_periods=60).mean().pow(.5).shift(1).reindex(range(len(r))).to_numpy()
    return r, scale


def study(a, step):
    t = a["time"].astype(np.int64)
    c = a["close"].astype(float)
    r, scale = return_features(a, step)
    pair = np.isfinite(r[:-1]) & np.isfinite(r[1:])
    x = r[np.isfinite(r)]
    fwd = np.r_[r[1:], np.nan]
    ext = (np.abs(r) > 2*scale) & np.isfinite(scale)
    ordinary = ~ext & np.isfinite(scale) & np.isfinite(r)
    months = t.astype("datetime64[s]").astype("datetime64[M]").astype(str)
    signed = np.sign(r)*fwd
    out = {"rows": len(a), "first": iso(t[0]), "last": iso(t[-1]), "valid_adjacent_returns": len(x),
           "excluded_nonadjacent_or_invalid_returns": int(len(r)-1-len(x)),
           "mean_log_return": float(np.mean(x)), "sd": float(np.std(x)),
           "skew": float(stats.skew(x)), "excess_kurtosis": float(stats.kurtosis(x)),
           "return_quantiles": np.quantile(x, [.001, .01, .05, .5, .95, .99, .999]).tolist(),
           "return_lag1": float(np.corrcoef(r[:-1][pair], r[1:][pair])[0,1]),
           "absolute_return_lag1": float(np.corrcoef(np.abs(r[:-1][pair]), np.abs(r[1:][pair]))[0,1]),
           "effects": {"extreme_continuation": clustered_effect(signed, ext, months),
                       "ordinary_continuation": clustered_effect(signed, ordinary, months),
                       "extreme_next_volatility_premium": clustered_effect(np.abs(fwd), ext, months, ordinary)}}
    # Subsequent bar extrema relative to prior close, in trigger direction.
    hi = np.r_[a["high"][1:], np.nan]
    lo = np.r_[a["low"][1:], np.nan]
    move_up, move_down = hi/c-1, lo/c-1
    favorable = np.where(r >= 0, move_up, -move_down)
    adverse = np.where(r >= 0, -move_down, move_up)
    eligible = ext & np.isfinite(fwd)
    out["extreme_next_bar_excursions"] = {
        "n": int(eligible.sum()), "mean_favorable_fraction": float(np.mean(favorable[eligible])) if eligible.any() else None,
        "mean_adverse_fraction": float(np.mean(adverse[eligible])) if eligible.any() else None,
        "note": "Descriptive range from previous close; not executable MFE/MAE or barrier ordering."}
    out["eras"] = {}
    year = pd.to_datetime(t, unit="s", utc=True).year.to_numpy()
    for label, lower, upper in (("2004_2015",2004,2016),("2016_2021",2016,2022),("2022_oct2026",2022,2027)):
        m = (year >= lower) & (year < upper) & eligible
        out["eras"][label] = {"extreme_n": int(m.sum()),
                             "extreme_signed_forward_mean": float(np.mean(signed[m])) if m.any() else None}
    if step == 900:
        local = pd.to_datetime(t, unit="s", utc=True)
        out["local_clock_descriptive"] = {}
        for zone in ("Europe/London", "America/New_York", "Asia/Tokyo"):
            hours = local.tz_convert(zone).hour
            rows = []
            for hour in range(24):
                y = r[(hours == hour) & np.isfinite(r)]
                rows.append({"hour":hour,"n":len(y),"mean_bps":float(np.mean(y)*10000),
                             "rms_bps":float(np.sqrt(np.mean(y*y))*10000)})
            out["local_clock_descriptive"][zone] = rows
    return out


def macro():
    f = pd.read_csv(ROOT / "research/data/d1_study/master.csv", index_col=0, parse_dates=True)
    f = f[f.index < "2026-11-01"].sort_index()
    gold = np.log(f.gold).diff()
    out = {}
    for name in ("dxy", "y10", "vix", "spx", "gld"):
        change = f[name].diff() if name == "y10" else np.log(f[name].where(f[name] > 0)).diff()
        both = pd.concat([gold, change, change.shift(1)], axis=1).dropna()
        out[name] = {"n_complete":len(both), "contemporaneous_corr":float(both.iloc[:,0].corr(both.iloc[:,1])),
                     "previous_row_change_corr":float(both.iloc[:,0].corr(both.iloc[:,2])),
                     "warning":"Daily labels lack release/close time/vintage; lagged row is not certified causal availability."}
    return out


def write_reports(result):
    stats_by_tf = result["timeframes"]
    lines = ["# Gold market atlas — 2026-11-18", "", "Exploratory empirical evidence, not a profitable strategy or independent holdout test.", "",
             "Protocol committed before computation, with a committed clarification after the first run exposed empty hourly/daily groups: volatility uses previous60 valid adjacent returns, not60 consecutive elapsed bars. That first run failed serialization; this correction is disclosed rather than called independent confirmation. Frozen November2026 observations excluded. All historical eras here have influenced prior project research; splitting them again does not restore independence.", "",
             "## Distributions and dependence", "", "| TF | Bars | Return pairs | Skew | Excess kurtosis | Return lag1 | Absolute lag1 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, d in stats_by_tf.items():
        lines.append(f"| {name} | {d['rows']:,} | {d['valid_adjacent_returns']:,} | {d['skew']:.3f} | {d['excess_kurtosis']:.2f} | {d['return_lag1']:.4f} | {d['absolute_return_lag1']:.4f} |")
    lines += ["", "Adjacent exact-duration returns only; market closures and missing observations are excluded. This conditions the sample toward continuous trading and understates reopening jump exposure. Fat tails and volatility persistence describe risk; neither establishes directional trading edge.", "",
              "## Fixed conditional effects", "", "Extreme means absolute return >2× previous60-bar RMS. Subsequent return must be adjacent. Monthly cluster bootstrap999 resamples, seed20261118; Bonferroni18 applies only to this fixed family, not prior research searches.", "",
              "| TF | Effect | N | Mean bps | 95% interval bps | Adjusted p |", "|---|---|---:|---:|---|---:|"]
    for name, d in stats_by_tf.items():
        for effect, e in d["effects"].items():
            if "ci95" in e:
                lines.append(f"| {name} | {effect} | {e['observations']:,} | {e['estimate_log_return']*1e4:.3f} | [{e['ci95'][0]*1e4:.3f}, {e['ci95'][1]*1e4:.3f}] | {e['p_bonferroni18']:.3f} |")
    lines += ["", "A volatility premium predicts movement magnitude, not profitable direction. Signed continuation is measured from close to next close, before executable spread/fees/slippage. Monthly resampling assumes month clusters exchangeable and does not establish stationary regimes. Microstructure bid bounce, source differences and close-price conventions can dominate tiny signed effects.", "",
              "## Sessions, excursions and regimes", "", "Machine-readable results include24 local-clock bins for London, NewYork and Tokyo with daylight-saving conversion, fixed-era extreme-return effects, and next-bar range excursions. These are descriptive; no best session is selected. Range extrema do not identify first passage, executable path, or stop-before-target order. Separate native resolutions have different coverage; H1 is constructed from complete four-M15 groups because BarSet exposes no H1 field. Cross-timeframe rankings are confounded by source and era.", "",
              "## Macro explanations versus predictions", "", "| Variable | Complete rows | Same-row correlation | Previous-row correlation |", "|---|---:|---:|---:|"]
    for name, d in result["macro"].items():
        lines.append(f"| {name} | {d['n_complete']} | {d['contemporaneous_corr']:.4f} | {d['previous_row_change_corr']:.4f} |")
    lines += ["", "Daily proxy CSVs have no certified quote timestamp, release vintage or synchronous close. Gold may be a futures proxy; ETF exposure mechanically tracks gold. Same-row association is explanatory, and previous-row association is only a candidate feature audit. No economic-announcement surprise can be reconstructed from release dates alone.", "",
              "## Economic model and next evidence", "", "For observable information F_t and executable action a, V(a|F_t)=E[liquidation cashflow−entry cashflow−commission−financing−slippage|F_t]. Abstain when the lower uncertainty bound on incremental V relative to matched-time random-direction and exposure controls is nonpositive. Estimate outcomes with real bid/ask paths and full account constraints. Price-return dependence alone is insufficient.", "",
              "The fixed extreme-return study is a mechanism screen. Any candidate needs a separate committed specification, strictly causal features, BacktestEngine minute execution, historical-cost stress, matched-time controls and prospective demo confirmation. No new strategy is approved from this atlas. The remaining gaps include PACF/MI/change-point formal tests, calibrated live slippage, quote/trade arrival data, joint DXY/yield timestamp alignment, barrier-time distributions, and central-bank data with publication vintages. These are not claimed completed.", "",
              "Reproduce: `venv/Scripts/python.exe -m scripts.research.market_atlas`. Inputs, source provenance, code hash and detailed results: `research/results/finalization_2026-11-18/market_atlas.json`."]
    (ROOT / "research/GOLD_MARKET_ATLAS.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    inv = result["inventory"]
    lines = ["# Data forensics report — 2026-11-18", "", f"Scanned {len(inv)} accessible NPY/CSV files under research/data* and research/events. Per-file content hashes and numerical diagnostics are saved in market_atlas.json. This is a bounded inventory, not a claim to have inspected all laptop files or JSON trade records.", "",
             "| File | Rows | Preholdout rows | Duplicates | Largest elapsed gap seconds | Error |", "|---|---:|---:|---:|---:|---|"]
    for d in inv:
        lines.append(f"| {d['path']} | {d.get('rows','?')} | {d.get('analyzed_preholdout_rows','?')} | {d.get('duplicate_timestamps','?')} | {d.get('largest_elapsed_gap_seconds','?')} | {d.get('error','')} |")
    lines += ["", "## Interpretation and restrictions", "", "Elapsed gaps include scheduled closures; no complete historical broker session/holiday calendar has been established. Duplicate event timestamps can be legitimate simultaneous releases; they are not automatically duplicate events. Missing fields are not imputed. NPY rows after November1 are counted by timestamp but their prices are excluded from diagnostics. Whole-file hashing does not evaluate holdout returns.", "",
              "Broker/archive source priority and the January2026 archive cutoff remain as declared in master.py. Dukascopy bid/ask snapshots remain separate and are not spliced into broker data. A valid OHLC envelope is not verification of first-touch ordering or a complete tick history. Spread points require historical point/digit metadata; zero values are not free execution. Tick volume is quote activity rather than centralized gold transaction volume.", "",
              "The September–October2025 archive hole and January2026 archive divergence invalidate continuous account conclusions through those spans without a declared missing-data policy. Historical backtest artifacts with unchecked gaps are not upgraded by this inventory. A recent broker cache does not reconstruct prior actual Atlas terms or fills.", "",
              "Raw daily macro CSVs lack vintage and close-time availability. Event-calendar source labels/verified flags are metadata, not independent release-time or surprise validation. Remaining trade-log forensics and native-tick/broker reconciliation are documented separately in BACKTEST_REALITY_AUDIT and DEPLOYMENT_READINESS.", "",
              "The daily gold proxy contains441 inconsistent OHLC envelopes; for example2001-02-13 has open/high/low261 and close260.299988, and2003-04-29 has open/high/low333 and close333.700012. Settlement or adjustment conventions require source verification. Do not use these rows as executable gold OHLC. The BLS array is163×61 event windows; its flattened representation is annotated and is not certified as a continuous tradable series. Archive and Genesis spread columns are100% zero, hence missing cost evidence rather than zero-cost execution.", "",
              "Master M5 includes100,000 observations although a larger raw M5 archive exists: master source declarations do not select that archive resolution. This source-coverage difference, and limited native H4 history, confound cross-timeframe rankings. The audit preserved the loader declarations."]
    (ROOT / "research/DATA_FORENSICS_REPORT.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"protocol":"research/registry/PREREG_MarketAtlas_2026-11-18.md", "script_sha256":sha(Path(__file__)),
              "cutoff_exclusive":iso(HOLDOUT_FROM), "classification":"exploratory_previously_explored_history",
              "inventory":inventory(), "timeframes":{}, "provenance":{}}
    # Save numerical inventory before the heavier master merges.
    (OUT / "data_inventory.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    for tf in TF:
        source_tf = "M15" if tf == "H1" else tf
        bars = load_master((source_tf,), end=HOLDOUT_FROM, use_cache=False)
        a = getattr(bars, source_tf.lower())
        if tf == "H1":
            a = hour_from_m15(a)
        assert np.all(a["time"] < HOLDOUT_FROM)
        result["timeframes"][tf] = study(a, TF[tf])
        result["provenance"][tf] = bars.provenance
        print("studied", tf, len(a), flush=True)
        del bars, a
    result["macro"] = macro()
    (OUT / "market_atlas.json").write_text(json.dumps(result, indent=2, allow_nan=False, default=str), encoding="utf-8")
    write_reports(result)
    print("Reports written", flush=True)


if __name__ == "__main__":
    main()
