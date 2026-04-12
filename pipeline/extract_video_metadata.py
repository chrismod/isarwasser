#!/usr/bin/env python3
"""
Extract metadata from raw videos (mp4_raw/) and enrich with water data.

For each .mp4 in web/public/mp4_raw/:
  1. Read GPS + creation_time via ffprobe.
  2. Find nearest water level + temperature from Parquet files and/or
     daily JSONL logs.
  3. Auto-label the location using the Overpass-derived GeoJSON files
     from tools/photo-curator/.
  4. Write web/public/videos/metadata.json.

The output is deployed together with the optimized videos — the frontend
reads it at runtime to populate the VideoInfoBubble.

Usage:
    python3 pipeline/extract_video_metadata.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
MP4_RAW = REPO_ROOT / "web" / "public" / "mp4_raw"
VIDEOS_DIR = REPO_ROOT / "web" / "public" / "videos"
PARQUET_DIR = REPO_ROOT / "data" / "parquet" / "raw"
JSONL_DIR = REPO_ROOT / "data" / "current"
ISAR_GEOJSON = REPO_ROOT / "tools" / "photo-curator" / "isar.geojson"
POIS_GEOJSON = REPO_ROOT / "tools" / "photo-curator" / "pois.geojson"

BERLIN_TZ = ZoneInfo("Europe/Berlin")

# ---------- ffprobe --------------------------------------------------------


def read_video_meta(path: Path) -> dict | None:
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=20,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return None
    fmt = data.get("format", {}) or {}
    tags = fmt.get("tags", {}) or {}
    out: dict = {}
    ct = tags.get("creation_time")
    if ct:
        try:
            dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            out["taken_at"] = dt.astimezone(BERLIN_TZ)
        except ValueError:
            pass
    loc = tags.get("location") or tags.get("location-eng")
    if loc:
        m = re.match(r"([+-]\d+\.?\d*)([+-]\d+\.?\d*)", loc)
        if m:
            out["lat"] = float(m.group(1))
            out["lon"] = float(m.group(2))
    dur = fmt.get("duration")
    if dur:
        try:
            out["duration_s"] = round(float(dur), 1)
        except ValueError:
            pass
    return out if ("taken_at" in out or "lat" in out) else None


# ---------- water data lookup ----------------------------------------------

_parquet_cache: dict[str, list] = {}


def _load_parquet(parameter: str) -> list[tuple[datetime, float]]:
    """Load a parquet file into a sorted list of (naive-utc-ts, value)."""
    if parameter in _parquet_cache:
        return _parquet_cache[parameter]
    fname = f"station_16005701_{parameter}.parquet"
    path = PARQUET_DIR / fname
    if not path.exists():
        _parquet_cache[parameter] = []
        return []
    import pyarrow.parquet as pq
    t = pq.read_table(path, columns=["ts", "value"])
    rows = [
        (ts.as_py(), v.as_py())
        for ts, v in zip(t.column("ts"), t.column("value"))
        if ts.as_py() is not None
    ]
    rows.sort(key=lambda r: r[0])
    _parquet_cache[parameter] = rows
    return rows


def _bisect_nearest(rows: list[tuple[datetime, float]], target: datetime,
                    max_delta: timedelta = timedelta(minutes=30)) -> float | None:
    """Binary search for the nearest value within max_delta."""
    import bisect
    idx = bisect.bisect_left(rows, (target,))
    best_val = None
    best_diff = max_delta
    for i in (idx - 1, idx, idx + 1):
        if 0 <= i < len(rows):
            diff = abs(rows[i][0] - target)
            if diff < best_diff and rows[i][1] is not None:
                best_diff = diff
                best_val = rows[i][1]
    return best_val


def _search_jsonl(date_str: str, target: datetime, data_type: str) -> float | None:
    """Search JSONL files for the nearest measurement."""
    best_val = None
    best_diff = timedelta(hours=6)
    for offset in (0, -1, 1):
        d = datetime.fromisoformat(date_str) + timedelta(days=offset)
        path = JSONL_DIR / f"{data_type}_{d.strftime('%Y-%m-%d')}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            ts_str = entry.get("timestamp")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
            except ValueError:
                continue
            diff = abs(ts - target)
            val = entry.get("value_cm") or entry.get("value_celsius")
            if diff < best_diff and val is not None:
                best_diff = diff
                best_val = val
    return best_val


def lookup_water(taken_at: datetime) -> dict:
    """Find the closest water level and temperature for a given timestamp."""
    naive = taken_at.replace(tzinfo=None) if taken_at.tzinfo else taken_at
    result: dict = {}
    # Parquet first (fast, covers 1973–Jan 2026)
    level_rows = _load_parquet("water_level_cm")
    if level_rows:
        val = _bisect_nearest(level_rows, naive)
        if val is not None:
            result["waterLevelCm"] = round(val, 1)
    temp_rows = _load_parquet("water_temperature_c")
    if temp_rows:
        val = _bisect_nearest(temp_rows, naive)
        if val is not None:
            result["waterTemperatureC"] = round(val, 1)
    # JSONL fallback for data beyond parquet range
    date_str = naive.strftime("%Y-%m-%d")
    if "waterLevelCm" not in result:
        val = _search_jsonl(date_str, naive, "water_level")
        if val is not None:
            result["waterLevelCm"] = round(val, 1)
    if "waterTemperatureC" not in result:
        val = _search_jsonl(date_str, naive, "water_temperature")
        if val is not None:
            result["waterTemperatureC"] = round(val, 1)
    return result


# ---------- location labeling (lightweight) --------------------------------

_geo_data = None


def _load_geo():
    global _geo_data
    if _geo_data is not None:
        return _geo_data
    from pyproj import Transformer
    from shapely.geometry import LineString, MultiLineString, Point, Polygon, shape
    from shapely.ops import transform as shp_transform
    from shapely.strtree import STRtree

    tx = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)

    def to_m(geom):
        return shp_transform(lambda x, y, z=None: tx.transform(x, y), geom)

    # Isar
    fc = json.loads(ISAR_GEOJSON.read_text())
    parts = [to_m(shape(f["geometry"])) for f in fc["features"]]
    isar = MultiLineString([p for p in parts if isinstance(p, LineString)])

    # POIs
    fc = json.loads(POIS_GEOJSON.read_text())
    geoms, props = [], []
    for f in fc["features"]:
        g = f["geometry"]
        if g["type"] == "LineString":
            coords = g["coordinates"]
            if len(coords) >= 4 and coords[0] == coords[-1]:
                geom = Polygon(coords)
                if not geom.is_valid:
                    geom = geom.buffer(0)
            else:
                geom = LineString(coords)
        else:
            geom = shape(g)
        try:
            geoms.append(to_m(geom))
            props.append(f["properties"])
        except Exception:
            continue
    tree = STRtree(geoms)
    _geo_data = (isar, geoms, props, tree, to_m)
    return _geo_data


def label_location(lat: float, lon: float) -> tuple[str, float]:
    """Returns (label, distance_to_isar_m)."""
    from shapely.geometry import LineString, Point, Polygon

    isar, geoms, props, tree, to_m = _load_geo()
    pt = to_m(Point(lon, lat))
    d_isar = pt.distance(isar)

    buf = pt.buffer(500)
    idxs = tree.query(buf)

    parks, bridges, places = [], [], []
    for idx in idxs:
        idx = int(idx)
        g, p = geoms[idx], props[idx]
        kind = p["kind"]
        if kind == "park" and isinstance(g, Polygon) and g.contains(pt):
            parks.append((0.0, p["name"]))
        elif kind == "bridge":
            d = pt.distance(g)
            if d <= 150:
                bridges.append((d, p["name"]))
        elif kind == "place":
            places.append((pt.distance(g), p["name"]))

    # Same phrasing logic as scan.py
    if parks:
        parks.sort()
        name = parks[0][1]
        nl = name.lower()
        enclosed = any(nl.endswith(s) for s in
                       ("garten", "park", "wald", "hain", "anlage", "anlagen",
                        "wiese", "aue", "auen"))
        if enclosed:
            if nl.endswith(("anlagen", "auen", "wiesen", "gärten")):
                label = f"in den {name}"
            else:
                label = f"im {name}"
        else:
            label = f"am {name}"
        return label, d_isar

    if bridges:
        bridges.sort()
        name = bridges[0][1]
        d = bridges[0][0]
        nl = name.lower()
        # Simple gender for preposition
        fem = any(nl.endswith(s) for s in ("brücke", "straße", "gasse"))
        if d <= 30:
            label = f"an der {name}" if fem else f"am {name}"
        elif d <= 80:
            label = f"bei der {name}" if fem else f"beim {name}"
        else:
            label = f"nahe der {name}" if fem else f"nahe {name}"
        return label, d_isar

    if places:
        places.sort()
        return f"in {places[0][1]}", d_isar

    return "an der Isar", d_isar


# ---------- season ---------------------------------------------------------

def season_for(dt: datetime) -> str:
    m = dt.month
    if m in (12, 1, 2):
        return "winter"
    if m in (3, 4, 5):
        return "spring"
    if m in (6, 7, 8):
        return "summer"
    return "autumn"


# ---------- main -----------------------------------------------------------

def main() -> int:
    if not MP4_RAW.exists():
        print(f"ERROR: {MP4_RAW} not found", file=sys.stderr)
        return 2

    files = sorted(MP4_RAW.glob("*.mp4"))
    print(f"Scanning {len(files)} raw videos in {MP4_RAW.relative_to(REPO_ROOT)}")

    metadata: dict = {}
    ok = skip = 0

    for path in files:
        meta = read_video_meta(path)
        if not meta or "taken_at" not in meta:
            print(f"  SKIP {path.name}: no creation_time")
            skip += 1
            continue

        taken: datetime = meta["taken_at"]
        entry: dict = {
            "recordedAt": taken.isoformat(),
            "season": season_for(taken),
        }

        if meta.get("duration_s"):
            entry["durationS"] = meta["duration_s"]

        # Location
        if "lat" in meta and "lon" in meta:
            label, d_isar = label_location(meta["lat"], meta["lon"])
            entry["location"] = {
                "lat": round(meta["lat"], 5),
                "lon": round(meta["lon"], 5),
                "name": label,
            }
            entry["distanceIsarM"] = round(d_isar, 1)

        # Water data
        water = lookup_water(taken)
        if water:
            entry.update(water)

        metadata[path.name] = entry
        wl = water.get("waterLevelCm", "?")
        wt = water.get("waterTemperatureC", "?")
        loc_name = entry.get("location", {}).get("name", "?")
        print(f"  OK {path.name}: {taken.strftime('%d.%m.%Y %H:%M')} · "
              f"{loc_name} · {wl} cm · {wt} °C")
        ok += 1

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VIDEOS_DIR / "metadata.json"
    out_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(f"\nWrote {out_path.relative_to(REPO_ROOT)} ({ok} entries, {skip} skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
