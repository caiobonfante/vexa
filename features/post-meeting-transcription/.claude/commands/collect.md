# /collect — Run a collection run for post-meeting transcription

You are in **Stage 1: COLLECTION RUN** for the post-meeting-transcription feature.

Read the generic stage protocol first: `/.claude/commands/collect.md`

## Before you start

You need a meeting URL. Use:
```
/host-teams-meeting-auto
```
Creates meeting, joins as host, starts auto-admit. Updates `.env` with `MEETING_URL`. No human needed.

Read `PLATFORM` from `.env` to determine the platform. Default: `ms-teams`.

## What's different about post-meeting collection

Unlike realtime-transcription, we are NOT testing live pipeline output. We are testing:
1. **Recording** — did the bot record and upload audio to MinIO?
2. **Speaker events** — did the bot collect and persist speaker events?
3. **Deferred transcription** — does POST /meetings/{id}/transcribe produce correct output?
4. **Dashboard playback** — does clicking a segment seek the recording correctly?

The collection run captures the **inputs** (recording + speaker events) so we can validate the **deferred transcription pipeline** after the meeting completes.

## You create the test data

Same as realtime-transcription: design a script, send TTS bots, capture output.

### MANDATORY: Multi-speaker setup

Same rules as realtime-transcription — each speaker = separate user = separate bot.
The recorder bot MUST have `transcribe_enabled: false` (we do NOT want live transcription — we're testing post-meeting only).

**Checklist — do NOT skip any step:**

- [ ] 1. Read `.env` for `API_TOKEN`, `NATIVE_MEETING_ID`, `MEETING_PASSCODE`, `MEETING_URL`
- [ ] 2. Send RECORDER bot (user 1, `API_TOKEN`, default bot_name, `transcribe_enabled: false`)
- [ ] 3. For EACH speaker, send a SPEAKER bot with unique `bot_name` and `voice_agent_enabled: true`
- [ ] 4. VERIFY: all bots appear in meeting
- [ ] 5. Send ONE test utterance — verify bot logs show speaker events being collected
- [ ] 6. Run the full script
- [ ] 7. End the meeting (all bots leave)
- [ ] 8. VERIFY: recording uploaded to MinIO (check bot logs for upload confirmation)
- [ ] 9. VERIFY: speaker_events stored in meeting.data (check via API or DB)
- [ ] 10. Run POST /meetings/{meeting_id}/transcribe
- [ ] 11. Score: compare transcription segments vs ground truth

### Speaker accounts

Same tokens as realtime-transcription:

| Role | bot_name | User | Token env var | Fallback token |
|------|----------|------|---------------|----------------|
| Recorder | (default) | user 1 | `API_TOKEN` | `vxa_user_pZqJ5dEQK47Mc7YeVTR53wAefBCs7Nf6d0fHbHs8` |
| Alice | `Alice` | user 5 | `ALICE_TOKEN` | `vxa_bot_db0x5tx0PRWvXYCXaBOTNEmjgpJPwZysIEUsTH94` |
| Bob | `Bob` | user 2 | `BOB_TOKEN` | `vxa_user_o9V6HLC3emrG4d1TRMrZtItnP1KJc6cOaCPeXcV1` |
| Charlie | `Charlie` | user 3 | `CHARLIE_TOKEN` | `vxa_user_l4GvApfciQGRrNuUNTNixCb5bLDQ0g171G5fbNay` |

### How to run bots

```bash
PLATFORM=$(grep '^PLATFORM=' .env | cut -d= -f2)

# 1. RECORDER bot — transcribe_enabled: false (post-meeting only)
curl -s -X POST http://localhost:8066/bots \
  -H "Content-Type: application/json" -H "X-API-Key: $API_TOKEN" \
  -d '{"platform":"'$PLATFORM'","native_meeting_id":"'$NATIVE_MEETING_ID'","meeting_url":"'$MEETING_URL'","transcribe_enabled":false}'

# 2. SPEAKER bots
curl -s -X POST http://localhost:8066/bots \
  -H "Content-Type: application/json" -H "X-API-Key: $ALICE_TOKEN" \
  -d '{"platform":"'$PLATFORM'","native_meeting_id":"'$NATIVE_MEETING_ID'","meeting_url":"'$MEETING_URL'","bot_name":"Alice","voice_agent_enabled":true}'

# 3. Make speakers speak
SPEAK_PLATFORM=$(echo $PLATFORM | sed 's/ms-teams/teams/')
curl -s -X POST "http://localhost:8066/bots/$SPEAK_PLATFORM/$NATIVE_MEETING_ID/speak" \
  -H "Content-Type: application/json" -H "X-API-Key: $ALICE_TOKEN" \
  -d '{"text":"Hello everyone, let me start with the quarterly numbers."}'
```

## After the meeting completes

### Post-meeting verification (the core of this feature)

1. **Check recording exists:**
   ```bash
   make -C tests check-recording MEETING_ID=$MEETING_ID
   ```

2. **Check speaker events:**
   ```bash
   make -C tests check-speaker-events MEETING_ID=$MEETING_ID
   ```

3. **Trigger deferred transcription:**
   ```bash
   make -C tests check-transcribe MEETING_ID=$MEETING_ID
   ```

4. **Check transcript output:**
   ```bash
   make -C tests check-playback MEETING_ID=$MEETING_ID PLATFORM=$PLATFORM NATIVE_MEETING_ID=$NATIVE_MEETING_ID
   ```

5. **Score against ground truth:**
   Compare returned segments' speakers and text against your script.

### Dataset directory

```
features/post-meeting-transcription/data/raw/{id}/
  manifest.md
  ground-truth.txt
  infra-snapshot.md
  recording/           # Recording metadata (not the audio file itself — it's in MinIO)
  speaker-events/      # Raw speaker_events from meeting.data
  transcription/       # POST /transcribe response + GET /transcripts response
```

### Ground truth format

```
[GT] <unix_timestamp> <speaker_name> "<text>"
[GT] 1774021330.638229769 Bob "Sounds great."
```

### After collection — convert to dataset and continue

1. Tag everything in the manifest
2. Run scoring (speaker attribution % and text match %)
3. Record baseline in manifest
4. Set status to `active`
5. **Immediately proceed to `/iterate`**
