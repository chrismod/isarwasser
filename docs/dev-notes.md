# Dev notes (current)

## PowerShell cwd confusion

Some commands failed because the working directory was not what we assumed (e.g. running `cd web; ...` while already inside `web/` or `pipeline/`).

Under WSL we’ll standardize on running from repo root and using explicit paths.

## Python ingestion (Windows)

`pipeline/ingest_lfu_csv_to_parquet.py` depends on `pyarrow`. With **Python 3.14 on Windows**, pip attempted to build `pyarrow` from source and failed. This is why a Node-based ingestion exists.

## Node ingestion memory

The historical CSVs are huge (millions of lines). Node can hit V8 heap limits while writing Parquet.

Mitigations already applied:
- smaller Parquet row groups (see `rowGroupSize` in `pipeline/ingest_lfu_csv_to_parquet.mjs`)
- run with larger heap:

```bash
node --max-old-space-size=8192 pipeline/ingest_lfu_csv_to_parquet.mjs ...
```

If it still OOMs, we should implement a flag to skip raw Parquet and only produce daily aggregates for the browser (much smaller).

## Frontend querying

Frontend uses DuckDB-WASM and reads Parquet over HTTP from:

- `web/public/data/parquet/raw/*.parquet`
- `web/public/data/parquet/daily/*.parquet`

Queries currently implemented:
- latest daily value
- seasonal percentiles (±7 days day-of-year window)
- all-time min/max records from raw series


