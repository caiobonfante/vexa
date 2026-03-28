#!/bin/bash
# Stop hook: checks if the current mission target is met.
# Only fires when CONDUCTOR_MISSION env var is set (delivery sessions).
# Returns {"decision":"block","reason":"..."} to force continuation.

set -euo pipefail

INPUT=$(cat)
STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')

# Already forced once — let it stop (prevent infinite loop)
if [[ "$STOP_ACTIVE" == "true" ]]; then
  exit 0
fi

# Only block delivery sessions (conductor sets CONDUCTOR_MISSION before launch)
if [[ -z "${CONDUCTOR_MISSION:-}" ]]; then
  exit 0
fi

# Find conductor dir
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
CONDUCTOR_DIR="${CWD}/conductor"
if [[ ! -d "$CONDUCTOR_DIR" ]]; then
  CONDUCTOR_DIR="$(cd "$CWD" && git rev-parse --show-toplevel 2>/dev/null)/conductor"
fi

MISSION_FILE="$CONDUCTOR_DIR/missions/${CONDUCTOR_MISSION}.md"
if [[ ! -f "$MISSION_FILE" ]]; then
  exit 0  # No mission file — allow stop
fi

# Check completion
RESULT=$(python3 "$CONDUCTOR_DIR/check-completion.py" --check --mission "$MISSION_FILE" --state "$CONDUCTOR_DIR/state.json" 2>&1 || true)

if echo "$RESULT" | grep -q "^DONE\|^STOP"; then
  exit 0  # Target met — allow stop
fi

# Not done — block and tell agent what's missing
REASON=$(echo "$RESULT" | head -5)
jq -n --arg reason "$REASON" '{
  decision: "block",
  reason: ("Mission not complete. " + $reason)
}'
exit 0
