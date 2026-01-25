# WSL2 migration notes

## What to move

Copy the whole repo folder into your WSL filesystem (recommended), or keep it on the Windows filesystem but work from WSL (slower for large IO).

## Prereqs (WSL)

- Node.js (LTS recommended)
- npm

Optional (only if you want the Python ingestion path):
- Python 3.11+ and `pip`

## First run (WSL)

### 1) Install pipeline deps

```bash
cd pipeline
npm install
```

### 2) Generate Parquet and sync to frontend static files

From repo root:

```bash
node --max-old-space-size=8192 pipeline/ingest_lfu_csv_to_parquet.mjs \
  --station-id 16005701 \
  --start-date 1975-01-01 \
  --sync-to-web-public web/public/data/parquet
```

Notes:
- The raw historical CSVs are huge; this can take time.
- Output folders are ignored by git (`data/parquet/`, `web/public/data/parquet/`).

### 3) Run the frontend

```bash
cd web
npm install
npm run dev
```

## If ingestion still OOMs

Try:

- Increase heap more (if you have RAM):

```bash
node --max-old-space-size=16384 pipeline/ingest_lfu_csv_to_parquet.mjs ...
```

- Temporarily disable raw Parquet writing and only write daily aggregates (we can implement a flag next session).


