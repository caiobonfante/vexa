#!/bin/bash
# Run single-speaker test commands.
#
# Usage:
#   ./run.sh core              Generate core data (transcript.jsonl)
#   ./run.sh tick N             Render tick N to output files
#   ./run.sh tick all           Render all ticks sequentially
#   ./run.sh step              Interactive dashboard replay
#   ./run.sh validate          Check core data for known issues

set -euo pipefail

CMD="${1:?Usage: ./run.sh <core|tick|step|validate> [args]}"
DIR="$(cd "$(dirname "$0")" && pwd)"
TESTS_DIR="$(dirname "$DIR")"
ENV_FILE="$DIR/../../.env"
DATASET_DIR="$DIR/dataset"
OUTPUT_DIR="$DIR/output"

if [ -f "$ENV_FILE" ]; then
  source "$ENV_FILE"
fi

mkdir -p "$OUTPUT_DIR" "$DATASET_DIR/core"

case "$CMD" in
  core)
    echo "=== Generating core data ==="
    echo "Audio: $DATASET_DIR/audio.wav"
    TRANSCRIPTION_URL="${TRANSCRIPTION_URL:?}" \
    TRANSCRIPTION_TOKEN="${TRANSCRIPTION_TOKEN:?}" \
    node "$TESTS_DIR/generate-core.js" \
      "$DATASET_DIR/audio.wav" \
      "$DATASET_DIR/core"
    echo ""
    echo "Output: $DATASET_DIR/core/transcript.jsonl"
    TICKS=$(wc -l < "$DATASET_DIR/core/transcript.jsonl")
    CONFIRMED=$(python3 -c "import json; print(sum(len(json.loads(l).get('confirmed',[])) for l in open('$DATASET_DIR/core/transcript.jsonl')))")
    echo "Ticks: $TICKS, Confirmed segments: $CONFIRMED"
    ;;

  tick)
    N="${2:?Usage: ./run.sh tick <number|all>}"
    JSONL="$DATASET_DIR/core/transcript.jsonl"
    GT="$DATASET_DIR/ground-truth.json"

    if [ ! -f "$JSONL" ]; then
      echo "Error: $JSONL not found. Run './run.sh core' first."
      exit 1
    fi

    if [ "$N" = "all" ]; then
      TOTAL=$(wc -l < "$JSONL")
      for i in $(seq 1 "$TOTAL"); do
        CORE_PATH="$JSONL" GT_PATH="$GT" OUT_DIR="$OUTPUT_DIR" node "$TESTS_DIR/tick.js" "$i" > /dev/null
        # Show one-line summary
        HEAD=$(head -1 "$OUTPUT_DIR/rendered.txt" 2>/dev/null | cut -c1-60)
        LINES=$(wc -l < "$OUTPUT_DIR/rendered.txt" 2>/dev/null)
        echo "TICK $i/$TOTAL | ${LINES} lines | ${HEAD}"
      done
    else
      CORE_PATH="$JSONL" GT_PATH="$GT" OUT_DIR="$OUTPUT_DIR" node "$TESTS_DIR/tick.js" "$N"
      echo ""
      echo "=== rendered.txt ==="
      cat "$OUTPUT_DIR/rendered.txt"
      echo ""
      echo "=== gt.txt ==="
      cat "$OUTPUT_DIR/gt.txt"
    fi
    ;;

  step)
    JSONL="$DATASET_DIR/core/transcript.jsonl"
    GT="$DATASET_DIR/ground-truth.json"

    if [ ! -f "$JSONL" ]; then
      echo "Error: $JSONL not found. Run './run.sh core' first."
      exit 1
    fi

    API_TOKEN="${API_TOKEN:?}" \
    REDIS_URL="${REDIS_URL:?}" \
    CORE_PATH="$JSONL" \
    GT_PATH="$GT" \
    node "$TESTS_DIR/step.js"
    ;;

  validate)
    JSONL="$DATASET_DIR/core/transcript.jsonl"

    if [ ! -f "$JSONL" ]; then
      echo "Error: $JSONL not found. Run './run.sh core' first."
      exit 1
    fi

    echo "=== Validating core data ==="
    python3 -c "
import json, sys

ticks = [json.loads(l) for l in open('$JSONL')]
issues = 0

# Check 1: confirmed/pending overlap
for i, t in enumerate(ticks):
    for c in t.get('confirmed', []):
        for p in t.get('pending', []):
            ct, pt = c.get('text','').strip(), p.get('text','').strip()
            if pt == ct or pt.startswith(ct) or ct.startswith(pt):
                print(f'OVERLAP tick {i+1}: C=\"{ct[:40]}\" P=\"{pt[:40]}\"')
                issues += 1

# Check 2: confirmed have required fields
for i, t in enumerate(ticks):
    for c in t.get('confirmed', []):
        if not c.get('absolute_start_time'):
            print(f'MISSING absolute_start_time tick {i+1}: \"{c.get(\"text\",\"\")[:40]}\"')
            issues += 1
        if not c.get('segment_id'):
            print(f'MISSING segment_id tick {i+1}: \"{c.get(\"text\",\"\")[:40]}\"')
            issues += 1
        if not c.get('completed'):
            print(f'MISSING completed tick {i+1}: \"{c.get(\"text\",\"\")[:40]}\"')
            issues += 1

# Check 3: monotonic confirmed count
confirmed = {}
prev_count = 0
for i, t in enumerate(ticks):
    for c in t.get('confirmed', []):
        key = c.get('segment_id') or c.get('absolute_start_time')
        confirmed[key] = c
    if len(confirmed) < prev_count:
        print(f'REGRESSION tick {i+1}: confirmed dropped from {prev_count} to {len(confirmed)}')
        issues += 1
    prev_count = len(confirmed)

total_confirmed = sum(len(t.get('confirmed',[])) for t in ticks)
print(f'Ticks: {len(ticks)}')
print(f'Confirmed segments: {total_confirmed}')
print(f'Issues: {issues}')
sys.exit(1 if issues > 0 else 0)
"
    ;;

  *)
    echo "Unknown command: $CMD"
    echo "Usage: ./run.sh <core|tick|step|validate>"
    exit 1
    ;;
esac
