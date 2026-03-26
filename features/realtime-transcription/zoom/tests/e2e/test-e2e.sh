#!/bin/bash
# End-to-end Zoom transcription pipeline test.
#
# Ground truth: TTS bots speak known scripts into a live Zoom meeting.
# Validation: fetch persisted segments from Postgres, compare against ground truth.
#
# Pipeline under test:
#   TTS bot audio → Zoom Web Client → Recorder bot audio capture →
#   Per-speaker ScriptProcessor → Speaker identity (DOM active speaker) →
#   SpeakerStreamManager → Whisper →
#   SegmentPublisher → Redis → Collector → Postgres
#
# Key difference from Google Meet:
#   - Audio capture: same per-speaker pattern (separate <audio> elements)
#   - Speaker identity: DOM active speaker CSS + isMostRecentlyActiveTrack()
#   - Audio channel join: bot must "Join Audio" post-admission (not automatic)
#   - No auto-admit yet: meeting host must admit bots manually (or disable waiting room)
#
# Key difference from MS Teams:
#   - Per-speaker audio (like GMeet), NOT mixed audio
#   - Speaker identity via DOM polling (like GMeet), NOT captions
#
# Prerequisites:
#   - Compose stack running (make all from deploy/compose/)
#   - A Zoom meeting with waiting room disabled (or a host ready to admit bots)
#   - MVP0 must be complete (audio channel join working)
#   - MVP1 must be complete (speaker identity working)
#
# Usage:
#   ./test-e2e.sh --meeting "https://zoom.us/j/84335626851?pwd=abc123"
#   ZOOM_MEETING_URL="https://zoom.us/j/..." ./test-e2e.sh

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/../../../.env"
RESULTS="$DIR/results/e2e-$(date +%Y-%m-%d-%H%M%S)"

source "$ENV_FILE" 2>/dev/null || true

ZOOM_MEETING_URL="${ZOOM_MEETING_URL:-}"
API_URL="${API_GATEWAY_URL:-http://localhost:8066}"

TOKEN_RECORDER="${API_TOKEN:-vxa_user_pZqJ5dEQK47Mc7YeVTR53wAefBCs7Nf6d0fHbHs8}"
TOKEN_ALICE="${TOKEN_ALICE:-vxa_user_JbJzIlIz5R60I4v4orayS02Pz3iW7lLFE4Mc3hVS}"
TOKEN_BOB="${TOKEN_BOB:-vxa_user_MTHCuOGLJXJj5xDLpmGjPbLRN784SzIsImuX8OcQ}"
TOKEN_CHARLIE="${TOKEN_CHARLIE:-vxa_user_6XwdTtVpZon3MvuYo5R568AFYTv6YOA9gfTkAEMq}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --meeting) ZOOM_MEETING_URL="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [ -z "$ZOOM_MEETING_URL" ]; then
  echo "ERROR: Set ZOOM_MEETING_URL or use --meeting"
  echo "  ./test-e2e.sh --meeting 'https://zoom.us/j/84335626851?pwd=abc123'"
  echo ""
  echo "NOTE: Zoom auto-admit (zoom-auto-admit.js) is not yet implemented."
  echo "The meeting host must admit bots manually, or disable waiting room."
  exit 1
fi

mkdir -p "$RESULTS"

# ─── Ground Truth Script ─────────────────────────────────────────────────────
# Same script as GMeet/Teams — enables cross-platform comparison.

cat > "$RESULTS/ground-truth.json" << 'GTEOF'
[
  {"speaker": "Alice", "text": "Welcome everyone to the quarterly planning meeting. I want to start by reviewing our progress on the mobile application redesign.", "pause": 12},
  {"speaker": "Bob", "text": "Thanks Alice. The mobile team completed the user authentication flow last week. We are now working on the dashboard components.", "pause": 12},
  {"speaker": "Charlie", "text": "I have an update on the backend services. The new API endpoints are deployed to staging and load testing shows three thousand requests per second.", "pause": 12},
  {"speaker": "Alice", "text": "That is excellent progress. Charlie, can you share the timeline for production deployment?", "pause": 10},
  {"speaker": "Charlie", "text": "We are targeting next Wednesday for the production rollout. The team needs two more days for integration testing.", "pause": 10},
  {"speaker": "Bob", "text": "I want to flag a dependency. The mobile app needs the new user profile endpoint before we can ship version two point zero.", "pause": 10},
  {"speaker": "Alice", "text": "Good point. Let us make sure that is prioritized. Any other blockers before we wrap up?", "pause": 8},
  {"speaker": "Charlie", "text": "No blockers from my side. Everything is on track.", "pause": 8},
  {"speaker": "Bob", "text": "All clear here as well. Great meeting everyone.", "pause": 8}
]
GTEOF

log() { echo "[$(date +%H:%M:%S)] $*"; }

# ─── Helpers ──────────────────────────────────────────────────────────────────

send_zoom_bot() {
  local name=$1 token=$2 meeting_url=$3 transcribe=${4:-false}
  local body="{\"platform\":\"zoom\",\"meeting_url\":\"$meeting_url\",\"bot_name\":\"$name\",\"transcribe_enabled\":$transcribe}"
  curl -s -X POST "$API_URL/bots" \
    -H "X-API-Key: $token" \
    -H "Content-Type: application/json" \
    -d "$body" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','ERR'))" 2>/dev/null
}

wait_for_bot() {
  local bot_id=$1 timeout=${2:-120}
  local start=$SECONDS
  while (( SECONDS - start < timeout )); do
    local container
    container=$(docker ps --format "{{.Names}}" | grep "vexa-bot-${bot_id}-" 2>/dev/null || true)
    if [ -n "$container" ]; then
      local in_meeting
      in_meeting=$(docker logs "$container" 2>&1 | grep -c "verified to be in meeting" || true)
      if [ "${in_meeting:-0}" -gt 0 ]; then
        echo "$container"
        return 0
      fi
    fi
    sleep 3
  done
  echo ""
  return 1
}

# Zoom TTS uses Redis commands (same as GMeet, unlike Teams REST endpoint)
REDIS_URL="${REDIS_URL:-redis://172.25.0.2:6379}"
REDIS_MODULE_PATH="$(find /home/dima/dev/vexa-restore/services -path '*/node_modules/redis/dist/index.js' -maxdepth 5 | head -1 | xargs dirname | xargs dirname 2>/dev/null || echo '')"

send_command() {
  local meeting_id=$1 payload=$2
  if [ -z "$REDIS_MODULE_PATH" ]; then
    log "WARNING: Redis module not found — cannot send command"
    return 1
  fi
  node -e "
    const { createClient } = require('$REDIS_MODULE_PATH');
    (async () => {
      const client = createClient({ url: '$REDIS_URL' });
      await client.connect();
      await client.publish('bot_commands:meeting:${meeting_id}', JSON.stringify($payload));
      await client.disconnect();
    })();
  " 2>&1
}

stop_bot() {
  local bot_id=$1
  send_command "$bot_id" '{"action":"leave"}' 2>/dev/null || true
  sleep 2
  local c=$(docker ps --format "{{.Names}}" | grep "vexa-bot-${bot_id}-" 2>/dev/null || true)
  [ -n "$c" ] && docker stop "$c" 2>/dev/null || true
  PGPASSWORD=postgres psql -h localhost -p 5448 -U postgres -d vexa_restore -c \
    "UPDATE meetings SET status='stopped', end_time=NOW() WHERE id=$bot_id AND status IN ('requested','active');" 2>/dev/null || true
}

log "Meeting: $ZOOM_MEETING_URL"
echo "$ZOOM_MEETING_URL" > "$RESULTS/meeting-url.txt"

# ─── Phase 1: Deploy bots ────────────────────────────────────────────────────

log "Sending Recorder bot..."
RECORDER_ID=$(send_zoom_bot "Recorder" "$TOKEN_RECORDER" "$ZOOM_MEETING_URL" true)
if [ "$RECORDER_ID" = "ERR" ]; then
  log "ERROR: Failed to create recorder bot"
  exit 1
fi
log "  Recorder=$RECORDER_ID"

RECORDER_CONTAINER=$(wait_for_bot "$RECORDER_ID" 120)
if [ -z "$RECORDER_CONTAINER" ]; then
  log "ERROR: Recorder did not join within 120s"
  log "HINT: Is the meeting started? Does the meeting have waiting room enabled?"
  log "HINT: Check bot logs: docker logs vexa-bot-${RECORDER_ID}-..."
  exit 1
fi
log "  Recorder joined: $RECORDER_CONTAINER"

# Verify audio channel was joined
sleep 10
AUDIO_JOINED=$(docker logs "$RECORDER_CONTAINER" 2>&1 | grep -c "Joined with Computer Audio\|Computer Audio\|Audio already joined" || true)
if [ "${AUDIO_JOINED:-0}" -eq 0 ]; then
  log "WARNING: Audio channel join not confirmed in logs"
  log "  MVP0 may not be complete — check prepareZoomWebMeeting() output"
fi

# Get session_uid
SESSION_UID=$(PGPASSWORD=postgres psql -h localhost -p 5448 -U postgres -d vexa_restore -t -c \
  "SELECT session_uid FROM meeting_sessions WHERE meeting_id=$RECORDER_ID ORDER BY id DESC LIMIT 1;" 2>/dev/null | tr -d ' ')
log "  Session UID: $SESSION_UID"
echo "$SESSION_UID" > "$RESULTS/session-uid.txt"

log "Sending speaker bots..."
ALICE_ID=$(send_zoom_bot "Alice" "$TOKEN_ALICE" "$ZOOM_MEETING_URL" false)
BOB_ID=$(send_zoom_bot "Bob" "$TOKEN_BOB" "$ZOOM_MEETING_URL" false)
CHARLIE_ID=$(send_zoom_bot "Charlie" "$TOKEN_CHARLIE" "$ZOOM_MEETING_URL" false)
log "  Alice=$ALICE_ID Bob=$BOB_ID Charlie=$CHARLIE_ID"

log "NOTE: If waiting room is enabled, admit bots manually now."

wait_for_bot "$ALICE_ID" 120 > /dev/null || log "WARNING: Alice did not join"
wait_for_bot "$BOB_ID" 120 > /dev/null || log "WARNING: Bob did not join"
wait_for_bot "$CHARLIE_ID" 120 > /dev/null || log "WARNING: Charlie did not join"
log "  All bots joined (or timed out)"

log "Waiting 20s for audio capture to initialize..."
sleep 20

# Check per-speaker audio elements
MEDIA_ELEMENTS=$(docker logs "$RECORDER_CONTAINER" 2>&1 | grep -c "PerSpeaker.*media elements" || true)
log "  Media element discoveries: $MEDIA_ELEMENTS"

# ─── Phase 2: Execute ground truth script ────────────────────────────────────

log "Executing ground truth script (9 utterances)..."

python3 -c "
import json
gt = json.load(open('$RESULTS/ground-truth.json'))
for entry in gt:
    speaker = entry['speaker']
    text = entry['text']
    pause = entry['pause']
    bot_ids = {'Alice': '$ALICE_ID', 'Bob': '$BOB_ID', 'Charlie': '$CHARLIE_ID'}
    print(f'{bot_ids[speaker]}|{text}|{pause}|{speaker}')
" | while IFS='|' read -r bot_id text pause speaker; do
  log "  $speaker: \"${text:0:60}...\""
  send_command "$bot_id" "{\"action\":\"speak\",\"text\":\"$text\"}"
  sleep "$pause"
done

log "All utterances sent. Waiting 30s for transcription + confirmation..."
sleep 30

# ─── Phase 3: Capture pipeline output ────────────────────────────────────────

log "Capturing recorder logs..."
docker logs "$RECORDER_CONTAINER" 2>&1 > "$RESULTS/recorder-full.log"
docker logs "$RECORDER_CONTAINER" 2>&1 | grep "CONFIRMED" > "$RESULTS/confirmed-segments.log" 2>/dev/null || true

# Zoom-specific: capture speaker detection events
docker logs "$RECORDER_CONTAINER" 2>&1 | grep -E "SPEAKER_START|SPEAKER_END|SpeakerIdentity|LOCKED|PerSpeaker" \
  > "$RESULTS/speaker-events.log" 2>/dev/null || true

log "Waiting 35s for immutability threshold..."
sleep 35

log "Fetching segments from Postgres..."
if [ -n "$SESSION_UID" ]; then
  PGPASSWORD=postgres psql -h localhost -p 5448 -U postgres -d vexa_restore \
    -c "COPY (
      SELECT segment_id, speaker, text, start_time, end_time, language, created_at
      FROM transcriptions
      WHERE session_uid = '$SESSION_UID'
      ORDER BY start_time
    ) TO STDOUT WITH CSV HEADER;" > "$RESULTS/db-segments.csv" 2>/dev/null
else
  echo "segment_id,speaker,text,start_time,end_time,language,created_at" > "$RESULTS/db-segments.csv"
  log "  WARNING: No session_uid — DB query skipped"
fi

DB_COUNT=$(tail -n +2 "$RESULTS/db-segments.csv" | wc -l | tr -d ' ')
log "  DB segments: $DB_COUNT"

# Parse bot segments from logs
grep "CONFIRMED" "$RESULTS/recorder-full.log" 2>/dev/null | python3 -c "
import sys, json, re
pat = re.compile(r'CONFIRMED\] (.+?) \| (\S+) \| [^|]+ \| ([^ ]+) \| \"(.*)\"')
segments = []
for line in sys.stdin:
    m = pat.search(line)
    if m:
        segments.append({
            'speaker': m.group(1), 'language': m.group(2),
            'segment_id': m.group(3), 'text': m.group(4),
        })
with open('$RESULTS/bot-segments.json', 'w') as f:
    json.dump(segments, f, indent=2)
print(f'{len(segments)} segments from bot logs')
" 2>/dev/null || echo "0 segments from bot logs"

# ─── Phase 4: Score ──────────────────────────────────────────────────────────

# Reuse the platform-agnostic scorer from Google Meet e2e
SCORER="$DIR/../../../google-meet/tests/e2e/score-e2e.py"
if [ ! -f "$SCORER" ]; then
  log "WARNING: Scorer not found at $SCORER"
  log "  Copy from google-meet/tests/e2e/score-e2e.py or run manually"
else
  log "Scoring..."
  python3 "$SCORER" "$RESULTS" 2>&1 | tee "$RESULTS/score.txt"
fi

# ─── Cleanup ──────────────────────────────────────────────────────────────────

log "Cleaning up bots..."
stop_bot "$ALICE_ID"
stop_bot "$BOB_ID"
stop_bot "$CHARLIE_ID"
stop_bot "$RECORDER_ID"

log ""
log "Results: $RESULTS"
log ""
log "Zoom-specific checks:"
log "  Audio channel joined: $([ "${AUDIO_JOINED:-0}" -gt 0 ] && echo 'YES' || echo 'NO — MVP0 incomplete')"
log "  Media elements found: $MEDIA_ELEMENTS"
log "  DB segments: $DB_COUNT"
