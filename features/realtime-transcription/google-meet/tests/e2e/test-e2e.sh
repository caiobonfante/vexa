#!/bin/bash
# End-to-end Google Meet transcription pipeline test.
#
# Ground truth: TTS bots speak known scripts into a live meeting.
# Validation: fetch persisted segments from Postgres, compare against ground truth.
#
# Pipeline under test:
#   TTS bot audio → Google Meet → Recorder bot audio capture →
#   Speaker identity → SpeakerStreamManager → Whisper →
#   SegmentPublisher → Redis → Collector → Postgres
#
# Usage:
#   ./test-e2e.sh --meeting abc-defg-hij
#   CDP_URL=http://IP:9223 ./test-e2e.sh

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/../../../.env"
SCRIPTS="$DIR/../../../scripts"
RESULTS="$DIR/results/e2e-$(date +%Y-%m-%d-%H%M%S)"

source "$ENV_FILE"

MEETING_ID="${MEETING_ID:-}"
CDP_URL="${CDP_URL:-}"
REDIS_URL="${REDIS_URL:-redis://:vexa-redis-dev@localhost:6379}"
API_URL="${API_GATEWAY_URL:-http://localhost:8056}"
PG_URL="${POSTGRES_URL:-postgresql://postgres:postgres@localhost:5438/vexa}"

TOKEN_RECORDER="${API_TOKEN}"
TOKEN_ALICE="${TOKEN_ALICE:-vxa_user_AliceTTSbot00000000000000000000000000}"
TOKEN_BOB="${TOKEN_BOB:-vxa_user_BobTTSbot0000000000000000000000000000}"
TOKEN_CHARLIE="${TOKEN_CHARLIE:-vxa_user_CharlieTTSbot000000000000000000000000}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --meeting) MEETING_ID="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

mkdir -p "$RESULTS"

# ─── Ground Truth Script ─────────────────────────────────────────────────────
# Each entry: speaker, text, pause_after_seconds
# These are the EXACT words we expect in the pipeline output.

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

send_bot() {
  local name=$1 token=$2 meeting=$3 transcribe=${4:-false} voice_agent=${5:-false}
  curl -s -X POST "$API_URL/bots" \
    -H "X-API-Key: $token" \
    -H "Content-Type: application/json" \
    -d "{\"platform\":\"google_meet\",\"native_meeting_id\":\"$meeting\",\"bot_name\":\"$name\",\"transcribe_enabled\":$transcribe,\"voice_agent_enabled\":$voice_agent}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','ERR'))" 2>/dev/null
}

wait_for_bot() {
  local bot_id=$1 timeout=${2:-90}
  local start=$SECONDS
  # Look up container ID from DB
  local cid
  cid=$(psql "$PG_URL" -t -c "SELECT bot_container_id FROM meetings WHERE id=$bot_id;" 2>/dev/null | tr -d ' ')
  while (( SECONDS - start < timeout )); do
    local container
    if [ -n "$cid" ]; then
      container=$(docker ps --format "{{.Names}}" --filter "id=$cid" 2>/dev/null | head -1)
    fi
    if [ -z "$container" ]; then
      # Fallback: re-query DB in case container was created after initial lookup
      cid=$(psql "$PG_URL" -t -c "SELECT bot_container_id FROM meetings WHERE id=$bot_id;" 2>/dev/null | tr -d ' ')
      container=$(docker ps --format "{{.Names}}" --filter "id=$cid" 2>/dev/null | head -1)
    fi
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

REDIS_MODULE_PATH="$(find /home/dima/dev/vexa-agentic-runtime/services -path '*/node_modules/redis/dist/index.js' -maxdepth 5 | head -1 | xargs dirname | xargs dirname)"

send_command() {
  local meeting_id=$1 payload=$2
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
  local cid=$(psql "$PG_URL" -t -c "SELECT bot_container_id FROM meetings WHERE id=$bot_id;" 2>/dev/null | tr -d ' ')
  local c=$(docker ps --format "{{.Names}}" --filter "id=$cid" 2>/dev/null | head -1)
  [ -n "$c" ] && docker stop "$c" 2>/dev/null || true
  psql "$PG_URL" -c \
    "UPDATE meetings SET status='stopped', end_time=NOW() WHERE id=$bot_id AND status IN ('requested','active','awaiting_admission','joining');" 2>/dev/null || true
}

# ─── Meeting setup ────────────────────────────────────────────────────────────

if [ -z "$MEETING_ID" ]; then
  if [ -z "$CDP_URL" ]; then
    echo "ERROR: Set CDP_URL or MEETING_ID"
    exit 1
  fi
  log "Creating Google Meet..."
  MEETING_OUTPUT=$(CDP_URL="$CDP_URL" node "$SCRIPTS/gmeet-host-auto.js" 2>&1)
  MEETING_ID=$(echo "$MEETING_OUTPUT" | grep "NATIVE_MEETING_ID=" | cut -d= -f2)
  if [ -z "$MEETING_ID" ]; then
    echo "Failed: $MEETING_OUTPUT"
    exit 1
  fi
  node "$SCRIPTS/auto-admit.js" "$CDP_URL" &
  ADMIT_PID=$!
  sleep 3
fi

log "Meeting: https://meet.google.com/$MEETING_ID"
echo "$MEETING_ID" > "$RESULTS/meeting-id.txt"

# ─── Phase 1: Deploy bots ────────────────────────────────────────────────────

log "Sending Recorder bot..."
RECORDER_ID=$(send_bot "Recorder" "$TOKEN_RECORDER" "$MEETING_ID" true)
log "  Recorder=$RECORDER_ID"

RECORDER_CONTAINER=$(wait_for_bot "$RECORDER_ID" 90)
if [ -z "$RECORDER_CONTAINER" ]; then
  log "ERROR: Recorder did not join"; exit 1
fi
log "  Recorder joined: $RECORDER_CONTAINER"

# Get session_uid for later DB query
sleep 5
SESSION_UID=$(docker logs "$RECORDER_CONTAINER" 2>&1 | grep -oP 'session_uid[=: ]+\K[a-f0-9-]+' | head -1 || true)
if [ -z "$SESSION_UID" ]; then
  SESSION_UID=$(psql "$PG_URL" -t -c \
    "SELECT session_uid FROM meeting_sessions WHERE meeting_id=$RECORDER_ID ORDER BY id DESC LIMIT 1;" 2>/dev/null | tr -d ' ')
fi
log "  Session UID: $SESSION_UID"
echo "$SESSION_UID" > "$RESULTS/session-uid.txt"

log "Sending speaker bots..."
ALICE_ID=$(send_bot "Alice" "$TOKEN_ALICE" "$MEETING_ID" false true)
BOB_ID=$(send_bot "Bob" "$TOKEN_BOB" "$MEETING_ID" false true)
CHARLIE_ID=$(send_bot "Charlie" "$TOKEN_CHARLIE" "$MEETING_ID" false true)
log "  Alice=$ALICE_ID Bob=$BOB_ID Charlie=$CHARLIE_ID"

wait_for_bot "$ALICE_ID" 90 > /dev/null
wait_for_bot "$BOB_ID" 90 > /dev/null
wait_for_bot "$CHARLIE_ID" 90 > /dev/null
log "  All bots joined"

log "Waiting 20s for audio capture to initialize..."
sleep 20

# ─── Phase 2: Execute ground truth script ────────────────────────────────────

log "Executing ground truth script (9 utterances)..."

# Read ground truth and send TTS commands sequentially
python3 -c "
import json, sys
gt = json.load(open('$RESULTS/ground-truth.json'))
for i, entry in enumerate(gt):
    speaker = entry['speaker']
    text = entry['text']
    pause = entry['pause']
    # Map speaker to bot ID
    bot_ids = {'Alice': '$ALICE_ID', 'Bob': '$BOB_ID', 'Charlie': '$CHARLIE_ID'}
    bot_id = bot_ids[speaker]
    print(f'{bot_id}|{text}|{pause}')
" | while IFS='|' read -r bot_id text pause; do
  speaker=$(python3 -c "ids={'$ALICE_ID':'Alice','$BOB_ID':'Bob','$CHARLIE_ID':'Charlie'}; print(ids.get('$bot_id','?'))" 2>/dev/null || echo "?")
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

log "Waiting 35s for immutability threshold (30s + buffer)..."
sleep 35

log "Fetching segments from Postgres..."
psql "$PG_URL" \
  -c "COPY (
    SELECT segment_id, speaker, text, start_time, end_time, language, created_at
    FROM transcriptions
    WHERE session_uid = '$SESSION_UID'
    ORDER BY start_time
  ) TO STDOUT WITH CSV HEADER;" > "$RESULTS/db-segments.csv" 2>/dev/null

DB_COUNT=$(tail -n +2 "$RESULTS/db-segments.csv" | wc -l | tr -d ' ')
log "  DB segments: $DB_COUNT"

# Also capture confirmed segments from bot logs
grep "CONFIRMED" "$RESULTS/recorder-full.log" | python3 -c "
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
" 2>/dev/null

# ─── Phase 4: Score ──────────────────────────────────────────────────────────

log "Scoring..."
python3 "$DIR/score-e2e.py" "$RESULTS" 2>&1 | tee "$RESULTS/score.txt"

# ─── Cleanup ──────────────────────────────────────────────────────────────────

log "Cleaning up bots..."
stop_bot "$ALICE_ID"
stop_bot "$BOB_ID"
stop_bot "$CHARLIE_ID"
stop_bot "$RECORDER_ID"
kill ${ADMIT_PID:-0} 2>/dev/null || true

log ""
log "Results: $RESULTS"
