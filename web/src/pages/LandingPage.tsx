import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getLatestDaily, getNowVsNormalDayOfYear } from '../lib/isarQueries'
import { getCurrentLiveData } from '../lib/liveData'
import type { LiveMeasurement } from '../lib/liveData'
import { useI18n } from '../lib/i18n'
import { VideoBackground } from '../components/VideoBackground'

function formatDate(date: any): string {
  if (!date) return ''
  
  let d: Date
  
  // If it's a string that looks like a Unix timestamp
  if (typeof date === 'string' && /^\d+$/.test(date)) {
    d = new Date(parseInt(date, 10))
  }
  // If it's a number (Unix timestamp in milliseconds)
  else if (typeof date === 'number') {
    d = new Date(date)
  }
  // If it's an ISO timestamp string (e.g., "2026-01-25T17:00:00")
  else if (typeof date === 'string' && date.includes('T')) {
    d = new Date(date)
  }
  // If it's already a string in YYYY-MM-DD format
  else if (typeof date === 'string' && date.includes('-')) {
    const parts = date.split('-')
    if (parts.length === 3) {
      // Check if it's just a date or has time component
      if (parts[2].includes(' ')) {
        // Has time: "2026-01-25 17:00"
        d = new Date(date.replace(' ', 'T'))
      } else {
        // Just date: "2026-01-25"
        return `${parts[2]}.${parts[1]}.${parts[0]}`
      }
    } else {
      d = new Date(date)
    }
  }
  // Try as Date object
  else {
    try {
      d = new Date(date)
    } catch (e) {
      console.error('Date formatting error:', e, date)
      return String(date)
    }
  }
  
  // Check if date is valid
  if (isNaN(d.getTime())) {
    return String(date)
  }
  
  const dateStr = d.toLocaleDateString('de-DE', { 
    day: '2-digit', 
    month: '2-digit', 
    year: 'numeric' 
  })
  
  const timeStr = d.toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit'
  })
  
  return `${dateStr} ${timeStr}`
}

export function LandingPage() {
  const { t } = useI18n()
  const [level, setLevel] = useState<any>(null)
  const [temp, setTemp] = useState<any>(null)
  const [liveLevel, setLiveLevel] = useState<LiveMeasurement | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [l, t, live] = await Promise.all([
          getLatestDaily('water_level_cm'),
          getLatestDaily('water_temperature_c'),
          getCurrentLiveData(),
        ])
        if (cancelled) return
        setLevel(l)
        setTemp(t)
        setLiveLevel(live.waterLevel)
      } catch (e: any) {
        if (cancelled) return
        setErr(String(e?.message ?? e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="landing-page">
      <VideoBackground />
      <div className="container section">
        <div className="hero-landing">
          <div className="hero-content">
            <h1 className="title">{t.landingTitle}</h1>
            <p className="lead">{t.landingLead}</p>
            
            {err ? (
              <div className="card error-card">{err}</div>
            ) : (
              <div className="hero-stats">
                <div className="stat-card stat-card-major">
                  <div className="stat-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M12 2v20M12 2c-2.5 0-4 2-4 4v12c0 2.5 1.5 4 4 4s4-1.5 4-4V6c0-2-1.5-4-4-4z"/>
                      <line x1="8" y1="10" x2="16" y2="10"/>
                      <line x1="8" y1="14" x2="16" y2="14"/>
                      <line x1="8" y1="18" x2="16" y2="18"/>
                    </svg>
                  </div>
                  <div className="stat-content">
                    <div className="stat-label">{t.landingWaterLevel}</div>
                    <div className="stat-value">
                      {liveLevel ? `${liveLevel.value_cm.toFixed(1)}` : level ? `${level.mean.toFixed(1)}` : '—'}
                      <span className="stat-unit">{t.unitCm}</span>
                    </div>
                    {(liveLevel?.timestamp || level?.date) && (
                      <div className="stat-date">
                        {liveLevel ? formatDate(liveLevel.timestamp) : formatDate(level.date)}
                      </div>
                    )}
                  </div>
                </div>

                <div className="stat-card stat-card-major">
                  <div className="stat-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>
                    </svg>
                  </div>
                  <div className="stat-content">
                    <div className="stat-label">{t.landingWaterTemp}</div>
                    <div className="stat-value">
                      {temp ? `${temp.mean.toFixed(1)}` : '—'}
                      <span className="stat-unit">{t.unitCelsius}</span>
                    </div>
                    {temp?.date && (
                      <div className="stat-date">
                        {formatDate(temp.date)}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className="callouts">
              <div className="card">
                <div className="cardKicker">{t.landingUpcoming}</div>
                <div className="cardTitle">{t.landingUpcomingTitle}</div>
                <div className="cardBody">{t.landingUpcomingBody}</div>
              </div>
              <Link to="/explore" className="card card-link">
                <div className="cardKicker">{t.navExplore}</div>
                <div className="cardTitle">{t.landingExploreTitle}</div>
                <div className="cardBody">{t.landingExploreBody}</div>
                <div className="card-arrow">→</div>
              </Link>
              <Link to="/records" className="card card-link">
                <div className="cardKicker">{t.navRecords}</div>
                <div className="cardTitle">{t.landingRecordsTitle}</div>
                <div className="cardBody">{t.landingRecordsBody}</div>
                <div className="card-arrow">→</div>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
