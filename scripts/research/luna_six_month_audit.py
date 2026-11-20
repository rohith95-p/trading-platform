"""Check Luna's native MT5 fills against Atlas equity floors on Exness quotes.

The CLI evaluates a single $5,000 evaluation attempt. MT5 reports deal times to
the second. For rule crossings, retain the quote and time since the last fill
so the result can be checked away from any ambiguous fill second.
"""
import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

STORE = Path("research/xauusd_archive/payload/exness/XAUUSDm")
METRICS = {"Ticks:", "Period:", "Profit Factor:", "Total Net Profit:", "Gross Profit:", "Gross Loss:",
           "Equity Drawdown Relative:", "Equity Drawdown Maximal:", "History Quality:", "Total Trades:",
           "Leverage:", "Profit Trades (% of total):"}
INITIAL = 5000.0


def read_report(path):
    soup = BeautifulSoup(path.read_bytes().decode("utf-16"), "html.parser")
    trades, metrics = [], {}
    in_deals = False
    for row in soup.select("tr"):
        cells = [td.get_text(" ", strip=True) for td in row.select("td")]
        for index, key in enumerate(cells[:-1]):
            if key in METRICS:
                metrics[key.rstrip(":")] = cells[index + 1]
        if "Deal" in cells and "Direction" in cells:
            in_deals = True
        if not in_deals or len(cells) < 12 or cells[4] not in ("in", "out"):
            continue
        volume, price, fee, swap, profit, balance = (
            float(cells[i].replace(" ", "")) for i in (5, 6, 8, 9, 10, 11))
        trades.append(dict(ts=pd.Timestamp(cells[0].replace(".", "-"), tz="UTC").timestamp(),
                           order=int(cells[7]), side=cells[3], action=cells[4], volume=volume,
                           price=price, fee=fee, swap=swap, profit=profit, balance=balance, symbol=cells[2]))
    return metrics, trades


def stamp(ms):
    return pd.Timestamp(ms, unit="ms", tz="UTC").isoformat()


def quote_chunks(month, cache):
    if cache:
        quotes = np.memmap(Path(cache) / f"ticks{month.month}.bin", mode="r",
                           dtype=[("ms", "<i8"), ("bid", "<f8"), ("ask", "<f8")])
        for i in range(0, len(quotes), 250000):
            chunk = quotes[i:i + 250000]
            yield chunk["ms"], chunk["bid"], chunk["ask"]
        return
    path = STORE / f"Exness_XAUUSDm_{month.year}_{month.month:02}.zip"
    with zipfile.ZipFile(path) as archive, archive.open(archive.namelist()[0]) as stream:
        for chunk in pd.read_csv(stream, usecols=["Timestamp", "Bid", "Ask"], chunksize=250000):
            times = pd.to_datetime(chunk.Timestamp, format="ISO8601", utc=True).dt.as_unit("ms")
            yield times.astype("int64").to_numpy(), chunk.Bid.to_numpy(), chunk.Ask.to_numpy()


def portfolio_states(deals):
    states = [(0, 0., 0., INITIAL, INITIAL)]
    long_oz = short_oz = 0.
    cash = balance = INITIAL
    for deal in deals:
        ounces = deal["volume"] * 100
        buy = deal["side"] == "buy"
        entering = deal["action"] == "in"
        if buy == entering:
            long_oz += ounces if entering else -ounces
        else:
            short_oz += ounces if entering else -ounces
        carry = deal["fee"] + deal["swap"]
        cash += (-ounces if buy else ounces) * deal["price"] + carry
        assert min(long_oz, short_oz) >= -1e-7
        assert abs(balance + carry + deal["profit"] - deal["balance"]) < .03
        balance = deal["balance"]
        if abs(long_oz) + abs(short_oz) < 1e-7:
            cash = balance  # MT5 settles each closed trade to cents.
        states.append((int(deal["ts"] * 1000), long_oz, short_oz, cash, balance))
    return np.array(states).T


def audit_ledger(metrics, deals, phase, end, start, cache=None):
    if phase != "eval":
        raise ValueError("This auditor evaluates the $5K evaluation phase only.")
    if deals:
        assert len({d["symbol"] for d in deals}) == 1
        assert deals[0]["symbol"] in {"XAUUSDm", "XAUUSDm.LUNA"}
    times_filled, longs, shorts, cash, balances = portfolio_states(deals)
    events, days = {}, {}
    target = next((d for d in deals if d["action"] == "out" and d["balance"] >= 5150), None)
    if target:
        events["target"] = dict(time=stamp(target["ts"] * 1000), balance=target["balance"])
    opens = [pd.Timestamp(d["ts"], unit="s", tz="UTC") for d in deals if d["action"] == "in"]
    for previous, following in zip([start, *opens], [*opens, end]):
        if following - previous >= pd.Timedelta(days=30):
            events["inactivity"] = dict(time=(previous + pd.Timedelta(days=30)).isoformat())
            break
    peak = last_equity = INITIAL
    months = pd.period_range(start.strftime("%Y-%m"), (end - pd.Timedelta(seconds=1)).strftime("%Y-%m"), freq="M")
    for month in months:
        for times, bids, asks in quote_chunks(month, cache):
            lo, hi = times.searchsorted([start.timestamp() * 1000, end.timestamp() * 1000])
            if lo == hi:
                continue
            times, bids, asks = times[lo:hi], bids[lo:hi], asks[lo:hi]
            pos = times_filled.searchsorted(times, side="right") - 1
            equities = cash[pos] + longs[pos] * bids - shorts[pos] * asks
            boundaries = np.r_[0, np.flatnonzero(np.diff(times // 86400000)) + 1, len(times)]
            for a, b in zip(boundaries[:-1], boundaries[1:]):
                day = stamp(times[a])[:10]
                stats = days.setdefault(day, dict(anchor=last_equity, minimum=float("inf"), ticks=0))
                equity = equities[a:b]
                peaks = np.maximum(peak, np.maximum.accumulate(equity))
                checks = {"daily": equity < stats["anchor"] * .95, "trailing": equity < peaks * .90}
                for name, breaches in checks.items():
                    if name in events or not breaches.any():
                        continue
                    j = int(np.argmax(breaches))
                    i = a + j
                    events[name] = dict(time=stamp(times[i]), equity=round(float(equity[j]), 3),
                                        anchor=stats["anchor"], peak=float(peaks[j]), balance=balances[pos[i]],
                                        long_oz=longs[pos[i]], short_oz=shorts[pos[i]], bid=bids[i], ask=asks[i],
                                        seconds_since_fill=(times[i] - times_filled[pos[i]]) / 1000)
                stats["minimum"] = min(stats["minimum"], float(equity.min()))
                stats["ticks"] += len(equity)
                peak, last_equity = float(peaks[-1]), float(equity[-1])
    first = min(events, key=lambda key: pd.Timestamp(events[key]["time"])) if events else None
    return dict(metrics=metrics, phase=phase, first_event=first, events=events, days=days, deals=deals)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for key in ["report", "phase", "start", "end", "output"]:
        parser.add_argument(key)
    parser.add_argument("--cache")
    args = parser.parse_args()
    result = audit_ledger(*read_report(Path(args.report)), args.phase, pd.Timestamp(args.end, tz="UTC"),
                          pd.Timestamp(args.start, tz="UTC"), args.cache)
    Path(args.output).write_text(json.dumps(result, indent=2))
    print(result["first_event"], result["events"], result["metrics"])
