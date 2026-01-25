# 🎬 Video Background Setup

## Quick Start

### 1. Install ffmpeg (if not already installed)

```bash
sudo apt update && sudo apt install -y ffmpeg
```

### 2. Optimize Videos

```bash
cd /home/retroflex/monoroc/isarwasser/web
./optimize_videos.sh
```

This will:
- Read all videos from `public/mp4_raw/`
- Optimize them (scale to 1280px, reduce bitrate, remove audio)
- Save to `public/videos/`
- Reduce file sizes by ~70-80%

**Expected results:**
- Input: 11-18 MB per video
- Output: 2-5 MB per video
- Total: ~200MB → ~40-60MB

### 3. Test Locally

```bash
npm run dev
```

Open http://localhost:5173 and refresh a few times to see different random videos.

## How It Works

### Video Selection
- **Random on first load:** Each session gets a random video
- **Persisted in session:** Same video during the entire browser session
- **Changes on refresh:** New session = new random video

### Technical Details

**Video Settings:**
- Max resolution: 1280x720px
- Frame rate: 30fps
- Codec: H.264 (best browser support)
- CRF: 28 (balanced quality/size)
- Audio: Removed (not needed for background)
- Faststart: Enabled (streams while loading)

**Browser Compatibility:**
- ✅ Chrome/Edge
- ✅ Firefox
- ✅ Safari
- ✅ Mobile browsers

### Performance
- Videos load in background (non-blocking)
- Fade in when ready
- Optimized for web streaming
- No impact on page interaction

## File Structure

```
web/
├── public/
│   ├── mp4_raw/           # Original videos (DO NOT COMMIT)
│   │   ├── 20260103_155322.mp4
│   │   ├── 20260115_142710.mp4
│   │   └── ...
│   └── videos/            # Optimized videos (COMMIT THESE)
│       ├── 20260103_155322.mp4  (optimized)
│       ├── 20260115_142710.mp4  (optimized)
│       └── ...
├── src/
│   └── components/
│       └── VideoBackground.tsx   # Component
└── optimize_videos.sh     # Optimization script
```

## Adding New Videos

1. Place raw video in `public/mp4_raw/`
2. Run `./optimize_videos.sh`
3. Add filename to `VIDEOS` array in `src/components/VideoBackground.tsx`:

```tsx
const VIDEOS = [
  '/videos/20260103_155322.mp4',
  '/videos/20260115_142710.mp4',
  // ... add new ones here
  '/videos/YOUR_NEW_VIDEO.mp4',
]
```

4. Commit only the optimized video in `public/videos/`

## Git Configuration

Add to `.gitignore`:

```gitignore
# Raw videos (too large for git)
/public/mp4_raw/*

# Keep the directory
!/public/mp4_raw/.gitkeep
```

**Important:** Only commit optimized videos (<5MB each) to keep repo size manageable.

## Troubleshooting

### Videos not showing?
1. Check browser console for errors
2. Verify videos exist in `public/videos/`
3. Check network tab - videos should load
4. Try hard refresh (Ctrl+Shift+R)

### Videos too large?
Adjust CRF in `optimize_videos.sh`:
- CRF 23 = higher quality, larger files (~5-8MB)
- CRF 28 = balanced (current, ~2-5MB)
- CRF 32 = lower quality, smaller files (~1-3MB)

### Videos choppy/laggy?
- Check CPU usage during playback
- Try lower resolution (change scale in script)
- Reduce frame rate to 24fps

### Script fails?
- Ensure ffmpeg is installed: `ffmpeg -version`
- Check file permissions: `chmod +x optimize_videos.sh`
- Check disk space: `df -h`

## Advanced: Manual Optimization

If the script doesn't work, manually optimize with:

```bash
ffmpeg -i public/mp4_raw/INPUT.mp4 \
  -vf "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease" \
  -c:v libx264 \
  -preset slow \
  -crf 28 \
  -r 30 \
  -movflags +faststart \
  -an \
  public/videos/OUTPUT.mp4
```

## Production Checklist

Before deploying:

- [ ] All videos optimized (<5MB each)
- [ ] Videos in `public/videos/` directory
- [ ] Video list updated in `VideoBackground.tsx`
- [ ] Tested on slow connection (throttle in DevTools)
- [ ] Tested on mobile
- [ ] Added `.gitignore` rules
- [ ] Raw videos NOT committed to git

## Future Improvements

Possible enhancements:
- [ ] WebM format (better compression, less browser support)
- [ ] Multiple resolutions (serve based on screen size)
- [ ] Lazy loading (load video after page ready)
- [ ] Preload hint for faster loading
- [ ] User preference (enable/disable video)
- [ ] Season-based video selection
