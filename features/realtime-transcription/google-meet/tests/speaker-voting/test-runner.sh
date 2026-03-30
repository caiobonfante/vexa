#!/bin/bash
# Speaker voting test — phased join/speak/leave/rejoin cycle.
#
# Tests the track-to-speaker voting mechanism by controlling exactly
# when each bot speaks, leaves, and joins. Uses TTS (speak command via Redis)
# instead of audio file playback.
#
# Usage:
#   CDP_URL=http://localhost:8066/b/TOKEN/cdp ./test-runner.sh
#   ./test-runner.sh --meeting abc-defg-hij
#
# Environment:
#   CDP_URL      — browser session for meeting creation + auto-admit
#   MEETING_ID   — reuse existing meeting (skip creation)
#   REDIS_URL    — Redis for sending commands (default: redis://172.25.0.2:6379)

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/../../../.env"
SCRIPTS="$DIR/../../../scripts"
RESULTS="$DIR/results/run-$(date +%Y-%m-%d-%H%M%S)"

source "$ENV_FILE"

MEETING_ID="${MEETING_ID:-}"
CDP_URL="${CDP_URL:-}"
REDIS_URL="${REDIS_URL:-redis://172.25.0.2:6379}"
API_URL="${API_GATEWAY_URL:-http://localhost:8066}"

# Tokens — each bot needs a different user to avoid per-user "active meeting" limit
TOKEN_RECORDER="${API_TOKEN}"
TOKEN_ALICE="${TOKEN_ALICE:-vxa_user_JbJzIlIz5R60I4v4orayS02Pz3iW7lLFE4Mc3hVS}"     # SpeakerA
TOKEN_BOB="${TOKEN_BOB:-vxa_user_MTHCuOGLJXJj5xDLpmGjPbLRN784SzIsImuX8OcQ}"         # SpeakerB
TOKEN_CHARLIE="${TOKEN_CHARLIE:-vxa_user_6XwdTtVpZon3MvuYo5R568AFYTv6YOA9gfTkAEMq}"  # SpeakerC
TOKEN_DAVE="${TOKEN_DAVE:-vxa_user_W8IAsiAZwowDYCnuOK2uSXTwQSEYHh1z67hnU5pe}"       # SpeakerD
TOKEN_EVE="${TOKEN_EVE:-vxa_user_f44my6ph4F6rPt2MATh3ZmpLixLy7bXBhZKYUKGN}"         # SpeakerE

while [[ $# -gt 0 ]]; do
  case $1 in
    --meeting) MEETING_ID="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

mkdir -p "$RESULTS"

# ─── Helpers ──────────────────────────────────────────────────────────────────

log() { echo "[$(date +%H:%M:%S)] $*"; }

send_bot() {
  local name=$1 token=$2 meeting=$3 transcribe=${4:-false}
  local resp
  resp=$(curl -s -X POST "$API_URL/bots" \
    -H "X-API-Key: $token" \
    -H "Content-Type: application/json" \
    -d "{\"platform\":\"google_meet\",\"native_meeting_id\":\"$meeting\",\"bot_name\":\"$name\",\"transcribe_enabled\":$transcribe}")
  local bot_id
  bot_id=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','ERR'))" 2>/dev/null)
  echo "$bot_id"
}

wait_for_bot() {
  local bot_id=$1 timeout=${2:-90}
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

get_container() {
  local bot_id=$1
  docker ps --format "{{.Names}}" | grep "vexa-bot-${bot_id}-" 2>/dev/null || true
}

# Send a command to a bot via Redis
REDIS_MODULE_PATH="$(find /home/dima/dev/vexa-restore/services -path '*/node_modules/redis/dist/index.js' -maxdepth 5 | head -1 | xargs dirname | xargs dirname)"

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

# Send TTS speak command to a specific bot
speak() {
  local meeting_id=$1 text=$2
  send_command "$meeting_id" "{\"action\":\"speak\",\"text\":\"$text\"}"
}

# Send leave command
leave_bot() {
  local meeting_id=$1
  send_command "$meeting_id" '{"action":"leave"}'
}

# Snapshot recorder logs at this point
snapshot_recorder() {
  local container=$1 phase_dir=$2
  mkdir -p "$phase_dir"
  docker logs "$container" 2>&1 > "$phase_dir/recorder-full.log"
  docker logs "$container" 2>&1 | grep -E "SpeakerIdentity|NEW SPEAKER|SPEAKER MAPPED|SPEAKER ACTIVE|LOCKED|Participant count|mappings cleared|PerSpeaker|CONFIRMED" \
    > "$phase_dir/speaker-events.log" 2>/dev/null || true
}

# Validate phase results
validate_phase() {
  local phase_dir=$1 phase_name=$2 expected_speakers=$3
  log "Validating $phase_name..."
  python3 "$DIR/score.py" "$phase_dir" "$expected_speakers" 2>&1 | tee "$phase_dir/score.txt"
}

# ─── Meeting setup ────────────────────────────────────────────────────────────

if [ -z "$MEETING_ID" ]; then
  if [ -z "$CDP_URL" ]; then
    echo "ERROR: Set CDP_URL or MEETING_ID"
    echo "  CDP_URL=http://localhost:8066/b/TOKEN/cdp ./test-runner.sh"
    echo "  ./test-runner.sh --meeting abc-defg-hij"
    exit 1
  fi

  log "Creating Google Meet..."
  MEETING_OUTPUT=$(CDP_URL="$CDP_URL" node "$SCRIPTS/gmeet-host-auto.js" 2>&1)
  MEETING_ID=$(echo "$MEETING_OUTPUT" | grep "NATIVE_MEETING_ID=" | cut -d= -f2)
  if [ -z "$MEETING_ID" ]; then
    echo "Failed to create meeting:"
    echo "$MEETING_OUTPUT"
    exit 1
  fi

  log "Starting auto-admit..."
  node "$SCRIPTS/auto-admit.js" "$CDP_URL" &
  ADMIT_PID=$!
  sleep 3
fi

log "Meeting: https://meet.google.com/$MEETING_ID"
echo "$MEETING_ID" > "$RESULTS/meeting-id.txt"

# ─── Send recorder bot first ─────────────────────────────────────────────────

log "Sending Recorder bot..."
RECORDER_ID=$(send_bot "Recorder" "$TOKEN_RECORDER" "$MEETING_ID" true)
log "  Recorder → bot $RECORDER_ID"

# Get the meeting_id that the bot uses internally (numeric, from meeting-api)
# The Redis command channel uses this numeric ID
RECORDER_MEETING_ID="$RECORDER_ID"

log "Waiting for Recorder to join..."
RECORDER_CONTAINER=$(wait_for_bot "$RECORDER_ID" 90)
if [ -z "$RECORDER_CONTAINER" ]; then
  log "ERROR: Recorder did not join"
  exit 1
fi
log "  Recorder ready: $RECORDER_CONTAINER"

# Wait for audio capture to initialize
sleep 10

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1: Join 3 + Speak + Validate
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ PHASE 1: Join 3 speakers, each speaks, validate locks ═══"

log "Sending Alice, Bob, Charlie..."
ALICE_ID=$(send_bot "Alice" "$TOKEN_ALICE" "$MEETING_ID" false)
BOB_ID=$(send_bot "Bob" "$TOKEN_BOB" "$MEETING_ID" false)
CHARLIE_ID=$(send_bot "Charlie" "$TOKEN_CHARLIE" "$MEETING_ID" false)
log "  Alice=$ALICE_ID  Bob=$BOB_ID  Charlie=$CHARLIE_ID"

log "Waiting for bots to join..."
ALICE_C=$(wait_for_bot "$ALICE_ID" 90)
BOB_C=$(wait_for_bot "$BOB_ID" 90)
CHARLIE_C=$(wait_for_bot "$CHARLIE_ID" 90)
log "  Alice=$ALICE_C"
log "  Bob=$BOB_C"
log "  Charlie=$CHARLIE_C"

# Wait for per-speaker audio capture to discover all elements
log "Waiting 20s for audio elements to stabilize..."
sleep 20

# Speak sequentially — each bot uses its own meeting_id for the Redis command
# But the command channel uses the meeting_id from meeting-api (numeric)
# Actually, the command goes to bot_commands:meeting:{meeting_id} where meeting_id
# is the DB meeting row ID. All bots in the same meeting share the channel.
# We need to target specific bots — but speak commands are broadcast to all.
# Only bots with TTS_SERVICE_URL + speaking capability will respond.
# Speaker bots have transcribe_enabled:false but still have TTS.
#
# PROBLEM: speak command is broadcast. All bots in the meeting hear it.
# We need the SPECIFIC bot to speak. Use meeting_id of the specific bot.

log "Alice speaks..."
# Each bot has its own meeting_id (the bot's ID in meeting-api DB)
send_command "$ALICE_ID" '{"action":"speak","text":"Hello, my name is Alice. I am testing the speaker identification system. This is a longer sentence to give the voting system enough time to accumulate votes and lock my track."}'
sleep 15

log "Bob speaks..."
send_command "$BOB_ID" '{"action":"speak","text":"This is Bob speaking now. I have a different voice and I want to make sure the system correctly identifies me as a separate speaker from Alice."}'
sleep 15

log "Charlie speaks..."
send_command "$CHARLIE_ID" '{"action":"speak","text":"Charlie here. I am the third speaker in this test. The voting system should create a third track and lock it to my name."}'
sleep 15

# Wait for locks to settle
log "Waiting 10s for locks to settle..."
sleep 10

# Snapshot and validate
snapshot_recorder "$RECORDER_CONTAINER" "$RESULTS/phase-1"
validate_phase "$RESULTS/phase-1" "Phase 1" "Alice,Bob,Charlie"

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2: Charlie leaves, Alice and Bob speak, validate
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ PHASE 2: Charlie leaves, 2 remaining speak, validate re-lock ═══"

log "Sending leave command to Charlie..."
send_command "$CHARLIE_ID" '{"action":"leave"}'
sleep 15  # Wait for Charlie to leave and participant count to change

log "Recording log line count before Phase 2 speaking..."
PHASE2_LOG_MARKER=$(docker logs "$RECORDER_CONTAINER" 2>&1 | wc -l)

log "Alice speaks again..."
send_command "$ALICE_ID" '{"action":"speak","text":"Alice here again after Charlie left. The system should have cleared all locks when it detected the participant count change. Now it needs to re-vote and re-lock my track."}'
sleep 15

log "Bob speaks again..."
send_command "$BOB_ID" '{"action":"speak","text":"Bob speaking after the leave event. My track should get re-locked to my name. The voting system needs to handle track reassignment correctly."}'
sleep 15

# Wait for re-locks
log "Waiting 10s for re-locks..."
sleep 10

# Snapshot and validate
snapshot_recorder "$RECORDER_CONTAINER" "$RESULTS/phase-2"
validate_phase "$RESULTS/phase-2" "Phase 2" "Alice,Bob"

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3: Dave and Eve join, all 4 speak, validate
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ PHASE 3: Dave and Eve join, all 4 speak, validate ═══"

log "Sending Dave, Eve..."
DAVE_ID=$(send_bot "Dave" "$TOKEN_DAVE" "$MEETING_ID" false)
EVE_ID=$(send_bot "Eve" "$TOKEN_EVE" "$MEETING_ID" false)
log "  Dave=$DAVE_ID  Eve=$EVE_ID"

log "Waiting for new bots to join..."
DAVE_C=$(wait_for_bot "$DAVE_ID" 90)
EVE_C=$(wait_for_bot "$EVE_ID" 90)
log "  Dave=$DAVE_C"
log "  Eve=$EVE_C"

# Wait for audio elements to stabilize
log "Waiting 20s for audio elements to stabilize..."
sleep 20

log "Alice speaks..."
send_command "$ALICE_ID" '{"action":"speak","text":"Alice speaking with four people now. Two new participants have joined and the system needs to discover their tracks."}'
sleep 15

log "Bob speaks..."
send_command "$BOB_ID" '{"action":"speak","text":"Bob here in the larger group. The voting system should handle the increased number of tracks correctly."}'
sleep 15

log "Dave speaks..."
send_command "$DAVE_ID" '{"action":"speak","text":"I am Dave, a new participant. The system has never seen me before and needs to create a fresh track mapping for my voice."}'
sleep 15

log "Eve speaks..."
send_command "$EVE_ID" '{"action":"speak","text":"Eve joining the conversation. I am the fifth speaker overall and the second new joiner. My track should lock independently."}'
sleep 15

# Wait for locks
log "Waiting 10s for locks..."
sleep 10

# Snapshot and validate
snapshot_recorder "$RECORDER_CONTAINER" "$RESULTS/phase-3"
validate_phase "$RESULTS/phase-3" "Phase 3" "Alice,Bob,Dave,Eve"

# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ TEST COMPLETE ═══"
log "Results: $RESULTS"
log ""

# Print summary of all phases
for phase in 1 2 3; do
  if [ -f "$RESULTS/phase-$phase/score.txt" ]; then
    echo "--- Phase $phase ---"
    cat "$RESULTS/phase-$phase/score.txt"
    echo ""
  fi
done

# Cleanup
kill ${ADMIT_PID:-0} 2>/dev/null || true
