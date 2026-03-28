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

# Find conductor dir
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
CONDUCTOR_DIR="${CWD}/conductor"
if [[ ! -d "$CONDUCTOR_DIR" ]]; then
  CONDUCTOR_DIR="$(cd "$CWD" && git rev-parse --show-toplevel 2>/dev/null)/conductor"
fi

# Check if there's an active mission in state.json
MISSION=$(python3 -c "
import json
from pathlib import Path
s = Path('$CONDUCTOR_DIR/state.json')
if s.exists():
    d = json.loads(s.read_text())
    m = d.get('mission','')
    status = d.get('status','')
    if m and status in ('running','delivering'):
        print(m)
" 2>/dev/null || true)

# No active mission — allow stop
if [[ -z "$MISSION" ]]; then
  exit 0
fi

MISSION_FILE="$CONDUCTOR_DIR/missions/${MISSION}.md"
if [[ ! -f "$MISSION_FILE" ]]; then
  exit 0
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
