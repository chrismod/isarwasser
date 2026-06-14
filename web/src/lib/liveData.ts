/**
 * Fetch current live data from JSONL files
 */

export type LiveMeasurement = {
  timestamp: string
  timestamp_unix: number
  date: string
  time: string
  value_cm?: number  // For water level
  value_celsius?: number  // For temperature
  unit: string
  station_id: string
  station_name: string
  source: string
  fetched_at: string
}

async function fetchLatestFromJSONL(filename: string): Promise<LiveMeasurement | null> {
  try {
    const response = await fetch(filename)
    
    if (!response.ok) {
      return null
    }
    
    const text = await response.text()
    const lines = text.trim().split('\n').filter(line => line.trim())
    
    if (lines.length === 0) {
      return null
    }
    
    // Get the last line (most recent measurement)
    const lastLine = lines[lines.length - 1]
    return JSON.parse(lastLine)
  } catch (error) {
    return null
  }
}

// How far back to walk if today's JSONL is missing. The scraper writes
// no file at all when the station returns no data, so a gap means
// outage. 14 days is enough to bridge typical sensor downtime; beyond
// that the value is too stale and we let the frontend fall back to the
// daily-mean path from Parquet.
const MAX_DAYS_BACK = 14

async function fetchLatestAvailable(prefix: string): Promise<LiveMeasurement | null> {
  const now = new Date()
  for (let i = 0; i <= MAX_DAYS_BACK; i++) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const day = d.toISOString().split('T')[0]
    const m = await fetchLatestFromJSONL(`/data/current/${prefix}_${day}.jsonl`)
    if (m) return m
  }
  return null
}

export async function getCurrentLiveData(): Promise<{
  waterLevel: LiveMeasurement | null
  waterTemp: LiveMeasurement | null
}> {
  const [waterLevel, waterTemp] = await Promise.all([
    fetchLatestAvailable('water_level'),
    fetchLatestAvailable('water_temperature'),
  ])

  return {
    waterLevel,
    waterTemp
  }
}
