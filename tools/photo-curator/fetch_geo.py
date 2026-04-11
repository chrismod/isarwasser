#!/usr/bin/env python3
"""
One-shot fetch of OSM data for the photo curator.

Pulls from Overpass:
  - Isar mainstream (waterway=river, name=Isar) within the Munich bbox.
    Side arms (Auer Mühlbach, Eisbach, Isarkanal, Floßlände) are excluded
    by name filter.
  - POIs we use to label photo locations: bridges crossing the Isar, parks
    and gardens near the Isar, suburbs/quarters, and notable attractions.

Writes two files in the same directory:
  - isar.geojson           (LineString collection of the mainstream)
  - pois.geojson           (FeatureCollection of labeled points/lines/polys)

Run once at setup time. The output is committed to the repo.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Munich bbox covering the Isar from south of Großhesselohe to north of Garching.
# (south, west, north, east)
BBOX = (48.05, 11.40, 48.30, 11.75)

# Side arms / parallel waterways we want to EXCLUDE from the mainstream.
SIDE_ARM_NAMES = {
    "Auer Mühlbach",
    "Eisbach",
    "Isarkanal",
    "Floßlände",
    "Floßkanal",
    "Großer Stadtbach",
    "Werkkanal",
    "Mühlbach",
}

OUT_DIR = Path(__file__).parent


def overpass(query: str) -> dict:
    print(f"  query length: {len(query)} chars", file=sys.stderr)
    for attempt in range(3):
        try:
            r = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=180,
                headers={"User-Agent": "isarwasser-photo-curator/0.1"},
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"  attempt {attempt + 1} failed: {e}", file=sys.stderr)
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_isar_mainstream() -> list[dict]:
    """Return list of GeoJSON LineString features for the Isar mainstream."""
    print("Fetching Isar mainstream from Overpass…", file=sys.stderr)
    s, w, n, e = BBOX
    query = f"""
    [out:json][timeout:120];
    (
      way["waterway"="river"]["name"="Isar"]({s},{w},{n},{e});
    );
    out geom;
    """
    data = overpass(query)
    features = []
    for el in data.get("elements", []):
        if el.get("type") != "way":
            continue
        tags = el.get("tags", {})
        # Should already be name=Isar from query, but be defensive.
        if tags.get("name") != "Isar":
            continue
        # Exclude any side-arm-tagged ways that slipped through.
        if tags.get("name:de") in SIDE_ARM_NAMES:
            continue
        coords = [[pt["lon"], pt["lat"]] for pt in el.get("geometry", [])]
        if len(coords) < 2:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "osm_id": el["id"],
                    "name": tags.get("name", "Isar"),
                    "waterway": tags.get("waterway"),
                },
            }
        )
    print(f"  got {len(features)} mainstream segments", file=sys.stderr)
    return features


def fetch_pois() -> list[dict]:
    """Bridges, parks, suburbs, attractions in the bbox."""
    print("Fetching POIs from Overpass…", file=sys.stderr)
    s, w, n, e = BBOX
    # We deliberately keep this list focused. The names will be used to build
    # human-readable location labels like "Isar bei der Reichenbachbrücke" or
    # "Isar im Englischen Garten".
    query = f"""
    [out:json][timeout:180];
    (
      // Bridges over the Isar
      way["man_made"="bridge"]["name"]({s},{w},{n},{e});
      way["bridge"="yes"]["name"]({s},{w},{n},{e});
      // Parks, gardens, recreational greens
      way["leisure"="park"]["name"]({s},{w},{n},{e});
      relation["leisure"="park"]["name"]({s},{w},{n},{e});
      way["leisure"="garden"]["name"]({s},{w},{n},{e});
      // Beer gardens (very München)
      node["amenity"="biergarten"]["name"]({s},{w},{n},{e});
      // Suburbs / quarters / neighbourhoods
      node["place"~"^(suburb|quarter|neighbourhood|borough)$"]["name"]({s},{w},{n},{e});
      // Tourist attractions and notable historic sites
      node["tourism"="attraction"]["name"]({s},{w},{n},{e});
      way["tourism"="attraction"]["name"]({s},{w},{n},{e});
      node["historic"]["name"]({s},{w},{n},{e});
    );
    out tags center geom;
    """
    data = overpass(query)
    features = []
    for el in data.get("elements", []):
        tags = el.get("tags", {}) or {}
        name = tags.get("name")
        if not name:
            continue
        # Determine geometry: prefer explicit geom, else center, else lat/lon.
        geom = None
        if el.get("type") == "node" and "lat" in el and "lon" in el:
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        elif "geometry" in el and el["geometry"]:
            coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
            if len(coords) >= 2:
                geom = {"type": "LineString", "coordinates": coords}
        elif "center" in el:
            c = el["center"]
            geom = {"type": "Point", "coordinates": [c["lon"], c["lat"]]}
        if not geom:
            continue
        # Classify
        if "man_made" in tags and tags["man_made"] == "bridge":
            kind = "bridge"
        elif tags.get("bridge") == "yes":
            kind = "bridge"
        elif tags.get("leisure") in ("park", "garden"):
            kind = "park"
        elif tags.get("amenity") == "biergarten":
            kind = "biergarten"
        elif tags.get("place") in ("suburb", "quarter", "neighbourhood", "borough"):
            kind = "place"
        elif tags.get("tourism") == "attraction":
            kind = "attraction"
        elif "historic" in tags:
            kind = "historic"
        else:
            kind = "other"
        features.append(
            {
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "osm_id": el["id"],
                    "osm_type": el["type"],
                    "name": name,
                    "kind": kind,
                    "raw_tags": {
                        k: v
                        for k, v in tags.items()
                        if k
                        in (
                            "place",
                            "leisure",
                            "tourism",
                            "historic",
                            "bridge",
                            "man_made",
                            "amenity",
                            "wikidata",
                        )
                    },
                },
            }
        )
    print(f"  got {len(features)} POI features", file=sys.stderr)
    # Deduplicate by (kind, name) keeping first occurrence.
    seen = set()
    unique = []
    for f in features:
        key = (f["properties"]["kind"], f["properties"]["name"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    print(f"  {len(unique)} after dedup", file=sys.stderr)
    return unique


def write_geojson(features: list[dict], path: Path) -> None:
    fc = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(fc, ensure_ascii=False, indent=2))
    print(f"  wrote {path} ({path.stat().st_size // 1024} KB)", file=sys.stderr)


def main() -> int:
    isar = fetch_isar_mainstream()
    if not isar:
        print("ERROR: no Isar segments returned", file=sys.stderr)
        return 1
    write_geojson(isar, OUT_DIR / "isar.geojson")

    pois = fetch_pois()
    write_geojson(pois, OUT_DIR / "pois.geojson")

    return 0


if __name__ == "__main__":
    sys.exit(main())
