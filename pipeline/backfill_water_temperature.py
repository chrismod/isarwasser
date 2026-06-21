#!/usr/bin/env python3
"""
One-shot backfill of water-temperature JSONLs from the GKD table.

The live scraper (fetch_and_store_isar.py) stores only the newest
value per run. When it has been down for a stretch (e.g. the June 2026
" Uhr"-suffix regression), days without a JSONL show no live value on
the frontend. The GKD measurement table holds about a week of 15-min
samples — this script grabs all of them and fills any missing day
file. Days that already have a file are left untouched.

Idempotent. Safe to re-run.

Usage:
    python3 pipeline/backfill_water_temperature.py
    python3 pipeline/backfill_water_temperature.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "current"
STATION_ID = "16005701"
URL = (
    f"https://www.gkd.bayern.de/de/fluesse/wassertemperatur/isar/"
    f"muenchen-{STATION_ID}/messwerte/tabelle"
)


def parse_row(date_str: str, value_str: str) -> dict | None:
    date_str = re.sub(r"\s*Uhr\s*$", "", date_str).strip()
    value_str = value_str.replace(",", ".").strip()
    if value_str in ("--", "", "n/a", "N/A"):
        return None
    try:
        ts = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
    except ValueError:
        return None
    try:
        value = float(value_str)
    except ValueError:
        return None
    return {
        "timestamp": ts.isoformat(),
        "timestamp_unix": int(ts.timestamp()),
        "date": ts.strftime("%Y-%m-%d"),
        "time": ts.strftime("%H:%M:%S"),
        "value_celsius": value,
        "unit": "°C",
        "station_id": STATION_ID,
        "station_name": "München / Isar",
        "source": "gkd.bayern.de",
        "fetched_at": datetime.now().isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Fetching {URL}")
    r = requests.get(
        URL, timeout=30, headers={"User-Agent": "IsarWasser-Backfill/1.0"}
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        print("ERROR: no table found", file=sys.stderr)
        return 2

    rows = table.find_all("tr")[1:]  # skip header
    print(f"Found {len(rows)} rows in GKD table")

    by_day: dict[str, list[dict]] = defaultdict(list)
    for tr in rows:
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        m = parse_row(
            cells[0].get_text(strip=True), cells[1].get_text(strip=True)
        )
        if m is not None:
            by_day[m["date"]].append(m)

    if not by_day:
        print("WARNING: no parseable rows found")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    for day in sorted(by_day):
        out = DATA_DIR / f"water_temperature_{day}.jsonl"
        if out.exists():
            print(f"  SKIP {out.name} (exists)")
            skipped += 1
            continue
        measurements = sorted(by_day[day], key=lambda m: m["timestamp"])
        action = "WOULD WRITE" if args.dry_run else "WRITE"
        print(f"  {action} {out.name} ({len(measurements)} measurements)")
        if not args.dry_run:
            with open(out, "w", encoding="utf-8") as f:
                for m in measurements:
                    json.dump(m, f, ensure_ascii=False)
                    f.write("\n")
            written += 1

    summary = "(dry-run) " if args.dry_run else ""
    print(f"\n{summary}{written} files written, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
