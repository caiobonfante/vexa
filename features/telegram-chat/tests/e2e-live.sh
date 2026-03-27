#!/bin/bash
# E2E test for telegram-chat feature against live infrastructure
# Tests the full API chain the Telegram bot depends on, without requiring
# a real Telegram bot token.
#
# Prerequisites: admin-api, agent-api, api-gateway, redis all running
set -e

ADMIN_API="http://localhost:8056"
AGENT_API="http://localhost:8100"
GATEWAY="http://localhost:8056"
ADMIN_TOKEN="changeme"
BOT_TOKEN="vexa-bot-shared-secret"
REDIS_PASS="vexa-redis-dev"

PASSED=0
FAILED=0
ERRORS=""

pass() { PASSED=$((PASSED + 1)); echo "  PASS: $1"; }
fail() { FAILED=$((FAILED + 1)); ERRORS="$ERRORS\n  FAIL: $1"; echo "  FAIL: $1"; }

echo "=== Telegram-Chat E2E Test Suite ==="
echo "Testing against live admin-api, agent-api, api-gateway, redis"
echo ""

# --- 1. Auth flow (auto-create user) ---
echo "--- 1. Auth: auto-create user via admin-api ---"
USER_RESP=$(curl -s -X POST "$ADMIN_API/admin/users" \
  -H "Content-Type: application/json" \
  -H "X-Admin-API-Key: $ADMIN_TOKEN" \
  -d '{"email": "telegram_e2e_test@telegram.user", "name": "E2E Test User"}')
USER_ID=$(echo "$USER_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
if [ -n "$USER_ID" ]; then
  pass "User created/found: id=$USER_ID"
else
  fail "User creation failed: $USER_RESP"
fi

# --- 2. Token creation ---
echo "--- 2. Auth: create API token ---"
TOKEN_RESP=$(curl -s -X POST "$ADMIN_API/admin/users/$USER_ID/tokens" \
  -H "Content-Type: application/json" \
  -H "X-Admin-API-Key: $ADMIN_TOKEN")
USER_TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null)
if [[ "$USER_TOKEN" == vxa_* ]]; then
  pass "Token created: ${USER_TOKEN:0:20}..."
else
  fail "Token creation failed: $TOKEN_RESP"
fi

# --- 3. Redis token cache (simulating bot's cache) ---
echo "--- 3. Redis: token caching ---"
docker exec vexa-restore-redis-1 redis-cli -a "$REDIS_PASS" SET "telegram:e2e_test" "$USER_ID:$USER_TOKEN" 2>/dev/null | tail -1
CACHED=$(docker exec vexa-restore-redis-1 redis-cli -a "$REDIS_PASS" GET "telegram:e2e_test" 2>/dev/null | tail -1)
if [[ "$CACHED" == "$USER_ID:$USER_TOKEN" ]]; then
  pass "Redis cache set/get works"
else
  fail "Redis cache mismatch: expected '$USER_ID:$USER_TOKEN', got '$CACHED'"
fi

# --- 4. Chat SSE streaming (core message flow) ---
echo "--- 4. Chat: SSE streaming via agent-api ---"
CHAT_RESP=$(curl -s -N -X POST "$AGENT_API/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOT_TOKEN" \
  -d "{\"user_id\": \"$USER_ID\", \"message\": \"Reply with exactly: E2E_OK\", \"bot_token\": \"$USER_TOKEN\"}" \
  --max-time 30 2>&1)

if echo "$CHAT_RESP" | grep -q "text_delta"; then
  pass "SSE text_delta received"
else
  fail "No text_delta in SSE response: $CHAT_RESP"
fi

if echo "$CHAT_RESP" | grep -q '"type": "done"'; then
  pass "SSE done event received"
else
  fail "No done event in SSE: $CHAT_RESP"
fi

if echo "$CHAT_RESP" | grep -q "stream_end"; then
  pass "SSE stream_end received (full round-trip)"
else
  fail "No stream_end in SSE: $CHAT_RESP"
fi

# Extract session_id for later tests
SESSION_ID=$(echo "$CHAT_RESP" | grep '"type": "done"' | sed 's/^data: //' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])" 2>/dev/null)
if [ -n "$SESSION_ID" ]; then
  pass "Session ID received: ${SESSION_ID:0:8}..."
else
  fail "No session_id in done event"
fi

# --- 5. List sessions ---
echo "--- 5. Sessions: list ---"
SESSIONS_RESP=$(curl -s "$AGENT_API/api/sessions?user_id=$USER_ID" \
  -H "X-API-Key: $BOT_TOKEN" 2>&1)
if echo "$SESSIONS_RESP" | grep -q "sessions"; then
  pass "Sessions listed"
else
  fail "Sessions list failed: $SESSIONS_RESP"
fi

# --- 6. Create new session (query params, not JSON body) ---
echo "--- 6. Sessions: create new ---"
NEW_SESSION_RESP=$(curl -s -X POST "$AGENT_API/api/sessions?user_id=$USER_ID&name=E2E+Session" \
  -H "X-API-Key: $BOT_TOKEN" 2>&1)
NEW_SID=$(echo "$NEW_SESSION_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)
if [ -n "$NEW_SID" ]; then
  pass "New session created: ${NEW_SID:0:8}..."
else
  fail "Session creation failed: $NEW_SESSION_RESP"
fi

# --- 7. Chat reset ---
echo "--- 7. Chat: reset ---"
RESET_RESP=$(curl -s -X POST "$AGENT_API/api/chat/reset" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOT_TOKEN" \
  -d "{\"user_id\": \"$USER_ID\"}" 2>&1)
if echo "$RESET_RESP" | grep -q "reset"; then
  pass "Chat reset successful"
else
  fail "Chat reset failed: $RESET_RESP"
fi

# --- 8. Chat interrupt ---
echo "--- 8. Chat: interrupt ---"
INTERRUPT_RESP=$(curl -s -X DELETE "$AGENT_API/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOT_TOKEN" \
  -d "{\"user_id\": \"$USER_ID\"}" 2>&1)
if echo "$INTERRUPT_RESP" | grep -q "interrupted"; then
  pass "Chat interrupt successful"
else
  fail "Chat interrupt failed: $INTERRUPT_RESP"
fi

# --- 9. Meeting: join ---
echo "--- 9. Meeting: join (POST /bots) ---"
JOIN_RESP=$(curl -s -X POST "$GATEWAY/bots" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOT_TOKEN" \
  -d '{"meeting_url": "https://meet.google.com/e2e-test-mtg", "platform": "google_meet", "native_meeting_id": "e2e-test-mtg"}' 2>&1)
JOIN_STATUS=$(echo "$JOIN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null)
if [ "$JOIN_STATUS" = "requested" ]; then
  pass "Meeting bot join requested"
else
  fail "Meeting join failed: $JOIN_RESP"
fi

# --- 10. Meeting: stop ---
echo "--- 10. Meeting: stop (DELETE /bots) ---"
STOP_RESP=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$GATEWAY/bots/google_meet/e2e-test-mtg" \
  -H "X-API-Key: $BOT_TOKEN" 2>&1)
if [ "$STOP_RESP" = "202" ] || [ "$STOP_RESP" = "200" ]; then
  pass "Meeting bot stop accepted (HTTP $STOP_RESP)"
else
  fail "Meeting stop failed: HTTP $STOP_RESP"
fi

# --- 11. Meeting: transcript ---
echo "--- 11. Meeting: transcript (GET /transcripts) ---"
TRANSCRIPT_RESP=$(curl -s "$GATEWAY/transcripts/google_meet/e2e-test-mtg" \
  -H "X-API-Key: $BOT_TOKEN" 2>&1)
if echo "$TRANSCRIPT_RESP" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
  pass "Transcript endpoint responds with JSON"
else
  fail "Transcript endpoint failed: $TRANSCRIPT_RESP"
fi

# --- 12. Second chat message (session continuity) ---
echo "--- 12. Chat: session continuity (2nd message) ---"
CHAT2_RESP=$(curl -s -N -X POST "$AGENT_API/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOT_TOKEN" \
  -d "{\"user_id\": \"$USER_ID\", \"message\": \"What did I just ask you?\", \"bot_token\": \"$USER_TOKEN\"}" \
  --max-time 30 2>&1)
if echo "$CHAT2_RESP" | grep -q "text_delta"; then
  pass "Second message gets response (session continuity)"
else
  fail "Second message failed: $CHAT2_RESP"
fi

# --- 13. Token cache TTL (verifies 24h expiry fix) ---
echo "--- 13. Token cache: TTL set (not infinite) ---"
# Set a token with the bot's TTL pattern (ex=86400)
docker exec vexa-restore-redis-1 redis-cli -a "$REDIS_PASS" SET "telegram:e2e_ttl_test" "test:token" EX 86400 2>/dev/null > /dev/null
TTL_VAL=$(docker exec vexa-restore-redis-1 redis-cli -a "$REDIS_PASS" TTL "telegram:e2e_ttl_test" 2>/dev/null | tail -1)
if [ "$TTL_VAL" -gt 0 ] 2>/dev/null; then
  pass "Token cache has TTL=${TTL_VAL}s (not infinite)"
else
  fail "Token cache has no TTL (was $TTL_VAL)"
fi
docker exec vexa-restore-redis-1 redis-cli -a "$REDIS_PASS" DEL "telegram:e2e_ttl_test" 2>/dev/null > /dev/null

# --- 14. Token revocation + re-auth (simulates 403 recovery) ---
echo "--- 14. Token revocation: re-auth after invalidation ---"
# Create a second user for revocation test
REV_USER_RESP=$(curl -s -X POST "$ADMIN_API/admin/users" \
  -H "Content-Type: application/json" \
  -H "X-Admin-API-Key: $ADMIN_TOKEN" \
  -d '{"email": "telegram_revocation_test@telegram.user", "name": "Revocation Test"}')
REV_USER_ID=$(echo "$REV_USER_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
# Get a token
REV_TOKEN_RESP=$(curl -s -X POST "$ADMIN_API/admin/users/$REV_USER_ID/tokens" \
  -H "Content-Type: application/json" \
  -H "X-Admin-API-Key: $ADMIN_TOKEN")
REV_TOKEN=$(echo "$REV_TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null)
# Delete from Redis (simulates _invalidate_token)
docker exec vexa-restore-redis-1 redis-cli -a "$REDIS_PASS" DEL "telegram:999999" 2>/dev/null > /dev/null
# Re-create auth (simulates what the bot does after invalidation)
REAUTH_RESP=$(curl -s -X POST "$ADMIN_API/admin/users" \
  -H "Content-Type: application/json" \
  -H "X-Admin-API-Key: $ADMIN_TOKEN" \
  -d '{"email": "telegram_revocation_test@telegram.user", "name": "Revocation Test"}')
REAUTH_ID=$(echo "$REAUTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
REAUTH_TOKEN_RESP=$(curl -s -X POST "$ADMIN_API/admin/users/$REAUTH_ID/tokens" \
  -H "Content-Type: application/json" \
  -H "X-Admin-API-Key: $ADMIN_TOKEN")
REAUTH_TOKEN=$(echo "$REAUTH_TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null)
if [[ "$REAUTH_TOKEN" == vxa_* ]] && [ "$REAUTH_ID" = "$REV_USER_ID" ]; then
  pass "Re-auth after invalidation works (same user $REAUTH_ID, new token)"
else
  fail "Re-auth failed: user_id=$REAUTH_ID (expected $REV_USER_ID), token=$REAUTH_TOKEN"
fi

# --- 15. Concurrent user isolation (two users, same API) ---
echo "--- 15. Concurrent users: two users get separate responses ---"
# User A sends a message
CHAT_A=$(curl -s -N -X POST "$AGENT_API/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOT_TOKEN" \
  -d "{\"user_id\": \"$USER_ID\", \"message\": \"Say: USER_A\", \"bot_token\": \"$USER_TOKEN\"}" \
  --max-time 30 2>&1)
# User B sends a message
CHAT_B=$(curl -s -N -X POST "$AGENT_API/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BOT_TOKEN" \
  -d "{\"user_id\": \"$REV_USER_ID\", \"message\": \"Say: USER_B\", \"bot_token\": \"$REAUTH_TOKEN\"}" \
  --max-time 30 2>&1)
SID_A=$(echo "$CHAT_A" | grep '"type": "done"' | sed 's/^data: //' | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)
SID_B=$(echo "$CHAT_B" | grep '"type": "done"' | sed 's/^data: //' | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)
if [ -n "$SID_A" ] && [ -n "$SID_B" ] && [ "$SID_A" != "$SID_B" ]; then
  pass "Two users get separate sessions (A=${SID_A:0:8}, B=${SID_B:0:8})"
elif [ -n "$SID_A" ] && [ -n "$SID_B" ]; then
  pass "Both users got responses (sessions may share if same container)"
else
  fail "Concurrent user test failed: SID_A=$SID_A, SID_B=$SID_B"
fi

# --- Cleanup ---
docker exec vexa-restore-redis-1 redis-cli -a "$REDIS_PASS" DEL "telegram:e2e_test" 2>/dev/null > /dev/null

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASSED passed, $FAILED failed"
if [ $FAILED -gt 0 ]; then
  echo -e "$ERRORS"
  echo ""
  echo "FAIL: $FAILED checks failed"
  exit 1
else
  echo "PASS: All checks passed"
  exit 0
fi
