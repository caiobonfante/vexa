#!/bin/bash
# Stop hook: check confidence protocol compliance.
# Only BLOCKS (exit 2) when confidence is reported >= 80 without adversarial check.
# Otherwise warns (exit 0) so work isn't interrupted.

INPUT=$(cat)
LAST_MSG=$(echo "$INPUT" | jq -r '.last_assistant_message // empty')

# Check if confidence was reported
CONF=$(echo "$LAST_MSG" | grep -oP 'Confidence:\s*\K\d+' | tail -1)

if [[ -z "$CONF" ]]; then
  # No confidence reported — warn but don't block
  echo "Confidence protocol not followed:"
  echo "- No confidence level reported. State your confidence (0-100) based on OBSERVABLE evidence (test results, curl responses, browser verification). 'Code looks correct' = 0."
  echo ""
  echo "Read .claude/CLAUDE.md 'Confidence Protocol' section. Then: report confidence from evidence, run adversarial check if >= 80, verify system health."
  exit 0  # warn, don't block
fi

# Confidence >= 80: require adversarial check
if [[ "$CONF" -ge 80 ]]; then
  HAS_ADVERSARIAL=$(echo "$LAST_MSG" | grep -ci "adversarial\|what bugs\|what could go wrong\|self-assessment")
  if [[ "$HAS_ADVERSARIAL" -eq 0 ]]; then
    echo "Confidence >= 80 reported ($CONF) but no adversarial self-assessment found."
    echo "Run: 'what bugs can you find in what I just did?' before declaring done."
    exit 2  # BLOCK
  fi
fi

exit 0
