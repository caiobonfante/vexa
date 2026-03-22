# MS Teams E2E Transcription Tests

End-to-end validation of the full pipeline:
TTS bots speak scripted utterances into a live Teams meeting, audio is captured per-speaker, speaker identity locks via voting, Whisper transcribes, segments flow through Redis to the collector, and persist to Postgres. Ground truth is exact because we wrote the script.

## Test Scripts

| Script | Utterances | Coverage |
|--------|-----------|----------|
| `test-e2e.sh` | 9 | Basic — short sentences, 3 speakers, clean turn-taking |
| `test-e2e-stress.sh` | 20 | Stress — long monologues, technical jargon, short interjections |

Both scripts send TTS bots via REST (`/bots/teams/{meeting_id}/speak` with `voice` parameter), wait for pipeline completion, then dump output segments.

## Scorer

`score-e2e.py` lives in `google-meet/tests/e2e/` (shared across platforms). It matches ground-truth utterances to output segments via text similarity (difflib), then computes:

- **Speaker accuracy** — % of matched segments attributed to the correct speaker
- **WER** — word error rate across all matched segments
- **Completeness** — % of GT utterances that matched an output segment

## Pass Criteria

| Metric | Threshold |
|--------|-----------|
| Speaker accuracy | >= 90% |
| Completeness | >= 80% |
| WER | <= 30% |

## Results (2026-03-23)

| Test | Matched | Speaker | WER | Result |
|------|---------|---------|-----|--------|
| Basic (9 utterances) | 9/9 | 100% | 14% | PASS |
| Stress (20 utterances) | 18/20 | 100% | 15% | PASS |

The 2 missing utterances in the stress test are single-word interjections ("Agreed.", "Perfect.") that Whisper merges into adjacent segments rather than emitting as standalone segments.

## Usage

```bash
# Basic test (requires meeting URL and passcode)
./test-e2e.sh --meeting "https://teams.microsoft.com/..." --passcode "abc123"

# Stress test
./test-e2e-stress.sh --meeting "https://teams.microsoft.com/..." --passcode "abc123"

# Score results (scorer lives in google-meet/tests/e2e/)
python3 ../../google-meet/tests/e2e/score-e2e.py results/<run-dir>/
```

Ensure the compose stack is running (`make all` from `deploy/compose/`) before starting.

## Teams-Specific Notes

- **Passcode required:** Teams meetings require `--passcode` for bot admission.
- **Lobby admission:** The meeting host must have the People panel open, or use the `auto-admit` script (`scripts/gmeet-host-auto.js`) to bypass the lobby.
- **Recorder user:** Use `2280905@gmail.com` (user_id=5) as the recorder for dashboard visibility.
