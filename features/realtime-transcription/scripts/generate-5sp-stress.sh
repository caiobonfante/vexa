#!/bin/bash
# Generate TTS audio + ground truth + synthetic events for teams-5sp-stress dataset
set -e

OUTDIR="$(cd "$(dirname "$0")" && pwd)/../data/raw/teams-5sp-stress/audio"
mkdir -p "$OUTDIR"
NETWORK="vexa-restore_vexa_default"
TTS_HOST="tts-service:8002"
VOICE="en_US-lessac-medium"

BASE_TS="2026-03-21T02:00:00"
EVENTS_FILE="$OUTDIR/events.txt"
> "$EVENTS_FILE"

generate() {
  local num="$1" speaker="$2" offset="$3" tag="$4"
  shift 4
  local text="$*"

  local wavfile="$OUTDIR/${num}-${speaker}.wav"
  local txtfile="$OUTDIR/${num}-${speaker}.txt"

  echo "[$num] $speaker @ ${offset}s ($tag): \"${text:0:50}...\""

  # Generate TTS WAV via stdout
  docker run --rm --network "$NETWORK" curlimages/curl \
    -s -X POST "http://$TTS_HOST/v1/audio/speech" \
    -H "Content-Type: application/json" \
    -d "{\"input\":\"$text\",\"voice\":\"$VOICE\"}" \
    > "$wavfile"

  echo "$text" > "$txtfile"
}

add_speaker_change() {
  local offset="$1" from_display="$2" to_display="$3"
  echo "${BASE_TS}.${offset}00000000Z [BotCore] [Teams Captions] Speaker change: $from_display → $to_display (Guest) (flushed 5 chunks, discarded 0 stale)" >> "$EVENTS_FILE"
}

add_caption() {
  local offset="$1" display="$2"
  shift 2
  local text="$*"
  echo "${BASE_TS}.${offset}00000000Z [BotCore] [📝 TEAMS CAPTION] \"$display (Guest)\": $text" >> "$EVENTS_FILE"
}

echo "=== Generating teams-5sp-stress dataset ==="

prev=""

emit() {
  local num="$1" speaker="$2" offset="$3" tag="$4"
  shift 4
  local text="$*"

  # Map speaker to display name
  local display
  case "$speaker" in
    alice) display="Alice" ;;
    bob) display="Bob" ;;
    charlie) display="Charlie" ;;
    diana) display="Diana" ;;
    eddie) display="Eddie" ;;
  esac

  generate "$num" "$speaker" "$offset" "$tag" "$text"

  if [ "$speaker" != "$prev" ]; then
    local from_display
    case "$prev" in
      alice) from_display="Alice" ;;
      bob) from_display="Bob" ;;
      charlie) from_display="Charlie" ;;
      diana) from_display="Diana" ;;
      eddie) from_display="Eddie" ;;
      *) from_display="(none)" ;;
    esac
    add_speaker_change "$offset" "$from_display" "$display"
    prev="$speaker"
  fi

  add_caption "$offset" "$display" "$text"
}

# Control normal (5 utterances, >3s gaps)
emit 01 alice   0   control-normal "Good morning everyone. Let me walk through the quarterly results for all five regions."
emit 02 bob     14  control-normal "Sounds good. Which region should we start with?"
emit 03 charlie 21  control-normal "Let us begin with Europe since that had the strongest growth this quarter."
emit 04 diana   30  control-normal "I agree. The European numbers were really impressive across all segments."
emit 05 eddie   39  control-normal "Before we dive in, I want to flag that the Asia Pacific numbers also exceeded our forecast by a significant margin."

# Short phrases (10 utterances, 2s gaps)
emit 06 alice   52  short-phrase "Right."
emit 07 bob     54  short-phrase "OK."
emit 08 charlie 56  short-phrase "Sure."
emit 09 diana   58  short-phrase "Got it."
emit 10 eddie   60  short-phrase "Agreed."
emit 11 alice   62  short-phrase "Yes."
emit 12 bob     64  short-phrase "Makes sense."
emit 13 charlie 66  short-phrase "Noted."
emit 14 diana   68  short-phrase "Done."
emit 15 eddie   70  short-phrase "Perfect."

# 30s silence gap (72s - 102s) — no utterances

# Rapid exchange (8 utterances, <1s gaps)
emit 16 alice   104 rapid-exchange "Any other thoughts on the budget?"
emit 17 bob     105 rapid-exchange "I think we should increase it."
emit 18 charlie 107 rapid-exchange "Same here."
emit 19 diana   108 rapid-exchange "How much more?"
emit 20 eddie   109 rapid-exchange "At least twenty percent."
emit 21 alice   110 rapid-exchange "That works for me."
emit 22 bob     112 rapid-exchange "Agreed, let us do it."
emit 23 charlie 113 rapid-exchange "I will update the spreadsheet."

# Control close (2 utterances, 3s gaps)
emit 24 diana   120 control-close "Thanks everyone for a productive discussion. I will send the meeting notes shortly."
emit 25 eddie   130 control-close "Great meeting. Talk to you all next week."

echo ""
echo "=== Generated ==="
echo "WAV files: $(ls "$OUTDIR"/*.wav 2>/dev/null | wc -l)"
echo "TXT files: $(ls "$OUTDIR"/*.txt 2>/dev/null | wc -l)"
echo "Events: $(wc -l < "$EVENTS_FILE") lines"
echo ""
echo "To replay: DATASET=teams-5sp-stress make play-replay"
