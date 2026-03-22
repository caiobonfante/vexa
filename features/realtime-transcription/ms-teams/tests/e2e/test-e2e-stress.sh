#!/bin/bash
# Teams Stress E2E test — realistic meeting with long monologues, technical jargon, etc.
#
# Usage:
#   ./test-e2e-stress.sh --meeting 9381798594528 --passcode ceUIpyzx0FlxFnDUQX

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/../../../.env"
RESULTS="$DIR/results/stress-$(date +%Y-%m-%d-%H%M%S)"
SCORER="$DIR/../../../google-meet/tests/e2e/score-e2e.py"

source "$ENV_FILE" 2>/dev/null || true

TEAMS_MEETING_ID="${TEAMS_MEETING_ID:-}"
TEAMS_PASSCODE="${TEAMS_PASSCODE:-}"
API_URL="${API_GATEWAY_URL:-http://localhost:8066}"

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

[ -z "$TEAMS_MEETING_ID" ] && echo "ERROR: --meeting required" && exit 1
[ -z "$TEAMS_PASSCODE" ] && echo "ERROR: --passcode required" && exit 1

mkdir -p "$RESULTS"

# ─── Ground Truth (same realistic meeting script) ────────────────────────────

cat > "$RESULTS/ground-truth.json" << 'GTEOF'
[
  {"speaker": "Alice", "voice": "nova", "text": "Good morning everyone. Before we dive into the agenda I want to acknowledge the fantastic work the team did last sprint. We shipped the authentication overhaul three days ahead of schedule and the error rate dropped from two point five percent down to zero point three percent. That is a significant improvement and I want to make sure we celebrate that.", "pause": 30},
  {"speaker": "Bob", "voice": "echo", "text": "Thanks Alice. The auth team really pulled together on that one. I do want to flag that we discovered a regression in the OAuth two point zero token refresh flow during our load testing yesterday. Under sustained traffic of about fifteen hundred requests per second the token cache starts evicting entries prematurely.", "pause": 27},
  {"speaker": "Alice", "voice": "nova", "text": "How critical is that? Are we seeing it in production?", "pause": 7},
  {"speaker": "Bob", "voice": "echo", "text": "Not yet. It only manifests above twelve hundred requests per second and our current peak is around eight hundred. But with the holiday season coming we could hit that threshold.", "pause": 16},
  {"speaker": "Charlie", "voice": "onyx", "text": "I can jump in here. I reviewed the token cache implementation yesterday. The issue is in the LRU eviction policy. We are using a fixed size of ten thousand entries but each entry now includes the refresh token metadata which doubled the memory footprint. My recommendation is to switch to a time based expiration with a thirty minute TTL instead of the LRU approach.", "pause": 31},
  {"speaker": "Alice", "voice": "nova", "text": "That sounds reasonable. Charlie can you put together a design document by end of day Thursday? I want to review it before we commit engineering resources.", "pause": 14},
  {"speaker": "Charlie", "voice": "onyx", "text": "Yes absolutely. I will have it ready by Thursday noon so you have time to review before the Friday planning session.", "pause": 12},
  {"speaker": "Bob", "voice": "echo", "text": "Agreed.", "pause": 4},
  {"speaker": "Alice", "voice": "nova", "text": "Perfect.", "pause": 4},
  {"speaker": "Bob", "voice": "echo", "text": "Moving on to the infrastructure update. We completed the migration from AWS US East One to a multi region setup. We now have active active deployments in US East One, EU West One, and AP Southeast One. Latency for European users dropped from two hundred and forty milliseconds to sixty five milliseconds. For Asia Pacific users it went from three hundred and eighty milliseconds down to ninety milliseconds.", "pause": 34},
  {"speaker": "Alice", "voice": "nova", "text": "Those are impressive numbers. What is the cost impact?", "pause": 7},
  {"speaker": "Bob", "voice": "echo", "text": "Monthly infrastructure cost went up by about forty two percent from eighteen thousand dollars to roughly twenty five thousand six hundred dollars. But we are projecting a fifteen percent reduction in churn for international users which more than offsets the cost increase.", "pause": 23},
  {"speaker": "Charlie", "voice": "onyx", "text": "I want to add some context on the database side. We are running PostgreSQL fifteen with logical replication across the three regions. Write latency for cross region operations is averaging about one hundred and twenty milliseconds which is within our SLA of two hundred milliseconds. The replication lag is consistently under five seconds.", "pause": 29},
  {"speaker": "Alice", "voice": "nova", "text": "Excellent. Now let me walk through the product roadmap for Q2. We have four major initiatives. First is the real time collaboration feature which Bob's team is leading. Second is the mobile app redesign targeting iOS seventeen and Android fourteen. Third is the enterprise SSO integration with support for SAML two point zero and OpenID Connect. And fourth is the analytics dashboard rebuild using React eighteen with server side rendering for improved performance. Each of these has a dedicated squad and I want weekly status updates starting next Monday.", "pause": 45},
  {"speaker": "Bob", "voice": "echo", "text": "For the collaboration feature we are planning to use WebSockets with a fallback to server sent events. The initial prototype is working with up to fifty concurrent users in a single session. We need to stress test it to our target of five hundred concurrent users before the beta launch on April fifteenth.", "pause": 26},
  {"speaker": "Charlie", "voice": "onyx", "text": "On the enterprise SSO front I have been evaluating three identity providers. Okta, Azure Active Directory, and OneLogin. All three support SAML two point zero but the OpenID Connect implementations vary significantly. I recommend we start with Okta integration since sixty percent of our enterprise prospects already use it.", "pause": 27},
  {"speaker": "Alice", "voice": "nova", "text": "Good analysis Charlie. Let us go with Okta first and add Azure AD in the following sprint. Any other topics before we wrap up?", "pause": 13},
  {"speaker": "Bob", "voice": "echo", "text": "One more thing. The candidate we interviewed last week for the senior backend role accepted our offer. She starts on April first. Her name is Sarah Chen and she has twelve years of experience with distributed systems at Google and Stripe.", "pause": 21},
  {"speaker": "Charlie", "voice": "onyx", "text": "That is great news. We have been understaffed on the backend team for months. Looking forward to having her on board.", "pause": 12},
  {"speaker": "Alice", "voice": "nova", "text": "Wonderful. Let us make sure her onboarding is smooth. I will send out the agenda for next week. Thanks everyone for a productive meeting.", "pause": 13}
]
GTEOF

log() { echo "[$(date +%H:%M:%S)] $*"; }

# ─── Helpers ──────────────────────────────────────────────────────────────────

send_teams_bot() {
  local name=$1 token=$2 meeting_id=$3 passcode=$4 transcribe=${5:-false}
  curl -s -X POST "$API_URL/bots" \
    -H "X-API-Key: $token" \
    -H "Content-Type: application/json" \
    -d "{\"platform\":\"teams\",\"native_meeting_id\":\"$meeting_id\",\"bot_name\":\"$name\",\"transcribe_enabled\":$transcribe,\"passcode\":\"$passcode\"}" \
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

log "Meeting: $TEAMS_MEETING_ID (passcode: $TEAMS_PASSCODE)"
echo "$TEAMS_MEETING_ID" > "$RESULTS/meeting-id.txt"

# ─── Deploy bots ──────────────────────────────────────────────────────────────

log "Sending Recorder..."
RECORDER_ID=$(send_teams_bot "Recorder" "$TOKEN_RECORDER" "$TEAMS_MEETING_ID" "$TEAMS_PASSCODE" true)
[ "$RECORDER_ID" = "ERR" ] && log "ERROR: Recorder failed" && exit 1
RECORDER_CONTAINER=$(wait_for_bot "$RECORDER_ID" 120)
[ -z "$RECORDER_CONTAINER" ] && log "ERROR: Recorder timeout" && exit 1
log "  Recorder: $RECORDER_CONTAINER"

sleep 5
SESSION_UID=$(PGPASSWORD=postgres psql -h localhost -p 5448 -U postgres -d vexa_restore -t -c \
  "SELECT session_uid FROM meeting_sessions WHERE meeting_id=$RECORDER_ID ORDER BY id DESC LIMIT 1;" 2>/dev/null | tr -d ' ')
echo "$SESSION_UID" > "$RESULTS/session-uid.txt"
log "  Session: $SESSION_UID"

log "Sending speakers..."
ALICE_ID=$(send_teams_bot "Alice" "$TOKEN_ALICE" "$TEAMS_MEETING_ID" "$TEAMS_PASSCODE" false)
BOB_ID=$(send_teams_bot "Bob" "$TOKEN_BOB" "$TEAMS_MEETING_ID" "$TEAMS_PASSCODE" false)
CHARLIE_ID=$(send_teams_bot "Charlie" "$TOKEN_CHARLIE" "$TEAMS_MEETING_ID" "$TEAMS_PASSCODE" false)
log "  Alice=$ALICE_ID Bob=$BOB_ID Charlie=$CHARLIE_ID"

wait_for_bot "$ALICE_ID" 120 > /dev/null
wait_for_bot "$BOB_ID" 120 > /dev/null
wait_for_bot "$CHARLIE_ID" 120 > /dev/null
log "  All joined"

log "Waiting 15s for audio + captions..."
sleep 15

# ─── Execute ground truth ─────────────────────────────────────────────────────

GT_COUNT=$(python3 -c "import json; print(len(json.load(open('$RESULTS/ground-truth.json'))))")
log "Executing ground truth ($GT_COUNT utterances)..."

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
  log "  $speaker (${#text} chars, ${pause}s)"
  speak_teams "$token" "$TEAMS_MEETING_ID" "$text" "$voice"
  sleep "$pause"
done

log "All sent. Waiting 45s..."
sleep 45

# ─── Capture output ───────────────────────────────────────────────────────────

log "Capturing logs..."
docker logs "$RECORDER_CONTAINER" 2>&1 > "$RESULTS/recorder-full.log"

log "Waiting 40s for immutability..."
sleep 40

log "Fetching DB segments..."
if [ -n "$SESSION_UID" ]; then
  PGPASSWORD=postgres psql -h localhost -p 5448 -U postgres -d vexa_restore \
    -c "COPY (SELECT segment_id, speaker, text, start_time, end_time, language, created_at
         FROM transcriptions WHERE session_uid = '$SESSION_UID' ORDER BY start_time
    ) TO STDOUT WITH CSV HEADER;" > "$RESULTS/db-segments.csv" 2>/dev/null
else
  echo "segment_id,speaker,text,start_time,end_time,language,created_at" > "$RESULTS/db-segments.csv"
fi

DB_COUNT=$(tail -n +2 "$RESULTS/db-segments.csv" | wc -l | tr -d ' ')
log "  DB: $DB_COUNT segments"

grep "CONFIRMED" "$RESULTS/recorder-full.log" 2>/dev/null | python3 -c "
import sys, json, re
pat = re.compile(r'CONFIRMED\] (.+?) \| (\S+) \| [^|]+ \| ([^ ]+) \| \"(.*)\"')
segments = []
for line in sys.stdin:
    m = pat.search(line)
    if m:
        segments.append({'speaker': m.group(1), 'language': m.group(2), 'segment_id': m.group(3), 'text': m.group(4)})
with open('$RESULTS/bot-segments.json', 'w') as f:
    json.dump(segments, f, indent=2)
print(f'{len(segments)} bot segments')
" 2>/dev/null || echo "0 bot segments"

# ─── Score ────────────────────────────────────────────────────────────────────

log "Scoring..."
python3 "$SCORER" "$RESULTS" 2>&1 | tee "$RESULTS/score.txt"

# ─── Cleanup ──────────────────────────────────────────────────────────────────

log "Cleaning up..."
stop_bot "$ALICE_ID"
stop_bot "$BOB_ID"
stop_bot "$CHARLIE_ID"
stop_bot "$RECORDER_ID"

log "Results: $RESULTS"
