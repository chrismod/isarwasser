# Pipeline

This folder contains the ingestion scripts that normalize the Bayern LfU CSV exports in [`../data/`](../data/) into Parquet for fast in-browser querying (DuckDB-WASM).

## Install (recommended: Node)

```bash
cd pipeline
npm install
```

## Ingest station 16005701 (München)

Writes outputs to `data/parquet/` and also syncs them into the frontend's static directory so Vite can serve them.

```bash
node pipeline/ingest_lfu_csv_to_parquet.mjs --station-id 16005701 --sync-to-web-public web/public/data/parquet
```

## Outputs

- `data/parquet/raw/station_16005701_water_level_cm.parquet`
- `data/parquet/raw/station_16005701_water_temperature_c.parquet`
- `data/parquet/daily/station_16005701_water_level_cm_daily.parquet`
- `data/parquet/daily/station_16005701_water_temperature_c_daily.parquet`
- `data/parquet/station_meta.json`

## Python note

There is also a Python prototype script (`pipeline/ingest_lfu_csv_to_parquet.py`) but it depends on `pyarrow`, which may not have wheels for very new Python versions on Windows. Prefer the Node script above.


