"""Reconstruct MT5 holding-time bounds from full exits and realized price P&L."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from scripts.research.luna_six_month_audit import read_report


def classify(deals):
    # Ticket-specific exits are absent from the HTML ledger. Pair by side, lot
    # and price-based P&L. Require a unique match before assigning duration.
    active = []
    by_year = defaultdict(Counter)
    for row in deals:
        if row["action"] == "in":
            active.append(row)
            continue
        amount = row["volume"] * 100
        sign = 1 if row["side"] == "sell" else -1
        matches = [d for d in active if d["side"] != row["side"] and d["volume"] == row["volume"]
                   and abs((row["price"] - d["price"]) * amount * sign - row["profit"]) <= .011]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous or missing position for order {row['order']}; {len(matches)} possible")
        entry = matches[0]
        active.remove(entry)
        stats = by_year[pd.Timestamp(row["ts"], unit="s", tz="UTC").year]
        stats["closed"] += 1
        if row["ts"] - entry["ts"] < 180:
            stats["short_duration"] += 1
            if row["profit"] > 0:
                stats["short_wins"] += 1
                stats["short_win_dollars"] += row["profit"]
    assert not active
    for stats in by_year.values():
        stats["short_win_dollars"] = round(stats["short_win_dollars"], 2)
    return by_year


def classify_stops(report, deals, result):
    entries = {d["order"]: d for d in deals if d["action"] == "in"}
    seen = set()
    soup = BeautifulSoup(report.read_text(encoding="utf-16"), "html.parser")
    for row in soup.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.select("td")]
        if len(cells) != 11 or cells[9] != "filled" or not cells[1].isdigit():
            continue
        ticket = int(cells[1])
        if ticket in entries:
            seen.add(ticket)
            year = pd.Timestamp(entries[ticket]["ts"], unit="s", tz="UTC").year
            result[year]["entry_orders"] += 1
            result[year]["entry_orders_without_sl"] += float(cells[6] or 0) == 0
    assert seen == entries.keys()
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("report", type=Path)
    args = p.parse_args()
    records = read_report(args.report)[1]
    print(json.dumps(classify_stops(args.report, records, classify(records)), indent=2))
