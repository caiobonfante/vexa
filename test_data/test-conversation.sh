#!/bin/bash
# Test conversation for Teams speaker attribution testing.
# Requires: 3 speaker bots (Karl, Francesco, Alberto) already active in the meeting.
# Speaker keys stored in /tmp/speakers.txt (uid:key:voice:name per line).
#
# Usage: bash test_data/test-conversation.sh

API_URL="${API_URL:-http://localhost:8066}"
MEETING_ID="${MEETING_ID:-9383010294321}"

declare -A KEYS VOICES
while IFS=: read uid key voice name; do
  KEYS[$name]=$key
  VOICES[$name]=$voice
done < /tmp/speakers.txt

speak() {
  local name=$1 text=$2
  curl -s -X POST "$API_URL/bots/teams/$MEETING_ID/speak" \
    -H "X-API-Key: ${KEYS[$name]}" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"$text\",\"voice\":\"${VOICES[$name]}\"}" > /dev/null &
}

echo "=== Test conversation: launch planning sync ==="
echo "Speakers: Karl (alloy), Francesco (echo), Alberto (fable)"
echo ""

speak Karl "Hey everyone, quick sync on the launch timeline."
sleep 5

speak Francesco "We're on track for Thursday. QA signed off yesterday."
sleep 5

speak Alberto "Did they test the payment flow? That was the blocker last week."
sleep 5

speak Francesco "Yes, all payment scenarios passed including refunds and partial captures."
sleep 6

speak Karl "What about load testing?"
sleep 3

speak Alberto "We ran it. Peak handles twelve thousand requests per second."
sleep 5

speak Karl "That's above our target. Good work."
sleep 4

speak Francesco "One concern though. The error rate spikes at around ten thousand."
sleep 5

speak Karl "How high does it spike?"
sleep 3

speak Francesco "About two percent. Mostly timeouts on the inventory service."
sleep 5

speak Alberto "We can add a circuit breaker there. I can have it done by tomorrow."
sleep 5

speak Karl "Do it. Anything else blocking the launch?"
sleep 4

speak Francesco "Documentation needs an update but that won't block."
sleep 4

speak Karl "Agreed. Let's ship Thursday. Good meeting everyone."
sleep 5

wait
echo ""
echo "=== Conversation complete ==="
