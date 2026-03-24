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

## MVP4: 2026-03-24 — Orchestrator picks work across features

**Objective:** Prove the orchestrator can read all features' findings, pick the highest-impact work, spawn a team, and move a score — without being told which feature to work on.

**Priority map built from all features' findings:**

| Feature | Score | Impact | Decision |
|---------|-------|--------|----------|
| calendar-integration | 0 | HIGH | SKIP — no code to test |
| chat | 0 | MEDIUM | candidate |
| speaking-bot | 0 | MEDIUM | **PICKED** — code-complete, TTS infra proven |
| knowledge-workspace | 30 | MEDIUM | blocked on entity extraction |
| scheduler (E2E) | 0 | HIGH | blocked on Redis port |
| realtime-transcription | 80 | CRITICAL | needs Level 6 (human meeting) |
| post-meeting-transcription | 80 | HIGH | Gate 4 needs browser |

**Target:** speaking-bot, score 0, code-complete across full stack, TTS infrastructure already running.

**Team:** researcher (industry practices) + executor (Level 1-5 validation) + verifier (independent confirmation)

### What happened

1. **Researcher** investigated speak API path AND industry practices:
   - Mapped full API path: gateway → bot-manager → Redis → bot → TTS → PulseAudio
   - Found Recall.ai's approach (pre-rendered MP3) vs Vexa's (server-side TTS) — Vexa's is better
   - Established latency quality bar from Twilio/Picovoice: POST→audible <800ms
   - Documented 6 PulseAudio gotchas
   - **Found 3 bugs** in browser_session bot speak path before executor ran

2. **Executor** validated Level 1-5:
   - Level 1: POST speak → 202 ✅
   - Level 2: TTS generates 52-54KB WAV ✅
   - Level 3: Regular bots receive and play ✅, browser_session broken ❌ (3 bugs)
   - Level 5: Meeting 42 has 16 complete speak cycles in Redis ✅

3. **Verifier** confirmed all 6 claims independently, zero discrepancies.

### Bugs found (3)

1. **Channel mismatch**: bot-manager publishes to `bot_commands:meeting:{id}`, browser_session subscribes to `browser_session:{container_name}`
2. **No speak handler**: browser-session.ts only handles `save_storage` and `stop`
3. **Missing env var**: `TTS_SERVICE_URL` not passed to browser_session containers

### Score change

**speaking-bot: 0 → 70** (Level 5 validated for regular bots, blocked at Level 3 for browser_session)

### What MVP4 proved

- Orchestrator reads all features' findings and builds a meaningful priority map
- Orchestrator picks the right feature (code-complete, score 0, infrastructure available)
- 3-agent team (researcher + executor + verifier) works without lead intervention beyond initial spawn
- Researcher finding bugs before execution saves executor from debugging
- Zero-discrepancy verification gives high-confidence scores
- The loop works across features, not just realtime-transcription

### What's next

1. Fix the 3 browser_session bugs → speaking-bot score 70→80
2. Pick next feature from priority map (chat: score 0, code-complete)
3. Consider: should the orchestrator fix bugs it finds, or just report them?

**MVP4 verdict: PASS.** The orchestrator picks cross-feature work, spawns teams, and moves scores autonomously.
