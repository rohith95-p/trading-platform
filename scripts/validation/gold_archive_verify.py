"""Verify all catalogued files and independently recompute one full minute per 2026 month."""
import csv
import io
import json
from datetime import datetime, timezone
import zipfile

import numpy as np
from scripts.research.collect_gold_ticks import STORE, sha


def check_minute(zip_path, bars):
    # Second observed minute is internal to the file. Retain feed order on ties.
    target = bars[1]
    epoch = int(target["time"])
    prefix = datetime.fromtimestamp(epoch,timezone.utc).strftime("%Y-%m-%d %H:%M")
    picked = []
    with zipfile.ZipFile(zip_path) as z, z.open(z.namelist()[0]) as binary:
        for i,r in enumerate(csv.DictReader(io.TextIOWrapper(binary,encoding="utf-8"))):
            stamp = r["Timestamp"]
            if stamp[:16]>prefix and picked:
                break
            if stamp[:16]==prefix and r["Symbol"]=="XAUUSDm":
                bid, ask = float(r["Bid"]),float(r["Ask"])
                if 0<bid<=ask and np.isfinite(ask):
                    picked.append((stamp,i,bid,ask))
    picked.sort()
    if len(picked)!=target["quotes"]:
        raise ValueError(f"Quote count mismatch at {prefix}")
    bid, ask = np.array([r[2:] for r in picked]).T
    for side,values in [("bid",bid),("ask",ask)]:
        actual = [target[f"{side}_{key}"] for key in ["open","high","low","close"]]
        if not np.allclose(actual,[values[0],values.max(),values.min(),values[-1]],atol=1e-10,rtol=0):
            raise ValueError(f"OHLC mismatch {prefix}, {side}")
    if not np.isclose(target["spread_mean"],np.mean(ask-bid),atol=1e-10,rtol=0):
        raise ValueError(f"Spread mismatch {prefix}")
    return dict(minute_utc=prefix,quotes=len(picked))


def main():
    manifest = json.loads((STORE/"reference_catalog.json").read_text())
    entries = manifest["project_inputs"]+manifest["master"]+[r for r in manifest["external"] if r["status"]=="stored"]
    library = json.loads((STORE/"literature_catalog.json").read_text())
    entries.extend(r for r in library["records"] if r["status"]=="stored")
    clock_bars = json.loads((STORE/"clock_bars.json").read_text())
    if clock_bars["source_sha256"]!=next(r["sha256"] for r in manifest["master"] if r["timeframe"]=="M1"):
        raise ValueError("Clock aggregates refer to a different M1 snapshot")
    entries.extend(clock_bars["files"])
    ticks = {}
    for symbol,first,last in [("XAUUSDm",2019,2026),("XAUUSD_Raw_Spread",2019,2026),("XAUUSDm",2004,2018)]:
        key = symbol if first==2019 else f"{symbol}_{first}_{last}"
        months = json.loads((STORE/f"ticks_{key}.json").read_text())
        wanted = {f"{y}-{m:02d}" for y in range(first,last+1) for m in range(1,13) if (y,m)<(2026,11)}
        if {r["month"] for r in months}!=wanted or len(months)!=len(wanted):
            raise ValueError(f"Incomplete inventory {symbol}")
        verified = [r for r in months if r["status"]=="verified"]
        entries.extend(verified)
        ticks[key] = dict(months_requested=len(months),months_verified=len(verified),
                             missing={r["month"]:r["status"] for r in months if r["status"]!="verified"},
                             quote_rows=sum(r["quote_rows"] for r in verified),bytes=sum(r["bytes"] for r in verified))
    raw = {r["month"]:r for r in entries if r.get("symbol")=="XAUUSDm" and r["month"].startswith("2026")}
    profile = json.loads((STORE/"quote_profile.json").read_text())
    derived = profile["months"]
    if {r["month"] for r in derived}!=raw.keys():
        raise ValueError("2026 minute coverage differs from source inventory")
    checks = []
    for r in derived:
        source = raw[r["month"]]
        if r["source_sha256"]!=source["sha256"] or r["source_rows"]!=source["quote_rows"]:
            raise ValueError(f"Source row or hash mismatch {r['month']}")
        bars = np.load(STORE/r["path"],mmap_mode="r",allow_pickle=False)
        checks.append(check_minute(STORE/source["path"],bars))
    entries.extend(derived)
    total = 0
    for r in entries:
        path = STORE/r["path"]
        if path.stat().st_size!=r["bytes"] or sha(path)!=r["sha256"]:
            raise ValueError(f"File differs from manifest {path}")
        total += path.stat().st_size
    audit = dict(status="verified",verified_payload_files=len(entries),verified_payload_bytes=total,
                 monthly_ticks=ticks,minute_checks=checks,master_bars=sum(r["rows"] for r in manifest["master"]),
                 derived_standard_minutes=sum(r["minutes"] for r in derived),
                 excluded_standard_quotes=sum(r["invalid_quotes"] for r in derived),
                 out_of_order_standard_quotes=sum(r["out_of_order_quotes"] for r in derived))
    (STORE/"verification.json").write_text(json.dumps(audit,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(audit,indent=2))


if __name__=="__main__":
    main()
