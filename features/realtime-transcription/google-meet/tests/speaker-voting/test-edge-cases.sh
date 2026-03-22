#!/bin/bash
# Speaker voting edge case tests — stress the hardest attribution scenarios.
#
# Edge cases tested:
#   1. Simultaneous speech — two bots speak at the same time
#   2. Rapid leave/rejoin — bot leaves and rejoins quickly
#   3. Short utterances — very brief speech (1-2 seconds)
#   4. Back-to-back speakers — no gap between speakers
#   5. All speak after invalidation — everyone speaks after a leave event
#
# Usage:
#   ./test-edge-cases.sh --meeting abc-defg-hij
#   CDP_URL=http://IP:9223 ./test-edge-cases.sh

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/../../../.env"
SCRIPTS="$DIR/../../../scripts"
RESULTS="$DIR/results/edge-$(date +%Y-%m-%d-%H%M%S)"

source "$ENV_FILE"

MEETING_ID="${MEETING_ID:-}"
CDP_URL="${CDP_URL:-}"
REDIS_URL="${REDIS_URL:-redis://172.25.0.2:6379}"
API_URL="${API_GATEWAY_URL:-http://localhost:8066}"

TOKEN_RECORDER="${API_TOKEN}"
TOKEN_ALICE="${TOKEN_ALICE:-vxa_user_JbJzIlIz5R60I4v4orayS02Pz3iW7lLFE4Mc3hVS}"
TOKEN_BOB="${TOKEN_BOB:-vxa_user_MTHCuOGLJXJj5xDLpmGjPbLRN784SzIsImuX8OcQ}"
TOKEN_CHARLIE="${TOKEN_CHARLIE:-vxa_user_6XwdTtVpZon3MvuYo5R568AFYTv6YOA9gfTkAEMq}"

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
  echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','ERR'))" 2>/dev/null
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

snapshot_recorder() {
  local container=$1 phase_dir=$2
  mkdir -p "$phase_dir"
  docker logs "$container" 2>&1 > "$phase_dir/recorder-full.log"
  docker logs "$container" 2>&1 | grep -E "SpeakerIdentity|NEW SPEAKER|SPEAKER MAPPED|SPEAKER ACTIVE|LOCKED|Participant count|mappings cleared|PerSpeaker|CONFIRMED" \
    > "$phase_dir/speaker-events.log" 2>/dev/null || true
}

validate_phase() {
  local phase_dir=$1 phase_name=$2 expected_speakers=$3
  log "Validating $phase_name..."
  python3 "$DIR/score.py" "$phase_dir" "$expected_speakers" 2>&1 | tee "$phase_dir/score.txt"
}

stop_bot() {
  local bot_id=$1
  # Send leave command
  send_command "$bot_id" '{"action":"leave"}' || true
  sleep 2
  # Force stop container if still running
  local container
  container=$(docker ps --format "{{.Names}}" | grep "vexa-bot-${bot_id}-" 2>/dev/null || true)
  [ -n "$container" ] && docker stop "$container" 2>/dev/null || true
  # Mark as stopped in DB
  PGPASSWORD=postgres psql -h localhost -p 5448 -U postgres -d vexa_restore -c \
    "UPDATE meetings SET status='stopped', end_time=NOW() WHERE id=$bot_id AND status IN ('requested','active');" 2>/dev/null || true
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

# ─── Send recorder bot ───────────────────────────────────────────────────────

log "Sending Recorder bot..."
RECORDER_ID=$(send_bot "Recorder" "$TOKEN_RECORDER" "$MEETING_ID" true)
log "  Recorder → bot $RECORDER_ID"

log "Waiting for Recorder to join..."
RECORDER_CONTAINER=$(wait_for_bot "$RECORDER_ID" 90)
if [ -z "$RECORDER_CONTAINER" ]; then
  log "ERROR: Recorder did not join"
  exit 1
fi
log "  Recorder ready: $RECORDER_CONTAINER"
sleep 10

# ══════════════════════════════════════════════════════════════════════════════
# EDGE 1: Baseline — Sequential speech (establish correct mapping first)
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ EDGE 1: Baseline — sequential speech to establish mappings ═══"

log "Sending Alice, Bob, Charlie..."
ALICE_ID=$(send_bot "Alice" "$TOKEN_ALICE" "$MEETING_ID" false)
BOB_ID=$(send_bot "Bob" "$TOKEN_BOB" "$MEETING_ID" false)
CHARLIE_ID=$(send_bot "Charlie" "$TOKEN_CHARLIE" "$MEETING_ID" false)
log "  Alice=$ALICE_ID  Bob=$BOB_ID  Charlie=$CHARLIE_ID"

log "Waiting for bots to join..."
ALICE_C=$(wait_for_bot "$ALICE_ID" 90)
BOB_C=$(wait_for_bot "$BOB_ID" 90)
CHARLIE_C=$(wait_for_bot "$CHARLIE_ID" 90)
log "  All joined"

log "Waiting 20s for audio elements..."
sleep 20

log "Sequential speech to lock mappings..."
send_command "$ALICE_ID" '{"action":"speak","text":"Hello, this is Alice. I am establishing my voice track for the baseline test."}'
sleep 12

send_command "$BOB_ID" '{"action":"speak","text":"This is Bob. My track should be identified separately from Alice."}'
sleep 12

send_command "$CHARLIE_ID" '{"action":"speak","text":"Charlie here. Third speaker establishing the baseline mapping."}'
sleep 12

log "Waiting 10s for locks..."
sleep 10

snapshot_recorder "$RECORDER_CONTAINER" "$RESULTS/edge-1-baseline"
validate_phase "$RESULTS/edge-1-baseline" "Edge 1: Baseline" "Alice,Bob,Charlie"

# ══════════════════════════════════════════════════════════════════════════════
# EDGE 2: Simultaneous speech — two speakers talk at the same time
# Voting requires single speaker active. With two speaking, no votes
# should accumulate. Attribution should still be correct from prior lock.
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ EDGE 2: Simultaneous speech — Alice and Bob speak at same time ═══"

# Send both speak commands without waiting between them
send_command "$ALICE_ID" '{"action":"speak","text":"Alice speaking simultaneously with Bob. This tests whether the system handles overlapping speech correctly without misattributing segments."}'
sleep 1
send_command "$BOB_ID" '{"action":"speak","text":"Bob also speaking at the same time as Alice. The system should not confuse our identities during overlap."}'

# Wait for both to finish
sleep 20

snapshot_recorder "$RECORDER_CONTAINER" "$RESULTS/edge-2-simultaneous"
validate_phase "$RESULTS/edge-2-simultaneous" "Edge 2: Simultaneous" "Alice,Bob,Charlie"

# ══════════════════════════════════════════════════════════════════════════════
# EDGE 3: Short utterances — very brief speech
# Tests whether very short audio segments still get attributed correctly.
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ EDGE 3: Short utterances — rapid brief messages ═══"

send_command "$ALICE_ID" '{"action":"speak","text":"Yes."}'
sleep 5
send_command "$BOB_ID" '{"action":"speak","text":"No."}'
sleep 5
send_command "$CHARLIE_ID" '{"action":"speak","text":"Okay."}'
sleep 5
send_command "$ALICE_ID" '{"action":"speak","text":"Agreed."}'
sleep 5
send_command "$BOB_ID" '{"action":"speak","text":"Done."}'
sleep 10

snapshot_recorder "$RECORDER_CONTAINER" "$RESULTS/edge-3-short"
validate_phase "$RESULTS/edge-3-short" "Edge 3: Short utterances" "Alice,Bob,Charlie"

# ══════════════════════════════════════════════════════════════════════════════
# EDGE 4: Back-to-back speakers — no gap between speakers
# One finishes and next starts immediately. Tests transition handling.
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ EDGE 4: Back-to-back speakers — rapid transitions ═══"

send_command "$ALICE_ID" '{"action":"speak","text":"Alice starting a rapid handoff sequence now."}'
sleep 6
send_command "$BOB_ID" '{"action":"speak","text":"Bob picking up immediately after Alice stops."}'
sleep 6
send_command "$CHARLIE_ID" '{"action":"speak","text":"Charlie continuing the chain without any pause."}'
sleep 6
send_command "$ALICE_ID" '{"action":"speak","text":"Alice back again in rapid succession."}'
sleep 6
send_command "$BOB_ID" '{"action":"speak","text":"Bob finishing the rapid chain."}'
sleep 10

snapshot_recorder "$RECORDER_CONTAINER" "$RESULTS/edge-4-backtoback"
validate_phase "$RESULTS/edge-4-backtoback" "Edge 4: Back-to-back" "Alice,Bob,Charlie"

# ══════════════════════════════════════════════════════════════════════════════
# EDGE 5: Leave and rejoin — Charlie leaves, everyone speaks, Charlie rejoins
# After leave: invalidation, re-resolve with 2 speakers.
# After rejoin: second invalidation, re-resolve with 3 speakers.
# The critical test: does Charlie get correctly attributed after rejoin?
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ EDGE 5: Leave/rejoin — Charlie leaves then comes back ═══"

log "Charlie leaving..."
send_command "$CHARLIE_ID" '{"action":"leave"}'
sleep 10

log "Alice and Bob speak after Charlie's departure..."
send_command "$ALICE_ID" '{"action":"speak","text":"Alice speaking after Charlie left. Only two of us now."}'
sleep 12
send_command "$BOB_ID" '{"action":"speak","text":"Bob confirming after the leave. Two speakers remaining."}'
sleep 12

# Charlie rejoins (new bot, same name, different user token still)
log "Charlie rejoining..."
# First clean up old Charlie meeting record
stop_bot "$CHARLIE_ID"
sleep 3
CHARLIE_ID=$(send_bot "Charlie" "$TOKEN_CHARLIE" "$MEETING_ID" false)
log "  New Charlie=$CHARLIE_ID"
CHARLIE_C=$(wait_for_bot "$CHARLIE_ID" 90)
log "  Charlie rejoined: $CHARLIE_C"

log "Waiting 20s for elements to stabilize..."
sleep 20

log "All three speak after rejoin..."
send_command "$ALICE_ID" '{"action":"speak","text":"Alice here with Charlie back. Testing whether the system correctly identifies all three of us after the rejoin cycle."}'
sleep 12
send_command "$BOB_ID" '{"action":"speak","text":"Bob speaking after Charlie rejoined. My attribution should remain stable."}'
sleep 12
send_command "$CHARLIE_ID" '{"action":"speak","text":"Charlie is back after leaving and rejoining. The system should recognize me on my new track."}'
sleep 15

snapshot_recorder "$RECORDER_CONTAINER" "$RESULTS/edge-5-rejoin"
validate_phase "$RESULTS/edge-5-rejoin" "Edge 5: Leave/rejoin" "Alice,Bob,Charlie"

# ══════════════════════════════════════════════════════════════════════════════
# EDGE 6: Simultaneous speech right after invalidation
# The hardest case: someone leaves, then multiple people speak overlapping
# before the system has time to re-lock. Tests worst-case attribution.
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ EDGE 6: Overlap after invalidation — hardest case ═══"

log "Charlie leaving again to trigger invalidation..."
send_command "$CHARLIE_ID" '{"action":"leave"}'
sleep 8

log "Alice and Bob speak SIMULTANEOUSLY right after invalidation..."
send_command "$ALICE_ID" '{"action":"speak","text":"Alice speaking right after the invalidation event. This is the hardest case because locks were just cleared and multiple speakers are active."}'
send_command "$BOB_ID" '{"action":"speak","text":"Bob also speaking simultaneously right after invalidation. The system must handle this gracefully without cross-attributing our speech."}'
sleep 20

# Then sequential to re-establish
log "Sequential recovery speech..."
send_command "$ALICE_ID" '{"action":"speak","text":"Alice again, now speaking alone to help the system re-establish my track mapping."}'
sleep 12
send_command "$BOB_ID" '{"action":"speak","text":"Bob alone now. This sequential speech should allow re-locking."}'
sleep 15

# Stop old Charlie and clean up
stop_bot "$CHARLIE_ID"

snapshot_recorder "$RECORDER_CONTAINER" "$RESULTS/edge-6-overlap-invalidation"
validate_phase "$RESULTS/edge-6-overlap-invalidation" "Edge 6: Overlap after invalidation" "Alice,Bob"

# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════

log ""
log "═══ EDGE CASE TESTS COMPLETE ═══"
log "Results: $RESULTS"
log ""

PASS_COUNT=0
FAIL_COUNT=0
for edge in edge-1-baseline edge-2-simultaneous edge-3-short edge-4-backtoback edge-5-rejoin edge-6-overlap-invalidation; do
  if [ -f "$RESULTS/$edge/score.txt" ]; then
    overall=$(grep -o 'PASS\|FAIL' "$RESULTS/$edge/score.txt" | head -1)
    echo "  $edge: $overall"
    [ "$overall" = "PASS" ] && PASS_COUNT=$((PASS_COUNT + 1)) || FAIL_COUNT=$((FAIL_COUNT + 1))
  else
    echo "  $edge: NO RESULTS"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
done

echo ""
echo "Total: $PASS_COUNT PASS, $FAIL_COUNT FAIL out of 6 edge cases"

# Cleanup
stop_bot "$ALICE_ID"
stop_bot "$BOB_ID"
stop_bot "$RECORDER_ID"
kill ${ADMIT_PID:-0} 2>/dev/null || true
