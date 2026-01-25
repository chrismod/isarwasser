/**
 * Fetch current live data from JSONL files
 */

export type LiveMeasurement = {
  timestamp: string
  timestamp_unix: number
  date: string
  time: string
  value_cm: number
  unit: string
  station_id: string
  station_name: string
  source: string
  fetched_at: string
}

export async function getCurrentLiveData(): Promise<{
  waterLevel: LiveMeasurement | null
  waterTemp: LiveMeasurement | null
}> {
  // Return null data if in development and file doesn't exist
  const defaultResult = { waterLevel: null, waterTemp: null }
  
  try {
    // Get today's date for the filename
    const today = new Date().toISOString().split('T')[0]
    const jsonlUrl = `/data/current/water_level_${today}.jsonl`
    
    const response = await fetch(jsonlUrl)
    
    if (!response.ok) {
      // File doesn't exist yet - this is OK, just use Parquet data
      return defaultResult
    }
    
    const text = await response.text()
    const lines = text.trim().split('\n').filter(line => line.trim())
    
    if (lines.length === 0) {
      return defaultResult
    }
    
    // Get the last line (most recent measurement)
    const lastLine = lines[lines.length - 1]
    const measurement: LiveMeasurement = JSON.parse(lastLine)
    
    return {
      waterLevel: measurement,
      waterTemp: null // Temperature not implemented yet
    }
  } catch (error) {
    // Silent fail - just use Parquet data instead
    console.info('Live data not available, using Parquet data')
    return defaultResult
  }
}
