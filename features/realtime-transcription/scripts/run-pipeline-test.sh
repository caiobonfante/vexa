#!/bin/bash
# Run the SpeakerStreamManager pipeline tests against real audio + real Whisper.
#
# Usage:
#   bash tests/run-pipeline-test.sh              # run all tests
#   bash tests/run-pipeline-test.sh short        # run one test
#   bash tests/run-pipeline-test.sh /path/to.wav # test custom file
#
# Requires:
#   - transcription-service running (port 8085)
#   - Test audio files in data/raw/synthetic/audio/ (run generate-test-audio.sh first)

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
AUDIO_DIR="$SCRIPT_DIR/../data/raw/synthetic/audio"
BOT_DIR="$REPO_ROOT/services/vexa-bot"
TEST_SCRIPT="$BOT_DIR/core/src/services/speaker-streams.wav-test.ts"

# Check prerequisites
if ! curl -s http://localhost:8085/health | grep -q healthy; then
  echo "ERROR: transcription-service not running on port 8085"
  exit 1
fi

if [ ! -d "$AUDIO_DIR" ] || [ -z "$(ls "$AUDIO_DIR"/*.wav 2>/dev/null)" ]; then
  echo "No test audio files. Generating..."
  bash "$SCRIPT_DIR/generate-test-audio.sh"
fi

echo "============================================================"
echo "  SpeakerStreamManager Pipeline Test"
echo "  Audio → chunk → SpeakerStreamManager → Whisper → segments"
echo "============================================================"
echo ""

run_test() {
  local wav="$1"
  local name="$(basename "$wav" .wav)"
  local duration
  duration=$(python3 -c "
import struct, sys
with open('$wav', 'rb') as f:
    f.read(24)
    sr = struct.unpack('<I', f.read(4))[0]
    f.read(6)
    bits = struct.unpack('<H', f.read(2))[0]
    f.seek(0, 2)
    size = f.tell()
print(f'{(size - 44) / (sr * bits / 8):.1f}')
" 2>/dev/null || echo "?")

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "TEST: $name (${duration}s)"
  echo "FILE: $wav"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  cd "$BOT_DIR"
  npx ts-node "$TEST_SCRIPT" "$wav" 2>&1
  local exit_code=$?

  echo ""
  if [ $exit_code -eq 0 ]; then
    echo "→ PASSED"
  else
    echo "→ FAILED (exit $exit_code)"
  fi
  echo ""
}

# Unit tests first
echo "── Unit Tests ──────────────────────────────────────────────"
cd "$BOT_DIR"
npx ts-node core/src/services/speaker-streams.test.ts 2>&1
echo ""

# WAV pipeline tests
echo "── Pipeline Tests (real audio + real Whisper) ─────────────"

if [ -n "$1" ]; then
  # Specific test
  if [ -f "$1" ]; then
    run_test "$1"
  elif [ -f "$AUDIO_DIR/$1.wav" ]; then
    run_test "$AUDIO_DIR/$1.wav"
  else
    echo "Not found: $1"
    exit 1
  fi
else
  # All tests
  for wav in "$AUDIO_DIR"/*.wav; do
    run_test "$wav"
  done
fi

echo "============================================================"
echo "  ALL TESTS COMPLETE"
echo "============================================================"
