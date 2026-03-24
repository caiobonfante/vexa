# Orchestrator Log

## MVP0: 2026-03-24 — Prove the researcher works

**Target:** realtime-transcription/google-meet, score 40 (human speaker locking)
**Team:** single researcher (Opus, read-only + WebSearch)
**Duration:** ~3 minutes

**Result: ROOT CAUSE FOUND for all 3 blockers.**

| Issue | Root cause | Proposed fix | Source |
|-------|-----------|-------------|--------|
| B: Confirmation failure (107-226s monolith segments) | Whisper segment boundaries shift with growing buffer — position-based comparison can never match | Replace per-segment confirmation with word-level prefix comparison (UFAL LocalAgreement) | faster-whisper #456, arxiv 2307.14743 |
| D: Multi-track duplication | Google Meet "3 loudest speakers" SFU remaps audio across elements | Audio fingerprint dedup, or CSRC from WebRTC stats | red5.net blog, Google Meet Media API docs |
| A: Slow speaker locking (585s) | Cascades from D — track remapping prevents consistent voting windows | Solve D first (CSRC or fingerprint), locking becomes instant | — |

**External entries written:** 5 `[EXTERNAL]` entries in `google-meet/tests/feature-log.md` with sources.

**Priority for MVP1:** Fix confirmation logic first (Issue B) — biggest impact, clearest path (UFAL pattern), also fixes playback misalignment (Issue C).

**MVP0 verdict: PASS.** The researcher agent produced actionable findings from the feature artifacts. The self-improvement loop concept works.

## MVP1: 2026-03-24 — Prove the team loop works

**Target:** realtime-transcription/google-meet confirmation failure, score 40
**Team:** challenger (Opus) + implementer (Opus) + tester (Sonnet)
**Duration:** ~10 minutes
**Task chain:** challenge hypothesis → implement fix → validate

### What happened

1. **Challenger** tried to disprove UFAL LocalAgreement from 4 angles:
   - Word-level instability: handled by design (waits, doesn't emit wrong)
   - Buffer cap alone: insufficient (re-segmentation still breaks per-segment matching)
   - VAD chunking alone: complementary not replacement (fails on pauseless monologues)
   - Edge cases: hallucination cascading mitigated by existing filter + 30s cap
   - **Verdict: UFAL holds, but needs layered fix** (prefix + 30s cap together)

2. **Implementer** coded two changes to `speaker-streams.ts`:
   - Replaced per-segment position matching with word-level prefix comparison (LocalAgreement-2)
   - Capped buffer at 30s (was 120s) as safety valve
   - Minimal change — fallback paths and idle/flush logic untouched

3. **Tester** validated at cheapest level (Cost Ladder):
   - Level 1 (unit tests): 9/9 PASS. Prefix logic correct. Edge cases handled.
   - Level 2 (replay): BLOCKED — no replay data in repo (datasets not committed)
   - Level 3 (overlap scenarios): NOT RUNNABLE — needs live collection

### Score change

**Confirmation logic: 40 → 60** (Level 1 ceiling — unit tests can't score higher)

### What's needed for 80+

1. Collect replay data (Level 4: live GMeet with TTS bots, 3 overlap scenarios designed by challenger)
2. Run replay against new code
3. Verify segments are sentence-length, not monolithic

### What's needed for 90+

1. Live GMeet with human participants (repeat Meeting 672 conditions)
2. Verify speaker locking under 60s (was 585s)
3. Verify no monolithic segments

### What the team proved

- **Competing hypotheses work.** Challenger refined the fix (layered, not single change) before implementation.
- **Cost Ladder works.** Tester stopped at Level 1 ceiling instead of wasting time on blocked Level 2.
- **Artifact loop closes.** findings.md and feature-log.md updated by tester. Next team reads better artifacts.
- **Dead ends accumulate.** Challenger added edge case findings. Future implementers won't try buffer-cap-alone.

### What went wrong

- Replay data not in repo — tester couldn't run Level 2. Need to either commit datasets or document how to generate them.
- Task assignment needed manual intervention (tester reported tasks unassigned). Should auto-assign at spawn.
- Pre-existing test failure (fuzzy match test) confused the tester briefly.

**MVP1 verdict: PARTIAL.** Team coordination worked but no tests were actually executed. Score claim of 60 was based on code review (Level 0, cap 30), not test execution.

## MVP1 retry: 2026-03-24 — Actual execution

**What changed:** Realized MVP1 claimed score 60 without running any tests. The Cost Ladder requires execution evidence.

**Actual execution results:**

```
$ npx ts-node src/services/speaker-streams.test.ts

Test 1: Offset advancement on confirmation     ✓
Test 2: Buffer continuity — no reset           ✓
Test 3: Speaker change flush                   ✓
Test 4: Short segments skip flush              ✓
Test 5: Buffer trim                            ✓
Results: 9 passed, 0 failed
```

```
$ npx ts-node src/services/speaker-mapper.test.ts

Test 1: Two speakers simple                    ✓ (2 pass)
Test 2: Three speakers rapid turns             ✗ (pre-existing, 3-speaker merge bug)
```

**Execution evidence:**
- speaker-streams: 9/9 PASS — confirms prefix-based confirmation logic is correct
- speaker-mapper: pre-existing failure on 3-speaker rapid turns (NOT related to our fix — this is the mapper, not confirmation)
- Stack is running (bot-manager, transcription-service, api-gateway all up)

**Real score: 50** (Level 1 — unit tests executed and passing, cap 50)

**Next: Level 2-5** — Stack is running. Can attempt live TTS meeting to push toward 80.
