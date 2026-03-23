# /collect — Run a collection run for realtime transcription

You are in **Stage 1: COLLECTION RUN** for the realtime-transcription feature.

Read the generic stage protocol first: `/.claude/commands/collect.md`

## Before you start

You need a meeting URL. How depends on the platform:

**MS Teams (autonomous):**
```
/host-teams-meeting-auto
```
Creates meeting, joins as host, starts auto-admit. Updates `.env` with `MEETING_URL`. No human needed.

**Google Meet (needs Google-authenticated browser session):**
```bash
# Use an existing browser session with Google logged in, or create one and log in via VNC
cd /home/dima/dev/vexa-restore/services/vexa-bot && \
  CDP_URL="http://localhost:8066/b/{SESSION_TOKEN}/cdp" \
  node /home/dima/dev/vexa-restore/features/realtime-transcription/scripts/gmeet-host-auto.js
```
Outputs `MEETING_URL` and `NATIVE_MEETING_ID`. Then start auto-admit:
```bash
sshpass -p "$SESSION_TOKEN" ssh -o StrictHostKeyChecking=no root@localhost -p $SSH_PORT \
  "cd /workspace && nohup node /home/dima/dev/vexa-restore/features/realtime-transcription/scripts/auto-admit.js http://localhost:9222 google_meet > /tmp/auto-admit.log 2>&1 &"
```

Read `PLATFORM` from `.env` to determine which path to take. If not set, ask the user.

## You create the test data

You are fully autonomous. You design the conversation script, create TTS bots that speak it into a live meeting, and capture the pipeline output. No human speaks — you drive everything through the API.

### How it works

1. **Design a script** — decide what each speaker says, when, and why (targeting specific scenarios)
2. **Send 1 RECORDER bot** — joins as default "VexaBot-XXX", captures audio and transcribes
3. **Send N SPEAKER bots** — one per speaker, each a separate user with unique `bot_name`
4. **Bots speak via API** — `POST /bots/{platform}/{native_meeting_id}/speak` with text per speaker
5. **Pipeline captures and transcribes** — platform-specific audio routing, shared Whisper pipeline
6. **You collect the output** — ground truth (what you sent) vs pipeline output (what came back)

The ground truth is exact because YOU wrote the script and know the timestamps.

### MANDATORY: Multi-speaker setup

**Every speaker in the script MUST be a separate user with a separate bot.** This is not optional.
The recorder bot filters out any speaker whose name contains "vexa", so speaker bots MUST use
`bot_name` without "vexa" (e.g., "Alice", "Bob"). The recorder keeps its default "VexaBot-XXX" name.

**Checklist — do NOT skip any step:**

- [ ] 1. Read `.env` for `API_TOKEN`, `NATIVE_MEETING_ID`, `MEETING_PASSCODE`, `MEETING_URL`
- [ ] 2. Send RECORDER bot (user 1, `API_TOKEN` from `.env`, default bot_name, `transcribe_enabled: true`)
- [ ] 3. For EACH speaker in the script, send a SPEAKER bot:
  - Each speaker uses a **different user token** and a **unique `bot_name`** (no "vexa" in name)
  - Set `voice_agent_enabled: true` on speaker bots
- [ ] 4. VERIFY: all bots appear in meeting (check bot-manager logs or `/bots` endpoint)
- [ ] 5. VERIFY: recorder bot is polling captions (check recorder docker logs for `Captions POLL`)
- [ ] 6. Send ONE test utterance from one speaker bot — verify recorder captures it with correct speaker name
- [ ] 7. Only THEN run the full script, routing each utterance to the correct speaker's bot

**If you need more speakers than tokens exist:** create them. See "Creating speaker users" below.

### Speaker accounts

Read the tokens from `.env` or from the table below. Each speaker = 1 user = 1 token = 1 bot.

| Role | bot_name | User | Token env var | Fallback token |
|------|----------|------|---------------|----------------|
| Recorder | (default) | user 1 | `API_TOKEN` | `vxa_user_pZqJ5dEQK47Mc7YeVTR53wAefBCs7Nf6d0fHbHs8` |
| Alice | `Alice` | user 5 | `ALICE_TOKEN` | `vxa_bot_db0x5tx0PRWvXYCXaBOTNEmjgpJPwZysIEUsTH94` |
| Bob | `Bob` | user 2 | `BOB_TOKEN` | `vxa_user_o9V6HLC3emrG4d1TRMrZtItnP1KJc6cOaCPeXcV1` |
| Charlie | `Charlie` | user 3 | `CHARLIE_TOKEN` | `vxa_user_l4GvApfciQGRrNuUNTNixCb5bLDQ0g171G5fbNay` |
| Diana | `Diana` | user 4 | `DIANA_TOKEN` | `vxa_user_LTprigX65ZYP0eJzpQbv9PPKTg3rdrNWgPDO82xH` |

### Creating speaker users

If you need more speakers than exist in the table above, create them via the admin API:

```bash
ADMIN_PORT=8057

# 1. Create user
USER_RESP=$(curl -s -X PUT "http://localhost:$ADMIN_PORT/users" \
  -H "Content-Type: application/json" \
  -d '{"email":"speaker-eve@vexa.test","name":"Eve"}')
USER_ID=$(echo "$USER_RESP" | jq -r '.id')

# 2. Generate token for user
TOKEN_RESP=$(curl -s -X POST "http://localhost:$ADMIN_PORT/users/$USER_ID/tokens?scope=user")
TOKEN=$(echo "$TOKEN_RESP" | jq -r '.token')

echo "Eve: user_id=$USER_ID token=$TOKEN"
# Add EVE_TOKEN=$TOKEN to .env and update the speaker table above
```

After creating, add the new speaker to the table in this file and to `.env` so future runs can reuse them.

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

### How to run bots

The API is the same for both platforms — only `platform` and meeting fields differ.

**Platform-specific fields:**

| Field | MS Teams | Google Meet |
|-------|---------|-------------|
| `platform` | `"teams"` | `"google_meet"` |
| `native_meeting_id` | numeric ID from URL | meeting code (e.g. `jbo-umhn-rge`) |
| `passcode` | from URL `?p=` param | not used |
| `meeting_url` | `https://teams.live.com/meet/{id}?p={pass}` | `https://meet.google.com/{code}` |
| speak endpoint | `/bots/teams/{id}/speak` | `/bots/google_meet/{code}/speak` |

```bash
# Read platform from .env
PLATFORM=$(grep '^PLATFORM=' .env | cut -d= -f2)

# 1. RECORDER bot (user 1 — captures transcription)
curl -s -X POST http://localhost:8066/bots \
  -H "Content-Type: application/json" -H "X-API-Key: $API_TOKEN" \
  -d '{"platform":"'$PLATFORM'","native_meeting_id":"'$NATIVE_MEETING_ID'","meeting_url":"'$MEETING_URL'","transcribe_enabled":true}'

# 2. SPEAKER bots (one per speaker — each with unique token + bot_name)
curl -s -X POST http://localhost:8066/bots \
  -H "Content-Type: application/json" -H "X-API-Key: $ALICE_TOKEN" \
  -d '{"platform":"'$PLATFORM'","native_meeting_id":"'$NATIVE_MEETING_ID'","meeting_url":"'$MEETING_URL'","bot_name":"Alice","voice_agent_enabled":true}'

curl -s -X POST http://localhost:8066/bots \
  -H "Content-Type: application/json" -H "X-API-Key: $BOB_TOKEN" \
  -d '{"platform":"'$PLATFORM'","native_meeting_id":"'$NATIVE_MEETING_ID'","meeting_url":"'$MEETING_URL'","bot_name":"Bob","voice_agent_enabled":true}'

# ... repeat for Charlie, Diana, etc.

# 3. Make a specific speaker's bot speak (use THAT speaker's token)
# Platform in the URL: /bots/{platform}/{native_meeting_id}/speak
SPEAK_PLATFORM=$(echo $PLATFORM | sed 's/ms-teams/teams/')
curl -s -X POST "http://localhost:8066/bots/$SPEAK_PLATFORM/$NATIVE_MEETING_ID/speak" \
  -H "Content-Type: application/json" -H "X-API-Key: $ALICE_TOKEN" \
  -d '{"text":"Hello everyone, let me start with the quarterly numbers."}'

curl -s -X POST "http://localhost:8066/bots/$SPEAK_PLATFORM/$NATIVE_MEETING_ID/speak" \
  -H "Content-Type: application/json" -H "X-API-Key: $BOB_TOKEN" \
  -d '{"text":"Thanks Alice, the numbers look great this quarter."}'
```

**CRITICAL:** Each `/speak` call MUST use the correct speaker's `X-API-Key`. The bot-manager
routes the speak command to that user's bot. If you use the wrong token, the wrong bot speaks
and speaker attribution is incorrect.

## Feature-specific context

### Dataset ID format

`{platform}-{N}sp-{scenario-tag}-{YYYYMMDD}`

Examples: `teams-3sp-diverse-20260320`, `gmeet-2sp-normal-20260321`

### Dataset directory

```
features/realtime-transcription/data/raw/{id}/
  manifest.md
  ground-truth.txt
  infra-snapshot.md
  audio/               # Per-utterance WAVs
  events/              # caption-events.json, speaker-changes.json
```

### What we capture

**Shared (both platforms):**

| Data | Source | Destination |
|------|--------|------------|
| Ground truth | Your script (send times + text) | `ground-truth.txt` |
| Audio (WAV) | TTS bot output | `audio/` |
| Pipeline output | SpeakerStreamManager drafts + confirmations | `pipeline/bot-logs.txt` |
| REST segments | `GET /transcripts/{platform}/{native_meeting_id}` | `pipeline/rest-segments.json` |

**MS Teams additional:**

| Data | Source | Destination |
|------|--------|------------|
| Caption events | DOM MutationObserver on `[data-tid="closed-caption-text"]` | `events/caption-events.json` |
| Speaker changes | `[data-tid="author"]` changes | `events/speaker-changes.json` |

**Google Meet additional:**

| Data | Source | Destination |
|------|--------|------------|
| Speaker events | `__vexaSpeakerEvents` (SPEAKER_START/SPEAKER_END) | `events/speaker-events.json` |
| Identity votes | Speaker identity voting/locking log lines | `events/identity-votes.txt` |

### Ground truth format

```
[GT] <unix_timestamp> <speaker_name> "<text>"
[GT] 1774021330.638229769 Bob "Sounds great."
```

### How to capture logs

```bash
docker logs --timestamps vexa-restore-bot-manager-1 2>&1 | tee data/raw/{id}/events/raw-logs.txt
```

### Existing datasets

Check `features/realtime-transcription/data/raw/` for existing datasets. Review manifests to avoid duplicating scenarios and include controls from previous runs.

### Platform specifics

**MS Teams:**
- Captions must be enabled in the meeting (bot does this automatically)
- Caption events have ~1.5-2.5s delay from speech — expected, not a bug
- Speaker changes in captions are atomic — no overlap
- Single-word utterances may not generate separate caption events

**Google Meet:**
- Per-speaker audio streams — each speaker gets a separate audio track
- Speaker identity via DOM voting — needs single-speaker windows to lock (3 votes at 70%)
- First few seconds may have unmapped speakers (before voting locks)
- No caption dependency — audio routing doesn't depend on a button press
- Meeting host must admit bots from lobby (use auto-admit script)

### After collection — convert to dataset and continue

Do NOT stop after collecting raw data. Complete the full dataset:

1. Tag everything in the manifest's files table with scenario tags
2. Check against existing datasets — does this supersede any?
3. Run `make play-replay DATASET={id}` to get baseline scoring
4. Record baseline in manifest
5. Set status to `active`
6. **Immediately proceed to `/iterate`** — do not wait for human input
