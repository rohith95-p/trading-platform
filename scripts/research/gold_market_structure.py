"""Describe dependence and calendar shifts without opening trades."""
from itertools import groupby
import json
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from scripts.research.collect_gold_ticks import STORE, sha
from scripts.research.market_atlas import TF
from src.backtesting.master import HOLDOUT_FROM


def partial(values, lag):
    windows = sliding_window_view(values, lag+1)
    total = np.zeros((lag+1, lag+1))
    sums = np.zeros(lag+1)
    n = 0
    for i in range(0,len(windows),100_000):
        part = windows[i:i+100_000]
        part = part[np.isfinite(part).all(axis=1)]
        total += part.T @ part
        sums += part.sum(axis=0)
        n += len(part)
    if n < 100:
        return {"windows":n,"partial_correlation":None}
    cov = total/n-np.outer(sums/n,sums/n)
    ends = [0,lag]
    res = cov[np.ix_(ends,ends)]
    if lag>1:
        cross = cov[ends,1:-1]
        res = res - cross @ np.linalg.pinv(cov[1:-1,1:-1]) @ cross.T
    denom = np.sqrt(res[0,0]*res[1,1])
    return {"windows":n,"partial_correlation":float(res[0,1]/denom) if denom else None}


def mutual(values):
    cuts = np.unique(np.nanquantile(values,[.25,.5,.75]))
    valid = np.isfinite(values[:-1]) & np.isfinite(values[1:])
    labels = np.searchsorted(cuts,values,side="right")
    size = len(cuts)+1
    counts = np.bincount(labels[:-1][valid]*size+labels[1:][valid],minlength=size*size).reshape(size,size)
    probs = counts/counts.sum()
    independent = probs.sum(axis=0)[None,:]*probs.sum(axis=1)[:,None]
    keep = probs>0
    return dict(pairs=int(counts.sum()),bits=float(np.sum(probs[keep]*np.log2(probs[keep]/independent[keep]))),
                cuts_bps=cuts.tolist(),pair_counts=counts.tolist())


def shift(values, end_times):
    months = pd.to_datetime(end_times,unit="s",utc=True).tz_localize(None).to_period("M")
    grouped = pd.Series(abs(values),index=months).groupby(level=0).agg(["median","count"])
    medians = grouped.loc[grouped["count"]>=10,"median"]
    counts = medians.groupby(medians.index.year).size()
    years = counts.index[counts==12].to_list()
    runs = [[v for _,v in group] for _,group in groupby(enumerate(years),key=lambda p:p[1]-p[0])]
    longest = max(runs,key=len,default=[])
    if len(longest)<6:
        return dict(status="insufficient_contiguous_complete_years",complete_years=longest)
    sample = medians[np.isin(medians.index.year,longest)]
    x = sample.to_numpy()
    def search(a):
        curve = np.abs(np.cumsum(a-a.mean()))[23:len(a)-24]
        idx = int(np.argmax(curve))
        return idx+24, float(curve[idx])
    split, stat = search(x)
    rng = np.random.default_rng(20261118)
    blocks = x.reshape(-1,12)
    exceed = sum(search(blocks[rng.permutation(len(blocks))].ravel())[1]>=stat for _ in range(999))
    p = (1+exceed)/1000
    return dict(status="measured",complete_years=longest,first_month_after_split=str(sample.index[split]),
                mean_before_bps=float(x[:split].mean()),mean_after_bps=float(x[split:].mean()),
                cusum=stat,p_year_block=p,p_adjusted_six=min(1.,p*6))


def main():
    results = {}
    for tf, step in TF.items():
        path = STORE/"payload/master"/f"XAUUSDm_{tf}.npy"
        bars = np.load(path,mmap_mode="r",allow_pickle=False)
        ts = bars["time"].astype("int64")
        px = bars["close"]
        good = (np.diff(ts)==step) & (ts[1:]+step<HOLDOUT_FROM)
        good &= np.isfinite(px[:-1]) & np.isfinite(px[1:]) & (px[:-1]>0) & (px[1:]>0)
        ret = np.full(len(ts)-1,np.nan)
        ret[good] = np.log(px[1:][good]/px[:-1][good])*10000
        results[tf] = dict(input_sha256=sha(path),lags={str(k):partial(ret,k) for k in range(1,5)},
                           signed_mi=mutual(ret),absolute_mi=mutual(abs(ret)),shift=shift(ret,ts[1:]+step))
    (STORE/"market_structure.json").write_text(json.dumps(dict(protocol_commit="2a91b4a",results=results),
                                            indent=2,allow_nan=False)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
