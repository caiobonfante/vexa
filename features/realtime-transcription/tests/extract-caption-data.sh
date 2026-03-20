#!/bin/bash
# Extract raw caption event data from a listener bot's Docker logs.
# Outputs structured JSON for analysis.
#
# Usage: bash extract-caption-data.sh <container-name-or-id> [output.json]

CONTAINER=${1:?Usage: extract-caption-data.sh <container> [output.json]}
OUTPUT=${2:-/tmp/caption-events.json}

echo "Extracting caption data from $CONTAINER..."

docker logs "$CONTAINER" 2>&1 | python3 -c "
import sys, json, re

events = []
for line in sys.stdin:
    line = line.strip()

    # Caption text events: [📝 TEAMS CAPTION] \"Speaker\": text
    m = re.search(r'\[📝 TEAMS CAPTION\] \"([^\"]+)\": (.+)', line)
    if m:
        events.append({
            'type': 'caption_text',
            'speaker': m.group(1),
            'text': m.group(2),
            'raw': line,
        })
        continue

    # Speaker change: [Teams Captions] Speaker change: A → B
    m = re.search(r'Speaker change: (.+?) → (.+?)(?:\s*\(|$)', line)
    if m:
        events.append({
            'type': 'speaker_change',
            'from': m.group(1),
            'to': m.group(2),
            'raw': line,
        })
        continue

    # Caption flush: [Teams Captions] Flushed N chunks to Speaker
    m = re.search(r'Flushed (\d+) chunks to (.+?)(?:\s*\(|$)', line)
    if m:
        events.append({
            'type': 'flush',
            'chunks': int(m.group(1)),
            'speaker': m.group(2),
            'raw': line,
        })
        continue

    # DOM speaker events: SPEAKER_START/SPEAKER_END
    m = re.search(r'(SPEAKER_START|SPEAKER_END): (.+?) \(ID:', line)
    if m:
        events.append({
            'type': m.group(1).lower(),
            'speaker': m.group(2),
            'raw': line,
        })
        continue

    # MutationObserver fired
    m = re.search(r'MutationObserver fired \(#(\d+)', line)
    if m:
        events.append({
            'type': 'mutation',
            'count': int(m.group(1)),
            'raw': line,
        })
        continue

    # Confirmed segments
    m = re.search(r'\[📝 CONFIRMED\] (.+?) \| (\w+) \| ([\d.]+)s-([\d.]+)s \| .+? \| \"(.+?)\"', line)
    if m:
        events.append({
            'type': 'confirmed',
            'speaker': m.group(1),
            'language': m.group(2),
            'start_sec': float(m.group(3)),
            'end_sec': float(m.group(4)),
            'text': m.group(5),
            'raw': line,
        })
        continue

    # Draft segments
    m = re.search(r'\[📝 DRAFT\] (.+?) \| (\w+) \| ([\d.]+)s-([\d.]+)s \| .+? \| \"(.+?)\"', line)
    if m:
        events.append({
            'type': 'draft',
            'speaker': m.group(1),
            'language': m.group(2),
            'start_sec': float(m.group(3)),
            'end_sec': float(m.group(4)),
            'text': m.group(5),
            'raw': line,
        })
        continue

# Number events by sequence
for i, e in enumerate(events):
    e['seq'] = i

# Summary
caption_texts = [e for e in events if e['type'] == 'caption_text']
speaker_changes = [e for e in events if e['type'] == 'speaker_change']
flushes = [e for e in events if e['type'] == 'flush']
confirmed = [e for e in events if e['type'] == 'confirmed']
drafts = [e for e in events if e['type'] == 'draft']

print(f'Caption text events: {len(caption_texts)}', file=sys.stderr)
print(f'Speaker changes: {len(speaker_changes)}', file=sys.stderr)
print(f'Audio flushes: {len(flushes)}', file=sys.stderr)
print(f'Draft segments: {len(drafts)}', file=sys.stderr)
print(f'Confirmed segments: {len(confirmed)}', file=sys.stderr)
print(f'Total events: {len(events)}', file=sys.stderr)

# Unique speakers in captions
speakers = set(e['speaker'] for e in caption_texts)
print(f'Speakers: {speakers}', file=sys.stderr)

# Output
output = {
    'summary': {
        'caption_texts': len(caption_texts),
        'speaker_changes': len(speaker_changes),
        'flushes': len(flushes),
        'drafts': len(drafts),
        'confirmed': len(confirmed),
        'total': len(events),
        'speakers': list(speakers),
    },
    'events': events,
}

with open('$OUTPUT', 'w') as f:
    json.dump(output, f, indent=2)
print(f'Written to $OUTPUT', file=sys.stderr)
"

echo ""
echo "Raw data saved to $OUTPUT"
echo "Analyze with: python3 -c \"import json; d=json.load(open('$OUTPUT')); ...\""
