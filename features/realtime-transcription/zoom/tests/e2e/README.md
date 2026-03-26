# Zoom E2E Transcription Tests

End-to-end validation of the Zoom browser-based transcription pipeline:
TTS bots speak scripted utterances into a live Zoom meeting, audio is captured per-speaker (same pattern as Google Meet), speaker identity locks via DOM active speaker detection, Whisper transcribes, segments flow through Redis to the collector, and persist to Postgres.

## Test Scripts

| Script | Utterances | Coverage | Prerequisites |
|--------|-----------|----------|---------------|
| `test-e2e.sh` | 9 | Basic — 3 speakers, clean turn-taking | MVP0 (audio) + MVP1 (speaker) + MVP3 (auto-admit) |

Stress test (`test-e2e-stress.sh`) will be added after MVP3 (TTS bot testing infrastructure).

## Scorer

Reuses `google-meet/tests/e2e/score-e2e.py` — the scorer is platform-agnostic. It matches ground-truth utterances to output segments via text similarity, then computes speaker accuracy, WER, and completeness.

## Pass Criteria

| Metric | Threshold |
|--------|-----------|
| Speaker accuracy | >= 90% |
| Completeness | >= 80% |
| WER | <= 30% |

## Results

No results yet — blocked by MVP0 (audio channel join) and MVP3 (auto-admit / TTS bots).

## Current Blockers

1. **MVP0 (audio channel join):** Recorder bot enters meeting without audio. `test-e2e.sh` will warn if audio channel join is not confirmed in logs.
2. **MVP3 (auto-admit):** No `zoom-auto-admit.js` yet. Meeting host must admit bots manually, or meeting must have waiting room disabled.
3. **MVP3 (TTS bot ejection):** TTS bots currently ejected in ~4s due to false-positive removal detection.

## Usage

```bash
# Requires a live Zoom meeting URL
./test-e2e.sh --meeting "https://zoom.us/j/84335626851?pwd=abc123"

# Or via env var
ZOOM_MEETING_URL="https://zoom.us/j/..." ./test-e2e.sh
```

## Differences from Siblings

| Aspect | Google Meet | MS Teams | Zoom |
|--------|-----------|----------|------|
| Audio pattern | Per-speaker `<audio>` | Mixed stream + captions | Per-speaker `<audio>` (same as GMeet) |
| Speaker identity | DOM voting + locking | Caption author | DOM active speaker + voting |
| Auto-admit | `gmeet-host-auto.js` + `auto-admit.js` | `/host-teams-meeting-auto` | Not implemented yet |
| TTS command | Redis `speak` | REST `/bots/teams/{id}/speak` | Redis `speak` (same as GMeet) |
| Meeting creation | `meet.new` via CDP | Browser session via skill | Not implemented yet |
