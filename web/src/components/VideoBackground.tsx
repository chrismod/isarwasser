import { useEffect, useState } from 'react'

// List of available background videos
// Update this list after running optimize_videos.sh
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

function getRandomVideo() {
  // Use sessionStorage to keep same video during session
  const stored = sessionStorage.getItem('bg-video')
  if (stored && VIDEOS.includes(stored)) {
    return stored
  }
  
  const random = VIDEOS[Math.floor(Math.random() * VIDEOS.length)]
  sessionStorage.setItem('bg-video', random)
  return random
}

export function VideoBackground() {
  const [videoSrc, setVideoSrc] = useState<string>('')
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    setVideoSrc(getRandomVideo())
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
