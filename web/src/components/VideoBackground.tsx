import { useEffect, useState } from 'react'
import { getCurrentLiveData } from '../lib/liveData'

// List of available background videos.
// Update this list after running optimize_videos.sh.
const VIDEOS = [
  '/videos/20260103_155322.mp4',
  '/videos/20260115_142710.mp4',
  '/videos/20260115_142722.mp4',
  '/videos/20260115_144132.mp4',
  '/videos/20260115_144757.mp4',
  '/videos/20260115_145149.mp4',
  '/videos/20260115_145205.mp4',
  '/videos/20260121_142353.mp4',
  '/videos/20260121_142731.mp4',
  '/videos/20260121_142804.mp4',
  '/videos/20260123_153323.mp4',
  '/videos/20260123_153336.mp4',
  '/videos/20260123_153709.mp4',
  '/videos/20260123_154203.mp4',
  '/videos/20260123_154226.mp4',
]

// Water level (cm) at or above which flood-tagged clips may appear in
// the background-video pool. Below this, they are unconditionally hidden.
// Conservative default — chosen high enough that ordinary winter peaks
// stay below it. Tweak once we wire the official Bavarian Meldestufen.
const FLOOD_LEVEL_CM = 200

type FloodSet = { flood_videos: { filename: string }[] }

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

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const [floodSet, live] = await Promise.all([
        loadFloodSet(),
        getCurrentLiveData(),
      ])

      // Fail-safe flood gate: anything we are not 100% sure about counts
      // as "no flood right now" → flood clips stay hidden.
      const liveLevel = live.waterLevel?.value_cm ?? null
      const floodAllowed = liveLevel !== null && liveLevel >= FLOOD_LEVEL_CM

      const allowed = VIDEOS.filter(path => {
        if (floodAllowed) return true
        const filename = path.split('/').pop() || ''
        return !floodSet.has(filename)
      })

      if (cancelled) return
      const chosen = pickVideo(allowed)
      if (chosen) setVideoSrc(chosen)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (!videoSrc) {
    return null
  }

  return (
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
  )
}
