#!/bin/bash
# Split source audio into per-speaker segment files using ground truth.
#
# Usage: ./split-audio.sh
#
# Requires: ffmpeg, python3
# Input: dataset/source-16k.wav + dataset/ground-truth.json
# Output: dataset/speakers/{speaker}/*.wav + playlist.json

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
DATASET="$DIR/dataset"

python3 -c "
import json, subprocess, os

gt = json.load(open('$DATASET/ground-truth.json'))
audio = '$DATASET/source-16k.wav'
speakers_dir = '$DATASET/speakers'

by_speaker = {}
for i, seg in enumerate(gt):
    sp = seg['speaker'].lower().replace(' ', '-')
    if sp not in by_speaker:
        by_speaker[sp] = []
    by_speaker[sp].append({ 'index': i, **seg })

for sp, segs in by_speaker.items():
    sp_dir = os.path.join(speakers_dir, sp)
    os.makedirs(sp_dir, exist_ok=True)
    playlist = []
    for seg in segs:
        fname = f'{seg[\"index\"]:02d}-{seg[\"start\"]:.1f}-{seg[\"end\"]:.1f}.wav'
        fpath = os.path.join(sp_dir, fname)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', audio,
                        '-ss', str(seg['start']), '-to', str(seg['end']),
                        '-ar', '16000', '-ac', '1', fpath], check=True)
        playlist.append({ 'file': fname, 'start': seg['start'], 'end': seg['end'], 'text': seg['text'][:60] })
    json.dump(playlist, open(os.path.join(sp_dir, 'playlist.json'), 'w'), indent=2)
    print(f'  {sp}: {len(segs)} segments')

print('Done')
"
