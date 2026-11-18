"""Reproduce the fixed PathRisk protocol on pre-holdout XAUUSD bars."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.market_atlas import OUT, ROOT, return_features, sha
from src.backtesting.master import HOLDOUT_FROM, load_master


def quantiles(values):
    return dict(zip(("p10", "median", "p90"), np.quantile(values, [.1, .5, .9]).tolist())) if len(values) else {}


def risk_paths(bars, returns):
    observed = pd.Series(returns).dropna()
    # At the opening of row i, only returns ending before i are available.
    previous_rms = observed.pow(2).rolling(60).mean().pow(.5).reindex(range(len(bars))).ffill().shift(1)
    starts = np.flatnonzero((bars["time"] % 14400 == 0) & previous_rms.gt(0).to_numpy())
    starts = starts[starts + 15 < len(bars)]
    grid = starts[:, None] + np.arange(16)
    complete = (bars["time"][grid] == bars["time"][starts, None] + 900*np.arange(16)).all(axis=1)
    grid, starts = grid[complete], starts[complete]
    opens = bars["open"][starts, None]
    scale = previous_rms.to_numpy()[starts, None]
    upper = np.log(bars["high"][grid]/opens) / scale
    lower = -np.log(bars["low"][grid]/opens) / scale
    def first_hit(paths):
        hits = paths >= 1
        return np.where(hits.any(axis=1), hits.argmax(axis=1), 16)
    up, down = first_hit(upper), first_hit(lower)
    first = np.minimum(up, down)
    touched = first < 16
    return dict(eligible=len(starts), incomplete=int((~complete).sum()), upper_first=int((up<down).sum()),
                lower_first=int((down<up).sum()), ambiguous=int(((up==down)&touched).sum()),
                timeout=int((~touched).sum()), upper_excursion_in_sigma=quantiles(upper.max(axis=1)),
                lower_excursion_in_sigma=quantiles(lower.max(axis=1)),
                first_hit_bar_one_based=quantiles(1+first[touched]))


def dependence(r):
    out = {}
    for lag in range(1, 9):
        windows = np.lib.stride_tricks.sliding_window_view(r, lag+1)
        sample = windows[np.isfinite(windows).all(axis=1)]
        # Gram matrix of centered columns; remove covariance explained by intervening lags.
        covariance = np.cov(sample, rowvar=False)
        precision = np.linalg.inv(covariance)
        out[lag] = dict(n=len(sample), pacf=float(-precision[0,-1]/np.sqrt(precision[0,0]*precision[-1,-1])))
    valid = np.isfinite(r[:-1]) & np.isfinite(r[1:])
    codes = (np.sign(r[:-1][valid])+1)*3 + (np.sign(r[1:][valid])+1)
    joint = np.bincount(codes.astype(int), minlength=9).reshape(3,3)/valid.sum()
    independent = joint.sum(axis=1)[:,None]*joint.sum(axis=0)
    used = joint > 0
    return dict(partial_autocorrelation=out, sign_mi_nats=float(np.sum(joint[used]*np.log(joint[used]/independent[used]))),
                sign_pair_count=int(valid.sum()), sign_joint=joint.tolist())


def describe(x):
    a = np.asarray(x)
    a = a[np.isfinite(a)]
    if not len(a):
        return dict(n=0)
    return dict(n=len(a), mean_bps=float(a.mean()*10000), rms_bps=float(np.sqrt(np.mean(a*a))*10000),
                fraction_up=float(np.mean(a>0)), quantiles_bps=quantiles(a*10000))


def calendar(b, r):
    utc = pd.to_datetime(b["time"], unit="s", utc=True)
    ny, lon, tok = (utc.tz_convert(z) for z in ("America/New_York","Europe/London","Asia/Tokyo"))
    def early(clock, left, right):
        hours = clock.hour + clock.minute/60
        return (hours>=left) & (hours<right)
    masks = {"Tokyo_09_15":early(tok,9,15),"London_08_09":early(lon,8,9),"London_09_12":early(lon,9,12),
             "London_NY_overlap":early(lon,8,17)&early(ny,8,17),"NY_0830_0930":early(ny,8.5,9.5),
             "NY_13_16":early(ny,13,16),"NY_17_18":early(ny,17,18)}
    periods = utc.tz_localize(None).to_period("M")
    dates = utc.normalize()
    table = pd.DataFrame({"month":periods,"day":dates,"quarter":utc.tz_localize(None).to_period("Q")})
    for unit in ("month","quarter"):
        last = table.groupby(unit)["day"].transform("max")
        masks["last_observed_day_"+unit] = (dates==last) & (table[unit] != table[unit].iloc[-1])
    sessions = {name:describe(r[mask]) for name,mask in masks.items()}
    weekend = (np.diff(b["time"])>=36*3600)&(np.diff(b["time"])<=84*3600)&(utc.weekday[:-1]==4)
    sessions["Friday_to_reopen_gap"] = describe(np.log(b["open"][1:]/b["close"][:-1])[weekend])
    quarters = {str(k):describe(x) for k,x in pd.Series(r).groupby(table.quarter)}
    close = pd.Series(b["close"], index=utc).groupby(dates).last()
    dd = close/close.cummax()-1
    underwater = dd<0
    episodes = []
    for _, values in dd.groupby(underwater.ne(underwater.shift()).cumsum()):
        if values.iloc[0] < 0:
            recovery = close.index.searchsorted(values.index[-1], side="right")
            episodes.append(dict(depth=float(-values.min()), underwater_closes=len(values),
                                 recovered=bool(recovery<len(close)), first=str(values.index[0]), trough=str(values.idxmin()),
                                 recovery=str(close.index[recovery]) if recovery<len(close) else None))
    return dict(session=sessions, quarter=quarters, daily_spot_drawdowns=episodes)


def macro_agreement():
    d = pd.read_csv(ROOT/"research/data/d1_study/master.csv", index_col="Date", parse_dates=True).loc[:"2026-10-31"]
    x, y, g = np.log(d.dxy).diff(), d.y10.diff(), np.log(d.gold).diff()
    return {name:dict(same_row=describe(g[mask]), next_row=describe(g.shift(-1)[mask]))
            for name, mask in {"both_rise":(x>0)&(y>0), "both_fall":(x<0)&(y<0),
                               "dollar_up_yield_down":(x>0)&(y<0), "dollar_down_yield_up":(x<0)&(y>0)}.items()}


def main():
    b = load_master(("M15",), end=HOLDOUT_FROM).m15
    assert b["time"].max()<HOLDOUT_FROM
    r, _ = return_features(b, 900)
    out = dict(script_sha256=sha(Path(__file__)), data_sha256=hashlib.sha256(b.tobytes()).hexdigest(),
               cutoff_exclusive=HOLDOUT_FROM, barriers=risk_paths(b,r), returns=dependence(r),
               magnitude=dependence(abs(r)), calendar=calendar(b,r), daily_macro=macro_agreement())
    path = OUT/"path_risk.json"
    path.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(out["barriers"]))


if __name__ == "__main__":
    main()
