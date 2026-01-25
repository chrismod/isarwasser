import * as duckdb from '@duckdb/duckdb-wasm'

import duckdbMvpWasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url'
import duckdbMvpWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url'

import duckdbEhWasm from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url'
import duckdbEhWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url'

type DuckDbState = {
  db: duckdb.AsyncDuckDB
  conn: duckdb.AsyncDuckDBConnection
}

let _statePromise: Promise<DuckDbState> | null = null

export function getDuckDb(): Promise<DuckDbState> {
  if (_statePromise) return _statePromise
  _statePromise = (async () => {
    const logger = new duckdb.ConsoleLogger()

    const bundles: duckdb.DuckDBBundles = {
      mvp: {
        mainModule: duckdbMvpWasm,
        mainWorker: duckdbMvpWorker,
      },
      eh: {
        mainModule: duckdbEhWasm,
        mainWorker: duckdbEhWorker,
      },
    }

    const bundle = await duckdb.selectBundle(bundles)
    const worker = new Worker(bundle.mainWorker!, { type: 'module' })
    const db = new duckdb.AsyncDuckDB(logger, worker)
    await db.instantiate(bundle.mainModule!, bundle.pthreadWorker)

    // Helpful for parquet/http access in WASM.
    // Some builds auto-load httpfs; installing is safe even if it already exists.
    await db.open({ query: { castTimestampToDate: true } })
    const conn = await db.connect()
    await conn.query(`INSTALL httpfs; LOAD httpfs;`)

    return { db, conn }
  })()
  return _statePromise
}

export async function registerParquetFile(name: string, url: string) {
  const { db } = await getDuckDb()
  await db.registerFileURL(name, url, duckdb.DuckDBDataProtocol.HTTP, false)
}


