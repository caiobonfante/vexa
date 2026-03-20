# /collect — Run a collection run for realtime transcription

You are in **Stage 1: COLLECTION RUN** for the realtime-transcription feature.

Read the generic stage protocol first: `/.claude/commands/collect.md`

## Feature-specific context

### What we're collecting

This feature needs these data types from a live meeting:

| Data | Source | How it's captured |
|------|--------|------------------|
| Audio (WAV) | TTS bots speak in meeting | Bot's TTS output files saved locally |
| Caption events | Teams: DOM MutationObserver on `[data-tid="closed-caption-text"]` | Bot logs with `--timestamps` |
| Speaker changes | Teams: `[data-tid="author"]` changes | Bot logs with `--timestamps` |
| Pipeline output | SpeakerStreamManager drafts + confirmations | Bot logs with `--timestamps` |
| Ground truth | Script send times (Unix timestamps from TTS API calls) | Script runner output |

### How to run bots

Use the test conversation scripts or replay-meeting.js:

```bash
# Simple: 2-3 bots from a script
API_KEY=<key> bash test_data/test-conversation.sh <meeting_url>

# Advanced: replay a full transcript
API_KEY=<key> node test_data/replay-meeting.js <meeting_url> <script_file> --limit=N
```

Bots need to be admitted through the meeting lobby. Use `/host-teams-meeting` to create a meeting with auto-admit, or admit manually.

### How to capture logs

```bash
# Capture all bot logs with timestamps
docker logs --timestamps vexa-restore-bot-manager-1 2>&1 | tee features/realtime-transcription/tests/{name}-raw-logs.txt

# Extract timestamped events (caption texts, speaker changes, drafts, confirmations)
# Parse from raw logs into structured JSON
```

### Ground truth format

```
[GT] <unix_timestamp> <speaker_name> "<text>"
[GT] 1774021330.638229769 Bob "Sounds great."
```

The TTS script runner logs the exact send time of each utterance. These are the ground truth.

### Existing collected data

Check `features/realtime-transcription/tests/README.md` section "Collected data from collection runs" for what already exists. New collection runs should add to this, not replace it.

### Platform: MS Teams specifics

- Captions must be enabled in the meeting (bot does this automatically)
- Caption events have ~1.5-2.5s delay from speech — this is expected, not a bug
- Speaker changes in captions are atomic — no overlap
- See `features/realtime-transcription/ms-teams/teams-caption-behavior.md` for observed patterns

### Verify completeness

After collection, check:
1. Ground truth file has all utterances from the script
2. Caption events cover the full meeting duration
3. Bot logs contain DRAFT and CONFIRMED segments
4. Audio WAVs exist for all TTS utterances
5. `make play-replay` can consume the new data
