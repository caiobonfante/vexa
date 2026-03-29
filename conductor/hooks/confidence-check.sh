#!/bin/bash
# Stop hook: enforces the confidence protocol on DELIVERY responses only.
# Skips casual responses. Only enforces when the agent reports completed work.

LOGFILE="/tmp/vexa-hooks.log"

INPUT=$(cat)
STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')

if [[ "$STOP_ACTIVE" == "true" ]]; then
  echo "[$(date '+%H:%M:%S')] Stop: PASS (anti-loop)" >> "$LOGFILE"
  exit 0
fi

LAST_MSG=$(echo "$INPUT" | jq -r '.last_assistant_message // empty')

# Only enforce on delivery-like responses.
# A delivery response is long AND contains completion language.
MSG_LEN=${#LAST_MSG}
if [[ "$MSG_LEN" -lt 300 ]]; then
  echo "[$(date '+%H:%M:%S')] Stop: SKIP (${MSG_LEN} chars — not a delivery)" >> "$LOGFILE"
  exit 0
fi

# Check if message looks like a delivery (reporting results/completion)
IS_DELIVERY=$(echo "$LAST_MSG" | grep -ciE "pass|done|fixed|working|complete|verified|test.*pass|all.*pass|result|deploy|implement|finish" || true)
if [[ "$IS_DELIVERY" -eq 0 ]]; then
  echo "[$(date '+%H:%M:%S')] Stop: SKIP (no delivery language)" >> "$LOGFILE"
  exit 0
fi

# This is a delivery — enforce confidence protocol
echo "[$(date '+%H:%M:%S')] Stop: ENFORCING (delivery detected, ${MSG_LEN} chars)" >> "$LOGFILE"

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
RECENT=""
if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  RECENT=$(tail -30 "$TRANSCRIPT_PATH" 2>/dev/null || true)
fi
SEARCH_TEXT="${LAST_MSG}
${RECENT}"

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
HAS_HEALTH=$(echo "$SEARCH_TEXT" | grep -ciE "dashboard.*(load|reach|access|200|respond)|curl.*(dashboard|localhost|gateway)|entry.?point.*(work|load|respond|verified)|system.*(health|check|verified)|user.*(can|able).*(reach|access|load)" || true)
if [[ "$HAS_HEALTH" -eq 0 ]]; then
  MISSING="${MISSING}\n- No system health verification. Before stopping, verify the user can reach the entry point (dashboard loads, API responds)."
fi

if [[ -z "$MISSING" ]]; then
  echo "[$(date '+%H:%M:%S')] Stop: PASS (confidence protocol followed)" >> "$LOGFILE"
  exit 0
fi

echo "[$(date '+%H:%M:%S')] Stop: BLOCK" >> "$LOGFILE"

REASON=$(printf "Confidence protocol not followed:%b\n\nRead .claude/CLAUDE.md 'Confidence Protocol' section. Then: report confidence from evidence, run adversarial check if >= 80, verify system health." "$MISSING")
jq -n --arg reason "$REASON" '{
  decision: "block",
  reason: $reason
}'
exit 0
