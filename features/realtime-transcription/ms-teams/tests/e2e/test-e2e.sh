#!/bin/bash
# End-to-end MS Teams transcription pipeline test.
#
# Ground truth: Multiple bots speak known scripts via TTS into a live Teams meeting.
# Validation: fetch persisted segments from Postgres, compare against ground truth.
#
# Pipeline under test:
#   Bot TTS audio → Teams mixed stream → Recorder bot audio capture →
#   Caption-driven speaker routing → SpeakerStreamManager → Whisper →
#   SegmentPublisher → Redis → Collector → Postgres
#
# Key difference from Google Meet:
#   - Teams has ONE mixed audio stream (not per-speaker)
#   - Speaker identity comes from live captions (not DOM voting)
#   - Each speaker is a separate bot with its own API token
#   - TTS via REST /bots/teams/{meeting_id}/speak (not Redis commands)
#
# Usage:
#   ./test-e2e.sh --meeting 9378555217628 --passcode aPmMabx3MSJ
#   TEAMS_MEETING_ID=... TEAMS_PASSCODE=... ./test-e2e.sh

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/../../../.env"
SCRIPTS="$DIR/../../../scripts"
RESULTS="$DIR/results/e2e-$(date +%Y-%m-%d-%H%M%S)"

source "$ENV_FILE" 2>/dev/null || true

TEAMS_MEETING_ID="${TEAMS_MEETING_ID:-}"
TEAMS_PASSCODE="${TEAMS_PASSCODE:-}"
API_URL="${API_GATEWAY_URL:-http://localhost:8066}"

# Recorder uses the main API token; speakers use separate user tokens
TOKEN_RECORDER="${API_TOKEN:-vxa_user_pZqJ5dEQK47Mc7YeVTR53wAefBCs7Nf6d0fHbHs8}"
TOKEN_ALICE="${TOKEN_ALICE:-vxa_user_JbJzIlIz5R60I4v4orayS02Pz3iW7lLFE4Mc3hVS}"
TOKEN_BOB="${TOKEN_BOB:-vxa_user_MTHCuOGLJXJj5xDLpmGjPbLRN784SzIsImuX8OcQ}"
TOKEN_CHARLIE="${TOKEN_CHARLIE:-vxa_user_6XwdTtVpZon3MvuYo5R568AFYTv6YOA9gfTkAEMq}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --meeting) TEAMS_MEETING_ID="$2"; shift 2 ;;
    --passcode) TEAMS_PASSCODE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [ -z "$TEAMS_MEETING_ID" ]; then
  echo "ERROR: Set TEAMS_MEETING_ID or use --meeting"
  echo "  ./test-e2e.sh --meeting 9378555217628 --passcode aPmMabx3MSJ"
  echo ""
  echo "To create a Teams meeting automatically:"
  echo "  Use /host-teams-meeting-auto skill, or create via browser session"
  exit 1
fi

mkdir -p "$RESULTS"

# ─── Ground Truth Script ─────────────────────────────────────────────────────

cat > "$RESULTS/ground-truth.json" << 'GTEOF'
[
  {"speaker": "Alice", "voice": "nova", "text": "Welcome everyone to the quarterly planning meeting. I want to start by reviewing our progress on the mobile application redesign.", "pause": 14},
  {"speaker": "Bob", "voice": "echo", "text": "Thanks Alice. The mobile team completed the user authentication flow last week. We are now working on the dashboard components.", "pause": 14},
  {"speaker": "Charlie", "voice": "onyx", "text": "I have an update on the backend services. The new API endpoints are deployed to staging and load testing shows three thousand requests per second.", "pause": 14},
  {"speaker": "Alice", "voice": "nova", "text": "That is excellent progress. Charlie, can you share the timeline for production deployment?", "pause": 10},
  {"speaker": "Charlie", "voice": "onyx", "text": "We are targeting next Wednesday for the production rollout. The team needs two more days for integration testing.", "pause": 10},
  {"speaker": "Bob", "voice": "echo", "text": "I want to flag a dependency. The mobile app needs the new user profile endpoint before we can ship version two point zero.", "pause": 12},
  {"speaker": "Alice", "voice": "nova", "text": "Good point. Let us make sure that is prioritized. Any other blockers before we wrap up?", "pause": 10},
  {"speaker": "Charlie", "voice": "onyx", "text": "No blockers from my side. Everything is on track.", "pause": 8},
  {"speaker": "Bob", "voice": "echo", "text": "All clear here as well. Great meeting everyone.", "pause": 8}
]
GTEOF

log() { echo "[$(date +%H:%M:%S)] $*"; }

# ─── Helpers ──────────────────────────────────────────────────────────────────

send_teams_bot() {
  local name=$1 token=$2 meeting_id=$3 passcode=$4 transcribe=${5:-false}
  local body="{\"platform\":\"teams\",\"native_meeting_id\":\"$meeting_id\",\"bot_name\":\"$name\",\"transcribe_enabled\":$transcribe"
  if [ -n "$passcode" ]; then
    body="$body,\"passcode\":\"$passcode\""
  fi
  body="$body}"
  local resp
  resp=$(curl -s -X POST "$API_URL/bots" \
    -H "X-API-Key: $token" \
    -H "Content-Type: application/json" \
    -d "$body")
  echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','ERR'))" 2>/dev/null
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

speak_teams() {
  local token=$1 meeting_id=$2 text=$3 voice=${4:-nova}
  curl -s -X POST "$API_URL/bots/teams/$meeting_id/speak" \
    -H "X-API-Key: $token" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"$text\",\"voice\":\"$voice\"}" > /dev/null 2>&1
}

stop_bot() {
  local bot_id=$1
  local c=$(docker ps --format "{{.Names}}" | grep "vexa-bot-${bot_id}-" 2>/dev/null || true)
  [ -n "$c" ] && docker stop "$c" 2>/dev/null || true
  PGPASSWORD=postgres psql -h localhost -p 5448 -U postgres -d vexa_restore -c \
    "UPDATE meetings SET status='stopped', end_time=NOW() WHERE id=$bot_id AND status IN ('requested','active');" 2>/dev/null || true
}

log "Meeting: $TEAMS_MEETING_ID (passcode: ${TEAMS_PASSCODE:-none})"
echo "$TEAMS_MEETING_ID" > "$RESULTS/meeting-id.txt"

# ─── Phase 1: Deploy bots ────────────────────────────────────────────────────

log "Sending Recorder bot..."
RECORDER_ID=$(send_teams_bot "Recorder" "$TOKEN_RECORDER" "$TEAMS_MEETING_ID" "$TEAMS_PASSCODE" true)
if [ "$RECORDER_ID" = "ERR" ]; then
  log "ERROR: Failed to create recorder bot"
  exit 1
fi
log "  Recorder=$RECORDER_ID"

RECORDER_CONTAINER=$(wait_for_bot "$RECORDER_ID" 120)
if [ -z "$RECORDER_CONTAINER" ]; then
  log "ERROR: Recorder did not join within 120s"
  exit 1
fi
log "  Recorder joined: $RECORDER_CONTAINER"

# Get session_uid
sleep 5
SESSION_UID=$(PGPASSWORD=postgres psql -h localhost -p 5448 -U postgres -d vexa_restore -t -c \
  "SELECT session_uid FROM meeting_sessions WHERE meeting_id=$RECORDER_ID ORDER BY id DESC LIMIT 1;" 2>/dev/null | tr -d ' ')
log "  Session UID: $SESSION_UID"
echo "$SESSION_UID" > "$RESULTS/session-uid.txt"

log "Sending speaker bots..."
ALICE_ID=$(send_teams_bot "Alice" "$TOKEN_ALICE" "$TEAMS_MEETING_ID" "$TEAMS_PASSCODE" false)
BOB_ID=$(send_teams_bot "Bob" "$TOKEN_BOB" "$TEAMS_MEETING_ID" "$TEAMS_PASSCODE" false)
CHARLIE_ID=$(send_teams_bot "Charlie" "$TOKEN_CHARLIE" "$TEAMS_MEETING_ID" "$TEAMS_PASSCODE" false)
log "  Alice=$ALICE_ID Bob=$BOB_ID Charlie=$CHARLIE_ID"

# Teams bots take longer to join (lobby, permissions)
wait_for_bot "$ALICE_ID" 120 > /dev/null
wait_for_bot "$BOB_ID" 120 > /dev/null
wait_for_bot "$CHARLIE_ID" 120 > /dev/null
log "  All bots joined"

log "Waiting 15s for audio + captions to initialize..."
sleep 15

# ─── Phase 2: Execute ground truth script ────────────────────────────────────

log "Executing ground truth script (9 utterances)..."

python3 -c "
import json
gt = json.load(open('$RESULTS/ground-truth.json'))
for entry in gt:
    speaker = entry['speaker']
    text = entry['text']
    voice = entry.get('voice', 'nova')
    pause = entry['pause']
    tokens = {'Alice': '$TOKEN_ALICE', 'Bob': '$TOKEN_BOB', 'Charlie': '$TOKEN_CHARLIE'}
    print(f'{tokens[speaker]}|{voice}|{text}|{pause}|{speaker}')
" | while IFS='|' read -r token voice text pause speaker; do
  log "  $speaker ($voice): \"${text:0:60}...\""
  speak_teams "$token" "$TEAMS_MEETING_ID" "$text" "$voice"
  sleep "$pause"
done

log "All utterances sent. Waiting 30s for transcription + confirmation..."
sleep 30

# ─── Phase 3: Capture pipeline output ────────────────────────────────────────

log "Capturing recorder logs..."
docker logs "$RECORDER_CONTAINER" 2>&1 > "$RESULTS/recorder-full.log"
docker logs "$RECORDER_CONTAINER" 2>&1 | grep "CONFIRMED" > "$RESULTS/confirmed-segments.log" 2>/dev/null || true

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

# Parse bot segments
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

# Reuse the same scorer from Google Meet e2e (it's platform-agnostic)
SCORER="$DIR/../../../google-meet/tests/e2e/score-e2e.py"
if [ ! -f "$SCORER" ]; then
  # Fallback: check if it's in our own dir
  SCORER="$DIR/score-e2e.py"
fi

log "Scoring..."
python3 "$SCORER" "$RESULTS" 2>&1 | tee "$RESULTS/score.txt"

# ─── Cleanup ──────────────────────────────────────────────────────────────────

log "Cleaning up bots..."
stop_bot "$ALICE_ID"
stop_bot "$BOB_ID"
stop_bot "$CHARLIE_ID"
stop_bot "$RECORDER_ID"

log ""
log "Results: $RESULTS"
