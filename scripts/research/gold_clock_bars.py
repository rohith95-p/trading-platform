"""Archive five UTC aggregations of the same M1 series, with explicit minute coverage."""
import json

import numpy as np
from scripts.research.collect_gold_ticks import STORE, sha


def aggregate(source, step):
    ts = source["time"].astype("int64")
    if np.any(ts % 60) or np.any(np.diff(ts)<=0):
        raise ValueError("Unordered or off-minute M1 timestamps")
    buckets = ts//step*step
    starts = np.r_[0,np.flatnonzero(np.diff(buckets))+1]
    ends = np.r_[starts[1:]-1,len(ts)-1]
    out = np.empty(len(starts),dtype=[("time","<i8"),("open","<f8"),("high","<f8"),("low","<f8"),("close","<f8"),
                                      ("minutes_observed","<i4"),("first_minute","<i8"),("last_minute","<i8"),("complete","?")])
    out["time"] = buckets[starts]
    out["open"],out["close"] = source["open"][starts],source["close"][ends]
    out["high"],out["low"] = np.maximum.reduceat(source["high"],starts),np.minimum.reduceat(source["low"],starts)
    out["minutes_observed"] = ends-starts+1
    out["first_minute"],out["last_minute"] = ts[starts],ts[ends]
    out["complete"] = out["minutes_observed"]==step//60
    if out["minutes_observed"].sum()!=len(source) or np.any(out["minutes_observed"]>step//60):
        raise ValueError("Minute allocation error")
    return out


def main():
    source = STORE/"payload/master/XAUUSDm_M1.npy"
    rows = np.load(source,mmap_mode="r",allow_pickle=False)
    folder = STORE/"payload/from_master_m1"
    folder.mkdir(parents=True,exist_ok=True)
    meta = dict(source_sha256=sha(source),source_rows=len(rows),time_zone="UTC",files=[])
    for name, step in [("M5",300),("M15",900),("H1",3600),("H4",14400),("D1",86400)]:
        arr = aggregate(rows,step)
        path = folder/f"{name}.npy"
        np.save(path,arr,allow_pickle=False)
        if not np.array_equal(np.load(path,mmap_mode="r",allow_pickle=False),arr):
            raise ValueError(f"Persisted array differs {name}")
        meta["files"].append(dict(timeframe=name,path=path.relative_to(STORE).as_posix(),bytes=path.stat().st_size,
                                  rows=len(arr),full_clock_intervals=int(arr["complete"].sum()),sha256=sha(path)))
    (STORE/"clock_bars.json").write_text(json.dumps(meta,indent=2)+"\n")


if __name__=="__main__":
    main()
