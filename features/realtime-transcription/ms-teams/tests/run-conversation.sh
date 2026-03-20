#!/bin/bash
# Long multi-speaker conversation with ground truth
# Speakers: Alice (user 1), Bob (user 2), Charlie (user 3)
# Patterns: normal turns, back-to-back, overlapping, short interjections

API="http://localhost:8066"
ALICE="vxa_user_pZqJ5dEQK47Mc7YeVTR53wAefBCs7Nf6d0fHbHs8"
BOB="vxa_user_o9V6HLC3emrG4d1TRMrZtItnP1KJc6cOaCPeXcV1"
CHARLIE="vxa_user_l4GvApfciQGRrNuUNTNixCb5bLDQ0g171G5fbNay"
MID="9378555217628"

speak() {
  local token=$1 voice=$2 text=$3 speaker=$4
  local ts=$(date +%s.%N)
  echo "[GROUND_TRUTH] t=$ts speaker=$speaker voice=$voice text=\"$text\""
  curl -s -X POST "$API/bots/teams/$MID/speak" \
    -H "X-API-Key: $token" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"$text\",\"provider\":\"openai\",\"voice\":\"$voice\"}" > /dev/null
}

echo "=== CONVERSATION START $(date -Iseconds) ==="

# --- ROUND 1: Normal turns with pauses ---
echo "--- Round 1: Normal turns ---"
speak "$ALICE" "nova" "Good morning everyone. I want to start by reviewing our product metrics from last month. We had over fifty thousand active users which is a new record for us." "Alice"
sleep 14

speak "$BOB" "echo" "Those numbers are impressive Alice. Can you break down the user growth by region? I am particularly interested in the European market expansion." "Bob"
sleep 14

speak "$CHARLIE" "onyx" "I can add some context there. The European launch exceeded our targets by twenty percent. Germany and France were the strongest markets with over ten thousand users each." "Charlie"
sleep 14

# --- ROUND 2: Back-to-back (minimal gap) ---
echo "--- Round 2: Back-to-back rapid turns ---"
speak "$ALICE" "nova" "That is excellent news from Europe. What about customer retention rates?" "Alice"
sleep 8

speak "$BOB" "echo" "Retention is at eighty five percent which is up from last quarter." "Bob"
sleep 7

speak "$CHARLIE" "onyx" "And churn has decreased to just three percent overall." "Charlie"
sleep 7

speak "$ALICE" "nova" "Perfect. Those are strong numbers across the board." "Alice"
sleep 8

# --- ROUND 3: Longer monologue (single speaker) ---
echo "--- Round 3: Long monologue ---"
speak "$BOB" "echo" "Let me walk through the technical roadmap for next quarter. We are planning three major releases. First we will launch the new dashboard with real time analytics. Second we are rebuilding the notification system to support push notifications on mobile. And third we are introducing an API version two with better rate limiting and pagination. The engineering team has been working on these features for the past six weeks and we are on track for an April launch." "Bob"
sleep 25

# --- ROUND 4: Quick back and forth (2-person rapid exchange) ---
echo "--- Round 4: Quick exchange Alice-Charlie ---"
speak "$ALICE" "nova" "Will the new API be backwards compatible?" "Alice"
sleep 6

speak "$CHARLIE" "onyx" "Yes completely backwards compatible. We are keeping all version one endpoints active." "Charlie"
sleep 7

speak "$ALICE" "nova" "Good. And what about the authentication changes?" "Alice"
sleep 6

speak "$CHARLIE" "onyx" "We are moving to OAuth two point zero. The migration guide is already drafted." "Charlie"
sleep 7

# --- ROUND 5: Overlap attempt (send two speakers with minimal gap) ---
echo "--- Round 5: Near-simultaneous speech ---"
speak "$ALICE" "nova" "I think we should also discuss the budget allocation for the marketing team." "Alice"
sleep 2
speak "$BOB" "echo" "Before we move on I wanted to mention that we need additional cloud infrastructure budget for the API launch." "Bob"
sleep 14

# --- ROUND 6: Short interjections ---
echo "--- Round 6: Short interjections ---"
speak "$CHARLIE" "onyx" "Agreed." "Charlie"
sleep 4

speak "$ALICE" "nova" "Absolutely." "Alice"
sleep 4

speak "$BOB" "echo" "Makes sense." "Bob"
sleep 4

speak "$CHARLIE" "onyx" "Let us circle back on the budget discussion next week. I will prepare a detailed cost breakdown for the cloud infrastructure and marketing spend. Great meeting everyone." "Charlie"
sleep 14

echo "=== CONVERSATION END $(date -Iseconds) ==="
echo "Waiting 30s for pipeline to settle..."
sleep 30
echo "Done."
