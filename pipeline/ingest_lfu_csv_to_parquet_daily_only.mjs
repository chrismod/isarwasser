import fs from 'node:fs'
import path from 'node:path'
import readline from 'node:readline'
import { fileURLToPath } from 'node:url'
import parquet from 'parquetjs-lite'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true })
}

function parseArgs(argv) {
  const args = {
    dataRoot: path.resolve(__dirname, '..', 'data'),
    outRoot: path.resolve(__dirname, '..', 'data', 'parquet'),
    stationId: '16005701',
    startDate: '1975-01-01',
    syncToWebPublic: '',
  }
  for (let i = 2; i < argv.length; i += 1) {
    const a = argv[i]
    const v = argv[i + 1]
    if (!v || v.startsWith('--')) continue
    if (a === '--data-root') args.dataRoot = path.resolve(v)
    if (a === '--out-root') args.outRoot = path.resolve(v)
    if (a === '--station-id') args.stationId = v
    if (a === '--start-date') args.startDate = v
    if (a === '--sync-to-web-public') args.syncToWebPublic = path.resolve(v)
  }
  return args
}

function parseMetaLine(line) {
  // Key:;Value (German export). Example: Messstellen-Nr.:;16005701
  const parts = line.split(';')
  if (parts.length < 2) return null
  const key = parts[0].trim().replace(/:$/, '')
  const value = (parts[1] ?? '').trim().replace(/^"|"$/g, '')
  return { key, value, parts }
}

function detectParameterFromHeader(headerLine) {
  // Datum;"Wasserstand [cm]";Prüfstatus
  if (headerLine.includes('Wasserstand')) return { parameter: 'water_level_cm', unit: 'cm' }
  if (headerLine.includes('Wassertemperatur')) return { parameter: 'water_temperature_c', unit: '°C' }
  return { parameter: 'unknown', unit: '' }
}

function parseDataRow(line) {
  // We only parse the table portion where the format is stable:
  // "YYYY-MM-DD HH:MM";94,00;Rohdaten
  // Value may be empty ("" between separators).
  const parts = line.split(';')
  if (parts.length < 3) return null
  const ts = parts[0].trim().replace(/^"|"$/g, '')
  const valueRaw = (parts[1] ?? '').trim().replace(/^"|"$/g, '')
  const status = (parts[2] ?? '').trim().replace(/^"|"$/g, '') || null
  const value =
    valueRaw === '' ? null : Number.parseFloat(valueRaw.replace(',', '.'))
  return { ts, value: Number.isFinite(value) ? value : null, status }
}

function dateFromTs(ts) {
  // ts: "YYYY-MM-DD HH:MM"
  return ts.slice(0, 10)
}

function cmpDate(a, b) {
  // both YYYY-MM-DD
  return a < b ? -1 : a > b ? 1 : 0
}

async function forEachLine(filePath, onLine) {
  const input = fs.createReadStream(filePath, { encoding: 'utf-8' })
  const rl = readline.createInterface({ input, crlfDelay: Infinity })

  let closed = false
  const closeOnce = () => {
    if (closed) return
    closed = true
    rl.close()
    input.destroy()
  }

  return await new Promise((resolve, reject) => {
    rl.on('line', (line0) => {
      try {
        onLine(line0)
      } catch (err) {
        closeOnce()
        reject(err)
      }
    })
    rl.on('close', () => resolve())
    rl.on('error', (err) => {
      closeOnce()
      reject(err)
    })
    input.on('error', (err) => {
      closeOnce()
      reject(err)
    })
  })
}

async function ingestGroupDailyOnly({ csvFiles, outDailyParquet, startDate }) {
  if (csvFiles.length === 0) throw new Error('No files')

  ensureDir(path.dirname(outDailyParquet))

  let station = {
    station_id: null,
    station_name: null,
    river: null,
    time_ref: null,
    easting: null,
    northing: null,
    coord_ref: null,
    gauge_zero: null,
    raw_meta: {},
  }

  const daily = new Map()
  // date -> { sum, count, min, max, statusCounts: Map<string, number> }

  let parameter = 'unknown'

  for (const csvPath of csvFiles) {
    console.log(`Processing ${csvPath}...`)
    let inTable = false
    let headerLine = ''
    let lineCount = 0
    
    await forEachLine(csvPath, (line0) => {
      const line = String(line0).trim()
      if (!line) return

      if (!inTable) {
        if (line.startsWith('Datum;')) {
          inTable = true
          headerLine = line
          const p = detectParameterFromHeader(headerLine)
          parameter = p.parameter
          return
        }

        const meta = parseMetaLine(line)
        if (!meta) return
        station.raw_meta[meta.key] = meta.value
        if (meta.key === 'Zeitbezug') station.time_ref = meta.value
        if (meta.key === 'Messstellen-Name') station.station_name = meta.value
        if (meta.key === 'Messstellen-Nr.') station.station_id = Number(meta.value)
        if (meta.key === 'Gewässer') station.river = meta.value
        if (meta.key === 'Pegelnullpunktshöhe') station.gauge_zero = meta.value
        if (meta.key === 'Ostwert') {
          station.easting = Number(meta.value) || null
          const parts = meta.parts
          // Ostwert:;693161;Nordwert:;5335716;"ETRS89 / UTM Zone 32N"
          if (parts.length >= 4 && parts[2].trim().startsWith('Nordwert')) {
            station.northing = Number(parts[3].replace(/"/g, '')) || null
          }
          if (parts.length >= 5) {
            station.coord_ref = parts[4].replace(/"/g, '').trim() || null
          }
        }
        return
      }

      // table row
      const row = parseDataRow(line)
      if (!row) return
      const d = dateFromTs(row.ts)
      if (cmpDate(d, startDate) < 0) return

      lineCount++
      if (lineCount % 100000 === 0) {
        console.log(`  Processed ${lineCount} rows...`)
      }

      // daily aggregate only when value present
      if (row.value !== null) {
        const cur = daily.get(d) || {
          sum: 0,
          count: 0,
          min: row.value,
          max: row.value,
          statusCounts: new Map(),
        }
        cur.sum += row.value
        cur.count += 1
        cur.min = Math.min(cur.min, row.value)
        cur.max = Math.max(cur.max, row.value)
        daily.set(d, cur)
      }

      if (row.status) {
        const cur = daily.get(d) || {
          sum: 0,
          count: 0,
          min: null,
          max: null,
          statusCounts: new Map(),
        }
        const prev = cur.statusCounts.get(row.status) || 0
        cur.statusCounts.set(row.status, prev + 1)
        daily.set(d, cur)
      }
    })
  }

  // Build daily parquet
  const dailyWriter = await parquet.ParquetWriter.openFile(
    new parquet.ParquetSchema({
      station_id: { type: 'INT32' },
      parameter: { type: 'UTF8' },
      date: { type: 'UTF8' },
      count: { type: 'INT32' },
      mean: { type: 'DOUBLE' },
      min: { type: 'DOUBLE', optional: true },
      max: { type: 'DOUBLE', optional: true },
      status_mode: { type: 'UTF8', optional: true },
    }),
    outDailyParquet,
    { useDataPageV2: false, rowGroupSize: 10_000 }
  )

  const dates = Array.from(daily.keys()).sort()
  console.log(`Writing ${dates.length} daily rows...`)
  
  for (const d of dates) {
    const cur = daily.get(d)
    if (!cur || cur.count <= 0) continue
    let statusMode = null
    if (cur.statusCounts && cur.statusCounts.size > 0) {
      let best = null
      let bestN = -1
      for (const [k, n] of cur.statusCounts.entries()) {
        if (n > bestN) {
          bestN = n
          best = k
        }
      }
      statusMode = best
    }
    await dailyWriter.appendRow({
      station_id: station.station_id,
      parameter,
      date: d,
      count: cur.count,
      mean: cur.sum / cur.count,
      min: cur.min ?? null,
      max: cur.max ?? null,
      status_mode: statusMode,
    })
  }

  await dailyWriter.close()
  console.log(`Daily parquet written: ${outDailyParquet}`)
  return station
}

function copyTree(src, dst) {
  ensureDir(dst)
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name)
    const d = path.join(dst, entry.name)
    if (entry.isDirectory()) copyTree(s, d)
    else fs.copyFileSync(s, d)
  }
}

async function main() {
  const args = parseArgs(process.argv)

  const levelDir = path.join(args.dataRoot, 'fluesse-wasserstand')
  const tempDir = path.join(args.dataRoot, 'fluesse-wassertemperatur')

  const levelFiles = fs
    .readdirSync(levelDir)
    .filter((f) => f.startsWith(`${args.stationId}_`) && f.endsWith('.csv'))
    .map((f) => path.join(levelDir, f))
    .sort()
  const tempFiles = fs
    .readdirSync(tempDir)
    .filter((f) => f.startsWith(`${args.stationId}_`) && f.endsWith('.csv'))
    .map((f) => path.join(tempDir, f))
    .sort()

  if (levelFiles.length === 0 && tempFiles.length === 0) {
    throw new Error(`No files found for station ${args.stationId}`)
  }

  const outRoot = args.outRoot
  const dailyDir = path.join(outRoot, 'daily')
  ensureDir(dailyDir)

  let station = null
  const meta = { generated_at: new Date().toISOString() }

  if (levelFiles.length > 0) {
    console.log('=== Processing water level ===')
    station = await ingestGroupDailyOnly({
      csvFiles: levelFiles,
      outDailyParquet: path.join(dailyDir, `station_${args.stationId}_water_level_cm_daily.parquet`),
      startDate: args.startDate,
    })
    meta.water_level_files = levelFiles
  }

  if (tempFiles.length > 0) {
    console.log('=== Processing water temperature ===')
    station =
      (await ingestGroupDailyOnly({
        csvFiles: tempFiles,
        outDailyParquet: path.join(dailyDir, `station_${args.stationId}_water_temperature_c_daily.parquet`),
        startDate: args.startDate,
      })) || station
    meta.water_temperature_files = tempFiles
  }

  meta.station = station
  fs.writeFileSync(path.join(outRoot, 'station_meta.json'), JSON.stringify(meta, null, 2), 'utf-8')

  if (args.syncToWebPublic) {
    copyTree(outRoot, args.syncToWebPublic)
    console.log(`Synced parquet outputs to: ${args.syncToWebPublic}`)
  }
  console.log(`Done. Parquet written to: ${outRoot}`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})



