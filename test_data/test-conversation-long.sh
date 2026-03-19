#!/bin/bash
# Longer test conversation — speakers give fuller answers, more natural flow.
# Requires: 3 speaker bots (Karl, Francesco, Alberto) already active in the meeting.
# Speaker keys stored in /tmp/speakers.txt (uid:key:voice:name per line).
#
# Usage: MEETING_ID=xxx bash test_data/test-conversation-long.sh

API_URL="${API_URL:-http://localhost:8066}"
MEETING_ID="${MEETING_ID:-$(cat /tmp/meeting-id.txt 2>/dev/null)}"

if [ -z "$MEETING_ID" ]; then echo "Set MEETING_ID or write it to /tmp/meeting-id.txt"; exit 1; fi

declare -A KEYS VOICES
while IFS=: read uid key voice name; do
  KEYS[$name]=$key
  VOICES[$name]=$voice
done < /tmp/speakers.txt

speak() {
  local name=$1 text=$2
  echo "[$name]: ${text:0:70}..."
  curl -s -X POST "$API_URL/bots/teams/$MEETING_ID/speak" \
    -H "X-API-Key: ${KEYS[$name]}" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"$text\",\"voice\":\"${VOICES[$name]}\"}" > /dev/null &
}

echo "=== Long conversation: product strategy meeting ==="
echo "Meeting: $MEETING_ID"
echo ""

speak Karl "Good morning everyone. Today I want to talk about our product strategy for the next quarter. We have three major initiatives on the table, and I'd like to get alignment from the team before we finalize the roadmap."
sleep 14

speak Francesco "Thanks Karl. I've been thinking a lot about this. From the engineering side, I believe our top priority should be the API redesign. The current architecture is hitting scaling limits, and we're seeing increased latency during peak hours. If we don't address this now, it will only get worse as we onboard more enterprise customers."
sleep 18

speak Alberto "I agree that the API is important, but I want to make sure we don't lose sight of the user experience. Our latest customer surveys show that onboarding completion rates dropped fifteen percent last quarter. New users are struggling with the initial setup flow, and that directly impacts our conversion funnel."
sleep 16

speak Karl "Both valid points. Francesco, how long would the API redesign take if we dedicated a full squad to it?"
sleep 6

speak Francesco "Realistically, about eight to ten weeks for the core migration. We can do it incrementally though. Start with the highest traffic endpoints, swap them out one by one behind a feature flag. That way we reduce risk and can measure performance gains at each step."
sleep 14

speak Karl "And Alberto, what's your proposal for the onboarding issue?"
sleep 5

speak Alberto "I've been working with the design team on a new guided setup wizard. It breaks the current twelve step process into three simple phases. We tested a prototype with twenty users last week and saw completion rates jump from sixty to ninety two percent. It's a massive improvement."
sleep 16

speak Francesco "That's impressive. How much engineering effort does the wizard need?"
sleep 4

speak Alberto "About three weeks of frontend work, plus one week for backend changes to support the new progressive disclosure API. It's relatively contained and low risk."
sleep 10

speak Karl "OK so here's what I'm thinking. We run both in parallel. Francesco, your team starts the API migration with the top five endpoints. Alberto, you take a small squad and build the onboarding wizard. We review progress in four weeks and adjust if needed."
sleep 14

speak Francesco "That works for me. I'll draft the migration plan and share it by Friday. One thing though, we should coordinate on the API changes for Alberto's wizard so we're not duplicating work."
sleep 10

speak Alberto "Good call. Let's set up a thirty minute sync next Tuesday to align on the API contract for the new onboarding endpoints. I'll prepare the spec beforehand."
sleep 8

speak Karl "Perfect. Last topic. The third initiative was the analytics dashboard overhaul. Given what we just decided, should we push that to next quarter?"
sleep 8

speak Francesco "I think so. We don't have the bandwidth for three major projects simultaneously without burning out the team. The dashboard works, it's just not pretty. That can wait."
sleep 10

speak Alberto "Agreed. Let's focus on what moves the needle most. API performance and onboarding are both directly tied to revenue. The dashboard is nice to have."
sleep 8

speak Karl "Then we're aligned. API migration and onboarding wizard this quarter, dashboard next quarter. I'll update the roadmap and send it out today. Great discussion everyone, thanks for the input."
sleep 10

wait
echo ""
echo "=== Conversation complete ==="
