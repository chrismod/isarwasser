import { DATASETS } from './datasets'
import { getDuckDb, registerParquetFile } from './duckdbClient'

export type ParameterKey = 'water_level_cm' | 'water_temperature_c'
export type SeriesPoint = { x: string; y: number }

const REGISTERED = new Set<string>()

async function ensureRegistered() {
  const toRegister = [
    DATASETS.level_raw,
    DATASETS.level_daily,
    DATASETS.temp_raw,
    DATASETS.temp_daily,
  ]
  for (const ds of toRegister) {
    if (REGISTERED.has(ds.name)) continue
    await registerParquetFile(ds.name, ds.url)
    REGISTERED.add(ds.name)
  }
}

function dailyName(parameter: ParameterKey) {
  return parameter === 'water_level_cm'
    ? DATASETS.level_daily.name
    : DATASETS.temp_daily.name
}

function rawName(parameter: ParameterKey) {
  return parameter === 'water_level_cm'
    ? DATASETS.level_raw.name
    : DATASETS.temp_raw.name
}

export async function getDailyRange(
  parameter: ParameterKey,
  startDate: string,
  endDate: string
): Promise<SeriesPoint[]> {
  await ensureRegistered()
  const { conn } = await getDuckDb()
  const file = dailyName(parameter)

  const result = await conn.query(`
    SELECT date::VARCHAR AS x, mean AS y
    FROM parquet_scan('${file}')
    WHERE date >= '${startDate}' AND date <= '${endDate}'
      AND mean IS NOT NULL
    ORDER BY date ASC
  `)
  return result.toArray().map((r) => ({ x: String(r.x), y: Number(r.y) }))
}

export async function getHourlyRange(
  parameter: ParameterKey,
  startDate: string,
  endDate: string
): Promise<SeriesPoint[]> {
  await ensureRegistered()
  const { conn } = await getDuckDb()
  const file = rawName(parameter)

  const result = await conn.query(`
    SELECT 
      strftime(ts, '%Y-%m-%d %H:00:00')::VARCHAR AS x,
      AVG(value) AS y
    FROM parquet_scan('${file}')
    WHERE ts >= '${startDate}' AND ts <= '${endDate}'
      AND value IS NOT NULL
    GROUP BY strftime(ts, '%Y-%m-%d %H:00:00')
    ORDER BY x ASC
  `)
  return result.toArray().map((r) => ({ x: String(r.x), y: Number(r.y) }))
}

export async function getRawRange(
  parameter: ParameterKey,
  startDate: string,
  endDate: string
): Promise<SeriesPoint[]> {
  await ensureRegistered()
  const { conn } = await getDuckDb()
  const file = rawName(parameter)

  const result = await conn.query(`
    SELECT ts::VARCHAR AS x, value AS y
    FROM parquet_scan('${file}')
    WHERE ts >= '${startDate}' AND ts <= '${endDate}'
      AND value IS NOT NULL
    ORDER BY ts ASC
  `)
  return result.toArray().map((r) => ({ x: String(r.x), y: Number(r.y) }))
}

export async function getLatestDaily(parameter: ParameterKey) {
  await ensureRegistered()
  const { conn } = await getDuckDb()
  const file = dailyName(parameter)
  const result = await conn.query(`
    SELECT date, mean, min, max, count, status_mode
    FROM parquet_scan('${file}')
    WHERE mean IS NOT NULL
    ORDER BY date DESC
    LIMIT 1
  `)
  const row = result.toArray()[0] as any
  return row
    ? {
        date: String(row.date),
        mean: Number(row.mean),
        min: row.min == null ? null : Number(row.min),
        max: row.max == null ? null : Number(row.max),
        count: Number(row.count),
        statusMode: row.status_mode == null ? null : String(row.status_mode),
      }
    : null
}

export async function getRecords(parameter: ParameterKey) {
  await ensureRegistered()
  const { conn } = await getDuckDb()
  const file = rawName(parameter)

  // Use raw 15-minute data for true extremes
  const minRow = await conn.query(`
    SELECT ts, value, status
    FROM parquet_scan('${file}')
    WHERE value IS NOT NULL
    ORDER BY value ASC
    LIMIT 1
  `)
  const maxRow = await conn.query(`
    SELECT ts, value, status
    FROM parquet_scan('${file}')
    WHERE value IS NOT NULL
    ORDER BY value DESC
    LIMIT 1
  `)
  const min = minRow.toArray()[0] as any
  const max = maxRow.toArray()[0] as any
  return {
    min: min
      ? { ts: String(min.ts), value: Number(min.value), status: String(min.status ?? '') }
      : null,
    max: max
      ? { ts: String(max.ts), value: Number(max.value), status: String(max.status ?? '') }
      : null,
  }
}

export async function getNowVsNormalDayOfYear(parameter: ParameterKey) {
  await ensureRegistered()
  const { conn } = await getDuckDb()
  const file = dailyName(parameter)

  // Percentiles are seasonality-aware: same day-of-year window (±7 days).
  const q = await conn.query(`
    WITH daily AS (
      SELECT CAST(date AS DATE) AS d, mean
      FROM parquet_scan('${file}')
      WHERE mean IS NOT NULL
    ),
    target AS (
      SELECT strftime(current_date, '%j')::INT AS doy
    ),
    subset AS (
      SELECT mean
      FROM daily, target
      WHERE abs(strftime(d, '%j')::INT - target.doy) <= 7
    )
    SELECT
      quantile_cont(mean, 0.05) AS p05,
      quantile_cont(mean, 0.25) AS p25,
      quantile_cont(mean, 0.50) AS p50,
      quantile_cont(mean, 0.75) AS p75,
      quantile_cont(mean, 0.95) AS p95
    FROM subset
  `)
  const row = q.toArray()[0] as any
  return row
    ? {
        p05: Number(row.p05),
        p25: Number(row.p25),
        p50: Number(row.p50),
        p75: Number(row.p75),
        p95: Number(row.p95),
      }
    : null
}


