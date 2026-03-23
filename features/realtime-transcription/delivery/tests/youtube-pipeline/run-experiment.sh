#!/bin/bash
# Run multi-speaker YouTube pipeline experiment.
#
# Prerequisites:
#   - Browser session logged into Google (for hosting meeting)
#   - Audio split per speaker (run split-audio.sh first)
#   - .env configured with TRANSCRIPTION_URL, API_TOKEN, etc.
#
# Usage:
#   ./run-experiment.sh                          # create new meeting
#   ./run-experiment.sh muc-yuco-tgz             # use existing meeting
#   BROWSER_TOKEN=xxx ./run-experiment.sh        # specify browser session

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
DATASET="$DIR/dataset"
ENV_FILE="$DIR/../../.env"
SCRIPTS="$DIR/../../../scripts"

source "$ENV_FILE"

NATIVE_ID="${1:-}"
BROWSER_TOKEN="${BROWSER_TOKEN:-smhc12N7_1JlSm288W7qFeF0n8TWqW9d}"
CDP_URL="http://localhost:8066/b/$BROWSER_TOKEN/cdp"
API_URL="${API_GATEWAY_URL:-http://localhost:8066}"

# Speaker bot tokens (one user per bot to bypass per-user limit)
TOKEN_HOST="vxa_user_JbJzIlIz5R60I4v4orayS02Pz3iW7lLFE4Mc3hVS"    # SpeakerA
TOKEN_MUKUND="vxa_user_MTHCuOGLJXJj5xDLpmGjPbLRN784SzIsImuX8OcQ"   # SpeakerB
TOKEN_MADHAV="vxa_user_6XwdTtVpZon3MvuYo5R568AFYTv6YOA9gfTkAEMq"   # SpeakerC
TOKEN_RECORDER="$API_TOKEN"                                          # Main user

echo "=== Multi-Speaker YouTube Pipeline Experiment ==="
echo ""

# --- Step 1: Create or reuse meeting ---
if [ -z "$NATIVE_ID" ]; then
  echo "[1/6] Creating Google Meet via browser session..."
  MEETING_OUTPUT=$(CDP_URL="$CDP_URL" node "$SCRIPTS/gmeet-host-auto.js" 2>&1)
  NATIVE_ID=$(echo "$MEETING_OUTPUT" | grep "NATIVE_MEETING_ID=" | cut -d= -f2)
  if [ -z "$NATIVE_ID" ]; then
    echo "Failed to create meeting. Output:"
    echo "$MEETING_OUTPUT"
    echo ""
    echo "If mic dialog appears, run manually:"
    echo "  node -e \"... click Continue without microphone ...\""
    exit 1
  fi
  echo "  Meeting: https://meet.google.com/$NATIVE_ID"
else
  echo "[1/6] Using existing meeting: $NATIVE_ID"
fi

# --- Step 2: Start auto-admit ---
echo "[2/6] Starting auto-admit..."
node "$DIR/../../../remote-browser/scripts/auto-admit.js" "$CDP_URL" &
ADMIT_PID=$!
echo "  Auto-admit PID: $ADMIT_PID"
sleep 2

# --- Step 3: Send bots ---
echo "[3/6] Sending 4 bots (3 speakers + 1 recorder)..."
MEETING_IDS=""
for pair in "Host:$TOKEN_HOST" "Mukund:$TOKEN_MUKUND" "Madhav:$TOKEN_MADHAV"; do
  IFS=: read -r name token <<< "$pair"
  RESP=$(curl -s -X POST "$API_URL/bots" \
    -H "X-API-Key: $token" \
    -H "Content-Type: application/json" \
    -d "{\"platform\":\"google_meet\",\"native_meeting_id\":\"$NATIVE_ID\",\"bot_name\":\"$name\",\"transcribe_enabled\":false}")
  BOT_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','ERR'))" 2>/dev/null)
  echo "  $name bot: ID $BOT_ID"
  MEETING_IDS="$MEETING_IDS $BOT_ID"
done

RESP=$(curl -s -X POST "$API_URL/bots" \
  -H "X-API-Key: $TOKEN_RECORDER" \
  -H "Content-Type: application/json" \
  -d "{\"platform\":\"google_meet\",\"native_meeting_id\":\"$NATIVE_ID\",\"bot_name\":\"Recorder\"}")
RECORDER_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','ERR'))" 2>/dev/null)
echo "  Recorder bot: ID $RECORDER_ID"

# --- Step 4: Wait for bots to join ---
echo "[4/6] Waiting 45s for bots to join and get admitted..."
sleep 45

# Find bot containers
echo "  Bot containers:"
for id in $MEETING_IDS $RECORDER_ID; do
  CONTAINER=$(docker ps --format "{{.Names}}" | grep "vexa-bot-${id}-" || echo "NOT_FOUND")
  echo "    $id → $CONTAINER"
done

# --- Step 5: Unmute + copy audio + play ---
echo "[5/6] Preparing playback..."

for pair in "Host:host:$MEETING_IDS"; do
  # Get first meeting ID for Host
  break
done

# Copy audio and unmute each speaker bot
for speaker_pair in "Host:host:$(echo $MEETING_IDS | awk '{print $1}')" \
                     "Mukund:mukund:$(echo $MEETING_IDS | awk '{print $2}')" \
                     "Madhav:madhav:$(echo $MEETING_IDS | awk '{print $3}')"; do
  IFS=: read -r name spdir bot_id <<< "$speaker_pair"
  CONTAINER=$(docker ps --format "{{.Names}}" | grep "vexa-bot-${bot_id}-" || echo "")
  if [ -z "$CONTAINER" ]; then
    echo "  WARNING: No container for $name (bot $bot_id)"
    continue
  fi

  echo "  $name ($CONTAINER):"

  # Unmute PulseAudio
  docker exec "$CONTAINER" pactl set-sink-mute tts_sink 0 2>/dev/null
  docker exec "$CONTAINER" pactl set-source-mute virtual_mic 0 2>/dev/null
  echo "    PulseAudio unmuted"

  # Copy audio files
  SP_DIR="$DATASET/speakers/$spdir"
  if [ -d "$SP_DIR" ]; then
    docker exec "$CONTAINER" mkdir -p /tmp/audio
    for wav in "$SP_DIR"/*.wav; do
      docker cp "$wav" "$CONTAINER:/tmp/audio/$(basename $wav)" 2>/dev/null
    done
    docker cp "$SP_DIR/playlist.json" "$CONTAINER:/tmp/audio/playlist.json" 2>/dev/null
    NFILES=$(ls "$SP_DIR"/*.wav 2>/dev/null | wc -l)
    echo "    Copied $NFILES audio files"
  fi
done

# --- Step 6: Start tick capture BEFORE playback ---
echo "[6/7] Starting tick capture..."
CORE_DIR="$DATASET/core"
mkdir -p "$CORE_DIR"
TICK_JSONL="$CORE_DIR/transcript.jsonl"
> "$TICK_JSONL"  # clear previous

node -e "
const path = require('path');
const fs = require('fs');
const { createClient } = require(path.resolve('$DIR/../../../..', 'services/vexa-bot/node_modules/redis'));
async function main() {
  const client = createClient({ url: '${REDIS_URL:-redis://172.25.0.2:6379}' });
  await client.connect();
  const stream = fs.createWriteStream('$TICK_JSONL');
  let count = 0;
  await client.pSubscribe('tc:meeting:${RECORDER_ID}:mutable', (msg) => {
    const tick = JSON.parse(msg);
    if (tick.type === 'transcript') {
      stream.write(JSON.stringify({ ts: tick.ts, speaker: tick.speaker, confirmed: tick.confirmed || [], pending: tick.pending || [] }) + '\n');
      count++;
    }
  });
  console.log('Tick capture started for meeting $RECORDER_ID');
  setTimeout(() => { stream.end(); client.disconnect(); console.log('Captured ' + count + ' ticks'); process.exit(0); }, 360000);
  process.on('SIGINT', () => { stream.end(); client.disconnect(); console.log('Captured ' + count + ' ticks'); process.exit(0); });
}
main();
" &
CAPTURE_PID=$!
echo "  Tick capture PID: $CAPTURE_PID"
sleep 2

# --- Step 7: Orchestrate playback ---
echo "[7/7] Starting synchronized playback..."
echo "  T=0 at $(date -Iseconds)"

# Play each speaker's segments at the correct offsets
for speaker_pair in "Host:host:$(echo $MEETING_IDS | awk '{print $1}')" \
                     "Mukund:mukund:$(echo $MEETING_IDS | awk '{print $2}')" \
                     "Madhav:madhav:$(echo $MEETING_IDS | awk '{print $3}')"; do
  IFS=: read -r name spdir bot_id <<< "$speaker_pair"
  CONTAINER=$(docker ps --format "{{.Names}}" | grep "vexa-bot-${bot_id}-" || echo "")
  [ -z "$CONTAINER" ] && continue

  # Play in background — each bot plays its playlist sequentially
  (
    PLAYLIST="$DATASET/speakers/$spdir/playlist.json"
    [ ! -f "$PLAYLIST" ] && exit 0
    PREV_END=0
    while IFS= read -r seg; do
      START=$(echo "$seg" | python3 -c "import sys,json; print(json.load(sys.stdin)['start'])")
      FILE=$(echo "$seg" | python3 -c "import sys,json; print(json.load(sys.stdin)['file'])")
      # Wait until this segment's start time
      DELAY=$(python3 -c "print(max(0, $START - $PREV_END))")
      sleep "$DELAY"
      docker exec "$CONTAINER" paplay --device=tts_sink "/tmp/audio/$FILE" 2>/dev/null
      PREV_END=$(echo "$seg" | python3 -c "import sys,json; print(json.load(sys.stdin)['end'])")
    done < <(python3 -c "import json; [print(json.dumps(s)) for s in json.load(open('$PLAYLIST'))]")
    echo "  $name: playback complete"
  ) &
done

echo "  Playback started for all speakers (background)"
echo "  Waiting for playback to finish..."
wait

echo ""
echo "=== Experiment complete ==="
echo "Meeting: https://meet.google.com/$NATIVE_ID"
echo "Recorder bot: $RECORDER_ID"
echo ""
echo "Next steps:"
echo "  1. Check recorder bot logs: docker logs vexa-bot-${RECORDER_ID}-*"
echo "  2. Check dashboard: http://localhost:3001/meetings/$RECORDER_ID"
echo ""

# Wait for final processing (30s for last confirmations)
echo "Waiting 30s for final confirmations..."
sleep 30

# Cleanup
kill $CAPTURE_PID 2>/dev/null
kill $ADMIT_PID 2>/dev/null

# Report tick capture
TICK_COUNT=$(wc -l < "$TICK_JSONL" 2>/dev/null || echo 0)
echo "Tick capture: $TICK_COUNT ticks saved to $TICK_JSONL"
