# Methodology (v1)

This project aims to be *experience-first* but scientifically transparent.

## Data source

CSV exports from **Bayerisches Landesamt für Umwelt** (`gkd.bayern.de`), station **16005701 (München)**.

The CSVs include:
- A metadata header (station name/id, time reference, coordinates, etc.).
- A table with columns like:
  - `Datum` (timestamp, 15-minute steps)
  - `Wasserstand [cm]` or `Wassertemperatur [°C]`
  - `Prüfstatus` (e.g. `Geprueft`, `Rohdaten`)

## Normalization (ingestion)

We ingest the CSVs into Parquet:

- **Raw series** (15-minute rows):
  - `station_id`, `parameter`, `ts`, `value`, `status`
- **Daily aggregates**:
  - `date`, `mean`, `min`, `max`, `count`, `status_mode`

Null/missing values are excluded from aggregates.

## “How normal is now”

Seasonality-aware context is computed from the **daily mean** series:

- Take the current day-of-year (DuckDB `current_date`).
- Build a comparison set from historical days within a **±7-day window** around the same day-of-year.
- Compute percentiles: p05/p25/p50/p75/p95.

This yields a simple but robust “normal band” for the current season.

## Records

Records are computed from the **raw 15-minute** series:

- Min record: smallest non-null `value`
- Max record: largest non-null `value`

We also display `Prüfstatus` to distinguish raw vs checked data.

## Known limitations (v1)

- Timezone: CSV includes `Zeitbezug` (MEZ/MESZ) but timestamps are treated as provided (no DST normalization yet).
- Day-of-year percentile window: currently based on `current_date` rather than “latest available data date”; we can improve this.
- Temperature series includes long periods of missing values in early years; percentiles should eventually account for availability density.


