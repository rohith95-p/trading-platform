"""Delayed macro feature feasibility, following preregistration 2a7d847."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.market_atlas import ROOT, OUT, sha
from src.backtesting.master import HOLDOUT_FROM, load_master
from src.backtesting.costs import SCENARIOS


def macro_side_at(dates, frame):
    if not frame.index.is_monotonic_increasing or not frame.index.is_unique:
        raise ValueError("Macro dates must be unique and chronological")
    idx = frame.index.searchsorted(dates, side="left")-2
    valid = idx>=1
    selected = np.maximum(idx,1)
    feature_date = frame.index[selected]
    prior_date = frame.index[selected-1]
    valid &= ((dates-feature_date).days<=7) & ((feature_date-prior_date).days<=5)
    changes = frame[["dxy","y10"]].diff().to_numpy()[selected]
    side = np.where((changes<0).all(axis=1),1,np.where((changes>0).all(axis=1),-1,0))
    return np.where(valid,side,0),feature_date


def summary(f):
    return dict(n=len(f),long=int((f.side==1).sum()),first=str(f.index.min()),last=str(f.index.max()),
                candidate_mean=float(f.net.mean()),always_long_mean=float(f.buy.mean()),
                always_short_mean=float(f.sell.mean()), balanced_mean=float((f.buy+f.sell).mean()/2),
                advantage_over_long=float(f.delta.mean()),double_cost_mean=float(f.stress.mean()))


def main():
    macro_path=ROOT/"research/data/d1_study/master.csv"
    macro=pd.read_csv(macro_path,index_col="Date",parse_dates=True).loc[:"2026-10-31"]
    b=load_master(("M15",),end=HOLDOUT_FROM)
    a=b.m15
    clock=pd.to_datetime(a["time"],unit="s",utc=True).tz_convert("America/New_York")
    starts=np.flatnonzero((clock.hour==9)&(clock.minute==45)&(clock.year>=2005))
    starts=starts[starts+24<len(a)]
    grids=starts[:,None]+np.arange(25)
    contiguous=(a["time"][grids]==a["time"][starts,None]+900*np.arange(25)).all(axis=1)
    starts=starts[contiguous]
    dates=clock[starts].tz_localize(None).normalize()
    side,feature_dates=macro_side_at(dates,macro)
    cost=SCENARIOS["realistic_ecn"]
    common=2*cost.slip(b.spec.point)+cost.commission(.02)/(.02*b.spec.contract_size)
    spread=lambda at: np.array([cost.spread_price(b.spec.point,p) for p in a["spread"][at]])
    buy_cost=spread(starts)+common
    sell_cost=spread(starts+24)+common
    move=a["open"][starts+24]-a["open"][starts]
    f=pd.DataFrame(dict(feature_date=feature_dates,side=side,buy=move-buy_cost,sell=-move-sell_cost),index=dates)
    f["net"]=np.where(side==1,f.buy,f.sell)
    f["stress"]=f.net-np.where(side==1,buy_cost,sell_cost)
    f["delta"]=f.net-f.buy
    f=f[f.side!=0]
    era={name:summary(f.loc[start:end]) for name,start,end in
         [("early","2005","2013"),("middle","2014","2020"),("recent","2021","2026")]}
    month=f.delta.groupby(f.index.to_period("M")).agg(["count","sum"])
    rng=np.random.default_rng(81)
    draws=rng.integers(0,len(month),size=(1999,len(month)))
    boot=month["sum"].to_numpy()[draws].sum(axis=1)/month["count"].to_numpy()[draws].sum(axis=1)
    ci=np.quantile(boot,[.025,.975]).tolist()
    run=dict(code_sha256=sha(Path(__file__)),macro_sha256=sha(macro_path),
             bar_sha256=hashlib.sha256(a.tobytes()).hexdigest(),eras=era,all=summary(f),ci95_advantage=ci,
             gate=bool(ci[0]>0 and all(v["n"]>=100 and min(v["candidate_mean"],v["advantage_over_long"])>0 for v in era.values())),
             missing_grid_session_starts=int((~contiguous).sum()),proxy_columns=["dxy","y10"],
             units="USD per ounce, session endpoint screen")
    (OUT/"delayed_macro_agreement.json").write_text(json.dumps(run,indent=2,allow_nan=False))
    print(json.dumps(run,indent=2))


if __name__=="__main__":
    main()
