#!/usr/bin/env python3
"""
Photo Curator — Phase 4: promote accepted assets.

Copies assets flagged 'accepted' or 'home-video' from their source location
into the web raw folders:
    photos → web/public/jpg_raw/
    videos → web/public/mp4_raw/

Sets promoted_at on each row so re-runs are idempotent. Filename collisions
get a numeric suffix.

Usage:
    python promote.py                # copy everything pending
    python promote.py --dry-run      # show what would happen
    python promote.py --status accepted    # only accepted, skip home-video
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = REPO_ROOT / "imgsort"
DB_PATH = STATE_DIR / "curator.db"

VIDEOS_DIR = REPO_ROOT / "web" / "public" / "videos"
JPG_RAW = REPO_ROOT / "web" / "public" / "jpg_raw"
MP4_RAW = REPO_ROOT / "web" / "public" / "mp4_raw"
FLOOD_SET_JSON = VIDEOS_DIR / "flood-set.json"

BERLIN_TZ = ZoneInfo("Europe/Berlin")


def unique_dest(dest_dir: Path, filename: str) -> Path:
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    i = 1
    while True:
        candidate = dest_dir / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--status",
        choices=["accepted", "home-video", "both"],
        default="both",
        help="Which status to promote (default: both)",
    )
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found.", file=sys.stderr)
        return 2

    JPG_RAW.mkdir(parents=True, exist_ok=True)
    MP4_RAW.mkdir(parents=True, exist_ok=True)

    if args.status == "both":
        statuses = ("accepted", "home-video")
    else:
        statuses = (args.status,)

    placeholders = ",".join("?" * len(statuses))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""SELECT * FROM assets
            WHERE status IN ({placeholders})
              AND promoted_at IS NULL
            ORDER BY taken_at""",
        statuses,
    ).fetchall()

    print(f"{len(rows)} asset(s) pending promotion ({', '.join(statuses)}).")
    if not rows:
        return 0

    now_iso = datetime.now(BERLIN_TZ).isoformat()
    promoted = 0
    skipped = 0

    for r in rows:
        src = Path(r["source_path"])
        if not src.exists():
            print(f"  SKIP missing: {src}")
            skipped += 1
            continue
        dest_dir = MP4_RAW if r["kind"] == "video" else JPG_RAW
        dest = unique_dest(dest_dir, src.name)
        rel = dest.relative_to(REPO_ROOT)
        flood_marker = " [FLOOD]" if r["is_flood"] else ""
        action = "WOULD COPY" if args.dry_run else "COPY"
        print(f"  {action}: {src.name}  →  {rel}  ({r['status']}, {r['location_label']}){flood_marker}")
        if not args.dry_run:
            shutil.copy2(src, dest)
            conn.execute(
                "UPDATE assets SET promoted_at = ?, promoted_path = ? WHERE id = ?",
                (now_iso, str(dest.relative_to(REPO_ROOT)), r["id"]),
            )
            conn.commit()
            promoted += 1

    if not args.dry_run:
        write_flood_set(conn)

    conn.close()
    if args.dry_run:
        print(f"\n(dry-run) {len(rows)} would be promoted, {skipped} skipped.")
    else:
        print(f"\nPromoted {promoted}, skipped {skipped}.")
    return 0


def write_flood_set(conn: sqlite3.Connection) -> None:
    """
    Rebuild web/public/videos/flood-set.json from scratch.

    Lists every video that is currently both promoted (file exists in
    mp4_raw) AND flagged is_flood=1. The frontend uses this list to
    *exclude* those clips when the live water level is below the flood
    threshold — fail-safe: empty file or missing file means "no clips
    are flood-restricted", but the frontend treats every file in this
    set as forbidden during normal water levels.
    """
    rows = conn.execute(
        """SELECT promoted_path, is_flood, location_label, taken_at
           FROM assets
           WHERE kind = 'video'
             AND is_flood = 1
             AND promoted_path IS NOT NULL"""
    ).fetchall()

    entries = []
    for r in rows:
        promoted = REPO_ROOT / r["promoted_path"]
        if not promoted.exists():
            continue
        entries.append({
            "filename": Path(r["promoted_path"]).name,
            "label": r["location_label"],
            "taken_at": r["taken_at"],
        })

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(BERLIN_TZ).isoformat(),
        "flood_videos": entries,
    }
    FLOOD_SET_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nWrote {FLOOD_SET_JSON.relative_to(REPO_ROOT)} ({len(entries)} flood clip(s)).")


if __name__ == "__main__":
    sys.exit(main())
