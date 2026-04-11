#!/usr/bin/env python3
"""
Photo Curator — Phase 2: thumbnails.

Generates 320 px JPEG thumbnails for every asset in the curator DB that
doesn't yet have one. Photos via PIL, videos via ffmpeg (single frame at 1s).

Idempotent — re-running only fills gaps.

Usage:
    python thumbs.py
    python thumbs.py --force      # rebuild everything
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageOps
from tqdm import tqdm

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = REPO_ROOT / "imgsort"
THUMBS_DIR = STATE_DIR / "thumbs"
DB_PATH = STATE_DIR / "curator.db"

THUMB_MAX = 320
JPEG_QUALITY = 78


def thumb_for_photo(src: Path, dst: Path) -> bool:
    try:
        with Image.open(src) as img:
            # Apply EXIF Orientation tag (rotate 90/180/270 / flip if needed)
            # so the saved thumbnail is in display-correct orientation.
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
            img.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return True
    except Exception as e:
        print(f"  ERROR photo {src.name}: {e}", file=sys.stderr)
        return False


def thumb_for_video(src: Path, dst: Path) -> bool:
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel", "error",
                "-ss", "00:00:01",
                "-i", str(src),
                "-frames:v", "1",
                "-vf", f"scale={THUMB_MAX}:-2",
                "-q:v", "4",
                str(dst),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            # Some clips are <1s; retry from frame 0.
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel", "error",
                    "-i", str(src),
                    "-frames:v", "1",
                    "-vf", f"scale={THUMB_MAX}:-2",
                    "-q:v", "4",
                    str(dst),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        return proc.returncode == 0 and dst.exists()
    except Exception as e:
        print(f"  ERROR video {src.name}: {e}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found. Run scan.py first.", file=sys.stderr)
        return 2

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if args.force:
        rows = cur.execute(
            "SELECT id, source_path, kind FROM assets ORDER BY id"
        ).fetchall()
    else:
        rows = cur.execute(
            "SELECT id, source_path, kind FROM assets WHERE thumb_path IS NULL ORDER BY id"
        ).fetchall()

    print(f"Generating thumbnails for {len(rows)} assets…")

    ok = fail = 0
    for asset_id, src_path, kind in tqdm(rows, desc="thumbs"):
        src = Path(src_path)
        if not src.exists():
            fail += 1
            continue
        dst = THUMBS_DIR / f"{asset_id}.jpg"
        success = thumb_for_photo(src, dst) if kind == "photo" else thumb_for_video(src, dst)
        if success:
            cur.execute(
                "UPDATE assets SET thumb_path = ? WHERE id = ?",
                (f"{asset_id}.jpg", asset_id),
            )
            conn.commit()
            ok += 1
        else:
            fail += 1

    conn.close()
    print(f"\nDone. ok={ok} fail={fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
