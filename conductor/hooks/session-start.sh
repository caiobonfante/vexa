#!/bin/bash
# SessionStart hook: loads confidence protocol and logs proof of firing.
LOGFILE="/tmp/vexa-hooks.log"
CLAUDE_MD="/home/dima/dev/vexa-agentic-runtime/.claude/CLAUDE.md"

echo "[$(date '+%H:%M:%S')] SessionStart fired" >> "$LOGFILE"

if [[ -f "$CLAUDE_MD" ]]; then
  cat "$CLAUDE_MD"
  echo "[$(date '+%H:%M:%S')] SessionStart: CLAUDE.md loaded" >> "$LOGFILE"
else
  echo "WARNING: $CLAUDE_MD not found"
  echo "[$(date '+%H:%M:%S')] SessionStart: CLAUDE.md NOT FOUND" >> "$LOGFILE"
fi
