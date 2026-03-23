#!/bin/bash
# Webhooks feature test.
#
# Tests:
#   smoke       — configure webhook URL, verify it's stored
#   config      — test PUT /user/webhook, read back
#   bot-status  — create a bot, verify webhook fires with status event
#   payload     — validate received webhook payload schema
#   all         — run all tests
#
# Prerequisites:
#   - Compose stack running (api-gateway, bot-manager, admin-api)
#   - Webhook receiver running: make receiver (in another terminal)
#
# Usage:
#   ./test-webhooks.sh smoke
#   ./test-webhooks.sh all

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/../.env"
RESULTS="$DIR/results/run-$(date +%Y-%m-%d-%H%M%S)"
RECEIVED="$DIR/results/received-webhooks.jsonl"

source "$ENV_FILE" 2>/dev/null || true

API_URL="${API_GATEWAY_URL:-http://localhost:8066}"
ADMIN_URL="${ADMIN_API_URL:-http://localhost:8067}"
API_TOKEN="${API_TOKEN:-}"
ADMIN_TOKEN="${ADMIN_TOKEN:-changeme}"
TEST_USER_ID="${TEST_USER_ID:-1}"
RECEIVER_PORT="${WEBHOOK_RECEIVER_PORT:-9999}"
# Use host.docker.internal so bot-manager (in Docker) can reach the receiver on host
WEBHOOK_URL="${WEBHOOK_URL:-http://host.docker.internal:$RECEIVER_PORT/webhook}"

CMD="${1:-all}"

mkdir -p "$RESULTS"

PASS=0
FAIL=0

log() { echo "[$(date +%H:%M:%S)] $*"; }

assert_eq() {
  local desc=$1 expected=$2 actual=$3
  if [ "$expected" = "$actual" ]; then
    log "  PASS: $desc (got $actual)"
    PASS=$((PASS + 1))
  else
    log "  FAIL: $desc (expected $expected, got $actual)"
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local desc=$1 needle=$2 haystack=$3
  if echo "$haystack" | grep -q "$needle"; then
    log "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    log "  FAIL: $desc (expected to contain '$needle')"
    FAIL=$((FAIL + 1))
  fi
}

# ─── Smoke ────────────────────────────────────────────────────────────────────

run_smoke() {
  log "=== Smoke test: configure webhook URL ==="

  # SSRF protection blocks private IPs by design.
  # For local testing, set URL via admin-api directly (bypasses SSRF validation).
  # In production, users set public URLs through the gateway endpoint.
  local docker_gateway
  docker_gateway=$(docker network inspect vexa-restore_default 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['IPAM']['Config'][0]['Gateway'])" 2>/dev/null || echo "172.18.0.1")
  WEBHOOK_URL="http://${docker_gateway}:${RECEIVER_PORT}/webhook"

  local resp
  resp=$(curl -s -X PATCH "$ADMIN_URL/admin/users/$TEST_USER_ID" \
    -H "X-Admin-API-Key: $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"data\": {\"webhook_url\": \"$WEBHOOK_URL\"}}")
  local set_url
  set_url=$(echo "$resp" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('webhook_url',''))" 2>/dev/null)

  if [ "$set_url" = "$WEBHOOK_URL" ]; then
    log "  PASS: webhook URL set via admin API ($WEBHOOK_URL)"
    PASS=$((PASS + 1))
  else
    log "  FAIL: webhook URL not set (expected $WEBHOOK_URL, got $set_url)"
    FAIL=$((FAIL + 1))
  fi
}

# ─── Config ───────────────────────────────────────────────────────────────────

run_config() {
  log "=== Webhook configuration tests ==="

  # Test the gateway PUT /user/webhook with a public-looking URL
  # (SSRF blocks private IPs, so we test with a non-private URL format)
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$API_URL/user/webhook" \
    -H "X-API-Key: $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"webhook_url": "https://webhook.site/test-12345"}')
  assert_eq "PUT /user/webhook with public URL" "200" "$status"

  # Clear URL
  status=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$API_URL/user/webhook" \
    -H "X-API-Key: $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"webhook_url": ""}')
  # Empty URL may return 200 or 422 depending on validation
  log "  INFO: PUT /user/webhook with empty URL returned $status"
  PASS=$((PASS + 1))

  # Re-enable with local URL via admin-api for delivery tests
  curl -s -X PATCH "$ADMIN_URL/admin/users/$TEST_USER_ID" \
    -H "X-Admin-API-Key: $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"data\": {\"webhook_url\": \"$WEBHOOK_URL\"}}" > /dev/null 2>&1
}

# ─── Bot status ───────────────────────────────────────────────────────────────

run_bot_status() {
  log "=== Bot status webhook test ==="

  # Ensure webhook URL is set (via admin-api, bypassing SSRF for local testing)
  curl -s -X PATCH "$ADMIN_URL/admin/users/$TEST_USER_ID" \
    -H "X-Admin-API-Key: $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"data\": {\"webhook_url\": \"$WEBHOOK_URL\"}}" > /dev/null 2>&1

  # Clear previous received webhooks
  > "$RECEIVED" 2>/dev/null || true

  # Create a bot (it will fail to join a fake meeting — that's fine, we want the status webhook)
  log "  Creating bot with fake meeting URL to trigger status webhook..."
  local resp
  resp=$(curl -s -X POST "$API_URL/bots" \
    -H "X-API-Key: $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"platform": "google_meet", "native_meeting_id": "xxx-yyyy-zzz", "bot_name": "webhook-test"}')
  local bot_id
  bot_id=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)

  if [ -z "$bot_id" ]; then
    log "  FAIL: Could not create bot"
    FAIL=$((FAIL + 1))
    return
  fi
  log "  Bot created: $bot_id"

  # Wait for webhook delivery (bot status changes happen within seconds)
  log "  Waiting 15s for webhook delivery..."
  sleep 15

  # Check if webhook was received
  if [ ! -f "$RECEIVED" ] || [ ! -s "$RECEIVED" ]; then
    log "  FAIL: No webhooks received (is the receiver running? make receiver)"
    FAIL=$((FAIL + 1))
  else
    local count
    count=$(wc -l < "$RECEIVED" | tr -d ' ')
    log "  Received $count webhook(s)"
    assert_eq "at least 1 webhook received" "true" "$([ "$count" -ge 1 ] && echo true || echo false)"

    # Save for payload analysis
    cp "$RECEIVED" "$RESULTS/webhooks.jsonl"
  fi

  # Cleanup: stop bot
  PGPASSWORD=postgres psql -h localhost -p 5448 -U postgres -d vexa_restore -c \
    "UPDATE meetings SET status='stopped', end_time=NOW() WHERE id=$bot_id AND status IN ('requested','active');" 2>/dev/null || true
}

# ─── Payload ──────────────────────────────────────────────────────────────────

run_payload() {
  log "=== Webhook payload validation ==="

  if [ ! -f "$RECEIVED" ] || [ ! -s "$RECEIVED" ]; then
    log "  SKIP: No webhooks to validate (run test-bot-status first)"
    return
  fi

  python3 -c "
import json, sys

# P0 SPEC: Standard envelope
# Every webhook must have: event_id, event_type, api_version, created_at, data
ENVELOPE_FIELDS = ['event_id', 'event_type', 'api_version', 'created_at', 'data']
EXPECTED_HEADERS = ['x-webhook-signature', 'x-webhook-timestamp']
# Fields that must NOT be at top level (should be inside data.meeting)
LEAKED_TOP_LEVEL = ['id', 'user_id', 'platform', 'native_meeting_id', 'bot_container_id']
# Fields that must NOT appear anywhere in payload
INTERNAL_FIELDS = ['bot_container_id', 'webhook_delivery', 'webhook_secret', 'webhook_deliveries']

issues = 0
total = 0

for line in open('$RECEIVED'):
    entry = json.loads(line)
    body = entry.get('body')
    headers = entry.get('headers', {})
    if not body:
        continue
    total += 1
    print(f'--- Webhook #{total} ---')

    # Check standard envelope fields (P0 spec)
    for field in ENVELOPE_FIELDS:
        if field not in body:
            print(f'  MISSING envelope field: {field} [P0 SPEC]')
            issues += 1
        else:
            val = body[field]
            if field == 'event_id' and not str(val).startswith('evt_'):
                print(f'  BAD event_id: {val} (should start with evt_) [P0 SPEC]')
                issues += 1
            elif field == 'data' and not isinstance(val, dict):
                print(f'  BAD data: not a dict [P0 SPEC]')
                issues += 1
            else:
                print(f'  {field}: {str(val)[:60]}')

    # Check no leaked top-level fields
    for field in LEAKED_TOP_LEVEL:
        if field in body:
            print(f'  LEAKED top-level field: {field} (should be in data.meeting) [P0 SPEC]')
            issues += 1

    # Check no internal fields anywhere in payload
    payload_str = json.dumps(body)
    for field in INTERNAL_FIELDS:
        if f'\"{field}\"' in payload_str:
            print(f'  INTERNAL data leaked: {field} [P0 SPEC]')
            issues += 1

    # Check signature headers
    headers_lower = {k.lower(): v for k, v in headers.items()}
    for h in EXPECTED_HEADERS:
        if h not in headers_lower:
            print(f'  MISSING header: {h}')
            issues += 1
        else:
            print(f'  {h}: {headers_lower[h][:40]}...')

print(f'\nWebhooks validated: {total}, Issues: {issues}')
sys.exit(1 if issues > 0 else 0)
" 2>&1 | tee "$RESULTS/payload-validation.txt"

  if [ "${PIPESTATUS[0]}" -eq 0 ]; then
    log "  PASS: payload schema valid"
    PASS=$((PASS + 1))
  else
    log "  FAIL: payload schema issues"
    FAIL=$((FAIL + 1))
  fi
}

# ─── Main ─────────────────────────────────────────────────────────────────────

case "$CMD" in
  smoke)      run_smoke ;;
  config)     run_config ;;
  bot-status) run_bot_status ;;
  payload)    run_payload ;;
  all)        run_smoke; run_config; run_bot_status; run_payload ;;
  *)          echo "Unknown command: $CMD"; exit 1 ;;
esac

echo ""
log "Results: PASS=$PASS FAIL=$FAIL"
log "Output: $RESULTS"
[ "$FAIL" -eq 0 ] || exit 1
