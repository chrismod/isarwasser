import { useEffect, useState } from 'react'
import { getCurrentLiveData } from '../lib/liveData'
import { VIDEOS } from '../generated/videoList'
import { VideoInfoBubble, type VideoMeta } from './VideoInfoBubble'

// Water level (cm) at or above which flood-tagged clips may appear in
// the background-video pool. Below this, they are unconditionally hidden.
// Conservative default — chosen high enough that ordinary winter peaks
// stay below it. Tweak once we wire the official Bavarian Meldestufen.
const FLOOD_LEVEL_CM = 200

type FloodSet = { flood_videos: { filename: string }[] }

type MetadataMap = Record<string, VideoMeta>

async function loadMetadata(): Promise<MetadataMap> {
  try {
    const r = await fetch('/videos/metadata.json', { cache: 'no-cache' })
    if (!r.ok) return {}
    return await r.json()
  } catch {
    return {}
  }
}

async function loadFloodSet(): Promise<Set<string>> {
  try {
    const r = await fetch('/videos/flood-set.json', { cache: 'no-cache' })
    if (!r.ok) return new Set()
    const data: FloodSet = await r.json()
    return new Set((data.flood_videos || []).map(v => v.filename))
  } catch {
    return new Set()
  }
}

function pickVideo(allowed: string[]): string | null {
  if (allowed.length === 0) return null
  const stored = sessionStorage.getItem('bg-video')
  if (stored && allowed.includes(stored)) {
    return stored
  }
  const choice = allowed[Math.floor(Math.random() * allowed.length)]
  sessionStorage.setItem('bg-video', choice)
  return choice
}

export function VideoBackground() {
  const [videoSrc, setVideoSrc] = useState<string>('')
  const [isLoaded, setIsLoaded] = useState(false)
  const [meta, setMeta] = useState<VideoMeta | null>(null)
  const [infoVisible, setInfoVisible] = useState(() => {
    return localStorage.getItem('video-info-visible') !== 'false'
  })

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const [floodSet, live, allMeta] = await Promise.all([
        loadFloodSet(),
        getCurrentLiveData(),
        loadMetadata(),
      ])

      const liveLevel = live.waterLevel?.value_cm ?? null
      const floodAllowed = liveLevel !== null && liveLevel >= FLOOD_LEVEL_CM

      const allowed = VIDEOS.filter(path => {
        if (floodAllowed) return true
        const filename = path.split('/').pop() || ''
        return !floodSet.has(filename)
      })

      if (cancelled) return
      const chosen = pickVideo(allowed)
      if (chosen) {
        setVideoSrc(chosen)
        const filename = chosen.split('/').pop() || ''
        setMeta(allMeta[filename] ?? null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const toggleInfo = () => {
    setInfoVisible(v => {
      localStorage.setItem('video-info-visible', String(!v))
      return !v
    })
  }

  if (!videoSrc) {
    return null
  }

  return (
    <>
      <div className="video-background">
        <video
          autoPlay
          muted
          loop
          playsInline
          className={`video-background__video ${isLoaded ? 'loaded' : ''}`}
          onCanPlay={() => setIsLoaded(true)}
        >
          <source src={videoSrc} type="video/mp4" />
        </video>
        <div className="video-background__overlay" />
      </div>
      <VideoInfoBubble meta={meta} visible={infoVisible} onToggle={toggleInfo} />
    </>
  )
}
