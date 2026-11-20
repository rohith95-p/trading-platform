"""Check frozen pullback brackets against the chronological broker quotes."""
from collections import defaultdict
from datetime import datetime, timedelta
import io
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import zipfile

import numpy as np
import pandas as pd

from scripts.research.london_absorption_data import ARCHIVE

REGISTRY = Path("research/registry")


def main():
    study = json.loads((REGISTRY / "public_gold_pullback_sessions.json").read_text())
    months = defaultdict(list)
    for row in study["records"]:
        months[row["date"][:7]].append(row)
    results = []
    for month, trades in months.items():
        path = ARCHIVE / "payload/exness/XAUUSDm" / ("Exness_XAUUSDm_" + month.replace("-", "_") + ".zip")
        with zipfile.ZipFile(path) as archive:
            data = archive.read(archive.namelist()[0])
        for trade in trades:
            entry = datetime.fromisoformat(trade["date"]).replace(hour=10, tzinfo=ZoneInfo("Europe/London")).astimezone(ZoneInfo("UTC"))
            def offset(minutes):
                stamp = (entry + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M")
                return data.index(f'"exness","XAUUSDm","{stamp}:'.encode())
            q = pd.read_csv(io.BytesIO(data[offset(0):offset(61)]), header=None, names=["venue","symbol","ts","bid","ask"])
            side = trade["side"]
            px = q["bid" if side == 1 else "ask"].to_numpy()
            sl = np.flatnonzero(side * (px - trade["stop"]) <= 0)
            tp = np.flatnonzero(side * (px - trade["target"]) >= 0)
            end = int(q.ts.searchsorted((entry + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")))
            assert 0 < end < len(q) and q.ts.is_monotonic_increasing
            i = min(sl[0] if len(sl) else end, tp[0] if len(tp) else end, end)
            price = (q.ask.iloc[0] if side == 1 else q.bid.iloc[0]) + side * .020
            assert abs(price - trade["entry"]) < .00001
            if i == end:
                reason, close = "time", px[i] - side * .020
            elif len(sl) and i == sl[0]:
                reason, close = "stop", px[i] - side * .020
            else:
                reason, close = "target", trade["target"]
            results.append(dict(date=trade["date"], side=side, ticks=len(q), exit_reason=reason, exit_tick=q.ts.iloc[i],
                                tick_net=side * (close - price) * 2 - .07, minute_net=trade["base"]))
    (REGISTRY / "public_gold_pullback_tick_check.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
