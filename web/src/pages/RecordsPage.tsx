import { Link } from 'react-router-dom'
import { TrendingDown, TrendingUp, AlertCircle, Calendar, CheckCircle } from 'react-feather'
import { getRecords } from '../lib/isarQueries'
import { useAsync } from '../lib/useAsync'
import { DataMissing } from '../components/DataMissing'
import { useI18n } from '../lib/i18n'

function formatDate(dateStr: string, language: 'de' | 'en'): string {
  // Handle multiple formats:
  // 1. Unix timestamp as string (e.g., "1328434200000")
  // 2. Date string (YYYY-MM-DD)
  // 3. Timestamp string (YYYY-MM-DD HH:MM:SS)
  
  let date: Date
  
  // Check if it's a numeric timestamp
  if (/^\d+$/.test(dateStr)) {
    // It's a Unix timestamp (milliseconds)
    date = new Date(parseInt(dateStr, 10))
  } else {
    // It's a date or datetime string
    const dateOnly = dateStr.split(' ')[0]
    date = new Date(dateOnly + 'T00:00:00')
  }
  
  if (isNaN(date.getTime())) {
    return dateStr // Return original if parsing fails
  }
  
  return date.toLocaleDateString(language === 'de' ? 'de-DE' : 'en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function getContextDateRange(dateStr: string): { start: string; end: string } {
  // Handle multiple formats:
  // 1. Unix timestamp as string (e.g., "1328434200000")
  // 2. Date string (YYYY-MM-DD)
  // 3. Timestamp string (YYYY-MM-DD HH:MM:SS)
  
  let date: Date
  
  // Check if it's a numeric timestamp
  if (/^\d+$/.test(dateStr)) {
    // It's a Unix timestamp (milliseconds)
    date = new Date(parseInt(dateStr, 10))
  } else {
    // It's a date or datetime string
    const dateOnly = dateStr.split(' ')[0]
    date = new Date(dateOnly + 'T00:00:00')
  }
  
  if (isNaN(date.getTime())) {
    // Fallback if date is invalid
    return {
      start: '1973-01-01',
      end: new Date().toISOString().slice(0, 10)
    }
  }
  
  const start = new Date(date)
  start.setDate(date.getDate() - 30)
  const end = new Date(date)
  end.setDate(date.getDate() + 30)
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  }
}

export function RecordsPage() {
  const { t, language } = useI18n()
  const levelState = useAsync(() => getRecords('water_level_cm'), [])
  const tempState = useAsync(() => getRecords('water_temperature_c'), [])

  const hasError = levelState.status === 'error' || tempState.status === 'error'
  const isLoading = levelState.status === 'loading' || tempState.status === 'loading'

  const level = levelState.status === 'success' ? levelState.data : null
  const temp = tempState.status === 'success' ? tempState.data : null

  return (
    <div className="container section">
      <h2 className="sectionTitle">{t.recordsTitle}</h2>
      <p className="muted">{t.recordsSubtitle}</p>

      {hasError && (
        <DataMissing
          error={
            levelState.status === 'error'
              ? levelState.error
              : tempState.status === 'error'
                ? tempState.error
                : 'Unknown error'
          }
        />
      )}

      {!hasError && (
        <div className="callouts">
          <div className="card">
            <div className="cardKicker">{t.recordsWaterLevel}</div>
            <div className="cardTitle">{t.recordsMinMax}</div>
            <div className="cardBody">
              {isLoading ? (
                <div className="muted">{t.recordsLoading}</div>
              ) : (
                <>
                  {level?.min && (
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <TrendingDown size={20} color="var(--accent2)" />
                        <div style={{ fontSize: '15px', fontWeight: 600 }}>
                          {t.recordsMin}: {level.min.value.toFixed(2)} {t.unitCm}
                        </div>
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--fg2)', marginTop: '4px', marginLeft: '28px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Calendar size={14} />
                        {formatDate(level.min.ts, language)}
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--fg2)', marginTop: '2px', marginLeft: '28px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {level.min.status ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                        {level.min.status || 'Unknown'}
                      </div>
                      <Link
                        to={`/explore?p=water_level_cm&start=${getContextDateRange(level.min.ts).start}&end=${getContextDateRange(level.min.ts).end}`}
                        style={{
                          display: 'inline-block',
                          marginTop: '8px',
                          marginLeft: '28px',
                          fontSize: '12px',
                          color: 'var(--accent)',
                          textDecoration: 'underline',
                        }}
                      >
                        {t.recordsViewAround}
                      </Link>
                    </div>
                  )}
                  {level?.max && (
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <TrendingUp size={20} color="var(--accent)" />
                        <div style={{ fontSize: '15px', fontWeight: 600 }}>
                          {t.recordsMax}: {level.max.value.toFixed(2)} {t.unitCm}
                        </div>
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--fg2)', marginTop: '4px', marginLeft: '28px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Calendar size={14} />
                        {formatDate(level.max.ts, language)}
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--fg2)', marginTop: '2px', marginLeft: '28px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {level.max.status ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                        {level.max.status || 'Unknown'}
                      </div>
                      <Link
                        to={`/explore?p=water_level_cm&start=${getContextDateRange(level.max.ts).start}&end=${getContextDateRange(level.max.ts).end}`}
                        style={{
                          display: 'inline-block',
                          marginTop: '8px',
                          marginLeft: '28px',
                          fontSize: '12px',
                          color: 'var(--accent)',
                          textDecoration: 'underline',
                        }}
                      >
                        {t.recordsViewAround}
                      </Link>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          <div className="card">
            <div className="cardKicker">{t.recordsWaterTemp}</div>
            <div className="cardTitle">{t.recordsMinMax}</div>
            <div className="cardBody">
              {isLoading ? (
                <div className="muted">{t.recordsLoading}</div>
              ) : (
                <>
                  {temp?.min && (
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <TrendingDown size={20} color="var(--accent2)" />
                        <div style={{ fontSize: '15px', fontWeight: 600 }}>
                          {t.recordsMin}: {temp.min.value.toFixed(2)} {t.unitCelsius}
                        </div>
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--fg2)', marginTop: '4px', marginLeft: '28px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Calendar size={14} />
                        {formatDate(temp.min.ts, language)}
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--fg2)', marginTop: '2px', marginLeft: '28px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {temp.min.status ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                        {temp.min.status || 'Unknown'}
                      </div>
                      <Link
                        to={`/explore?p=water_temperature_c&start=${getContextDateRange(temp.min.ts).start}&end=${getContextDateRange(temp.min.ts).end}`}
                        style={{
                          display: 'inline-block',
                          marginTop: '8px',
                          marginLeft: '28px',
                          fontSize: '12px',
                          color: 'var(--accent)',
                          textDecoration: 'underline',
                        }}
                      >
                        {t.recordsViewAround}
                      </Link>
                    </div>
                  )}
                  {temp?.max && (
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <TrendingUp size={20} color="var(--accent)" />
                        <div style={{ fontSize: '15px', fontWeight: 600 }}>
                          {t.recordsMax}: {temp.max.value.toFixed(2)} {t.unitCelsius}
                        </div>
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--fg2)', marginTop: '4px', marginLeft: '28px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Calendar size={14} />
                        {formatDate(temp.max.ts, language)}
                      </div>
                      <div style={{ fontSize: '13px', color: 'var(--fg2)', marginTop: '2px', marginLeft: '28px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {temp.max.status ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                        {temp.max.status || 'Unknown'}
                      </div>
                      <Link
                        to={`/explore?p=water_temperature_c&start=${getContextDateRange(temp.max.ts).start}&end=${getContextDateRange(temp.max.ts).end}`}
                        style={{
                          display: 'inline-block',
                          marginTop: '8px',
                          marginLeft: '28px',
                          fontSize: '12px',
                          color: 'var(--accent)',
                          textDecoration: 'underline',
                        }}
                      >
                        {t.recordsViewAround}
                      </Link>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          <div className="card">
            <div className="cardKicker">{t.recordsMethod}</div>
            <div className="cardTitle">{t.recordsMethodTitle}</div>
            <div className="cardBody">
              <p style={{ margin: '0 0 8px 0', fontSize: '14px' }}>
                {t.recordsMethodBody}
              </p>
              <p style={{ margin: 0, fontSize: '13px', color: 'var(--fg2)' }}>
                {t.recordsMethodSource}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
