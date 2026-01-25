import { useI18n } from '../lib/i18n'

export function DataMissing({ error }: { error: string }) {
  const { t } = useI18n()
  
  return (
    <div className="card" style={{ borderColor: 'rgba(255,100,100,0.3)' }}>
      <div className="cardKicker">{t.dataMissingTitle}</div>
      <div className="cardBody">
        <p>{error}</p>
        <details style={{ marginTop: '12px', fontSize: '13px' }}>
          <summary style={{ cursor: 'pointer', color: 'var(--fg2)' }}>
            {t.dataMissingHowToFix}
          </summary>
          <div style={{ marginTop: '8px', color: 'var(--fg1)' }}>
            <p>{t.dataMissingRunPipeline}</p>
            <pre
              style={{
                background: 'rgba(0,0,0,0.3)',
                padding: '8px',
                borderRadius: '6px',
                overflow: 'auto',
                fontSize: '12px',
              }}
            >
              {`node pipeline/ingest_lfu_csv_to_parquet_daily_only.mjs \\
  --station-id 16005701 \\
  --start-date 1975-01-01 \\
  --sync-to-web-public web/public/data/parquet`}
            </pre>
          </div>
        </details>
      </div>
    </div>
  )
}
