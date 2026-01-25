# Context (handoff)

This file captures **where we are**, **what we built**, and **why we’re moving to WSL2**.

## Product goal (v1)

Build an “experience-first” site for München / Isar station **16005701**:

- Explore water level + temperature over decades (1975 → today).
- Show historical highs/lows (records).
- Show “how normal is now” relative to historical context (seasonal percentiles).

## Architecture decisions (v1)

- **Local dev server** for now.
- Analytics happens **in the browser** using **DuckDB-WASM**.
- Data is served as static files (Parquet under `web/public/...`).
- CSV ingestion is done offline in `pipeline/` and produces Parquet + daily aggregates.

## What exists in code right now

### Frontend (`web/`)

- Vite + React + TypeScript + D3.
- Routing skeleton:
  - `/` Story/Landing
  - `/explore` placeholder (will become D3 explore)
  - `/records` shows min/max queries once Parquet is available
- DuckDB-WASM client + basic queries:
  - `web/src/lib/duckdbClient.ts`
  - `web/src/lib/isarQueries.ts`

### Ingestion (`pipeline/`)

Two approaches exist:

- **Node (recommended for Windows/WSL move)**: `pipeline/ingest_lfu_csv_to_parquet.mjs`
  - Parses the LfU CSV format (metadata header + semicolon table rows).
  - Writes:
    - raw Parquet (15-min) and
    - daily Parquet (mean/min/max/count + status mode)
  - Can sync output into `web/public/data/parquet` for frontend access.

- Python prototype: `pipeline/ingest_lfu_csv_to_parquet.py`
  - Uses `pandas` + `pyarrow`
  - On **Windows + Python 3.14**, `pyarrow` tried to build from source and failed.

### Generated outputs (may be partial)

- `data/parquet/` exists and is `.gitignore`’d.
- During the last run, at least `data/parquet/raw/station_16005701_water_level_cm.parquet` was created; the rest may be incomplete.

## Why WSL2

We hit Windows-specific friction:

- **Python 3.14 + pyarrow**: no convenient wheels → build failures.
- Node ingestion of multi-million-row CSVs can hit **heap OOM**; we mitigated with:
  - smaller parquet row groups
  - `node --max-old-space-size=8192 ...`

WSL2 typically makes “Linux wheels” and toolchains smoother.

## Next steps after moving to WSL2

See:
- [`docs/wsl2-migration.md`](wsl2-migration.md)
- [`docs/methodology.md`](methodology.md)


