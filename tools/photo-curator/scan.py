#!/usr/bin/env python3
"""
Photo Curator — Phase 1: scan.

Walks a directory of photos/videos, extracts EXIF (JPG) or container tags
(MP4), checks distance to the Isar mainstream, and stores Isar-near assets
in a local SQLite DB. Also auto-labels each asset with the nearest landmark
(bridge / park / suburb).

Nothing is copied or modified outside the curator state directory.

Usage:
    python scan.py --root /mnt/m/Photos/2026 --max 50
    python scan.py --root /mnt/m/Photos/2026 --all
    python scan.py --root /mnt/m/Photos/2026 --threshold 50 --rescan
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import transform as shp_transform
from shapely.strtree import STRtree
from tqdm import tqdm

from backup import snapshot_db

# ---------- paths ----------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_DIR = Path(__file__).resolve().parent
STATE_DIR = REPO_ROOT / "imgsort"
DB_PATH = STATE_DIR / "curator.db"
ISAR_GEOJSON = TOOL_DIR / "isar.geojson"
POIS_GEOJSON = TOOL_DIR / "pois.geojson"

BERLIN_TZ = ZoneInfo("Europe/Berlin")

# UTM 32N: metric CRS for Munich, ~10cm accuracy at this scale.
TRANSFORMER_LL_TO_M = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)


def to_metric(geom):
    return shp_transform(lambda x, y, z=None: TRANSFORMER_LL_TO_M.transform(x, y), geom)


# ---------- DB schema ------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
  id              INTEGER PRIMARY KEY,
  source_path     TEXT UNIQUE NOT NULL,
  filename        TEXT NOT NULL,
  kind            TEXT NOT NULL,
  taken_at        TEXT,
  lat             REAL,
  lon             REAL,
  distance_isar_m REAL,
  location_label  TEXT,
  file_size       INTEGER,
  duration_s      REAL,
  width           INTEGER,
  height          INTEGER,
  orientation     INTEGER NOT NULL DEFAULT 1,
  display_rotation INTEGER NOT NULL DEFAULT 0,
  is_flood        INTEGER NOT NULL DEFAULT 0,
  promoted_path   TEXT,
  sha1            TEXT,
  thumb_path      TEXT,
  status          TEXT NOT NULL DEFAULT 'new',
  tags            TEXT,
  notes           TEXT,
  scanned_at      TEXT NOT NULL,
  promoted_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_assets_status   ON assets(status);
CREATE INDEX IF NOT EXISTS idx_assets_taken_at ON assets(taken_at);
CREATE INDEX IF NOT EXISTS idx_assets_distance ON assets(distance_isar_m);
"""


def migrate_db(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the initial schema."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(assets)")}
    if "orientation" not in cols:
        conn.execute("ALTER TABLE assets ADD COLUMN orientation INTEGER NOT NULL DEFAULT 1")
    if "display_rotation" not in cols:
        conn.execute("ALTER TABLE assets ADD COLUMN display_rotation INTEGER NOT NULL DEFAULT 0")
    if "is_flood" not in cols:
        conn.execute("ALTER TABLE assets ADD COLUMN is_flood INTEGER NOT NULL DEFAULT 0")
    if "promoted_path" not in cols:
        conn.execute("ALTER TABLE assets ADD COLUMN promoted_path TEXT")
    conn.commit()


def open_db() -> sqlite3.Connection:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    migrate_db(conn)
    return conn


# ---------- geometry loading ----------------------------------------------


def load_isar() -> "tuple":
    """Returns (isar_metric_geoms, prepared_union) for distance queries."""
    fc = json.loads(ISAR_GEOJSON.read_text())
    parts = []
    for f in fc["features"]:
        g = shape(f["geometry"])
        parts.append(to_metric(g))
    if not parts:
        raise SystemExit(f"No Isar geometry in {ISAR_GEOJSON}")
    # Combined LineString collection — distance() picks the nearest.
    from shapely.geometry import MultiLineString

    combined = MultiLineString([p for p in parts if isinstance(p, LineString)] or parts)
    return combined


def load_pois() -> "tuple":
    """
    Returns (poi_geoms_metric, poi_props, strtree).
    Closed ways become Polygons; open ways stay LineStrings; nodes Points.
    """
    fc = json.loads(POIS_GEOJSON.read_text())
    geoms = []
    props = []
    for f in fc["features"]:
        g = f["geometry"]
        if g["type"] == "LineString":
            coords = g["coordinates"]
            if len(coords) >= 4 and coords[0] == coords[-1]:
                try:
                    geom = Polygon(coords)
                    if not geom.is_valid:
                        geom = geom.buffer(0)
                except Exception:
                    geom = LineString(coords)
            else:
                geom = LineString(coords)
        else:
            geom = shape(g)
        try:
            metric = to_metric(geom)
        except Exception:
            continue
        geoms.append(metric)
        props.append(f["properties"])
    tree = STRtree(geoms)
    return geoms, props, tree


# ---------- EXIF / metadata ------------------------------------------------


def _gps_to_decimal(coord, ref) -> float:
    if not coord or len(coord) < 3:
        return None
    deg, minutes, seconds = coord
    val = float(deg) + float(minutes) / 60 + float(seconds) / 3600
    if ref in ("S", "W"):
        val = -val
    return val


def read_jpg_meta(path: Path) -> dict:
    out = {
        "lat": None,
        "lon": None,
        "taken_at": None,
        "width": None,
        "height": None,
        "orientation": 1,
    }
    try:
        with Image.open(path) as img:
            out["width"], out["height"] = img.size
            exif = img._getexif() or {}
    except Exception as e:
        out["error"] = f"PIL: {e}"
        return out
    parsed = {}
    gps = {}
    for tag_id, val in exif.items():
        tag = TAGS.get(tag_id, tag_id)
        if tag == "GPSInfo":
            for k, v in val.items():
                gps[GPSTAGS.get(k, k)] = v
        else:
            parsed[tag] = val
    # EXIF Orientation tag (1, 3, 6, 8 are the common ones)
    ori = parsed.get("Orientation")
    if isinstance(ori, int) and ori in (1, 2, 3, 4, 5, 6, 7, 8):
        out["orientation"] = ori
    dt_str = parsed.get("DateTimeOriginal") or parsed.get("DateTime")
    if dt_str:
        try:
            dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
            out["taken_at"] = dt.replace(tzinfo=BERLIN_TZ).isoformat()
        except ValueError:
            pass
    if gps:
        lat = _gps_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
        lon = _gps_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
        if lat is not None and lon is not None:
            out["lat"] = lat
            out["lon"] = lon
    return out


def _parse_iso6109_location(s: str) -> "tuple|None":
    """Parse strings like '+48.1227+011.5681/' or '+48.1227+011.5681+556.000/'."""
    import re

    m = re.match(r"([+-]\d+\.?\d*)([+-]\d+\.?\d*)", s)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def _rotation_to_exif_orientation(deg: int) -> int:
    """Map a rotation in degrees (0/90/180/270, CW positive) to EXIF orientation."""
    deg = int(deg) % 360
    return {0: 1, 90: 6, 180: 3, 270: 8}.get(deg, 1)


def read_video_meta(path: Path) -> dict:
    out = {
        "lat": None,
        "lon": None,
        "taken_at": None,
        "duration_s": None,
        "width": None,
        "height": None,
        "orientation": 1,
    }
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as e:
        out["error"] = f"ffprobe spawn: {e}"
        return out
    if proc.returncode != 0:
        out["error"] = f"ffprobe rc={proc.returncode}: {proc.stderr.strip()[:200]}"
        return out
    try:
        data = json.loads(proc.stdout)
    except Exception as e:
        out["error"] = f"ffprobe json: {e}"
        return out
    fmt = data.get("format", {}) or {}
    tags = fmt.get("tags", {}) or {}
    if "duration" in fmt:
        try:
            out["duration_s"] = float(fmt["duration"])
        except ValueError:
            pass
    # Creation time is UTC.
    ct = tags.get("creation_time")
    if ct:
        try:
            dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            out["taken_at"] = dt.astimezone(BERLIN_TZ).isoformat()
        except ValueError:
            pass
    # Location is ISO-6709.
    loc = tags.get("location") or tags.get("location-eng")
    if loc:
        ll = _parse_iso6109_location(loc)
        if ll:
            out["lat"], out["lon"] = ll
    # First video stream for w/h + rotation
    for s in data.get("streams", []):
        if s.get("codec_type") != "video":
            continue
        out["width"] = s.get("width")
        out["height"] = s.get("height")
        # Rotation can live in stream tags ("rotate") or in side_data_list
        # ("rotation", which is signed and counter-clockwise).
        rot = None
        st_tags = s.get("tags") or {}
        if "rotate" in st_tags:
            try:
                rot = int(st_tags["rotate"])
            except ValueError:
                pass
        if rot is None:
            for sd in s.get("side_data_list", []) or []:
                if "rotation" in sd:
                    # ffprobe rotation is CCW; flip to CW for our convention.
                    rot = -int(sd["rotation"])
                    break
        if rot is not None:
            out["orientation"] = _rotation_to_exif_orientation(rot)
        break
    return out


def quick_sha1(path: Path, max_bytes: int = 1024 * 1024) -> str:
    """SHA1 of the first ~1 MB. Cheap dedup proxy."""
    h = hashlib.sha1()
    try:
        with path.open("rb") as f:
            h.update(f.read(max_bytes))
    except OSError:
        return ""
    return h.hexdigest()


# ---------- location labeling ---------------------------------------------

# Compass bearings → German cardinal phrases.
DIRECTIONS = [
    (0, "nördlich"),
    (45, "nordöstlich"),
    (90, "östlich"),
    (135, "südöstlich"),
    (180, "südlich"),
    (225, "südwestlich"),
    (270, "westlich"),
    (315, "nordwestlich"),
    (360, "nördlich"),
]


def cardinal_de(dx_m: float, dy_m: float) -> str:
    """dx east, dy north (metric). Returns German compass word."""
    import math

    bearing = (math.degrees(math.atan2(dx_m, dy_m)) + 360) % 360
    best = DIRECTIONS[0][1]
    best_diff = 999
    for ang, word in DIRECTIONS:
        diff = abs(((bearing - ang + 540) % 360) - 180)
        if diff < best_diff:
            best_diff = diff
            best = word
    return best


def grammatical_gender(name: str) -> str:
    """
    Coarse heuristic for German noun gender of a landmark name, based on
    common suffixes. Used to pick the right preposition + article.
    Returns 'f', 'm', or 'n'.
    """
    n = name.lower()
    # feminine
    for suf in ("brücke", "brueke", "straße", "strasse", "gasse", "allee", "insel", "wiese", "au", "halle", "kirche", "burg"):
        if n.endswith(suf):
            return "f"
    # neuter
    for suf in ("tor", "ufer", "feld", "haus", "schloss", "kloster", "tal", "viertel"):
        if n.endswith(suf):
            return "n"
    # masculine
    for suf in ("steg", "garten", "weg", "platz", "park", "berg", "hof", "bach", "graben", "anger", "see", "turm", "stein", "er", "markt", "ring", "damm", "rain", "grund"):
        if n.endswith(suf):
            return "m"
    # default: masculine (safer fallback for proper nouns)
    return "m"


# Phrase templates per (gender, register).
# register: 'at' (≤30m), 'near' (≤80m), 'dir' (with cardinal direction)
PHRASES = {
    ("f", "at"):  ("an der",        ""),
    ("f", "near"):("bei der",       ""),
    ("f", "dir"): ("{dir} der",     ""),
    ("m", "at"):  ("am",            ""),
    ("m", "near"):("beim",          ""),
    ("m", "dir"): ("{dir} des",     ""),
    ("n", "at"):  ("am",            ""),
    ("n", "near"):("beim",          ""),
    ("n", "dir"): ("{dir} des",     ""),
}


def phrase(name: str, register: str, direction: str | None = None) -> str:
    g = grammatical_gender(name)
    prep, _ = PHRASES[(g, register)]
    if "{dir}" in prep:
        prep = prep.format(dir=direction or "nahe")
    return f"{prep} {name}"


def label_for_point(
    point_metric: Point,
    pois_geoms: list,
    pois_props: list,
    tree: STRtree,
) -> str:
    """
    Build a human-readable German location label for a point near the Isar.
    Strategy:
      1. If inside a named park polygon → "im X".
      2. If a bridge is within 250 m → distance/direction phrasing.
      3. Else fallback: nearest suburb/quarter → "in X".
      4. Else "an der Isar".
    """
    # Query candidates with a 500m buffer for efficiency.
    buf = point_metric.buffer(500)
    candidate_idxs = tree.query(buf)

    parks = []
    bridges = []
    places = []
    attractions = []
    for idx in candidate_idxs:
        idx = int(idx)
        geom = pois_geoms[idx]
        prop = pois_props[idx]
        kind = prop["kind"]
        if kind == "park" and isinstance(geom, Polygon):
            if geom.contains(point_metric):
                parks.append((0.0, prop["name"]))
        elif kind == "bridge":
            d = point_metric.distance(geom)
            if d <= 300:
                # representative point for direction
                rep = geom.centroid if isinstance(geom, (LineString, Polygon)) else geom
                dx = point_metric.x - rep.x
                dy = point_metric.y - rep.y
                bridges.append((d, prop["name"], dx, dy))
        elif kind == "place":
            d = point_metric.distance(geom)
            places.append((d, prop["name"]))
        elif kind == "attraction":
            d = point_metric.distance(geom)
            if d <= 200:
                attractions.append((d, prop["name"]))

    if parks:
        parks.sort()
        name = parks[0][1]
        nl = name.lower()
        # Enclosed spaces (gardens, parks, forests) → "im/in der" (inside).
        # Place-like names (Flaucher, Mangfallplatz) → "am" (at).
        enclosed = any(nl.endswith(s) for s in ("garten", "park", "wald", "hain", "anlage", "anlagen", "wiese", "aue", "auen"))
        if enclosed:
            if nl.endswith(("anlagen", "auen", "wiesen", "gärten")):
                return f"in den {name}"
            g = grammatical_gender(name)
            return f"in der {name}" if g == "f" else f"im {name}"
        return f"am {name}"

    if bridges:
        bridges.sort()
        d, name, dx, dy = bridges[0]
        if d <= 30:
            return phrase(name, "at")
        if d <= 80:
            return phrase(name, "near")
        return phrase(name, "dir", direction=cardinal_de(dx, dy))

    if attractions:
        attractions.sort()
        return f"nahe {attractions[0][1]}"

    if places:
        places.sort()
        return f"in {places[0][1]}"

    return "an der Isar"


# ---------- main scan ------------------------------------------------------

EXTS_PHOTO = {".jpg", ".jpeg"}
EXTS_VIDEO = {".mp4", ".mov"}


def iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in EXTS_PHOTO:
            yield p, "photo"
        elif ext in EXTS_VIDEO:
            yield p, "video"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--max", type=int, default=None, help="Hard cap on files processed")
    ap.add_argument("--all", action="store_true", help="No cap (overrides --max)")
    ap.add_argument(
        "--threshold",
        type=float,
        default=30.0,
        help="Distance to Isar mainstream in metres (default: 30)",
    )
    ap.add_argument(
        "--rescan",
        action="store_true",
        help="Re-process files even if already in DB",
    )
    args = ap.parse_args()

    if not args.root.exists():
        print(f"ERROR: --root does not exist: {args.root}", file=sys.stderr)
        return 2

    snap = snapshot_db("scan")
    if snap is not None:
        print(f"DB snapshot → {snap.relative_to(REPO_ROOT)}")

    print("Loading Isar geometry…")
    isar_metric = load_isar()
    print("Loading POIs…")
    poi_geoms, poi_props, poi_tree = load_pois()
    print(f"  {len(poi_geoms)} POIs indexed")

    conn = open_db()
    cur = conn.cursor()

    files = list(iter_files(args.root))
    if not args.all and args.max:
        files = files[: args.max]
    print(f"Found {len(files)} candidate files under {args.root}")

    counts = {
        "scanned": 0,
        "skipped_known": 0,
        "no_gps": 0,
        "with_gps": 0,
        "near_isar": 0,
        "errors": 0,
    }

    now_iso = datetime.now(BERLIN_TZ).isoformat()

    for path, kind in tqdm(files, desc="scanning"):
        counts["scanned"] += 1

        if not args.rescan:
            cur.execute("SELECT 1 FROM assets WHERE source_path = ?", (str(path),))
            if cur.fetchone():
                counts["skipped_known"] += 1
                continue

        if kind == "photo":
            meta = read_jpg_meta(path)
        else:
            meta = read_video_meta(path)

        if "error" in meta:
            counts["errors"] += 1
            continue

        if meta["lat"] is None or meta["lon"] is None:
            counts["no_gps"] += 1
            continue
        counts["with_gps"] += 1

        # Distance to Isar
        pt_ll = Point(meta["lon"], meta["lat"])
        pt_m = to_metric(pt_ll)
        d_isar = pt_m.distance(isar_metric)
        if d_isar > args.threshold:
            continue
        counts["near_isar"] += 1

        label = label_for_point(pt_m, poi_geoms, poi_props, poi_tree)

        try:
            file_size = path.stat().st_size
        except OSError:
            file_size = None

        sha1 = quick_sha1(path)

        cur.execute(
            """
            INSERT INTO assets (
                source_path, filename, kind, taken_at, lat, lon,
                distance_isar_m, location_label, file_size, duration_s,
                width, height, orientation, sha1, status, scanned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
            ON CONFLICT(source_path) DO UPDATE SET
                taken_at        = excluded.taken_at,
                lat             = excluded.lat,
                lon             = excluded.lon,
                distance_isar_m = excluded.distance_isar_m,
                location_label  = excluded.location_label,
                file_size       = excluded.file_size,
                duration_s      = excluded.duration_s,
                width           = excluded.width,
                height          = excluded.height,
                orientation     = excluded.orientation,
                sha1            = excluded.sha1,
                scanned_at      = excluded.scanned_at
            """,
            (
                str(path),
                path.name,
                kind,
                meta.get("taken_at"),
                meta["lat"],
                meta["lon"],
                round(d_isar, 2),
                label,
                file_size,
                meta.get("duration_s"),
                meta.get("width"),
                meta.get("height"),
                meta.get("orientation", 1),
                sha1,
                now_iso,
            ),
        )
        conn.commit()

    conn.close()

    print()
    print("Done.")
    for k, v in counts.items():
        print(f"  {k:14s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
