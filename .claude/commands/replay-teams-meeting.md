# /replay-teams-meeting — Replay a saved transcript into a Teams meeting to test speaker attribution

Replays the saved closed-caption transcript with multiple speaking bots into a Teams test meeting, plus one listener bot that captures transcription. Compares source attribution to captured attribution to assess quality.

## Test meeting

URL: `https://teams.live.com/meet/9362871937755?p=cLiict8Ntx3kAFq2MD`

Multiple speakers join as TTS bots; one listener bot captures the transcription output.

## How to run

```bash
# From repo root — requires compose stack running (make all from deploy/compose/)
API_KEY=<your_api_key> node test_data/replay-meeting.js \
  "https://teams.live.com/meet/9362871937755?p=cLiict8Ntx3kAFq2MD" \
  test_data/meeting_saved_closed_caption.txt \
  --limit=20
```

### What it does

1. Parses the transcript file (6 speakers: Speaker A, Speaker B, Speaker C, Speaker D, Speaker E, Speaker F)
2. Creates one bot per speaker (each with unique API key via admin API) + one listener bot
3. All bots join the Teams meeting — **you must admit them from the lobby**
4. Speaker bots replay the transcript with TTS timing, listener captures transcription
5. At the end, fetches transcription and prints source vs captured comparison

### Parameters

- `--limit=N` — Only replay first N consolidated utterances (useful for quick tests)
- `API_URL` — Bot manager URL (default: `http://localhost:8066`)
- `ADMIN_URL` — Admin API URL (default: `http://localhost:8067`)

### What to look for

- **Speaker attribution accuracy:** Do the transcribed segments match the source speaker names?
- **Caption-driven detection:** Bot logs should show `[Teams Captions] Speaker change:` events
- **Ring buffer lookback:** Bot logs should show `Flushed N chunks` messages on speaker transitions
- **Fallback behavior:** If captions fail to enable, bot falls back to DOM blue squares

## Transcript file

`test_data/meeting_saved_closed_caption.txt` — Real Teams closed-caption export from a panel discussion meeting. 6 speakers, ~18 minutes of content.
