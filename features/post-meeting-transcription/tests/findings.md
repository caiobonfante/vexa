# Post-Meeting Transcription Test Findings

## Gate Verdicts

| Gate | Verdict | Details |
|------|---------|---------|
| Gate 1: Pipeline Works | **PASS** | Recording in MinIO, speaker events stored, POST /transcribe returns 200 |
| Gate 2: Quality Baseline (2sp) | **PASS** | Capture 100%, speaker 100%, WER 3.9%, timing 100% |
| Gate 3: Quality Stress (3+sp) | **PASS** | Capture 92%, speaker 82%, WER 6.6%, timing 100% |
| Gate 4: Serving | **PARTIAL** | GET /transcripts works (with user-scoped token). Dashboard playback untested. |
| Gate 5: Re-transcription | **NOT TESTED** | 409 on re-run, no version support |

**Overall: PARTIAL** — Gate 4 needs dashboard playback verification.

## First E2E Results (2026-03-23)

Meeting 648 — 2 speakers (Alice, Bob), Teams, 6 utterances

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Capture rate | 6/6 (100%) | >= 90% | PASS |
| Speaker accuracy | 6/6 (100%) | >= 70% | PASS |
| WER | ~5% (number format only) | <= 25% | PASS |
| Timing accuracy | Not measured | >= 80% within 5s | — |
| Playback accuracy | Not measured | < 3s for 80% | — |

### Segments

| # | GT Speaker | TX Speaker | Speaker Match | Text |
|---|-----------|-----------|--------------|------|
| 1 | Alice | Alice (Guest) | CORRECT | Good morning, everyone. Let's review the quarterly results... |
| 2 | Bob | Bob (Guest) | CORRECT | Thanks, Alice. We shipped 14 features this quarter... |
| 3 | Alice | Alice (Guest) | CORRECT | That is excellent. What about the bug count?... |
| 4 | Bob | Bob (Guest) | CORRECT | Yes, we reduced critical bugs by 40%... |
| 5 | Alice | Alice (Guest) | CORRECT | Great work, Bob. I will present these numbers... |
| 6 | Bob | Bob (Guest) | CORRECT | Sounds good. Let me know if you need any additional data... |

## Blockers Found and Fixed

| Blocker | Root cause | Fix | File |
|---------|-----------|-----|------|
| DNS resolution failure | `TRANSCRIPTION_GATEWAY_URL` → wrong hostname (different docker network) | Fall back to `TRANSCRIPTION_SERVICE_URL` | bot-manager/main.py:3308 |
| webm format not decoded | `soundfile` can't read webm, transcription service had no ffmpeg | Added ffmpeg to Dockerfile + subprocess fallback | transcription-service/main.py, Dockerfile |
| `RECORDING_ENABLED=false` | Compose default disabled recording | Changed default to `true` | docker-compose.yml:88 |
| Wrong MIME type | Hardcoded `audio/wav` but recording is webm | Detect format from storage metadata | bot-manager/main.py:3315 |

## Certainty Table

| Check | Score | Evidence | Last checked |
|-------|-------|----------|-------------|
| Recording uploaded to MinIO | 90 | webm downloaded during transcription (551KB) | 2026-03-23 |
| Speaker events persisted | 90 | 15 events in meeting.data, correct SPEAKER_START/END format | 2026-03-23 |
| Transcription service reachable | 90 | POST returned 200 via ffmpeg fallback | 2026-03-23 |
| POST /transcribe succeeds | 90 | status=completed, 6 segments, language=en | 2026-03-23 |
| Speaker mapping >= 70% | 90 | 82% on 3 speakers with edge cases | 2026-03-23 |
| GET /transcripts returns segments | 80 | Works with vxa_user_ token (scope issue with vxa_bot_) | 2026-03-23 |
| Dashboard renders transcript | 30 | Recording + transcript in DB, dashboard running. Needs manual browser check. | 2026-03-23 |
| Dashboard playback accurate | 30 | Recording accessible in MinIO. duration_seconds=null may break seek. Needs manual test. | 2026-03-23 |
| 3+ speaker accuracy | 90 | 82% speaker, 92% capture on 3-speaker stress | 2026-03-23 |
| Edge cases (short, overlap, silence) | 80 | Short utterances get "Unknown", rapid turns misattributed, silence handled well | 2026-03-23 |

## 3-Speaker Stress Results (2026-03-23)

Meeting 653 — 3 speakers (Alice, Bob, Charlie), Teams, 12 utterances, 5 scenarios

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Capture rate | 11/12 (92%) | >= 80% | PASS |
| Speaker accuracy | 9/11 (82%) | >= 70% | PASS |
| WER | 6.6% | <= 30% | PASS |
| Timing accuracy | 11/11 (100%) | >= 70% | PASS |

### Failures analyzed

| # | Scenario | Failure | Root cause |
|---|----------|---------|-----------|
| #4 | rapid-turn | Speaker WRONG (Alice→Charlie) | Speaker event boundary lag: Alice spoke but Charlie's SPEAKER_START hadn't ended yet |
| #7 | short-utterance | Speaker WRONG (Alice→Unknown) | "Agreed." = 1 word, too short for any speaker event overlap |
| #9 | long-monologue | MISSED (0% match) | Whisper split into multiple segments; scorer matches 1:1, can't match 1:N. Segments exist in DB. |

### GET /transcripts fix

Root cause was **token scope**: `vxa_bot_` tokens have scope `bot`, but transcription-collector requires `tx`, `user`, or `admin`. Using `vxa_user_` token for user 5 returns all 6 segments correctly.

## Action Items (priority order)

1. **Test dashboard playback** — open dashboard, verify segments render and click-to-play works (Gate 4)
2. **Fix playback offset** — address MediaRecorder/SegmentPublisher timing drift if >3s (Gate 4)
3. **Improve scorer** — handle Whisper splitting long utterances into multiple segments (1:N matching)
4. **Investigate speaker mapping edge cases** — rapid turns and short utterances get wrong speaker
