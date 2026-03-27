#!/bin/bash
set -e

cd /home/dima/dev/vexa-agentic-runtime

echo "=== STEP 1: Recreate worktree ==="
git worktree prune 2>&1
echo "Pruned stale worktrees"

git worktree add .worktrees/meeting-aware-agent conductor/meeting-aware-agent 2>&1
echo "Worktree created successfully"

echo ""
echo "=== STEP 2: Run Tests ==="

API_KEY="vxa_user_dG5r3woagusNVMIeFASWtorXkVypGE2u2tJ8E0Ut"

echo ""
echo "--- Test 1: Session creation with meeting_aware flag ---"
TEST1=$(curl -s -X POST http://localhost:8056/api/sessions \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "21", "name": "Test Meeting Aware", "meeting_aware": true}')
echo "$TEST1"

echo ""
echo "--- Test 2: Verify flag in Redis ---"
TEST2=$(docker exec vexa-restore-redis-1 redis-cli -a vexa-redis-dev HGETALL "agent:sessions:21" 2>&1)
echo "$TEST2"

echo ""
echo "--- Test 3: Check bots/status via gateway ---"
TEST3=$(curl -s http://localhost:8056/bots/status -H "X-API-Key: $API_KEY")
echo "$TEST3"

echo ""
echo "--- Test 4: Send a bot ---"
TEST4=$(curl -s -X POST "http://localhost:8056/bots" \
  -H "X-API-Key: vxa_bot_8Yb4m36xTtDlpuGkC8x9v4bwxxTe390ugjbDQ946" \
  -H "Content-Type: application/json" \
  -d '{"platform": "ms_teams", "native_meeting_id": "test-meeting-aware-9999"}')
echo "$TEST4"

echo ""
echo "--- Test 5: Check if bot shows in /bots/status (after 5s) ---"
sleep 5
TEST5=$(curl -s http://localhost:8056/bots/status \
  -H "X-API-Key: vxa_user_1GsamYGP2FVlBuo5hdVNbSFbfqVDR2Zk5RGcehks")
echo "$TEST5"

echo ""
echo "--- Test 6: Gateway health and agent routes ---"
TEST6A=$(curl -sf http://localhost:8056/ 2>&1)
echo "Health: $TEST6A"
TEST6B=$(curl -s http://localhost:8056/api/sessions?user_id=21 -H "X-API-Key: $API_KEY")
echo "Sessions: $TEST6B"

echo ""
echo "--- Test 7: Chat with manual X-Meeting-Context header ---"
MEETING_CTX='{"active_meetings":[{"meeting_id":"42","platform":"teams","native_meeting_id":"test-123","status":"active","participants":["Alice","Bob"],"latest_segments":[{"speaker":"Alice","text":"We need to finalize the Q1 budget","timestamp":"2026-03-28T00:00:00"},{"speaker":"Bob","text":"I agree, lets pull up the spreadsheet","timestamp":"2026-03-28T00:01:00"}]}]}'

TEST7=$(timeout 30 curl -s -N -X POST http://localhost:8100/api/chat \
  -H "Content-Type: application/json" \
  -H "X-Meeting-Context: $MEETING_CTX" \
  -d '{"user_id": "21", "message": "What are they talking about?"}' 2>&1 | head -20)
echo "$TEST7"

echo ""
echo "--- Test 8: Check prompt file in agent container ---"
CONTAINER=$(docker ps --format "{{.Names}}" | grep "agent-21" | head -1)
echo "Agent container: $CONTAINER"
if [ -n "$CONTAINER" ]; then
  docker exec $CONTAINER cat /tmp/.chat-prompt.txt 2>/dev/null | head -20 || echo "(no prompt file found)"
else
  echo "(no agent-21 container found)"
fi

echo ""
echo "--- Test 9: Non-meeting-aware session ---"
TEST9=$(curl -s -X POST http://localhost:8056/api/sessions \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "21", "name": "Normal Session"}')
echo "$TEST9"

echo ""
echo "--- Test 10: Gateway logs ---"
docker logs vexa-restore-api-gateway-new 2>&1 | tail -30

echo ""
echo "=== ALL TESTS COMPLETE ==="
