from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


@dataclass(frozen=True)
class StationMeta:
    station_id: int
    station_name: str
    river: str
    time_ref: str
    easting: Optional[int]
    northing: Optional[int]
    coord_ref: Optional[str]
    gauge_zero: Optional[str]
    raw_meta: Dict[str, str]


LFU_HEADER_ROW_RE = re.compile(r"^Datum;")


def _normalize_key(key: str) -> str:
    key = key.strip().strip(":").strip()
    key = key.replace("\ufeff", "")
    return key


def _parse_int_maybe(s: Optional[str]) -> Optional[int]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def find_table_header_line_idx(path: Path) -> int:
    # Return the 0-based index of the line containing "Datum;..."
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f):
            if LFU_HEADER_ROW_RE.match(line.strip()):
                return idx
    raise RuntimeError(f"Could not find table header row (Datum;...) in {path}")


def parse_station_meta_from_header(path: Path, header_line_idx: int) -> StationMeta:
    raw: Dict[str, str] = {}
    time_ref = ""
    station_name = ""
    station_id = 0
    river = ""
    easting: Optional[int] = None
    northing: Optional[int] = None
    coord_ref: Optional[str] = None
    gauge_zero: Optional[str] = None

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for _ in range(header_line_idx):
            line = f.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            # Most lines look like: Key:;Value
            parts = line.split(";")
            if len(parts) < 2:
                continue
            k = _normalize_key(parts[0])
            v = parts[1].strip().strip('"')
            if not k:
                continue
            raw[k] = v

            if k == "Zeitbezug":
                time_ref = v
            elif k == "Messstellen-Name":
                station_name = v
            elif k == "Messstellen-Nr.":
                station_id = int(v) if v else 0
            elif k == "Gewässer":
                river = v
            elif k == "Ostwert":
                # Example: Ostwert:;693161;Nordwert:;5335716;"ETRS89 / UTM Zone 32N"
                easting = _parse_int_maybe(v)
                if len(parts) >= 4 and _normalize_key(parts[2]) == "Nordwert:":
                    northing = _parse_int_maybe(parts[3].strip().strip('"'))
                if len(parts) >= 5:
                    coord_ref = parts[4].strip().strip('"') or None
            elif k == "Pegelnullpunktshöhe":
                gauge_zero = v or None

    if station_id == 0:
        raise RuntimeError(f"Could not parse station id from {path}")

    return StationMeta(
        station_id=station_id,
        station_name=station_name or str(station_id),
        river=river or "",
        time_ref=time_ref or "",
        easting=easting,
        northing=northing,
        coord_ref=coord_ref,
        gauge_zero=gauge_zero,
        raw_meta=raw,
    )


def detect_parameter_from_header(table_header: List[str]) -> Tuple[str, str]:
    # Returns (parameter_key, unit_label)
    # Examples:
    # ["Datum", "Wasserstand [cm]", "Prüfstatus"]
    # ["Datum", "Wassertemperatur [°C]", "Prüfstatus"]
    if len(table_header) < 3:
        raise RuntimeError(f"Unexpected table header: {table_header}")
    col = table_header[1]
    if "Wasserstand" in col:
        return ("water_level_cm", "cm")
    if "Wassertemperatur" in col:
        return ("water_temperature_c", "°C")
    return ("unknown", "")


def iter_csv_chunks(
    path: Path, header_line_idx: int, chunksize: int
) -> Iterator[pd.DataFrame]:
    # Read the LfU CSV table portion as chunks.
    # LfU format uses semicolon delimiter, decimal comma, and quotes around datetime.
    for chunk in pd.read_csv(
        path,
        sep=";",
        skiprows=header_line_idx,
        header=0,
        encoding="utf-8",
        decimal=",",
        dtype=str,
        chunksize=chunksize,
        na_values=["", " "],
        keep_default_na=True,
    ):
        yield chunk


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _parse_ts(series: pd.Series) -> pd.Series:
    # Input like: "2025-12-26 00:15"
    # Treat as naive local (MEZ/MESZ not encoded per-row in file; stored as given).
    return pd.to_datetime(series, format="%Y-%m-%d %H:%M", errors="coerce")


def _to_float(series: pd.Series) -> pd.Series:
    # The chunk is read as str; the decimal comma was already handled by read_csv
    # only if dtype wasn't forced. Here we still coerce robustly.
    # Replace commas just in case (older exports sometimes keep commas as text).
    return (
        series.astype(str)
        .str.replace(",", ".", regex=False)
        .replace({"nan": None, "None": None})
        .astype("float64")
    )


def _normalize_status(series: pd.Series) -> pd.Series:
    # Normalize common encodings: "Geprueft" vs "Geprüft", etc.
    return (
        series.astype(str)
        .str.strip()
        .str.replace("Geprüft", "Geprueft", regex=False)
        .replace({"nan": None, "None": None, "": None})
    )


def _write_raw_parquet(
    writer: pq.ParquetWriter,
    df: pd.DataFrame,
    station: StationMeta,
    parameter: str,
) -> None:
    table = pa.Table.from_pandas(
        df,
        schema=pa.schema(
            [
                ("station_id", pa.int32()),
                ("parameter", pa.string()),
                ("ts", pa.timestamp("ns")),
                ("value", pa.float64()),
                ("status", pa.string()),
            ]
        ),
        preserve_index=False,
    )
    writer.write_table(table)


def ingest_group(
    csv_files: List[Path],
    out_raw_parquet: Path,
    out_daily_parquet: Path,
    *,
    chunksize: int,
) -> StationMeta:
    if not csv_files:
        raise RuntimeError("No CSV files to ingest.")

    ensure_dir(out_raw_parquet.parent)
    ensure_dir(out_daily_parquet.parent)

    # We use the first file as canonical metadata for the group.
    first_header_idx = find_table_header_line_idx(csv_files[0])
    station = parse_station_meta_from_header(csv_files[0], first_header_idx)

    # Rolling daily aggregates keyed by date (YYYY-MM-DD).
    daily_sum: Dict[str, float] = defaultdict(float)
    daily_count: Dict[str, int] = defaultdict(int)
    daily_min: Dict[str, float] = {}
    daily_max: Dict[str, float] = {}
    daily_status_counts: Dict[str, Counter[str]] = defaultdict(Counter)

    writer: Optional[pq.ParquetWriter] = None
    schema = pa.schema(
        [
            ("station_id", pa.int32()),
            ("parameter", pa.string()),
            ("ts", pa.timestamp("ns")),
            ("value", pa.float64()),
            ("status", pa.string()),
        ]
    )

    try:
        writer = pq.ParquetWriter(out_raw_parquet, schema=schema, compression="zstd")

        for csv_path in csv_files:
            header_line_idx = find_table_header_line_idx(csv_path)
            # Determine parameter from the header row itself.
            with csv_path.open("r", encoding="utf-8", errors="replace") as f:
                for _ in range(header_line_idx):
                    f.readline()
                header_line = f.readline().strip()
            table_header = next(csv.reader([header_line], delimiter=";"))
            parameter, _unit = detect_parameter_from_header(table_header)

            for chunk in iter_csv_chunks(csv_path, header_line_idx, chunksize):
                # Expected columns: Datum, <value>, Prüfstatus
                cols = list(chunk.columns)
                if len(cols) < 3:
                    continue

                df = pd.DataFrame(
                    {
                        "station_id": station.station_id,
                        "parameter": parameter,
                        "ts": _parse_ts(chunk[cols[0]]),
                        "value": _to_float(chunk[cols[1]]),
                        "status": _normalize_status(chunk[cols[2]]),
                    }
                )
                df = df.dropna(subset=["ts"])

                # Write raw
                _write_raw_parquet(writer, df, station, parameter)

                # Update daily
                # Exclude NaN values from aggregates.
                df2 = df.dropna(subset=["value"]).copy()
                if df2.empty:
                    # Still track status distribution per day where possible
                    df_status = df.dropna(subset=["status"]).copy()
                    if not df_status.empty:
                        df_status["date"] = df_status["ts"].dt.strftime("%Y-%m-%d")
                        for date, grp in df_status.groupby("date"):
                            daily_status_counts[date].update(grp["status"].dropna().tolist())
                    continue

                df2["date"] = df2["ts"].dt.strftime("%Y-%m-%d")
                for date, grp in df2.groupby("date"):
                    vals = grp["value"].astype("float64")
                    daily_sum[date] += float(vals.sum())
                    daily_count[date] += int(vals.count())
                    vmin = float(vals.min())
                    vmax = float(vals.max())
                    if date not in daily_min:
                        daily_min[date] = vmin
                        daily_max[date] = vmax
                    else:
                        daily_min[date] = min(daily_min[date], vmin)
                        daily_max[date] = max(daily_max[date], vmax)
                    daily_status_counts[date].update(grp["status"].dropna().tolist())
    finally:
        if writer is not None:
            writer.close()

    # Build daily table
    dates = sorted(daily_count.keys())
    daily_rows: List[Dict[str, Any]] = []

    # Use parameter name from first file header (assumes consistent group).
    with csv_files[0].open("r", encoding="utf-8", errors="replace") as f:
        for _ in range(find_table_header_line_idx(csv_files[0])):
            f.readline()
        header_line = f.readline().strip()
    table_header = next(csv.reader([header_line], delimiter=";"))
    parameter, _unit = detect_parameter_from_header(table_header)

    for d in dates:
        cnt = daily_count[d]
        if cnt <= 0:
            continue
        stat_counter = daily_status_counts.get(d) or Counter()
        mode_status = stat_counter.most_common(1)[0][0] if stat_counter else None
        daily_rows.append(
            {
                "station_id": station.station_id,
                "parameter": parameter,
                "date": datetime.strptime(d, "%Y-%m-%d").date(),
                "count": cnt,
                "mean": float(daily_sum[d] / cnt),
                "min": float(daily_min[d]),
                "max": float(daily_max[d]),
                "status_mode": mode_status,
            }
        )

    daily_df = pd.DataFrame(daily_rows)
    daily_table = pa.Table.from_pandas(
        daily_df,
        schema=pa.schema(
            [
                ("station_id", pa.int32()),
                ("parameter", pa.string()),
                ("date", pa.date32()),
                ("count", pa.int32()),
                ("mean", pa.float64()),
                ("min", pa.float64()),
                ("max", pa.float64()),
                ("status_mode", pa.string()),
            ]
        ),
        preserve_index=False,
    )
    pq.write_table(daily_table, out_daily_parquet, compression="zstd")
    return station


def copy_tree(src: Path, dst: Path) -> None:
    ensure_dir(dst)
    for root, _dirs, files in os.walk(src):
        root_p = Path(root)
        rel = root_p.relative_to(src)
        out_dir = dst / rel
        ensure_dir(out_dir)
        for fn in files:
            shutil.copy2(root_p / fn, out_dir / fn)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data-root",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "data"),
        help="Repo data root (default: ../data)",
    )
    ap.add_argument(
        "--out-root",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "data" / "parquet"),
        help="Output parquet root (default: ../data/parquet)",
    )
    ap.add_argument(
        "--station-id",
        type=str,
        default="16005701",
        help="Station ID to ingest (default: 16005701)",
    )
    ap.add_argument(
        "--chunksize",
        type=int,
        default=200_000,
        help="CSV rows per chunk (default: 200000)",
    )
    ap.add_argument(
        "--sync-to-web-public",
        type=str,
        default="",
        help="If set, copy parquet outputs to this directory (e.g. web/public/data/parquet).",
    )
    args = ap.parse_args()

    data_root = Path(args.data_root)
    out_root = Path(args.out_root)
    station_id = args.station_id

    level_dir = data_root / "fluesse-wasserstand"
    temp_dir = data_root / "fluesse-wassertemperatur"
    level_files = sorted(level_dir.glob(f"{station_id}_*.csv"))
    temp_files = sorted(temp_dir.glob(f"{station_id}_*.csv"))
    if not level_files and not temp_files:
        raise SystemExit(f"No station files found for {station_id} under {data_root}")

    raw_dir = out_root / "raw"
    daily_dir = out_root / "daily"
    ensure_dir(raw_dir)
    ensure_dir(daily_dir)

    station_meta: Optional[StationMeta] = None
    meta_json: Dict[str, Any] = {"generated_at": datetime.utcnow().isoformat() + "Z"}

    if level_files:
        station_meta = ingest_group(
            level_files,
            raw_dir / f"station_{station_id}_water_level_cm.parquet",
            daily_dir / f"station_{station_id}_water_level_cm_daily.parquet",
            chunksize=args.chunksize,
        )
        meta_json["water_level_files"] = [str(p) for p in level_files]

    if temp_files:
        station_meta2 = ingest_group(
            temp_files,
            raw_dir / f"station_{station_id}_water_temperature_c.parquet",
            daily_dir / f"station_{station_id}_water_temperature_c_daily.parquet",
            chunksize=args.chunksize,
        )
        meta_json["water_temperature_files"] = [str(p) for p in temp_files]
        station_meta = station_meta or station_meta2

    if station_meta is not None:
        meta_json["station"] = {
            "station_id": station_meta.station_id,
            "station_name": station_meta.station_name,
            "river": station_meta.river,
            "time_ref": station_meta.time_ref,
            "easting": station_meta.easting,
            "northing": station_meta.northing,
            "coord_ref": station_meta.coord_ref,
            "gauge_zero": station_meta.gauge_zero,
            "raw_meta": station_meta.raw_meta,
        }

    ensure_dir(out_root)
    (out_root / "station_meta.json").write_text(
        json.dumps(meta_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.sync_to_web_public:
        dst = Path(args.sync_to_web_public)
        copy_tree(out_root, dst)
        print(f"Synced parquet outputs to: {dst}")

    print(f"Done. Parquet written to: {out_root}")


if __name__ == "__main__":
    main()


