"""Offline shadow replay of Luna's recorded baskets. Run from repository root."""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(os.environ["TEMP"]) / "UltraEAReview20261120"
SOURCE = Path("research/results/luna_six_month_20261120")
OUTPUT = Path(__file__).resolve().parent
DTYPE = [("ms", "<i8"), ("bid", "<f8"), ("ask", "<f8")]
DAY = 86_400_000


def split_baskets(deals):
    count = 0
    group = []
    for deal in deals:
        count += 1 if deal["action"] == "in" else -1
        group.append(deal)
        if count == 0:
            yield group
            group = []
    assert not group


def run(deals, cache, lot_guard):
    months = {}
    trades = []
    locked_day = -1
    balance = peak = 5000.
    max_dd = 0.
    for group in split_baskets(deals):
        opened = int(group[0]["ts"] * 1000)
        if opened // DAY == locked_day:
            continue
        cash = long = short = 0.
        forced = None
        for index, d in enumerate(group):
            ms = int(d["ts"] * 1000)
            month = pd.Timestamp(ms, unit="ms", tz="UTC").month
            if month not in months:
                months[month] = np.memmap(cache / f"ticks{month}.bin", mode="r", dtype=DTYPE)
            q = months[month]
            a = int(q["ms"].searchsorted(ms))
            if lot_guard and d["action"] == "in" and d["volume"] > .0200001:
                forced = "oversize"
                cross = q[a]
                break
            ounces = round(d["volume"] * 100)
            buy = d["side"] == "buy"
            cash += (-1 if buy else 1)*ounces*d["price"] + d["fee"] + d["swap"]
            if buy == (d["action"] == "in"):
                long += ounces if d["action"] == "in" else -ounces
            else:
                short += ounces if d["action"] == "in" else -ounces
            if index+1 == len(group):
                break
            until = int(group[index+1]["ts"] * 1000)
            assert until <= int(q[-1]["ms"])+1000, "basket spans archive month"
            b = int(q["ms"].searchsorted(until))
            segment = q[a:b]
            if not len(segment):
                continue
            marked = cash + long*segment["bid"] - short*segment["ask"]
            crossings = np.flatnonzero(marked <= -50.)
            if len(crossings):
                j = int(crossings[0])
                marked = marked[:j+1]
                forced = "basket stop"
                cross = segment[j]
            equity = balance + marked
            peaks = np.maximum.accumulate(np.maximum(peak,equity))
            max_dd = max(max_dd,float(np.max(peaks-equity)))
            peak = peaks[-1]
            if forced:
                break
        if forced:
            close = int(cross["ms"])
            pnl = cash + long*cross["bid"] - short*cross["ask"]
            # Stress exits by $0.10 per ounce for execution slippage.
            pnl -= .10*(long+short)
            locked_day = close // DAY
        else:
            close = int(group[-1]["ts"]*1000)
            pnl = sum(d["profit"]+d["fee"]+d["swap"] for d in group)
        balance += pnl
        peak = max(peak,balance)
        max_dd = max(max_dd,peak-balance)
        trades.append(dict(open=opened,close=close,pnl=round(float(pnl),3),reason=forced or "Luna exit"))
    r = np.array([t["pnl"] for t in trades])
    return dict(baskets=len(trades), net=round(float(balance-5000),2),
                pf=round(float(r[r>0].sum()/-r[r<0].sum()),3),
                win_pct=round(float((r>0).mean()*100),2), max_dd=round(float(max_dd),2),
                best_removed=round(float(r.sum()-r.max()),2),
                stops=sum(t["reason"]!="Luna exit" for t in trades), trades=trades)


if __name__ == "__main__":
    results = {}
    for name,folder in [("broker_evaluation",BASE/"Luna"/"direct_quote_cache"),
                        ("evaluation",BASE/"Velora"/"MQL5"/"Files"/"LunaArchive")]:
        deals = json.loads((SOURCE/f"{name}.json").read_text())["deals"]
        for cap in [False,True]:
            key=f"{name}_cap_{cap}"
            results[key]=run(deals,folder,cap)
            print(key,{k:v for k,v in results[key].items() if k!="trades"})
    (OUTPUT/"results.json").write_text(json.dumps(results,indent=2))
