# /collect — Run a collection run for realtime transcription

You are in **Stage 1: COLLECTION RUN** for the realtime-transcription feature.

Read the generic stage protocol first: `/.claude/commands/collect.md`

## Feature-specific context

### Dataset ID format for this feature

`{platform}-{N}sp-{scenario-tag}-{YYYYMMDD}`

Examples:
- `teams-3sp-diverse-20260320`
- `teams-2sp-shortphrase-20260405`
- `gmeet-5sp-overlap-20260410`

### Dataset directory

```
features/realtime-transcription/tests/datasets/{id}/
  manifest.md
  ground-truth.txt
  infra-snapshot.md
  audio/               # Per-utterance WAVs: {speaker}-{NN}.wav + combined.wav
  events/              # caption-events.json, speaker-changes.json
  pipeline/            # bot-logs.txt, segments.json
  README.md
```

### What we capture from this feature

| Data | Source | How it's captured | Destination |
|------|--------|------------------|------------|
| Audio (WAV) | TTS bots speak in meeting | Bot's TTS output files saved locally | `audio/` |
| Caption events | Teams: DOM MutationObserver on `[data-tid="closed-caption-text"]` | Bot logs with `--timestamps` | `events/caption-events.json` |
| Speaker changes | Teams: `[data-tid="author"]` changes | Bot logs with `--timestamps` | `events/speaker-changes.json` |
| Pipeline output | SpeakerStreamManager drafts + confirmations | Bot logs with `--timestamps` | `pipeline/bot-logs.txt` |
| Ground truth | Script send times (Unix timestamps from TTS API calls) | Script runner output | `ground-truth.txt` |

### How to run bots

```bash
# Simple: 2-3 bots from a script
API_KEY=<key> bash test_data/test-conversation.sh <meeting_url>

# Advanced: replay a full transcript
API_KEY=<key> node test_data/replay-meeting.js <meeting_url> <script_file> --limit=N
```

Bots need to be admitted through the meeting lobby. Use `/host-teams-meeting` to create a meeting with auto-admit.

### How to capture logs

```bash
# Capture all bot logs with timestamps
docker logs --timestamps vexa-restore-bot-manager-1 2>&1 | tee tests/datasets/{id}/pipeline/raw-logs.txt
```

### Ground truth format

```
[GT] <unix_timestamp> <speaker_name> "<text>"
[GT] 1774021330.638229769 Bob "Sounds great."
```

### Existing datasets

Check `features/realtime-transcription/tests/datasets/` for existing datasets. Review their manifests to:
- Avoid duplicating scenarios already well-covered
- Include control scenarios from existing datasets
- Check infra compatibility for future combining

### Platform: MS Teams specifics

- Captions must be enabled in the meeting (bot does this automatically)
- Caption events have ~1.5-2.5s delay from speech — this is expected, not a bug
- Speaker changes in captions are atomic — no overlap
- See `features/realtime-transcription/ms-teams/teams-caption-behavior.md` for observed patterns
- Single-word utterances may not generate separate caption events

### After collection

1. Tag everything in the manifest's files table with scenario tags
2. Check against existing datasets — does this supersede any?
3. Run `make play-replay DATASET={id}` to get baseline scoring
4. Record baseline in manifest
5. Set status to `active`
6. Ready for `/iterate`
