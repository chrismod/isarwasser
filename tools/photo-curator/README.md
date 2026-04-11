# Photo Curator

Local-only tool to find Isar-near photos and videos in `M:\Photos\*` (mounted
as `/mnt/m/Photos/...` from WSL), label them with the nearest landmark, and
hand-pick the best ones for the Isarwasser website.

The DB and thumbnails live under `imgsort/` and are gitignored. Only the
final accepted assets get copied into `web/public/jpg_raw/` and
`web/public/mp4_raw/`.

## One-time setup

Dependencies (installed once into the user site, no venv needed in WSL):

```bash
pip3 install --user pyproj shapely flask tqdm
```

`Pillow`, `requests`, `tqdm` are likely already present. `ffmpeg`/`ffprobe`
must be installed system-side (`apt install ffmpeg`).

The Overpass-derived `isar.geojson` and `pois.geojson` are committed to
this directory. Re-run `fetch_geo.py` only if OSM data needs refreshing.

## Workflow

```bash
# 1. Index a folder. Start small.
python3 tools/photo-curator/scan.py --root /mnt/m/Photos/2026 --max 50

# 2. Generate thumbnails for everything new.
python3 tools/photo-curator/thumbs.py

# 3. Review in the browser.
python3 tools/photo-curator/review.py
# → http://127.0.0.1:5757
# Keys: j/k navigate, a accept, r reject, h home-video, u undo, enter open, esc close

# 4. Copy accepted assets into the web raw folders.
python3 tools/photo-curator/promote.py --dry-run
python3 tools/photo-curator/promote.py
```

To process the full year:

```bash
python3 tools/photo-curator/scan.py --root /mnt/m/Photos/2026 --all
```

Then 2025, 2024, 2023.

## How filtering works

- Each file is parsed for GPS + creation time (PIL for JPG, ffprobe for MP4).
- Coordinates are projected to UTM 32N (metric).
- Distance to the **Isar mainstream** (no side arms) is computed via shapely.
- Only assets with `distance_isar_m ≤ 30` (default) are inserted into the DB.
- Auto-label uses `pois.geojson`: parks (point-in-polygon), bridges
  (within 300 m, with cardinal direction phrasing), suburbs as fallback.

## Status values

- `new` — fresh from scan, awaiting review
- `accepted` — gets copied into `jpg_raw`/`mp4_raw` on next promote
- `home-video` — same as accepted, plus marked as candidate for the
  Landing-Page video background
- `rejected` — kept in DB so re-scans don't re-surface them, but never copied

## Safety

- The review server binds to `127.0.0.1` only.
- `promote.py` never deletes the source.
- `imgsort/curator.db`, `imgsort/thumbs/`, and `web/public/jpg_raw/*.jpg`
  are gitignored — nothing private gets committed by accident.
