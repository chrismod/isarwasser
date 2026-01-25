# Isarwasser München

Interactive visualization of **water level** and **water temperature** data for the **Isar river in Munich** (Pegel 16005701) from 1973 to present.

🌐 **Live:** [isar.monoroc.de](https://isar.monoroc.de)

## Features

- 📊 **Interactive exploration** of 50+ years of historical data
- 🌡️ **Real-time data** scraped every 3 hours from LfU Bayern
- 📈 **Records analysis** - discover historical extremes
- 🎥 **Beautiful UI** with background videos of the Isar
- ⚡ **Fast client-side queries** using DuckDB-WASM + Parquet
- 🔒 **HTTPS** with automatic SSL certificates

## Tech Stack

- **Frontend:** React + TypeScript + Vite + D3.js
- **Data:** DuckDB-WASM querying Parquet files in-browser
- **Backend:** Python scraper + cron for live data
- **Deployment:** Docker + Nginx Proxy Manager on VPS
- **Data Source:** Bayerisches Landesamt für Umwelt (LfU Bayern)

## Repository Structure

- [`data/`](data/) - Raw CSV exports from gkd.bayern.de
- [`pipeline/`](pipeline/) - Data ingestion and scraping scripts
- [`web/`](web/) - React frontend application
- [`docs/`](docs/) - Methodology and documentation

## Local Development

### 1. Generate Parquet files from CSV data

```bash
node pipeline/ingest_lfu_csv_to_parquet_daily_only.mjs \
  --station-id 16005701 \
  --start-date 1975-01-01 \
  --sync-to-web-public web/public/data/parquet
```

### 2. Start the development server

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

## Production Deployment

See [`deploy.sh`](deploy.sh) and [`setup-data.sh`](setup-data.sh) for deployment scripts.

The application is designed to run in Docker containers with:
- Nginx for serving the static frontend
- Python cron job for periodic data scraping
- Volume mounts for live data persistence

## Data Sources

- **Historical data:** [Gewässerkundlicher Dienst Bayern](https://www.gkd.bayern.de/)
- **Live data:** Scraped from [HND Bayern](https://www.hnd.bayern.de/pegel/isar/muenchen-16005701) every 3 hours
- **Station:** Pegel 16005701 München/Isar

## Methodology

For details on data processing, aggregation, and scientific approach, see [`docs/methodology.md`](docs/methodology.md).

## License

Data: © Bayerisches Landesamt für Umwelt

Code: MIT License
