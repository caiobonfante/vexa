# /replay-teams-meeting — Replay a saved transcript into a Teams meeting to test speaker attribution

Replays the saved closed-caption transcript with multiple speaking bots into a Teams test meeting, plus one listener bot that captures transcription. Compares source attribution to captured attribution to assess quality.

## Prerequisites

- Compose stack running (`make all` from `deploy/compose/`)
- A Teams meeting link (created via browser or `/host-teams-meeting`)
- Meeting URL and passcode in feature `.env` (see below)

## Infrastructure

### Ports

| Service | Port | Purpose |
|---------|------|---------|
| API Gateway | 8066 | Bot creation, speak commands, transcription retrieval |
| Bot Manager | 8080 (internal) | Proxied through API Gateway |
| Transcription Service | 8083 | Whisper transcription |
| TTS Service | 8002 | Text-to-speech for speaker bots |
| Redis | 6379 | Segment streaming, pub/sub |
| Postgres | 5448 | Meeting records, API tokens, segments |

### Feature .env

The meeting link and API token should be in `features/realtime-transcription/.env`:

```bash
MEETING_URL=https://teams.live.com/meet/<ID>?p=<PASSCODE>
NATIVE_MEETING_ID=<numeric_id>
MEETING_PASSCODE=<passcode>
API_TOKEN=<vxa_user_xxx>
```

## How to send bots

### 1. Send a listener bot (captures transcription)

The listener bot joins from the authenticated account (`2280905@gmail.com`) and captures per-speaker audio, captions, and transcription.

```bash
curl -s -X POST http://localhost:8066/bots \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_TOKEN" \
  -d '{
    "platform": "teams",
    "native_meeting_id": "'$NATIVE_MEETING_ID'",
    "passcode": "'$MEETING_PASSCODE'",
    "meeting_url": "'$MEETING_URL'",
    "bot_name": "Vexa Transcription",
    "transcribe_enabled": true,
    "recording_enabled": false,
    "transcription_tier": "realtime",
    "authenticated": true
  }'
```

Response includes `id` (meeting ID) and `bot_container_id` (Docker container).

### 2. Send speaker bots (one per user account)

Each speaker bot must come from a **different user account** (bot-manager prevents duplicate bots per user per meeting).

Available speaker accounts and tokens:

| Speaker | User ID | Email | Token |
|---------|---------|-------|-------|
| Alice | 1 | test@vexa.ai | `vxa_user_pZqJ5dEQK47Mc7YeVTR53wAefBCs7Nf6d0fHbHs8` |
| Bob | 2 | wefwef@wedg.com | `vxa_user_o9V6HLC3emrG4d1TRMrZtItnP1KJc6cOaCPeXcV1` |
| Charlie | 3 | sedgfsedf@wedgw.com | `vxa_user_l4GvApfciQGRrNuUNTNixCb5bLDQ0g171G5fbNay` |
| Speaker 4 | 4 | ljkbkljb@sdglkn.com | `vxa_user_LTprigX65ZYP0eJzpQbv9PPKTg3rdrNWgPDO82xH` |

```bash
# Example: send Alice
curl -s -X POST http://localhost:8066/bots \
  -H "Content-Type: application/json" \
  -H "X-API-Key: vxa_user_pZqJ5dEQK47Mc7YeVTR53wAefBCs7Nf6d0fHbHs8" \
  -d '{
    "platform": "teams",
    "native_meeting_id": "'$NATIVE_MEETING_ID'",
    "passcode": "'$MEETING_PASSCODE'",
    "bot_name": "Alice",
    "transcribe_enabled": false,
    "recording_enabled": false,
    "voice_agent_enabled": true
  }'
```

### 3. Admit bots from lobby

Teams meetings require lobby admission. The meeting host must admit each bot as it joins.

### 4. Make a speaker bot speak

```bash
# POST /bots/{meeting_id}/speak
curl -s -X POST http://localhost:8066/bots/316/speak \
  -H "Content-Type: application/json" \
  -H "X-API-Key: vxa_user_pZqJ5dEQK47Mc7YeVTR53wAefBCs7Nf6d0fHbHs8" \
  -d '{"text": "Hello everyone, let me start with the quarterly revenue numbers."}'
```

The bot generates TTS audio and plays it into the meeting via PulseAudio virtual mic.

### 5. Monitor bot logs

```bash
# Listener bot logs (captions, speaker changes, transcription)
docker logs -f <listener_container_id>

# Speaker bot logs
docker logs -f <speaker_container_id>
```

Key log patterns:
- `[Teams Captions] Speaker change:` — caption-based speaker detection
- `[📝 TEAMS CAPTION]` — raw caption events
- `CONFIRMED` — transcription segment confirmed
- `[SpeakerStreams]` — buffer/submission activity

### 6. Check transcription results

```bash
# Get meeting transcription
curl -s http://localhost:8066/meetings/<listener_meeting_id>/transcription \
  -H "X-API-Key: $API_TOKEN" | python3 -m json.tool
```

## Automated replay script

For replaying a full saved transcript with proper timing:

```bash
API_KEY=<your_api_key> node test_data/replay-meeting.js \
  "$MEETING_URL" \
  test_data/meeting_saved_closed_caption.txt \
  --limit=20
```

### What it does

1. Parses the transcript file (6 speakers: Speaker A through F)
2. Creates one bot per speaker (each with unique API key) + one listener bot
3. All bots join the Teams meeting — **you must admit them from the lobby**
4. Speaker bots replay the transcript with TTS timing, listener captures transcription
5. At the end, fetches transcription and prints source vs captured comparison

### Parameters

- `--limit=N` — Only replay first N consolidated utterances (useful for quick tests)
- `API_URL` — Bot manager URL (default: `http://localhost:8066`)
- `ADMIN_URL` — Admin API URL (default: `http://localhost:8067`)

## What to look for

- **Speaker attribution accuracy:** Do the transcribed segments match the source speaker names?
- **Caption-driven detection:** Bot logs should show `[Teams Captions] Speaker change:` events
- **Ring buffer lookback:** Bot logs should show `Flushed N chunks` messages on speaker transitions
- **Fallback behavior:** If captions fail to enable, bot falls back to DOM blue squares
- **Stale response handling:** After speaker changes, old Whisper responses should be discarded (generation guard)
- **Short phrase capture:** Sub-1s utterances like "OK", "Sure" should be captured via flush-submit

## Transcript file

`test_data/meeting_saved_closed_caption.txt` — Anonymized Teams closed-caption export from a panel discussion. 6 speakers, ~18 minutes of content.

## Cleanup

```bash
# Stop a specific bot
curl -s -X DELETE http://localhost:8066/bots/<meeting_id> \
  -H "X-API-Key: <token>"

# Or stop the container directly
docker stop <container_id>
```
