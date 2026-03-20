#!/bin/bash
# Generate test WAV files using the Piper TTS service.
# Outputs to tests/audio/ directory.
#
# Requires: vexa-restore-tts-service-1 container running

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUDIO_DIR="$SCRIPT_DIR/audio"
mkdir -p "$AUDIO_DIR"

TTS_CONTAINER="vexa-restore-tts-service-1"

generate() {
  local name="$1" text="$2"
  local path="$AUDIO_DIR/$name.wav"
  echo "Generating $name..."
  docker exec "$TTS_CONTAINER" python3 -c "
import urllib.request, json
data = json.dumps({'input': '''$text''', 'voice': 'en_US-lessac-medium', 'response_format': 'wav'}).encode()
req = urllib.request.Request('http://localhost:8002/v1/audio/speech', data=data, headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
with open('/tmp/$name.wav', 'wb') as f:
    f.write(resp.read())
" 2>/dev/null
  docker cp "$TTS_CONTAINER:/tmp/$name.wav" "$path" 2>/dev/null
  echo "  → $path ($(du -h "$path" | cut -f1))"
}

echo "=== Generating test audio files ==="

generate "short-sentence" \
  "Hello everyone, this is a short test sentence."

generate "medium-paragraph" \
  "Hello everyone. I want to start by reviewing our product metrics from last month. We had over fifty thousand active users which is a new record for us. Europe grew by twenty percent, Asia by fifteen percent, and North America by ten percent."

generate "long-monologue" \
  "Let me walk through the full product roadmap. We are planning to release version three point zero in April. It includes a completely redesigned dashboard with real time analytics, a new notification system supporting push notifications on mobile devices, and an improved API with better rate limiting. The engineering team has been working on these features for six weeks. We are also investing in machine learning capabilities for our recommendation engine. Early tests show a thirty percent improvement in click through rates. Additionally we are exploring partnerships with several enterprise clients who have expressed interest in our platform. The sales team has been working closely with these prospects and we expect to close at least three major deals by the end of the quarter."

generate "two-speakers" \
  "Good morning everyone. I want to discuss the quarterly results. Revenue is up fifteen percent compared to last quarter and our customer base has grown significantly. That is great news. I think the marketing team deserves a lot of credit for the new campaign. The digital advertising spend was very efficient this quarter."

echo ""
echo "=== All files ==="
ls -la "$AUDIO_DIR"/*.wav
echo ""
echo "Run tests: bash $SCRIPT_DIR/run-pipeline-test.sh"
