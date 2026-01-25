export type DatasetId =
  | 'level_raw'
  | 'level_daily'
  | 'temp_raw'
  | 'temp_daily'
  | 'station_meta'

export const DATASETS: Record<DatasetId, { name: string; url: string }> = {
  level_raw: {
    name: 'station_16005701_water_level_cm.parquet',
    url: '/data/parquet/raw/station_16005701_water_level_cm.parquet',
  },
  level_daily: {
    name: 'station_16005701_water_level_cm_daily.parquet',
    url: '/data/parquet/daily/station_16005701_water_level_cm_daily.parquet',
  },
  temp_raw: {
    name: 'station_16005701_water_temperature_c.parquet',
    url: '/data/parquet/raw/station_16005701_water_temperature_c.parquet',
  },
  temp_daily: {
    name: 'station_16005701_water_temperature_c_daily.parquet',
    url: '/data/parquet/daily/station_16005701_water_temperature_c_daily.parquet',
  },
  station_meta: {
    name: 'station_meta.json',
    url: '/data/parquet/station_meta.json',
  },
}


