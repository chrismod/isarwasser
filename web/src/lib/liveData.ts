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

export async function getCurrentLiveData(): Promise<{
  waterLevel: LiveMeasurement | null
  waterTemp: LiveMeasurement | null
}> {
  // Get today's date for the filename
  const today = new Date().toISOString().split('T')[0]
  
  // Fetch both water level and temperature in parallel
  const [waterLevel, waterTemp] = await Promise.all([
    fetchLatestFromJSONL(`/data/current/water_level_${today}.jsonl`),
    fetchLatestFromJSONL(`/data/current/water_temperature_${today}.jsonl`)
  ])
  
  return {
    waterLevel,
    waterTemp
  }
}
