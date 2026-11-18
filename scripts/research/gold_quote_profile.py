"""Make source-isolated minute bars and a descriptive 2026 gold liquidity profile."""
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
from scripts.research.collect_gold_ticks import STORE, sha

FIELDS = {"bid_open":"first","bid_high":"max","bid_low":"min","bid_close":"last",
          "ask_open":"first","ask_high":"max","ask_low":"min","ask_close":"last",
          "spread_min":"min","spread_max":"max","spread_sum":"sum","quotes":"sum"}


def minutes(path):
    dest = STORE/"payload"/"standard_m1"
    dest.mkdir(parents=True,exist_ok=True)
    month = path.stem[-7:].replace("_","-")
    target = dest/f"{month}.npy"
    stamp = target.with_suffix(".json")
    digest = sha(path)
    if target.exists() and stamp.exists():
        previous = json.loads(stamp.read_text())
        if (previous.get("source_sha256")==digest and previous.get("sha256")==sha(target)
                and previous.get("processor_sha256")==sha(Path(__file__))):
            return previous
    lo = pd.Timestamp(month+"-01",tz="UTC")
    hi = lo + pd.offsets.MonthBegin()
    pieces = []
    seen = valid = out_of_order = tied = 0
    previous_ms = None
    with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as source:
        for part in pd.read_csv(source,chunksize=200_000,usecols=["Symbol","Timestamp","Bid","Ask"],
                                dtype={"Symbol":"category"},keep_default_na=False):
            seen += len(part)
            ts = pd.to_datetime(part.Timestamp,format="ISO8601",utc=True,errors="coerce")
            bid = pd.to_numeric(part.Bid,errors="coerce")
            ask = pd.to_numeric(part.Ask,errors="coerce")
            mask = part.Symbol.eq("XAUUSDm") & ts.ge(lo) & ts.lt(hi) & np.isfinite(bid) & np.isfinite(ask) & bid.gt(0) & ask.ge(bid)
            ms = ts[mask].dt.as_unit("ms").astype("int64").to_numpy()
            if len(ms)==0:
                continue
            valid += len(ms)
            dif = np.diff(ms,prepend=ms[0]-1 if previous_ms is None else previous_ms)
            out_of_order += int((dif<0).sum())
            tied += int((dif==0).sum())
            previous_ms = ms[-1]
            frame = pd.DataFrame({"minute":ms//60_000*60,"ms":ms,"bid":bid[mask].to_numpy(),"ask":ask[mask].to_numpy()})
            if (dif<0).any():
                frame = frame.sort_values("ms",kind="stable")
            frame["spread"] = frame.ask-frame.bid
            grouped = frame.groupby("minute",sort=False)
            piece = grouped.agg(bid_open=("bid","first"), bid_high=("bid","max"), bid_low=("bid","min"), bid_close=("bid","last"),
                                ask_open=("ask","first"), ask_high=("ask","max"), ask_low=("ask","min"), ask_close=("ask","last"),
                                spread_min=("spread","min"), spread_max=("spread","max"), spread_sum=("spread","sum"), quotes=("bid","size"),
                                first_ms=("ms","first"),last_ms=("ms","last"))
            pieces.append(piece)
    chunks = pd.concat(pieces)
    bars = chunks.groupby(level=0,sort=True).agg(FIELDS)
    if out_of_order:
        for field, order, choose in [("open","first_ms","first"),("close","last_ms","last")]:
            ordered = chunks.sort_values(order,kind="stable")
            for side in ["bid","ask"]:
                col = f"{side}_{field}"
                bars[col] = ordered.groupby(level=0)[col].agg(choose)
    bars.index.name = "time"
    bars["spread_mean"] = bars.pop("spread_sum")/bars.quotes
    for side in ["bid","ask"]:
        high, low = bars[side+"_high"],bars[side+"_low"]
        if any((~bars[side+"_"+k].between(low,high)).any() for k in ["open","close"]):
            raise ValueError("Invalid minute OHLC")
    if int(bars.quotes.sum())!=valid or (bars.spread_min<0).any():
        raise ValueError("Minute accounting error")
    np.save(target,bars.to_records(),allow_pickle=False)
    result = dict(month=month,source_sha256=digest,processor_sha256=sha(Path(__file__)),
                  sha256=sha(target),bytes=target.stat().st_size,path=target.relative_to(STORE).as_posix(),
                  source_rows=seen,valid_quotes=valid,invalid_quotes=seen-valid,tied_ms=tied,
                  out_of_order_quotes=out_of_order,minutes=len(bars))
    stamp.write_text(json.dumps(result,indent=2)+"\n")
    return result


def main():
    files = sorted((STORE/"payload/exness/XAUUSDm").glob("*_2026_*.zip"))
    if not files:
        raise ValueError("No verified 2026 Standard archives yet")
    with ProcessPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(minutes,files))
    df = pd.concat([pd.DataFrame(np.load(STORE/r["path"],allow_pickle=False)) for r in records])
    utc = pd.to_datetime(df.time,unit="s",utc=True)
    def business(tz):
        local = utc.dt.tz_convert(tz)
        return (local.dt.weekday<5) & local.dt.hour.between(8,16)
    london, ny = business("Europe/London"), business("America/New_York")
    df["clock"] = np.select([london&ny,london,ny],["overlap","London only","New York only"],default="outside both")
    df["bid_range"] = df.bid_high-df.bid_low
    groups = df.groupby("clock").agg(minutes=("time","size"),median_quotes_per_minute=("quotes","median"),
            median_minute_mean_spread_usd_oz=("spread_mean","median"),median_bid_range_usd_oz=("bid_range","median"))
    (STORE/"quote_profile.json").write_text(json.dumps(dict(protocol_commit="9e6e899",months=records,
            sessions=groups.to_dict("index")),indent=2)+"\n")
    print(groups)


if __name__=="__main__":
    main()
