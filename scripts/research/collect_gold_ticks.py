"""Archive public monthly Exness gold quotes, preserving feeds and original ZIPs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import os
from pathlib import Path
import time
import zipfile

import requests

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "research/xauusd_archive"


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def audit(path, symbol, month):
    """Reading to EOF checks the ZIP CRC. Keep original row order and bytes."""
    with zipfile.ZipFile(path) as z:
        members = [m for m in z.infolist() if not m.is_dir()]
        if len(members) != 1 or not members[0].filename.lower().endswith(".csv"):
            raise ValueError("Unexpected ZIP members")
        with z.open(members[0]) as f:
            header = next(csv.reader([f.readline().decode("utf-8-sig").strip()]))
            if header != ["Exness", "Symbol", "Timestamp", "Bid", "Ask"]:
                raise ValueError(f"Unexpected schema {header}")
            first = f.readline()
            rows = 1
            tail = b""
            for chunk in iter(lambda: f.read(1024*1024), b""):
                rows += chunk.count(b"\n")
                tail = (tail+chunk)[-512:]
            if tail and not tail.endswith(b"\n"):
                rows += 1
            last = tail.splitlines()[-1] if tail else first
            bounds = []
            for raw in (first, last):
                row = next(csv.reader([raw.decode().strip()]))
                if len(row) != 5 or row[1] != symbol or not row[2].startswith(month) or float(row[4]) < float(row[3]):
                    raise ValueError(f"Unexpected boundary row {row}")
                bounds.append(row[2])
    return dict(sha256=sha(path), bytes=path.stat().st_size, quote_rows=rows,
                first_utc=bounds[0], last_utc=bounds[1], member=members[0].filename,
                crc32=f"{members[0].CRC:08x}")


def fetch(key):
    symbol, year, month = key
    ym = f"{year}-{month:02d}"
    filename = f"Exness_{symbol}_{year}_{month:02d}.zip"
    url = f"https://ticks.ex2archive.com/ticks/{symbol}/{year}/{month:02d}/{filename}"
    path = STORE/"payload"/"exness"/symbol/filename
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(f".{os.getpid()}.part")
    row = dict(symbol=symbol, month=ym, url=url)
    for attempt in range(3):
        try:
            if not path.exists():
                with requests.get(url, stream=True, timeout=(12, 75)) as response:
                    if response.status_code == 404:
                        return dict(**row, status="provider_404")
                    response.raise_for_status()
                    with part.open("wb") as out:
                        for chunk in response.iter_content(512*1024):
                            out.write(chunk)
            meta = audit(path if path.exists() else part, symbol, ym)
            if not path.exists():
                part.replace(path)
            return dict(**row, **meta, status="verified", path=path.relative_to(STORE).as_posix())
        except (OSError, zipfile.BadZipFile, ValueError, requests.RequestException) as exc:
            reason = str(exc)
            if attempt < 2:
                time.sleep(1+attempt)
    return dict(**row, status="failed", reason=reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", choices=["XAUUSDm", "XAUUSD_Raw_Spread"], required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--first-year", type=int, default=2019, choices=range(2019,2027))
    args = parser.parse_args()
    months = [(args.symbol,y,m) for y in range(args.first_year,2027) for m in range(1,13) if (y,m)<(2026,11)]
    suffix = "" if args.first_year == 2019 else f"_{args.first_year}"
    output = STORE/f"ticks_{args.symbol}{suffix}.json"
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for r in pool.map(fetch, months):
            rows.append(r)
            tmp = output.with_suffix(".part")
            tmp.write_text(json.dumps(rows, indent=2)+"\n", encoding="utf-8")
            tmp.replace(output)
            print(r["month"], r["status"], r.get("quote_rows", r.get("reason", "")), flush=True)


if __name__ == "__main__":
    main()
