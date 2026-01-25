#!/bin/bash
#
# Video Optimization Script for Isar Water Web App
# Converts raw MP4 videos to web-optimized versions
#

set -e

INPUT_DIR="public/mp4_raw"
OUTPUT_DIR="public/videos"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "🎬 Optimizing videos for web..."
echo "================================"
echo ""

# Counter
count=0
total=$(find "$INPUT_DIR" -name "*.mp4" | wc -l)

for input_file in "$INPUT_DIR"/*.mp4; do
    if [ ! -f "$input_file" ]; then
        echo "No MP4 files found in $INPUT_DIR"
        exit 1
    fi
    
    filename=$(basename "$input_file")
    output_file="$OUTPUT_DIR/${filename}"
    
    count=$((count + 1))
    echo "[$count/$total] Processing: $filename"
    
    # Skip if output already exists and is newer
    if [ -f "$output_file" ] && [ "$output_file" -nt "$input_file" ]; then
        echo "  ⏭️  Skipping (already optimized)"
        echo ""
        continue
    fi
    
    # Get video info
    input_size=$(du -h "$input_file" | cut -f1)
    echo "  📦 Input size: $input_size"
    
    # Optimize video:
    # - Scale to max 1280px width (maintain aspect ratio)
    # - 30fps (smooth but efficient)
    # - CRF 28 (good quality/size balance for background video)
    # - H.264 codec (best browser compatibility)
    # - Faststart for web streaming
    # - 2-pass for better quality/size ratio
    
    ffmpeg -i "$input_file" \
        -vf "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2" \
        -c:v libx264 \
        -preset slow \
        -crf 28 \
        -r 30 \
        -movflags +faststart \
        -an \
        -y \
        "$output_file" \
        -loglevel error -stats
    
    output_size=$(du -h "$output_file" | cut -f1)
    
    # Calculate compression ratio
    input_bytes=$(stat -f%z "$input_file" 2>/dev/null || stat -c%s "$input_file")
    output_bytes=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file")
    ratio=$((100 - (output_bytes * 100 / input_bytes)))
    
    echo "  ✅ Output size: $output_size (${ratio}% smaller)"
    echo ""
done

echo "================================"
echo "✅ Done! Optimized $count video(s)"
echo ""
echo "📊 Total savings:"
du -sh "$INPUT_DIR" | awk '{print "   Input:  " $1}'
du -sh "$OUTPUT_DIR" | awk '{print "   Output: " $1}'
echo ""
echo "💡 Next: Update your app to use videos from /videos/"
