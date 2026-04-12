import { DATASETS } from './datasets'
import { getDuckDb, registerParquetFile } from './duckdbClient'

export type ParameterKey = 'water_level_cm' | 'water_temperature_c'
export type SeriesPoint = { x: string; y: number }

// --------------- JSONL live-data supplement --------------------------------
// The parquets are a snapshot. Live data beyond the parquet range lives in
// per-day JSONL files under /data/current/. These functions fetch them and
// return SeriesPoints so the explore chart can show recent data seamlessly.

function jsonlDataType(param: ParameterKey): string {
  return param === 'water_level_cm' ? 'water_level' : 'water_temperature'
}

function jsonlValueKey(param: ParameterKey): string {
  return param === 'water_level_cm' ? 'value_cm' : 'value_celsius'
}

async function fetchJsonlDay(
  param: ParameterKey,
  dateStr: string,
): Promise<SeriesPoint[]> {
  const dt = jsonlDataType(param)
  const vk = jsonlValueKey(param)
  try {
    const r = await fetch(`/data/current/${dt}_${dateStr}.jsonl`)
    if (!r.ok) return []
    const text = await r.text()
    const points: SeriesPoint[] = []
    for (const line of text.trim().split('\n')) {
      if (!line.trim()) continue
      try {
        const entry = JSON.parse(line)
        const v = entry[vk]
        if (v == null) continue
        points.push({ x: entry.timestamp, y: Number(v) })
      } catch { /* skip malformed lines */ }
    }
    return points
  } catch {
    return []
  }
}

function daysBetween(startStr: string, endStr: string): string[] {
  const days: string[] = []
  const d = new Date(startStr + 'T00:00:00')
  const end = new Date(endStr + 'T00:00:00')
  while (d <= end) {
    days.push(d.toISOString().slice(0, 10))
    d.setDate(d.getDate() + 1)
  }
  return days
}

export async function getJsonlRange(
  param: ParameterKey,
  startDate: string,
  endDate: string,
): Promise<SeriesPoint[]> {
  const days = daysBetween(startDate, endDate)
  const batches = await Promise.all(days.map((d) => fetchJsonlDay(param, d)))
  return batches.flat().sort((a, b) => (a.x < b.x ? -1 : a.x > b.x ? 1 : 0))
}

async function getParquetMaxDate(param: ParameterKey): Promise<string> {
  await ensureRegistered()
  const { conn } = await getDuckDb()
  const file = dailyName(param)
  const r = await conn.query(
    `SELECT max(date)::VARCHAR AS mx FROM parquet_scan('${file}')`,
  )
  const row = r.toArray()[0] as any
  return row?.mx ? String(row.mx).slice(0, 10) : '1970-01-01'
}

export async function getExploreRange(
  param: ParameterKey,
  startDate: string,
  endDate: string,
): Promise<SeriesPoint[]> {
  const parquetMax = await getParquetMaxDate(param)

  // Parquet covers the historical bulk.
  let parquetPoints: SeriesPoint[] = []
  if (startDate <= parquetMax) {
    parquetPoints = await getDailyRange(
      param,
      startDate,
      endDate < parquetMax ? endDate : parquetMax,
    )
  }

  // JSONL fills the gap from parquetMax+1 to endDate.
  let livePoints: SeriesPoint[] = []
  if (endDate > parquetMax) {
    const liveStart =
      startDate > parquetMax ? startDate : nextDay(parquetMax)
    livePoints = await getJsonlRange(param, liveStart, endDate)
    // Aggregate JSONL points to daily means to match the parquet granularity.
    livePoints = aggregateDaily(livePoints)
  }

  return [...parquetPoints, ...livePoints]
}

function nextDay(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

function aggregateDaily(points: SeriesPoint[]): SeriesPoint[] {
  const buckets = new Map<string, number[]>()
  for (const p of points) {
    const day = p.x.slice(0, 10)
    if (!buckets.has(day)) buckets.set(day, [])
    buckets.get(day)!.push(p.y)
  }
  return Array.from(buckets.entries())
    .map(([day, vals]) => ({
      x: day,
      y: Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10,
    }))
    .sort((a, b) => (a.x < b.x ? -1 : 1))
}

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

export type DayOfYearHistory = {
  recentYears: { year: number; mean: number; min: number; max: number }[]
  allTimeMin: { value: number; year: number }
  allTimeMax: { value: number; year: number }
}

export async function getDayOfYearHistory(
  parameter: ParameterKey,
): Promise<DayOfYearHistory | null> {
  await ensureRegistered()
  const { conn } = await getDuckDb()
  const file = dailyName(parameter)

  const currentYear = new Date().getFullYear()
  const doy = Math.floor(
    (Date.now() - new Date(currentYear, 0, 0).getTime()) / 86400000,
  )

  const result = await conn.query(`
    WITH daily AS (
      SELECT
        CAST(date AS DATE) AS d,
        extract(year FROM CAST(date AS DATE)) AS yr,
        mean, min, max
      FROM parquet_scan('${file}')
      WHERE mean IS NOT NULL
        AND abs(extract(doy FROM CAST(date AS DATE)) - ${doy}) <= 1
    )
    SELECT yr AS year,
           round(avg(mean), 1) AS mean,
           round(min(min), 1) AS min,
           round(max(max), 1) AS max
    FROM daily
    GROUP BY yr
    ORDER BY yr DESC
  `)

  const rows = result.toArray().map((r: any) => ({
    year: Number(r.year),
    mean: Number(r.mean),
    min: Number(r.min),
    max: Number(r.max),
  }))

  if (rows.length === 0) return null

  const recentYears = rows.filter(
    (r) => r.year >= currentYear - 2 && r.year < currentYear,
  )

  let allTimeMin = rows[0]
  let allTimeMax = rows[0]
  for (const r of rows) {
    if (r.min < allTimeMin.min) allTimeMin = r
    if (r.max > allTimeMax.max) allTimeMax = r
  }

  return {
    recentYears,
    allTimeMin: { value: allTimeMin.min, year: allTimeMin.year },
    allTimeMax: { value: allTimeMax.max, year: allTimeMax.year },
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


