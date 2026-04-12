import { useI18n } from '../lib/i18n'

export type VideoMeta = {
  recordedAt: string
  season?: string
  durationS?: number
  location?: { lat: number; lon: number; name: string }
  waterLevelCm?: number
  waterTemperatureC?: number
}

type Props = {
  meta: VideoMeta | null
  visible: boolean
  onToggle: () => void
}

export function VideoInfoBubble({ meta, visible, onToggle }: Props) {
  const { language } = useI18n()

  if (!meta) return null

  const dt = new Date(meta.recordedAt)
  const dateStr = dt.toLocaleDateString(language === 'de' ? 'de-DE' : 'en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
  const timeStr = dt.toLocaleTimeString(language === 'de' ? 'de-DE' : 'en-GB', {
    hour: '2-digit',
    minute: '2-digit',
  })

  const parts: string[] = []

  if (meta.location?.name) {
    parts.push(meta.location.name)
  }
  parts.push(`${dateStr}, ${timeStr}`)
  if (meta.waterLevelCm != null) {
    parts.push(`${language === 'de' ? 'Pegel' : 'Level'} ${meta.waterLevelCm} cm`)
  }
  if (meta.waterTemperatureC != null) {
    parts.push(`${meta.waterTemperatureC} °C`)
  }

  return (
    <div className="video-info-bubble">
      <button
        className={`video-info-toggle ${visible ? 'open' : ''}`}
        onClick={onToggle}
        aria-label="Video info"
      >
        i
      </button>
      {visible && (
        <div className="video-info-pill">
          {parts.join(' · ')}
        </div>
      )}
    </div>
  )
}
