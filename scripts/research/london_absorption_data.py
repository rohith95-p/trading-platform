"""Prepare the single-feed input for the London quote absorption study."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from scripts.research import gold_quote_profile as profile

ARCHIVE = Path("research/xauusd_archive")
CACHE = Path("research/data/london_quote_absorption")


def build(path):
    profile.STORE = CACHE
    result = profile.minutes(path)
    assert result["invalid_quotes"] == result["out_of_order_quotes"] == 0
    return result["month"]


if __name__ == "__main__":
    files = [p for p in sorted((ARCHIVE / "payload/exness/XAUUSDm").glob("*.zip"))
             if 2019 <= int(p.stem[-7:-3]) <= 2024]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for month in pool.map(build, files):
            print(month, flush=True)
