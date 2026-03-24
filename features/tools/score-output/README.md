# Score Output
Confidence: 90 — well-tested scoring scripts, used across all collection runs.
Command (E2E): `python3 features/realtime-transcription/google-meet/tests/e2e/score-e2e.py <results-dir>`
Command (speaker voting): `python3 features/realtime-transcription/google-meet/tests/speaker-voting/score.py <log-file> <expected-speakers>`
Output: score.json with per-check PASS/FAIL, speaker accuracy %, WER %, completeness %
Thresholds: speaker accuracy ≥ 90%, WER ≤ 30%, completeness ≥ 80%
Needs:
  - Python 3.8+
  - results directory with ground-truth.json, bot-segments.json (E2E) or speaker-events.log (voting)
  - No running services needed — operates on captured data
Dead ends: none — most stable tool in the chain.
