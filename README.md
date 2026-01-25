# Isarwasser

Interactive exploration of **water level** and **water temperature** for **Isar (München, Pegel 16005701)**.

## What’s in this repo

- [`data/`](data/): raw CSV exports from `gkd.bayern.de` (Bayerisches Landesamt für Umwelt).
- [`pipeline/`](pipeline/): ingestion scripts to normalize CSV → **Parquet** (raw + daily aggregates).
- [`web/`](web/): Vite + React + TypeScript + D3 frontend; queries Parquet via **DuckDB-WASM** in the browser.
- [`docs/`](docs/): methodology + WSL migration notes + current status.

## Quick start (WSL2 recommended)

1) Ingest CSV → Parquet (and sync into the frontend’s static directory):

```bash
node pipeline/ingest_lfu_csv_to_parquet.mjs \
  --station-id 16005701 \
  --start-date 1975-01-01 \
  --sync-to-web-public web/public/data/parquet
```

2) Start the frontend:

```bash
cd web
npm install
npm run dev
```

## Scientific transparency (v1)

See [`docs/methodology.md`](docs/methodology.md).


