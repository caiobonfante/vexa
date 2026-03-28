# Google Meet E2E Transcription Tests

End-to-end validation of the full pipeline:
TTS bots speak scripted utterances into a live Google Meet, audio is captured per-speaker, speaker identity locks via voting, Whisper transcribes, segments flow through Redis to the collector, and persist to Postgres. Ground truth is exact because we wrote the script.

## Test Scripts

| Script | Utterances | Coverage |
|--------|-----------|----------|
| `test-e2e.sh` | 9 | Basic — short sentences, 3 speakers, clean turn-taking |
| `test-e2e-stress.sh` | 20 | Stress — long monologues, technical jargon, short interjections |

Both scripts send TTS bots to speak, wait for pipeline completion, then dump output segments.

## Scorer

`score-e2e.py` (in this directory) matches ground-truth utterances to output segments via text similarity (difflib), then computes:

- **Speaker accuracy** — % of matched segments attributed to the correct speaker
- **WER** — word error rate across all matched segments
- **Completeness** — % of GT utterances that matched an output segment

## Pass Criteria

| Metric | Threshold |
|--------|-----------|
| Speaker accuracy | >= 90% |
| Completeness | >= 80% |
| WER | <= 30% |

## Results (2026-03-28)

| Test | Matched | Speaker | WER (bot) | WER (DB) | Result |
|------|---------|---------|-----------|----------|--------|
| Basic (9 utterances) | 9/9 | 100% | 3% | 7% | PASS |

Validated by independent reviewer. 14 segments in Postgres, 0 whisper failures, correct speaker attribution.
Results: `results/e2e-2026-03-28-193707/`

### Prior Results (2026-03-22)

| Test | Matched | Speaker | WER | Result |
|------|---------|---------|-----|--------|
| Basic (9 utterances) | 9/9 | 100% | 7% | PASS |
| Stress (20 utterances) | 18/20 | 100% | 15% | PASS |

The 2 missing utterances in the stress test are single-word interjections ("Agreed.", "Perfect.") that Whisper merges into adjacent segments rather than emitting as standalone segments.

## Usage

```bash
# Basic test (requires a live Google Meet URL)
./test-e2e.sh --meeting "https://meet.google.com/xxx-yyyy-zzz"

# Stress test
./test-e2e-stress.sh --meeting "https://meet.google.com/xxx-yyyy-zzz"

# Score results
python3 score-e2e.py results/<run-dir>/
```

Ensure the compose stack is running (`make all` from `deploy/compose/`) before starting.
