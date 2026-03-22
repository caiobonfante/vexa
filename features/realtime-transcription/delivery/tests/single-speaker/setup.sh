#!/bin/bash
# Setup a single-speaker test dataset from a YouTube video.
#
# Usage: ./setup.sh <youtube-url> [duration-seconds]
#   ./setup.sh "https://www.youtube.com/watch?v=kwSVtQ7dziU" 120
#
# Requires: python3.10 (for yt-dlp), ffmpeg, curl
# Env vars: TRANSCRIPTION_URL, TRANSCRIPTION_TOKEN (from ../../.env)

set -euo pipefail

URL="${1:?Usage: ./setup.sh <youtube-url> [duration-seconds]}"
DURATION="${2:-120}"
DIR="$(cd "$(dirname "$0")" && pwd)"
DATASET_DIR="$DIR/dataset"
ENV_FILE="$DIR/../../.env"

if [ -f "$ENV_FILE" ]; then
  source "$ENV_FILE"
fi

TRANSCRIPTION_URL="${TRANSCRIPTION_URL:?Set TRANSCRIPTION_URL in .env}"
TRANSCRIPTION_TOKEN="${TRANSCRIPTION_TOKEN:?Set TRANSCRIPTION_TOKEN in .env}"

echo "=== Single-Speaker Test Setup ==="
echo "URL: $URL"
echo "Duration: ${DURATION}s"
echo ""

# Step 1: Download audio
mkdir -p "$DATASET_DIR"
echo "[1/3] Downloading audio..."
if [ ! -f "$DATASET_DIR/audio-full.wav" ]; then
  python3.10 -m yt_dlp -x --audio-format wav \
    -o "$DATASET_DIR/audio-full.%(ext)s" \
    "$URL"
  echo "  Downloaded: $DATASET_DIR/audio-full.wav"
else
  echo "  Already exists: $DATASET_DIR/audio-full.wav (skipping)"
fi

# Step 2: Resample to 16kHz mono, trim to duration
echo "[2/3] Resampling to 16kHz mono, first ${DURATION}s..."
ffmpeg -y -loglevel error \
  -i "$DATASET_DIR/audio-full.wav" \
  -t "$DURATION" -ar 16000 -ac 1 \
  "$DATASET_DIR/audio.wav"
ACTUAL_DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$DATASET_DIR/audio.wav" | cut -d. -f1)
echo "  Output: $DATASET_DIR/audio.wav (${ACTUAL_DURATION}s, 16kHz mono)"

# Step 3: Generate ground truth with offline Whisper
echo "[3/3] Generating ground truth (offline Whisper)..."
curl -s -X POST "$TRANSCRIPTION_URL" \
  -H "Authorization: Bearer $TRANSCRIPTION_TOKEN" \
  -F "file=@$DATASET_DIR/audio.wav" \
  -F "model=large-v3-turbo" \
  -F "timestamp_granularities=segment" \
  -F "response_format=verbose_json" \
  > "$DATASET_DIR/ground-truth.json"

# Verify
SEGMENTS=$(python3 -c "import json; d=json.load(open('$DATASET_DIR/ground-truth.json')); print(len(d.get('segments', d)))")
echo "  Ground truth: $SEGMENTS segments"

# Save metadata
cat > "$DATASET_DIR/metadata.txt" <<METADATA
source: $URL
duration: ${ACTUAL_DURATION}s
created: $(date -Iseconds)
segments: $SEGMENTS
METADATA

echo ""
echo "=== Setup complete ==="
echo "  Audio: $DATASET_DIR/audio.wav"
echo "  Ground truth: $DATASET_DIR/ground-truth.json ($SEGMENTS segments)"
echo ""
echo "Next: ./run.sh core"
