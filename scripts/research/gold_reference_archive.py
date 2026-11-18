"""Capture and verify the research-input snapshot. Run from the repository root."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import shutil
import zipfile
from xml.etree import ElementTree

import numpy as np
import pandas as pd
import requests

from scripts.research.collect_gold_ticks import ROOT, STORE, sha
from scripts.research.market_atlas import TF, hour_from_m15
from src.backtesting.master import HOLDOUT_FROM, load_master

PAYLOAD = STORE / "payload"
FRED = {
    "rates": ["DGS2","DGS10","DGS30","DFII5","DFII10","T5YIE","T10YIE","DFF"],
    "markets": ["DTWEXBGS","DEXCHUS","DEXUSEU","DEXJPUS","VIXCLS","DCOILWTICO"],
    "economy": ["CPIAUCSL","PPIACO","PAYEMS","UNRATE","INDPRO"],
}
WGC = {
    "gold_premiums.xlsx": "/download/file/11657/gold-premiums.xlsx",
    "central_bank_reserves_quarterly.xlsx": "/download/file/8052/Quarterly_gold_and_FX_Reserves_Q3_2026.xlsx",
    "gold_etf_flows_october.xlsx": "/download/file/21341/ETF_Flows_2026-11-03.xlsx",
    "chinese_premium_methodology.pdf": "/download/file/11658/Chinese_premium-discount_methodology.pdf",
    "central_bank_methodology.pdf": "/download/file/12491/central_bank_data_methodology.pdf",
    "etf_flows_methodology.pdf": "/download/file/16223/ETF-Flows-Data-Methodology.pdf",
}


def capture(item):
    name, url, params = item
    folder = PAYLOAD / "reference"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    meta = dict(source=url, parameters=params, file=name)
    try:
        headers = {"Accept":"application/vnd.sdmx.data+csv;version=2.0.0"} if name.startswith("imf_") else {}
        r = requests.get(url, params=params, headers=headers, timeout=(12,60))
        r.raise_for_status()
        content = r.content
        if name.startswith("fred_"):
            series = params["id"].split(",")
            if zipfile.is_zipfile(io.BytesIO(content)):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    parts = [pd.read_csv(z.open(n)).set_index("observation_date") for n in z.namelist() if n.endswith(".csv")]
                frame = pd.concat(parts,axis=1).sort_index().reset_index()
            else:
                frame = pd.read_csv(io.BytesIO(content))
            frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="raise")
            frame = frame.set_index("observation_date").loc["2004-01-01":"2026-10-31", series]
            if frame.empty or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
                raise ValueError("Invalid FRED time axis")
            for s in series:
                if pd.to_numeric(frame[s].dropna(), errors="raise").empty:
                    raise ValueError(f"No observations for {s}")
            meta.update(observations={s:int(frame[s].count()) for s in series},
                        first=str(frame.index.min().date()), last=str(frame.index.max().date()))
            content = frame.to_csv(lineterminator="\n").encode()
        elif name.startswith("imf_"):
            frame = pd.read_csv(io.BytesIO(content),dtype=str)
            period = frame.TIME_PERIOD.str.replace("-M","-",regex=False)
            frame = frame.loc[period.between("2004-01","2026-10")].copy()
            keys = ["COUNTRY","INDICATOR","SECTOR","FREQUENCY","TIME_PERIOD"]
            if frame.empty or frame.duplicated(keys).any() or not frame.INDICATOR.eq("IRFCLDT1_IRFCL56V_FTO").all():
                raise ValueError("Unexpected official reserve series")
            meta.update(rows=len(frame), countries_or_areas=int(frame.COUNTRY.nunique()),
                        first=frame.TIME_PERIOD.min(), last=frame.TIME_PERIOD.max(),
                        use="Provider-reported stocks. Preserve SCALE, sector and units. Historical revisions and publication timestamps unknown.")
            content = frame.to_csv(index=False,lineterminator="\n").encode()
        elif name.startswith("cftc"):
            frame = pd.read_csv(io.BytesIO(content), dtype={"cftc_contract_market_code":str})
            dates = pd.to_datetime(frame["report_date_as_yyyy_mm_dd"])
            if (not 800<len(frame)<5000 or not dates.is_monotonic_increasing or dates.duplicated().any()
                    or not frame.cftc_contract_market_code.eq("088691").all() or dates.max()>=pd.Timestamp("2026-11-01")):
                raise ValueError("Unexpected COMEX gold COT coverage")
            meta.update(rows=len(frame), first=str(dates.min().date()), last=str(dates.max().date()))
        elif name.endswith(".xlsx"):
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                if z.testzip():
                    raise ValueError("Workbook CRC error")
                xml = ElementTree.fromstring(z.read("xl/workbook.xml"))
                meta["sheets"] = [e.attrib["name"] for e in xml.findall(".//{*}sheet")]
            meta["use"] = "Unfiltered source workbook and original sheet structure. May include sealed dates. Respect release dates when selecting historical columns."
        elif name.endswith(".xls"):
            if not content.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
                raise ValueError("Unexpected legacy workbook signature")
        elif not content.startswith(b"%PDF"):
            raise ValueError("Publisher did not return a PDF")
        part = path.with_suffix(path.suffix+".part")
        part.write_bytes(content)
        part.replace(path)
        return dict(**meta, status="stored", path=path.relative_to(STORE).as_posix(), sha256=sha(path), bytes=len(content))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, requests.RequestException) as exc:
        return dict(**meta, status="unavailable", reason=str(exc))


def local_inputs():
    research = ROOT/"research"
    folders = [p for p in research.glob("data*") if p.is_dir()]
    folders += [research/n for n in ("events","market","sources")]
    selected = {p for folder in folders for p in folder.rglob("*") if p.is_file()}
    selected.update(p for p in (research/"results/finalization_2026-11-18").glob("*.json")
                    if p.name in {"market_atlas.json","literature.json","quote_side_replication.json",
                                  "economic_hurdle.json","path_risk.json","data_inventory.json"})
    selected.update([research/"results/treasury_auction_gold_2026-11-18/calendar.json",
                     research/"results/gold_m15_forecast_2026-11-18.json"])
    out = []
    for src in sorted(selected):
        rel = src.relative_to(ROOT)
        dest = PAYLOAD/"project"/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        digest = sha(src)
        if not dest.exists() or sha(dest) != digest:
            shutil.copy2(src, dest)
        if sha(dest) != digest:
            raise IOError(f"Copy mismatch {rel}")
        out.append(dict(source=rel.as_posix(), path=dest.relative_to(STORE).as_posix(), sha256=digest, bytes=dest.stat().st_size))
    return out


def export_master():
    out = []
    for tf in TF:
        source = "M15" if tf == "H1" else tf
        master = load_master((source,), end=HOLDOUT_FROM, use_cache=False)
        arr = getattr(master, source.lower())
        if tf=="H1":
            arr = hour_from_m15(arr)
        if np.any(np.diff(arr["time"])<=0) or arr["time"][-1]>=HOLDOUT_FROM:
            raise ValueError(f"Invalid time axis {tf}")
        path = PAYLOAD/"master"/f"XAUUSDm_{tf}.npy"
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, arr, allow_pickle=False)
        saved = np.load(path, mmap_mode="r", allow_pickle=False)
        if not np.array_equal(arr,saved):
            raise ValueError(f"Round trip failed for {tf}")
        out.append(dict(timeframe=tf, rows=len(arr), first_utc=str(pd.Timestamp(int(arr["time"][0]),unit="s",tz="UTC")),
                        last_utc=str(pd.Timestamp(int(arr["time"][-1]),unit="s",tz="UTC")), fields=list(arr.dtype.names),
                        path=path.relative_to(STORE).as_posix(), sha256=sha(path), bytes=path.stat().st_size,
                        provenance=master.provenance))
    return out


def main():
    items = [(f"fred_{k}.csv","https://fred.stlouisfed.org/graph/fredgraph.csv",
              {"id":",".join(ids),"cosd":"2004-01-01","coed":"2026-10-31"}) for k,ids in FRED.items()]
    items += [(n, "https://www.gold.org"+u, {}) for n,u in WGC.items()]
    items.extend([
        ("world_bank_monthly_commodities.xlsx","https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx",{}),
        ("imf_official_gold_reserves.csv","https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IRFCL/12.0.0/*.IRFCLDT1_IRFCL56V_FTO.*.M",{}),
        ("premium_methodology_2019.pdf","https://www.gold.org/sites/default/files/downloads/2019-01/Chinese-premium-discount-methodology.pdf",{}),
        ("spdr_gld_historical.xlsx","https://api.spdrgoldshares.com/api/v1/historical-archive",
         {"product":"gld","exchange":"NYSE","lang":"en"}),
    ])
    fed = "https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/real-time-data/data-files/"
    for name in ["pcpiMvMd.xlsx","pcpi_first_second_third.xlsx","employMvMd.xlsx",
                 "employ_level_first_second_third.xlsx","rucQvMd.xlsx"]:
        items.append((name,fed+"xlsx/"+name,{}))
    name = "Release_-Dates-Employment_Situation-BLS.xls"
    items.append((name,fed+"documentation/"+name,{}))
    items.append(("cftc_comex_gold.csv","https://publicreporting.cftc.gov/resource/72hh-3qpy.csv",
                  {"cftc_contract_market_code":"088691","$where":"report_date_as_yyyy_mm_dd < '2026-11-01T00:00:00'",
                   "$limit":"5000","$order":"report_date_as_yyyy_mm_dd"}))
    with ThreadPoolExecutor(max_workers=5) as pool:
        remote = list(pool.map(capture,items))
    catalog = dict(cutoff="2026-11-01 UTC exclusive for analytical exports",
                   external=remote, project_inputs=local_inputs(), master=export_master())
    (STORE/"reference_catalog.json").write_text(json.dumps(catalog,indent=2)+"\n",encoding="utf-8")
    print([(r["file"],r["status"]) for r in remote],flush=True)


if __name__ == "__main__":
    main()
