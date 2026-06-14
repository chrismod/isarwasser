import { useEffect, useState } from 'react'
import { getCurrentLiveData } from '../lib/liveData'
import { VIDEOS } from '../generated/videoList'
import { VideoInfoBubble, type VideoMeta } from './VideoInfoBubble'

// Water level (cm) at or above which flood-tagged clips may appear in
// the background-video pool. Below this, they are unconditionally hidden.
// Conservative default — chosen high enough that ordinary winter peaks
// stay below it. Tweak once we wire the official Bavarian Meldestufen.
const FLOOD_LEVEL_CM = 200

// Weighted-random scoring constants. Score per video is
//   1 / (1 + SEASON_WEIGHT * seasonDistance + |levelDelta| / LEVEL_SCALE_CM)
// — i.e. lower season distance and smaller pegel delta produce higher
// pick probability, but no candidate is ever excluded. Tweak these to
// shift the bias balance.
const SEASON_WEIGHT = 1.5
const LEVEL_SCALE_CM = 60

type Season = 'winter' | 'spring' | 'summer' | 'autumn'

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

function currentSeason(now = new Date()): Season {
  // Meteorological seasons, Northern Hemisphere.
  const m = now.getMonth() // 0=Jan
  if (m <= 1 || m === 11) return 'winter'
  if (m <= 4) return 'spring'
  if (m <= 7) return 'summer'
  return 'autumn'
}

// Cyclic distance on the season ring (0..2).
function seasonDistance(a: Season, b: Season): number {
  const order: Season[] = ['winter', 'spring', 'summer', 'autumn']
  const d = Math.abs(order.indexOf(a) - order.indexOf(b))
  return Math.min(d, 4 - d)
}

function scoreVideo(
  path: string,
  meta: VideoMeta | undefined,
  nowSeason: Season,
  liveLevelCm: number | null,
): number {
  if (!meta) return 1 / (1 + SEASON_WEIGHT * 1) // neutral score when meta is missing
  const sDist =
    meta.season ? seasonDistance(nowSeason, meta.season as Season) : 1
  const levelPenalty =
    liveLevelCm !== null && typeof meta.waterLevelCm === 'number'
      ? Math.abs(meta.waterLevelCm - liveLevelCm) / LEVEL_SCALE_CM
      : 0
  return 1 / (1 + SEASON_WEIGHT * sDist + levelPenalty)
}

function weightedPick(items: { path: string; weight: number }[]): string | null {
  if (items.length === 0) return null
  const total = items.reduce((s, x) => s + x.weight, 0)
  if (total <= 0) return items[Math.floor(Math.random() * items.length)].path
  let r = Math.random() * total
  for (const x of items) {
    r -= x.weight
    if (r <= 0) return x.path
  }
  return items[items.length - 1].path
}

function pickVideo(
  allowed: string[],
  metaMap: MetadataMap,
  liveLevelCm: number | null,
): string | null {
  if (allowed.length === 0) return null
  const stored = sessionStorage.getItem('bg-video')
  if (stored && allowed.includes(stored)) {
    return stored
  }
  const nowSeason = currentSeason()
  const scored = allowed.map(path => {
    const filename = path.split('/').pop() || ''
    return { path, weight: scoreVideo(path, metaMap[filename], nowSeason, liveLevelCm) }
  })
  const choice = weightedPick(scored)
  if (choice) sessionStorage.setItem('bg-video', choice)
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
      const chosen = pickVideo(allowed, allMeta, liveLevel)
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
