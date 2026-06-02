"""
Snapshot the curator DB before destructive operations.

Every scan/thumbs/promote/review run calls snapshot_db() at startup. We keep
the most recent KEEP backups under imgsort/backups/ and rotate older ones
away. Restoring is a manual `cp` from that directory.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = REPO_ROOT / "imgsort"
DB_PATH = STATE_DIR / "curator.db"
BACKUP_DIR = STATE_DIR / "backups"
KEEP = 30

BERLIN_TZ = ZoneInfo("Europe/Berlin")


def snapshot_db(reason: str) -> Path | None:
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    src_sig = (DB_PATH.stat().st_size, DB_PATH.stat().st_mtime_ns)
    latest = _latest_backup()
    if latest is not None:
        prev_sig = (latest.stat().st_size, latest.stat().st_mtime_ns)
        if src_sig == prev_sig:
            return None

    ts = datetime.now(BERLIN_TZ).strftime("%Y-%m-%d_%H%M%S")
    dest = BACKUP_DIR / f"curator.{ts}.{reason}.db"
    shutil.copy2(DB_PATH, dest)
    _rotate()
    return dest


def _latest_backup() -> Path | None:
    backups = sorted(BACKUP_DIR.glob("curator.*.db"))
    return backups[-1] if backups else None


def _rotate() -> None:
    backups = sorted(BACKUP_DIR.glob("curator.*.db"))
    excess = len(backups) - KEEP
    if excess <= 0:
        return
    for b in backups[:excess]:
        b.unlink(missing_ok=True)
