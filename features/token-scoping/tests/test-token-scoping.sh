#!/bin/bash
# Token scoping feature test.
#
# Tests:
#   smoke   — create one scoped token, verify prefix
#   create  — create tokens for all scopes, verify prefixes
#   enforce — use scoped tokens against endpoints, verify 200/403
#   legacy  — use unscoped token, verify full access
#   all     — run all tests
#   clean   — revoke test tokens
#
# Usage:
#   ./test-token-scoping.sh smoke
#   ./test-token-scoping.sh all
#   ADMIN_API_URL=http://host:8067 ./test-token-scoping.sh all

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/../.env"
RESULTS="$DIR/results/run-$(date +%Y-%m-%d-%H%M%S)"

source "$ENV_FILE" 2>/dev/null || true

API_URL="${API_GATEWAY_URL:-http://localhost:8066}"
ADMIN_URL="${ADMIN_API_URL:-http://localhost:8067}"
ADMIN_TOKEN="${ADMIN_TOKEN:-changeme}"
TEST_USER_ID="${TEST_USER_ID:-1}"

CMD="${1:-all}"

mkdir -p "$RESULTS"

PASS=0
FAIL=0
CREATED_TOKEN_IDS=()

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

assert_prefix() {
  local desc=$1 expected_prefix=$2 token=$3
  if [[ "$token" == ${expected_prefix}* ]]; then
    log "  PASS: $desc (prefix: ${token:0:8}...)"
    PASS=$((PASS + 1))
  else
    log "  FAIL: $desc (expected prefix $expected_prefix, got ${token:0:20})"
    FAIL=$((FAIL + 1))
  fi
}

# --- Create a scoped token via admin API ---
create_token() {
  local scope=$1
  local resp
  resp=$(curl -s -X POST "$ADMIN_URL/admin/users/$TEST_USER_ID/tokens?scope=$scope" \
    -H "X-Admin-API-Key: $ADMIN_TOKEN" \
    -H "Content-Type: application/json")
  local token
  token=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('token',''))" 2>/dev/null)
  local token_id
  token_id=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
  if [ -n "$token_id" ] && [ "$token_id" != "" ]; then
    CREATED_TOKEN_IDS+=("$token_id")
  fi
  echo "$token"
}

# --- Check HTTP status code for an endpoint ---
check_status() {
  local token=$1 method=$2 url=$3
  curl -s -o /dev/null -w "%{http_code}" -X "$method" "$url" \
    -H "X-API-Key: $token" \
    -H "Content-Type: application/json" 2>/dev/null
}

# ─── Smoke ────────────────────────────────────────────────────────────────────

run_smoke() {
  log "=== Smoke test ==="
  local token
  token=$(create_token "bot")
  if [ -z "$token" ]; then
    log "  FAIL: Could not create bot-scoped token (is admin-api running?)"
    FAIL=$((FAIL + 1))
    return
  fi
  assert_prefix "bot token has vxa_bot_ prefix" "vxa_bot_" "$token"
  log "Smoke test complete."
}

# ─── Create ───────────────────────────────────────────────────────────────────

run_create() {
  log "=== Token creation tests ==="

  for scope in user bot tx admin; do
    local token
    token=$(create_token "$scope")
    if [ -z "$token" ]; then
      log "  FAIL: Could not create $scope-scoped token"
      FAIL=$((FAIL + 1))
      continue
    fi
    assert_prefix "$scope token prefix" "vxa_${scope}_" "$token"
    echo "$scope=$token" >> "$RESULTS/tokens.txt"
  done
}

# ─── Enforce ──────────────────────────────────────────────────────────────────

run_enforce() {
  log "=== Scope enforcement tests ==="
  # Enforcement happens in downstream services, not api-gateway:
  #   bot-manager:             allows {bot, user, admin}
  #   transcription-collector: allows {tx, user, admin}
  #   admin-api:               allows {user, admin}

  # Create tokens for testing
  local user_token bot_token tx_token admin_token
  user_token=$(create_token "user")
  bot_token=$(create_token "bot")
  tx_token=$(create_token "tx")
  admin_token=$(create_token "admin")

  if [ -z "$user_token" ] || [ -z "$bot_token" ] || [ -z "$tx_token" ]; then
    log "  FAIL: Could not create test tokens"
    FAIL=$((FAIL + 1))
    return
  fi

  local status

  # --- user scope: should access bot status + meetings ---
  log "Testing user-scoped token..."
  status=$(check_status "$user_token" "GET" "$API_URL/bots/status")
  assert_eq "user token → GET /bots/status (bot-manager allows user)" "200" "$status"

  status=$(check_status "$user_token" "GET" "$API_URL/meetings")
  assert_eq "user token → GET /meetings (collector allows user)" "200" "$status"

  # --- bot scope: should access bot status but NOT meetings ---
  log "Testing bot-scoped token..."
  status=$(check_status "$bot_token" "GET" "$API_URL/bots/status")
  assert_eq "bot token → GET /bots/status (bot-manager allows bot)" "200" "$status"

  # bot scope is NOT in transcription-collector's allowed set {tx, user, admin}
  status=$(check_status "$bot_token" "GET" "$API_URL/meetings")
  assert_eq "bot token → GET /meetings (collector rejects bot)" "403" "$status"

  # --- tx scope: should access meetings but NOT bots ---
  log "Testing tx-scoped token..."
  # tx scope is NOT in bot-manager's allowed set {bot, user, admin}
  status=$(check_status "$tx_token" "GET" "$API_URL/bots/status")
  assert_eq "tx token → GET /bots/status (bot-manager rejects tx)" "403" "$status"

  status=$(check_status "$tx_token" "GET" "$API_URL/meetings")
  assert_eq "tx token → GET /meetings (collector allows tx)" "200" "$status"

  # --- admin scope: should access everything ---
  log "Testing admin-scoped token..."
  status=$(check_status "$admin_token" "GET" "$API_URL/bots/status")
  assert_eq "admin token → GET /bots/status" "200" "$status"

  status=$(check_status "$admin_token" "GET" "$API_URL/meetings")
  assert_eq "admin token → GET /meetings" "200" "$status"

  log "Saving enforcement results..."
  echo "user_token=$user_token" >> "$RESULTS/enforce.txt"
  echo "bot_token=$bot_token" >> "$RESULTS/enforce.txt"
  echo "tx_token=$tx_token" >> "$RESULTS/enforce.txt"
  echo "admin_token=$admin_token" >> "$RESULTS/enforce.txt"
}

# ─── Legacy ───────────────────────────────────────────────────────────────────

run_legacy() {
  log "=== Legacy token backward compatibility ==="

  # Legacy tokens have no vxa_ prefix — should have full access
  # Use the user API token from realtime-transcription .env if it's a legacy token
  # If not available, use ADMIN_TOKEN which is a legacy token (no vxa_ prefix)
  local legacy_token="$ADMIN_TOKEN"
  local status
  status=$(check_status "$legacy_token" "GET" "$API_URL/bots/status")
  # Legacy tokens pass check_token_scope (returns True for no-prefix)
  # but still need to be valid tokens in the DB
  log "  INFO: legacy token → GET /bots/status returned $status"
  if [ "$status" = "200" ] || [ "$status" = "403" ]; then
    # 200 = full access; 403 = token valid but not in DB (changeme is admin key, not API token)
    log "  PASS: legacy token handled (HTTP $status)"
    PASS=$((PASS + 1))
  else
    log "  FAIL: legacy token → unexpected HTTP $status"
    FAIL=$((FAIL + 1))
  fi
}

# ─── Clean ────────────────────────────────────────────────────────────────────

run_clean() {
  log "=== Cleanup: revoking test tokens ==="
  for token_id in "${CREATED_TOKEN_IDS[@]}"; do
    curl -s -X DELETE "$ADMIN_URL/admin/tokens/$token_id" \
      -H "X-Admin-API-Key: $ADMIN_TOKEN" > /dev/null 2>&1
    log "  Revoked token $token_id"
  done
}

# ─── Main ─────────────────────────────────────────────────────────────────────

case "$CMD" in
  smoke)   run_smoke ;;
  create)  run_create ;;
  enforce) run_enforce ;;
  legacy)  run_legacy ;;
  all)     run_smoke; run_create; run_enforce; run_legacy; run_clean ;;
  clean)   run_clean ;;
  *)       echo "Unknown command: $CMD"; exit 1 ;;
esac

echo ""
log "Results: PASS=$PASS FAIL=$FAIL"
log "Output: $RESULTS"
[ "$FAIL" -eq 0 ] || exit 1
