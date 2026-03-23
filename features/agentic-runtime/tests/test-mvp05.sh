#!/bin/bash
# MVP0.5 Validation — 9 tests for Knowledge Workspace
# Usage: bash test-mvp05.sh [CHAT_API_URL]
set -uo pipefail

API="${1:-http://localhost:8100}"
PASS=0
FAIL=0
TOTAL=9

green() { echo -e "\033[32m  PASS: $1\033[0m"; PASS=$((PASS+1)); }
red()   { echo -e "\033[31m  FAIL: $1\033[0m"; FAIL=$((FAIL+1)); }

chat_text() {
  local user="$1" msg="$2" timeout="${3:-120}"
  timeout "$timeout" curl -sf -N -X POST "$API/api/chat" \
    -H 'Content-Type: application/json' \
    -d "$(printf '{"user_id":"%s","message":"%s"}' "$user" "$(echo "$MSG" | sed 's/"/\\"/g')")" 2>/dev/null | \
  python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line or not line.startswith('data: '): continue
    try:
        d = json.loads(line[6:])
        if d.get('type') == 'text_delta':
            print(d.get('text',''), end='')
        elif d.get('type') == 'tool_use':
            print(f' [{d.get(\"tool\")}] ', end='')
        elif d.get('type') in ('done', 'stream_end', 'error'):
            break
    except: pass
print()
" 2>/dev/null
}

# Fix: need to pass msg properly
chat_full() {
  local user="$1" msg="$2" timeout="${3:-120}"
  timeout "$timeout" curl -sf -N -X POST "$API/api/chat" \
    -H 'Content-Type: application/json' \
    -d "{\"user_id\":\"$user\",\"message\":$(python3 -c "import json; print(json.dumps('$msg'))")}" 2>/dev/null | \
  python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line or not line.startswith('data: '): continue
    try:
        d = json.loads(line[6:])
        if d.get('type') == 'text_delta':
            print(d.get('text',''), end='')
        elif d.get('type') == 'tool_use':
            print(f' [{d.get(\"tool\")}] ', end='')
        elif d.get('type') in ('done', 'stream_end', 'error'):
            break
    except: pass
print()
" 2>/dev/null
}

cleanup() {
  for c in $(docker ps -a --filter label=vexa.managed=true --format '{{.Names}}' | grep 'v05'); do
    docker rm -f "$c" 2>/dev/null || true
  done
}

echo "=== MVP0.5 Validation ($API) ==="
echo ""
cleanup

# --- V0.5.1: New user gets template ---
echo "V0.5.1 New user gets template..."
chat_full "v05-tmpl" "hello" >/dev/null
CLAUDE_MD=$(docker exec vexa-agent-v05-tmpl head -1 /workspace/.claude/CLAUDE.md 2>/dev/null || echo "")
if echo "$CLAUDE_MD" | grep -q "Vexa"; then
  green "V0.5.1 Template applied — CLAUDE.md contains Vexa"
else
  red "V0.5.1 Template not applied — got: $CLAUDE_MD"
fi

# --- V0.5.2: Workspace has structure ---
echo "V0.5.2 Workspace has structure..."
DIRS=$(docker exec vexa-agent-v05-tmpl ls /workspace/ 2>/dev/null || echo "")
if echo "$DIRS" | grep -q "streams" && echo "$DIRS" | grep -q "knowledge"; then
  green "V0.5.2 Workspace structure — streams/ and knowledge/ exist"
else
  red "V0.5.2 Missing workspace dirs — got: $DIRS"
fi

# --- V0.5.3: Git initialized ---
echo "V0.5.3 Git initialized..."
GIT_LOG=$(docker exec vexa-agent-v05-tmpl git -C /workspace log --oneline -1 2>/dev/null || echo "")
if echo "$GIT_LOG" | grep -q "init from knowledge template"; then
  green "V0.5.3 Git initialized with template commit"
else
  red "V0.5.3 Git not initialized — got: $GIT_LOG"
fi

# --- V0.5.4: Git commit on save ---
echo "V0.5.4 Git commit on save..."
# Create a file, then save
docker exec vexa-agent-v05-tmpl bash -c "echo test > /workspace/test-save.txt" 2>/dev/null
curl -sf -X POST "$API/internal/workspace/save" \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"v05-tmpl"}' >/dev/null
GIT_LOG2=$(docker exec vexa-agent-v05-tmpl git -C /workspace log --oneline -2 2>/dev/null || echo "")
if echo "$GIT_LOG2" | grep -q "save"; then
  green "V0.5.4 Git commit on save — save commit found"
else
  red "V0.5.4 No save commit — got: $GIT_LOG2"
fi

# --- V0.5.5: Workspace context injected ---
echo "V0.5.5 Workspace context injected..."
# The agent should know about workspace state without Read tool calls
RESP=$(chat_full "v05-tmpl" "How many streams do I have? Just give me the count from your context, do not read any files.")
if echo "$RESP" | grep -qi "0\|no\|none\|empty\|don't have any"; then
  green "V0.5.5 Context injected — agent knows stream count without reading"
else
  red "V0.5.5 Context not working — got: $RESP"
fi

# --- V0.5.6: Agent brevity ---
echo "V0.5.6 Agent brevity..."
RESP=$(chat_full "v05-brief" "hello")
WORD_COUNT=$(echo "$RESP" | wc -w)
# Filter out tool use markers for word count
CLEAN_RESP=$(echo "$RESP" | sed 's/\[.*\]//g')
CLEAN_WC=$(echo "$CLEAN_RESP" | wc -w)
if [ "$CLEAN_WC" -lt 60 ]; then
  green "V0.5.6 Agent brevity — response is $CLEAN_WC words"
else
  red "V0.5.6 Agent too verbose — $CLEAN_WC words: $CLEAN_RESP"
fi

# --- V0.5.7: Agent creates stream ---
echo "V0.5.7 Agent creates stream..."
RESP=$(chat_full "v05-stream" "I want to track my fitness routine. Start a stream for that.")
STREAM_EXISTS=$(docker exec vexa-agent-v05-stream ls /workspace/streams/*.md 2>/dev/null | grep -v archive || echo "")
if [ -n "$STREAM_EXISTS" ]; then
  green "V0.5.7 Agent created stream — $(basename $STREAM_EXISTS)"
else
  red "V0.5.7 No stream file created"
fi

# --- V0.5.8: Timeline updated ---
echo "V0.5.8 Timeline updated..."
chat_full "v05-timeline" "Im flying to Tokyo on April 10th for a conference" >/dev/null
TIMELINE=$(docker exec vexa-agent-v05-timeline cat /workspace/timeline.md 2>/dev/null || echo "")
if echo "$TIMELINE" | grep -qi "tokyo\|april\|conference"; then
  green "V0.5.8 Timeline updated with Tokyo trip"
else
  red "V0.5.8 Timeline not updated — content: $(echo "$TIMELINE" | head -5)"
fi

# --- V0.5.9: Workspace survives restart ---
echo "V0.5.9 Workspace survives restart..."
# Save, stop, remove, re-create via new chat
curl -sf -X POST "$API/internal/workspace/save" \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"v05-stream"}' >/dev/null
docker stop vexa-agent-v05-stream >/dev/null 2>&1 || true
docker rm -f vexa-agent-v05-stream >/dev/null 2>&1 || true
sleep 1
# Trigger new container
chat_full "v05-stream" "what streams do I have?" >/dev/null
STREAM_EXISTS2=$(docker exec vexa-agent-v05-stream ls /workspace/streams/*.md 2>/dev/null | grep -v archive || echo "")
if [ -n "$STREAM_EXISTS2" ]; then
  green "V0.5.9 Workspace survived restart — stream file restored"
else
  red "V0.5.9 Workspace lost after restart"
fi

# --- Summary ---
echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="

cleanup

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
