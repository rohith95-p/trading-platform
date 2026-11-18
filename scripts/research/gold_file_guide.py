"""Build a clickable, file-by-file index of the completed local market archive."""
import csv
import json
from pathlib import Path

import numpy as np
from scripts.research.collect_gold_ticks import STORE


def read(name):
    return json.loads((STORE/name).read_text(encoding="utf-8"))


def link(row, name=None):
    return f"[{name or Path(row['path']).name}](<{row['path']}>)"


def shape(path):
    if path.suffix==".npy":
        a = np.load(path,mmap_mode="r",allow_pickle=False)
        return f"Shape {a.shape}. Fields " + ", ".join(a.dtype.names or (str(a.dtype),))
    if path.suffix==".csv":
        with path.open(encoding="utf-8-sig",newline="") as f:
            header = next(csv.reader(f))
        return f"{len(header)} columns including " + ", ".join(header[:12])
    if path.suffix==".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data,dict):
            return "Recorded fields include " + ", ".join(list(data)[:8])
        if isinstance(data,list):
            return f"{len(data):,} records"
    if path.name.endswith(".response.gz"):
        return "Compressed original Dukascopy response with " + ("ask bars" if path.name.startswith("A_") else "bid bars")
    return {".md":"Existing research notes",".xlsx":"Original source workbook",".pine":"Previously archived public strategy source",
            ".response":"Original data acquisition response"}.get(path.suffix,"License text or source metadata")


def main():
    cat = read("reference_catalog.json")
    profile = read("quote_profile.json")
    lines = ["# File-by-file XAUUSD archive index","",
             "Start with the [archive guide](README.md) for the meaning of each dataset and the cutoff. Each link below opens a stored local file.",
             "","## Quote files by month","",
             "Each ZIP holds one broker feed for one calendar month. The CSV contains provider, symbol, quoted time in UTC, bid and ask in USD per troy ounce. Counts below are quote updates. The two price feeds can quote at different times.",
             "","| Month | Standard archive and updates | Raw Spread archive and updates | Derived Standard bid/ask minutes |",
             "|---|---|---|---|"]
    def ticks(names):
        return {r["month"]:r for n in names for r in read(n) if r["status"]=="verified"}
    standard = ticks(["ticks_XAUUSDm_2004_2018.json","ticks_XAUUSDm.json"])
    raw = ticks(["ticks_XAUUSD_Raw_Spread.json"])
    derived = {r["month"]:r for r in profile["months"]}
    for m in sorted(standard.keys()|raw.keys()):
        cells = []
        for records, key in [(standard,"quote_rows"),(raw,"quote_rows"),(derived,"minutes")]:
            r = records.get(m)
            cells.append(link(r,f"{r[key]:,}") if r else "—")
        lines.append("| "+" | ".join([m,*cells])+" |")
    lines.extend(["","## Historical candles","","| File | Rows | Coverage or source |","|---|---:|---|"])
    for r in cat["master"]:
        lines.append(f"| {link(r)} | {r['rows']:,} | {r['first_utc'][:10]} to {r['last_utc'][:10]} |")
    for r in read("clock_bars.json")["files"]:
        lines.append(f"| {link(r)} | {r['rows']:,} | UTC aggregates of master M1, {r['full_clock_intervals']:,} complete clock intervals |")
    lines.extend(["","## Economic and reference files","","| File | Contents |","|---|---|"])
    for r in cat["external"]:
        if r["status"]=="stored":
            detail = ", ".join(r["sheets"]) if "sheets" in r else shape(STORE/r["path"])
            if r["file"]=="Release_-Dates-Employment_Situation-BLS.xls":
                detail="Historical BLS employment report release dates"
            if r["file"].endswith(".pdf"):
                detail="World Gold Council methodology for estimating China's local gold premium"
            lines.append(f"| {link(r)} | {detail} |")
    lines.extend(["","## Project data copied into this archive","","| Original project file | Data or fields |","|---|---|"])
    for r in cat["project_inputs"]:
        detail = shape(STORE/r["path"]).replace("|","\\|").replace("\n"," ")
        lines.append(f"| {link(r,r['source'])} | {detail} |")
    lines.extend(["","## Papers and venue documentation","","| Stored file | Content |","|---|---|"])
    for r in read("literature_catalog.json")["records"]:
        if r["status"]=="stored":
            lines.append(f"| {link(r)} | {r['title']} ({r['content_scope']}) |")
    lines.extend(["","## Verification records","",
                  "Each monthly derived array has a matching JSON sidecar recording the source hash, processor hash, valid rows and exceptions. The [reference catalog](reference_catalog.json) lists unsuccessful reference requests as well as successful ones. [Verification totals](verification.json) · [Session measurements](quote_profile.json) · [Market structure measurements](market_structure.json)"])
    (STORE/"FILE_INDEX.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
