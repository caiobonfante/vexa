#!/usr/bin/env bash
# Teams data collection: join meeting → launch TTS speakers → capture dataset.
# One live meeting produces a reusable dataset for offline iteration.
#
# Usage:
#   TEAMS_MEETING_URL="https://teams.microsoft.com/meet/365488377316481?p=ryf9yhbfrc7MpM7kNv" \
#     make -C tests3 collect-teams
#
# Requires: human in the Teams meeting to admit bots from lobby.
#
# Reads:  .state/gateway_url, .state/api_token, .state/admin_url, .state/admin_token
# Writes: testdata/teams-{mode}-{YYMMDD}/
source "$(dirname "$0")/../lib/common.sh"

GATEWAY_URL=$(state_read gateway_url)
API_TOKEN=$(state_read api_token)
ADMIN_URL=$(state_read admin_url)
ADMIN_TOKEN=$(state_read admin_token)
DEPLOY_MODE=$(cat "$STATE/deploy_mode" 2>/dev/null || echo "compose")
T3=$(cd "$(dirname "$0")/.." && pwd)

if [ -z "$TEAMS_MEETING_URL" ]; then
    fail "TEAMS_MEETING_URL not set."
    exit 1
fi

NATIVE_ID=$(echo "$TEAMS_MEETING_URL" | grep -oP '/meet/\K\d{10,15}')
PASSCODE=$(echo "$TEAMS_MEETING_URL" | grep -oP '[?&]p=\K[A-Za-z0-9]+')
[ -z "$NATIVE_ID" ] && fail "Could not extract meeting ID" && exit 1
[ -z "$PASSCODE" ] && fail "Could not extract passcode" && exit 1

GROUND_TRUTH=(
    "Alice|0|Good morning everyone. Let's review the quarterly numbers."
    "Bob|12|Revenue increased by fifteen percent compared to last quarter."
    "Alice|24|Customer satisfaction score is ninety two percent."
    "Bob|36|The marketing budget needs to be increased by twenty percent."
)

DATE=$(date +%y%m%d)
DATASET_DIR="$T3/testdata/teams-${DEPLOY_MODE}-${DATE}"
mkdir -p "$DATASET_DIR/pipeline"

echo ""
echo "  collect-teams"
echo "  ══════════════════════════════════════════════"
info "native_meeting_id: $NATIVE_ID"
info "dataset: $DATASET_DIR"

# Ground truth JSON
python3 -c "
import json, sys
entries = []
for line in '''$(printf '%s\n' "${GROUND_TRUTH[@]}")'''.strip().split('\n'):
    parts = line.split('|', 2)
    if len(parts) == 3:
        entries.append({'speaker': parts[0], 'delay_ms': int(parts[1])*1000, 'text': parts[2]})
json.dump(entries, sys.stdout, indent=2)
print()
" > "$DATASET_DIR/ground-truth.json"
pass "ground truth: $DATASET_DIR/ground-truth.json"

# Cleanup stale bots
info "cleaning stale bots..."
curl -sf -H "X-API-Key: $API_TOKEN" "$GATEWAY_URL/bots/status" | python3 -c "
import sys,json
for b in json.load(sys.stdin).get('running_bots',[]):
    mid=b.get('native_meeting_id',''); p=b.get('platform','teams')
    mode=b.get('data',{}).get('mode','')
    if mode=='browser_session': print(f'browser_session/{mid}')
    else: print(f'{p}/{mid}')
" 2>/dev/null | while read -r bp; do
    curl -sf -X DELETE "$GATEWAY_URL/bots/$bp" -H "X-API-Key: $API_TOKEN" > /dev/null 2>&1 || true
done
sleep 5
pass "stale bots cleaned"

state_write native_meeting_id "$NATIVE_ID"
state_write meeting_platform "teams"
state_write meeting_url "$TEAMS_MEETING_URL"

echo "  ── phase 2: launch bots ─────────────────────"
declare -A SPEAKER_TOKENS
SPEAKERS=($(printf '%s\n' "${GROUND_TRUTH[@]}" | cut -d'|' -f1 | sort -u))

info "launching recorder..."
REC_RESP=$(curl -s -X POST "$GATEWAY_URL/bots" \
    -H "X-API-Key: $API_TOKEN" -H "Content-Type: application/json" \
    -d "{\"meeting_url\":\"$TEAMS_MEETING_URL\",\"bot_name\":\"Recorder\",\"transcribe_enabled\":true,\"automatic_leave\":{\"no_one_joined_timeout\":300000}}")
RECORDER_ID=$(echo "$REC_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
[ -z "$RECORDER_ID" ] && fail "recorder creation failed: $REC_RESP" && exit 1
state_write bot_id "$RECORDER_ID"
pass "recorder: id=$RECORDER_ID"

for SPEAKER in "${SPEAKERS[@]}"; do
    SPEAKER_LOWER=$(echo "$SPEAKER" | tr '[:upper:]' '[:lower:]')
    USER_RESP=$(curl -s "$ADMIN_URL/admin/users/email/${SPEAKER_LOWER}@vexa.ai" -H "X-Admin-API-Key: $ADMIN_TOKEN" -w "\n%{http_code}" 2>/dev/null)
    USER_HTTP=$(echo "$USER_RESP" | tail -1); USER_BODY=$(echo "$USER_RESP" | head -n -1)
    if [ "$USER_HTTP" = "200" ]; then
        USER_ID=$(echo "$USER_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
    else
        USER_BODY=$(curl -s -X POST "$ADMIN_URL/admin/users" -H "X-Admin-API-Key: $ADMIN_TOKEN" -H "Content-Type: application/json" \
            -d "{\"email\":\"${SPEAKER_LOWER}@vexa.ai\",\"name\":\"$SPEAKER\",\"max_concurrent_bots\":3}" 2>/dev/null)
        USER_ID=$(echo "$USER_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
    fi
    TOKEN=$(curl -s -X POST "$ADMIN_URL/admin/users/$USER_ID/tokens?scopes=bot,browser,tx&name=collect-$SPEAKER_LOWER" \
        -H "X-Admin-API-Key: $ADMIN_TOKEN" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
    SPEAKER_TOKENS[$SPEAKER]=$TOKEN
    BOT_RESP=$(curl -s -X POST "$GATEWAY_URL/bots" -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" \
        -d "{\"meeting_url\":\"$TEAMS_MEETING_URL\",\"bot_name\":\"$SPEAKER\",\"voice_agent_enabled\":true,\"automatic_leave\":{\"no_one_joined_timeout\":300000}}")
    BOT_ID=$(echo "$BOT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
    [ -n "$BOT_ID" ] && pass "speaker $SPEAKER: bot=$BOT_ID" || fail "speaker $SPEAKER: failed: $BOT_RESP"
done

TOTAL_BOTS=$(( 1 + ${#SPEAKERS[@]} ))

echo "  ── phase 3: admit bots ────────────────────────"
echo "  $TOTAL_BOTS bots waiting in Teams lobby. Admit them."

ALL_TOKENS=("$API_TOKEN")
for SPEAKER in "${SPEAKERS[@]}"; do ALL_TOKENS+=("${SPEAKER_TOKENS[$SPEAKER]}"); done
for i in $(seq 1 60); do
    ACTIVE=0
    for TK in "${ALL_TOKENS[@]}"; do
        A=$(curl -sf -H "X-API-Key: $TK" "$GATEWAY_URL/bots/status" | python3 -c "
import sys,json; bots=[b for b in json.load(sys.stdin).get('running_bots',[]) if b.get('native_meeting_id')=='$NATIVE_ID' and b.get('meeting_status','')=='active']; print(len(bots))" 2>/dev/null)
        ACTIVE=$(( ACTIVE + ${A:-0} ))
    done
    info "[$i] $ACTIVE/$TOTAL_BOTS active"
    [ "$ACTIVE" -ge "$TOTAL_BOTS" ] && break
    sleep 5
done
[ "$ACTIVE" -ge "$TOTAL_BOTS" ] && pass "all $TOTAL_BOTS bots active" || { fail "only $ACTIVE/$TOTAL_BOTS active"; exit 1; }

echo "  ── phase 4: send TTS (timed) ──────────────────"
SENT=0; PREV_DELAY=0
for entry in "${GROUND_TRUTH[@]}"; do
    SPEAKER=$(echo "$entry" | cut -d'|' -f1); DELAY_S=$(echo "$entry" | cut -d'|' -f2); TEXT=$(echo "$entry" | cut -d'|' -f3-)
    TOKEN=${SPEAKER_TOKENS[$SPEAKER]}
    WAIT_S=$(( DELAY_S - PREV_DELAY )); [ "$WAIT_S" -gt 0 ] && sleep "$WAIT_S"; PREV_DELAY=$DELAY_S
    TTS_CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$GATEWAY_URL/bots/teams/$NATIVE_ID/speak" \
        -H "X-API-Key: $TOKEN" -H "Content-Type: application/json" -d "{\"text\":\"$TEXT\",\"voice\":\"alloy\"}" 2>/dev/null || echo "000")
    if [ "$TTS_CODE" = "202" ] || [ "$TTS_CODE" = "200" ]; then
        SENT=$((SENT + 1)); info "[$SENT] $SPEAKER [${DELAY_S}s]: ${TEXT:0:60}"
    else fail "$SPEAKER: TTS failed (HTTP $TTS_CODE)"; fi
done
[ "$SENT" -ge "${#GROUND_TRUTH[@]}" ] && pass "TTS: $SENT/${#GROUND_TRUTH[@]}" || fail "TTS: only $SENT/${#GROUND_TRUTH[@]}"

echo "  ── phase 5: capture + score ─────────────────"
info "waiting 30s for pipeline..."; sleep 30
RESP=$(curl -sf -H "X-API-Key: $API_TOKEN" "$GATEWAY_URL/transcripts/teams/$NATIVE_ID")
echo "$RESP" | python3 -m json.tool > "$DATASET_DIR/pipeline/rest-segments.json" 2>/dev/null || echo "$RESP" > "$DATASET_DIR/pipeline/rest-segments.json"
SEGMENTS=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); segs=d.get('segments',[]) if isinstance(d,dict) else d; print(len(segs))" 2>/dev/null || echo "0")
state_write segments "${SEGMENTS:-0}"
[ "${SEGMENTS:-0}" -gt 0 ] && pass "captured: $SEGMENTS segments" || fail "0 segments"

echo "  ── phase 5b: bot logs + raw capture ─────────"
BOT_POD=$(find_bot_pod "")
if [ -n "$BOT_POD" ]; then
    pod_logs "$BOT_POD" > "$DATASET_DIR/pipeline/bot-logs.txt" 2>&1 || true
    pass "bot logs: $DATASET_DIR/pipeline/bot-logs.txt"
    LOGS=$(cat "$DATASET_DIR/pipeline/bot-logs.txt")
    DOM_EVENTS=$(echo "$LOGS" | grep -c '\[Unified\] SPEAKER_START' || true)
    [ "${DOM_EVENTS:-0}" -gt 0 ] && pass "dom: $DOM_EVENTS events" || fail "dom: 0 events"
    RAW_DIR=$(echo "$LOGS" | grep -oP 'Raw capture enabled .* \K/tmp/raw-capture-[^ ]+' | head -1 || true)
    if [ -n "$RAW_DIR" ]; then
        mkdir -p "$DATASET_DIR/raw"
        pod_copy "$BOT_POD" "$RAW_DIR/." "$DATASET_DIR/raw/" 2>/dev/null && pass "raw: $DATASET_DIR/raw/" || fail "raw: extract failed"
    else info "raw capture: not enabled"; fi
fi

echo "  ── phase 6: cleanup ─────────────────────────"
curl -sf -X DELETE "$GATEWAY_URL/bots/teams/$NATIVE_ID" -H "X-API-Key: $API_TOKEN" > /dev/null 2>&1 || true
for SPEAKER in "${SPEAKERS[@]}"; do
    curl -sf -X DELETE "$GATEWAY_URL/bots/teams/$NATIVE_ID" -H "X-API-Key: ${SPEAKER_TOKENS[$SPEAKER]}" > /dev/null 2>&1 || true
done
pass "cleanup done"
echo ""
echo "  Dataset: $DATASET_DIR"
echo "  Re-score: make -C tests3 score DATASET=teams-${DEPLOY_MODE}-${DATE}"
echo ""
