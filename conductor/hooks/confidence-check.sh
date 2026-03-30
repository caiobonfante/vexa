#!/bin/bash
# Stop hook: enforces the confidence protocol on EVERY stop.

LOGFILE="/tmp/vexa-hooks.log"

INPUT=$(cat)
STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')

if [[ "$STOP_ACTIVE" == "true" ]]; then
  echo "[$(date '+%H:%M:%S')] Stop: PASS (anti-loop)" >> "$LOGFILE"
  exit 0
fi

LAST_MSG=$(echo "$INPUT" | jq -r '.last_assistant_message // empty')

# Build search text: last message + recent transcript
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
RECENT=""
if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  RECENT=$(tail -50 "$TRANSCRIPT_PATH" 2>/dev/null || true)
fi
SEARCH_TEXT="${LAST_MSG}
${RECENT}"

echo "[$(date '+%H:%M:%S')] Stop: ENFORCING (${#LAST_MSG} chars)" >> "$LOGFILE"

MISSING=""

# Check 1: Confidence number reported?
HAS_CONFIDENCE=$(echo "$SEARCH_TEXT" | grep -ciE "confidence:?\s*[0-9]+|confidence\s+(is|at|level|of)\s+[0-9]+|[0-9]+/100" || true)
if [[ "$HAS_CONFIDENCE" -eq 0 ]]; then
  MISSING="${MISSING}\n- No confidence level reported. State your confidence (0-100) based on OBSERVABLE evidence (test results, curl responses, browser verification). 'Code looks correct' = 0."
fi

# Check 2: Adversarial check at 80+?
HIGH_CONF=$(echo "$SEARCH_TEXT" | grep -oiE "confidence:?\s*[0-9]+|[0-9]+/100" | grep -oE "[0-9]+" | tail -1 || true)
if [[ -n "$HIGH_CONF" ]] && [[ "$HIGH_CONF" -ge 80 ]]; then
  HAS_ADVERSARIAL=$(echo "$SEARCH_TEXT" | grep -ciE "what (bugs|could be wrong|might fail|could go wrong|issues can)|adversarial|bug.?find|what.*(wrong|break|fail)" || true)
  if [[ "$HAS_ADVERSARIAL" -eq 0 ]]; then
    MISSING="${MISSING}\n- Confidence >= 80 but no adversarial self-assessment. Before stopping, ask: 'What bugs can I find in what I just did?' and report findings."
  fi
fi

# Check 3: System health verified?
# Skip health check for planning/docs-only work (no code edits, no deploys, no service restarts).
IS_CODE_WORK=$(echo "$SEARCH_TEXT" | grep -ciE "edit.*file|wrote.*code|deploy|docker.*(up|restart|build)|compose.*up|service.*(start|restart|stop)|curl.*localhost|pip install|npm|make |build" || true)
if [[ "$IS_CODE_WORK" -gt 0 ]]; then
  HAS_HEALTH=$(echo "$SEARCH_TEXT" | grep -ciE "dashboard.*(load|reach|access|200|respond)|curl.*(dashboard|localhost|gateway)|entry.?point.*(work|load|respond|verified)|system.*(health|check|verified)|user.*(can|able).*(reach|access|load)|read-only.*(diagnostic|review|task)|no.*(code change|deploy|service)" || true)
  if [[ "$HAS_HEALTH" -eq 0 ]]; then
    MISSING="${MISSING}\n- No system health verification. Before stopping, verify the user can reach the entry point (dashboard loads, API responds)."
  fi
else
  echo "[$(date '+%H:%M:%S')] Stop: health check skipped (planning/docs-only work)" >> "$LOGFILE"
fi

if [[ -z "$MISSING" ]]; then
  echo "[$(date '+%H:%M:%S')] Stop: PASS (confidence protocol followed)" >> "$LOGFILE"
  echo "✓ confidence check passed" >&2
  exit 0
fi

echo "[$(date '+%H:%M:%S')] Stop: BLOCK" >> "$LOGFILE"

REASON=$(printf "Confidence protocol not followed:%b\n\nRead .claude/CLAUDE.md 'Confidence Protocol' section. Then: report confidence from evidence, run adversarial check if >= 80, verify system health." "$MISSING")
jq -n --arg reason "$REASON" '{
  decision: "block",
  reason: $reason
}'
exit 0
