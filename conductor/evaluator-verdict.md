# Evaluator Verdict — MS Teams Realtime Transcription Re-Evaluation

## Claims Reviewed

| Claim | Verified? | Evidence | Notes |
|-------|-----------|----------|-------|
| E2E basic: 9/9, 100% speaker, 14% WER | UNVERIFIABLE | Text in findings.md + e2e/README.md only | No stored test output (results/ gitignored, no logs in git history) |
| E2E stress: 18/20, 100% speaker, 15% WER | UNVERIFIABLE | Text in findings.md + e2e/README.md only | Same — zero raw output preserved |
| Bot code unchanged since tests | PARTIALLY FALSE | `git log --since=2026-03-23 -- platforms/msteams/` shows 2 commits | bdd68668 changed recording.ts (+11 lines), 8b095230 changed admission.ts. Findings.md only acknowledges admission.ts |
| Shared pipeline "improvements only" | INCOMPLETE | Findings acknowledges bdd68668 + ffd7c5f0 | **3 additional commits NOT mentioned**: f50f36cc (122-line rewrite of speaker-streams.ts), 54df04b4 (security hardening segment-publisher.ts + index.ts), 5f8dee7d (hallucination filter in speaker-streams.ts) |
| Backend pipeline validated via GMeet | TRUE | Commit 0ad8eae4 exists, GMeet scored 90 | Valid for shared downstream (Redis→collector→Postgres→REST→WS), not for Teams-specific capture |
| Commits bdd68668, ffd7c5f0, 0ad8eae4, 61f530d, 3b3a5b9 exist | TRUE | All 5 verified via `git show --stat` | Content matches descriptions |

## Code-README Alignment

| Component | README says | Code actually does | Match? |
|-----------|-------------|-------------------|--------|
| Audio queue / ring buffer | 3s max, chunks wait for caption | `MAX_QUEUE_AGE_MS = 3000`, `audioQueue[]` with timestamp pruning | YES |
| Caption selectors | `[data-tid="author"]` + `[data-tid="closed-caption-text"]` | Exact match in selectors.ts lines 375+377 | YES |
| Offset-based sliding window | `confirmedSamples` advances, only unconfirmed sent to Whisper | `confirmedSamples` field, `unconfirmedSamples()` method, `buffer[confirmedSamples:]` submission | YES |
| Config values | submitInterval=2s, confirmThreshold=2, maxBuffer=30s, idle=15s | Exact match: lines 92-95 of speaker-streams.ts | YES |
| Speaker mapper | Word timestamps mapped to speaker boundaries by overlap | `mapWordsToSpeakers()` in speaker-mapper.ts | YES |
| RMS silence filter | `RMS < 0.01` in browser | Present in recording.ts audio processor | YES |

## Missing Evidence

1. **No stored test output.** Test scripts save to `results/e2e-{date}/` but this directory is gitignored. No scorer output, no raw Postgres dumps, no curl responses preserved anywhere in git. The claims "9/9 segments, 100% speaker accuracy, 14% WER" are self-reported text — not independently verifiable.

2. **3 unacknowledged shared pipeline commits after test date (2026-03-23):**

   | Commit | Date | File | Change | Risk |
   |--------|------|------|--------|------|
   | f50f36cc | Mar 24 | speaker-streams.ts | **122 lines changed** — confirmation algorithm rewritten from per-segment to word-level prefix matching, maxBufferDuration 120s→30s | HIGH — core algorithm change |
   | 54df04b4 | Mar 24 | segment-publisher.ts (+13), index.ts (+39) | Security hardening: 5s Redis connect timeout, memory limits, non-root | LOW — defensive changes |
   | 5f8dee7d | Mar 27 | speaker-streams.ts (+18) | Hallucination filter wired into confirmation pipeline | MEDIUM — new filter could reject valid segments |

3. **recording.ts change not acknowledged.** bdd68668 added 11 lines to recording.ts (timestamp re-alignment via `__vexaRecordingStarted`). Findings.md says "only admission.ts" changed. The change is minor and likely an improvement, but the claim is factually incorrect.

## Score Assessment

**Claimed: 90. Recommended: 75.**

### What supports a high score:
- Architecture is solid — code matches README thoroughly
- All 8 referenced files exist and implement what's described
- Test infrastructure is real (scripts, scorer, ground truth conversation)
- GMeet validates the shared downstream pipeline at 90
- Known limitations are honestly documented
- The unacknowledged changes are likely improvements, not regressions

### What prevents confirming 90:
- **No reproducible test evidence.** The only proof is text written by the same team that wrote the code. No raw output, no scorer logs, no timestamps from test runs.
- **Core shared pipeline materially changed since tests.** speaker-streams.ts had 140+ lines changed across 3 commits after the test date. The confirmation algorithm was rewritten. We simply don't know if Teams E2E still passes.
- **5 days elapsed since last test** (Mar 23 → Mar 28) with significant pipeline changes in between.

### Certainty table re-scoring:

| Check | Claimed | True | Reason |
|-------|---------|------|--------|
| Bot joins live Teams meeting | 90 | 85 | Plausible from test scripts + admission.ts, but no recent evidence |
| Audio capture | 90 | 85 | Code verified, RTC hook exists, but not tested since pipeline changes |
| Caption-driven speaker routing | 90 | 80 | Code verified, architecture sound, but confirmation algorithm was rewritten post-test |
| Transcription pipeline | 90 | 70 | **122-line rewrite of speaker-streams.ts not tested with Teams** |
| Multi-speaker attribution | 90 | 75 | Depends on confirmation algorithm which changed |
| WS delivery | 90 | 90 | Shared, validated via GMeet ✓ |
| REST /transcripts | 90 | 90 | Shared, validated via GMeet ✓ |
| End-to-end pipeline | 90 | 75 | Chain is only as strong as weakest link (transcription pipeline = 70) |

**Weighted average: ~75**

## Known Gaps

1. **Re-run E2E tests** against current codebase to verify pipeline still works after speaker-streams.ts rewrite
2. **Store test output** in git (or at least commit scorer summary) so evidence is reproducible
3. **Acknowledge all post-test commits** in findings.md — currently 3 of 5 shared pipeline commits are missing

## Verdict: REJECT (iterate)

The code quality and architecture are strong, but the score claim of 90 is based on 5-day-old tests run before a 140+ line rewrite of the core confirmation algorithm. This is fixable:

1. **Re-run `test-e2e.sh` and `test-e2e-stress.sh`** against the current codebase. If results match or improve, score advances to 85-90.
2. **Save scorer output** (even a summary) so evidence is independently verifiable.
3. **Update findings.md** to acknowledge commits f50f36cc, 54df04b4, 5f8dee7d.

All three items are completable in a single iteration. If tests pass, I would ACCEPT 85-90. If tests fail, the gap is real and needs fixing.

**If tests cannot be run** (no live Teams meeting available, no credentials), then ACCEPT at 75 — the code is architecturally sound and likely works, but we can't prove it.
