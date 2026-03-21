# /collect — Run a collection run for realtime transcription

You are in **Stage 1: COLLECTION RUN** for the realtime-transcription feature.

Read the generic stage protocol first: `/.claude/commands/collect.md`

## Before you start

If you don't have a meeting URL with auto-admit running, create one now:
```
/host-teams-meeting-auto
```
This gives you `MEETING_URL` in `.env` and auto-admits all bots. No human needed.

## You create the test data

You are fully autonomous. You design the conversation script, create TTS bots that speak it into a live meeting, and capture the pipeline output. No human speaks — you drive everything through the API.

### How it works

1. **Design a script** — decide what each speaker says, when, and why (targeting specific scenarios)
2. **Send TTS bots** to the meeting — each bot is a speaker with a unique voice
3. **Bots speak via API** — `POST /bots/{meeting_id}/speak` with text, bot generates TTS audio and plays it into the meeting
4. **Pipeline captures and transcribes** — the listener bot captures audio, sends to Whisper, publishes segments
5. **You collect the output** — ground truth (what you sent) vs pipeline output (what came back)

The ground truth is exact because YOU wrote the script and know the timestamps.

### Design the script for what you need to test

If coming from `/expand`, use the collection manifest's scenarios. Otherwise, design scenarios based on gaps in existing datasets or the certainty table.

**Example scenarios to test:**
- Normal turns (2-3s gaps between speakers) — baseline accuracy
- Rapid exchanges (<1s gaps) — speaker boundary detection
- Short phrases ("OK", "Sure", "Got it") — sub-1s utterance capture
- Long monologues (20s+) — buffer management, confirmation logic
- Overlapping speech — simultaneous speakers
- Silence gaps (15s+) — idle timeout behavior
- Many speakers (5+) — speaker mapper scaling

**Available voices:** alloy, echo, fable, onyx, nova, shimmer (6 distinct TTS voices)

**Available speaker accounts:**

| Speaker | Token |
|---------|-------|
| Alice (user 1) | `vxa_user_pZqJ5dEQK47Mc7YeVTR53wAefBCs7Nf6d0fHbHs8` |
| Bob (user 2) | `vxa_user_o9V6HLC3emrG4d1TRMrZtItnP1KJc6cOaCPeXcV1` |
| Charlie (user 3) | `vxa_user_l4GvApfciQGRrNuUNTNixCb5bLDQ0g171G5fbNay` |
| Speaker 4 | `vxa_user_LTprigX65ZYP0eJzpQbv9PPKTg3rdrNWgPDO82xH` |

### How to run bots

```bash
# Create listener bot (captures transcription)
curl -s -X POST http://localhost:8066/bots \
  -H "Content-Type: application/json" -H "X-API-Key: $API_TOKEN" \
  -d '{"platform":"teams","native_meeting_id":"'$NATIVE_MEETING_ID'","passcode":"'$MEETING_PASSCODE'","meeting_url":"'$MEETING_URL'","bot_name":"Listener","transcribe_enabled":true}'

# Create speaker bot (one per speaker, each with unique API key)
curl -s -X POST http://localhost:8066/bots \
  -H "Content-Type: application/json" -H "X-API-Key: <speaker_token>" \
  -d '{"platform":"teams","native_meeting_id":"'$NATIVE_MEETING_ID'","passcode":"'$MEETING_PASSCODE'","bot_name":"Alice","voice_agent_enabled":true}'

# Make a bot speak
curl -s -X POST http://localhost:8066/bots/<meeting_id>/speak \
  -H "Content-Type: application/json" -H "X-API-Key: <speaker_token>" \
  -d '{"text":"Hello everyone, let me start with the quarterly numbers."}'

# Or use the existing script helpers:
API_KEY=<key> bash test_data/test-conversation.sh <meeting_url>
API_KEY=<key> node test_data/replay-meeting.js <meeting_url> <script_file> --limit=N
```

## Feature-specific context

### Dataset ID format

`{platform}-{N}sp-{scenario-tag}-{YYYYMMDD}`

Examples: `teams-3sp-diverse-20260320`, `teams-2sp-shortphrase-20260405`

### Dataset directory

```
features/realtime-transcription/tests/datasets/{id}/
  manifest.md
  ground-truth.txt
  infra-snapshot.md
  audio/               # Per-utterance WAVs
  events/              # caption-events.json, speaker-changes.json
  pipeline/            # bot-logs.txt, segments.json
  README.md
```

### What we capture

| Data | Source | Destination |
|------|--------|------------|
| Ground truth | Your script (send times + text) | `ground-truth.txt` |
| Audio (WAV) | TTS bot output | `audio/` |
| Caption events | DOM MutationObserver on `[data-tid="closed-caption-text"]` | `events/caption-events.json` |
| Speaker changes | `[data-tid="author"]` changes | `events/speaker-changes.json` |
| Pipeline output | SpeakerStreamManager drafts + confirmations | `pipeline/bot-logs.txt` |

### Ground truth format

```
[GT] <unix_timestamp> <speaker_name> "<text>"
[GT] 1774021330.638229769 Bob "Sounds great."
```

### How to capture logs

```bash
docker logs --timestamps vexa-restore-bot-manager-1 2>&1 | tee tests/datasets/{id}/pipeline/raw-logs.txt
```

### Existing datasets

Check `features/realtime-transcription/tests/datasets/` for existing datasets. Review manifests to avoid duplicating scenarios and include controls from previous runs.

### Platform: MS Teams specifics

- Captions must be enabled in the meeting (bot does this automatically)
- Caption events have ~1.5-2.5s delay from speech — expected, not a bug
- Speaker changes in captions are atomic — no overlap
- Single-word utterances may not generate separate caption events

### After collection — convert to dataset and continue

Do NOT stop after collecting raw data. Complete the full dataset:

1. Tag everything in the manifest's files table with scenario tags
2. Check against existing datasets — does this supersede any?
3. Run `make play-replay DATASET={id}` to get baseline scoring
4. Record baseline in manifest
5. Set status to `active`
6. **Immediately proceed to `/iterate`** — do not wait for human input
