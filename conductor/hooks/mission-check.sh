#!/bin/bash
# Stop hook: checks if the current mission target is met.
# If not, blocks Claude from stopping and injects what's missing.
#
# Called by Claude Code's Stop hook mechanism.
# Input: JSON on stdin with session_id, transcript_path, cwd, stop_hook_active
# Output: JSON with decision: "block" or nothing (exit 0 = allow)

set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')

# Prevent infinite loop — if we already forced continuation once, let it stop
if [[ "$STOP_ACTIVE" == "true" ]]; then
  exit 0
fi

# Find the active mission file
CONDUCTOR_DIR="${CWD}/conductor"
if [[ ! -d "$CONDUCTOR_DIR" ]]; then
  # Maybe we're in a worktree — check parent
  CONDUCTOR_DIR="$(cd "$CWD" && git rev-parse --show-toplevel 2>/dev/null)/conductor"
fi

# Find mission file — check state.json for active mission, or find newest mission file
MISSION_FILE=""
if [[ -f "$CONDUCTOR_DIR/state.json" ]]; then
  MISSION=$(python3 -c "import json; print(json.loads(open('$CONDUCTOR_DIR/state.json').read()).get('mission','') or '')" 2>/dev/null)
  if [[ -n "$MISSION" ]]; then
    MISSION_FILE="$CONDUCTOR_DIR/missions/${MISSION}.md"
  fi
fi

# No mission = allow stop
if [[ -z "$MISSION_FILE" || ! -f "$MISSION_FILE" ]]; then
  exit 0
fi

# Run completion check
RESULT=$(python3 "$CONDUCTOR_DIR/check-completion.py" --check --mission "$MISSION_FILE" --state "$CONDUCTOR_DIR/state.json" 2>&1 || true)

if echo "$RESULT" | grep -q "^DONE\|^STOP"; then
  # Target met — allow stop
  exit 0
fi

# Not done — block stop and tell agent what's missing
REASON=$(echo "$RESULT" | head -5)
jq -n --arg reason "$REASON" '{
  decision: "block",
  reason: ("Mission not complete. " + $reason)
}'
exit 0
