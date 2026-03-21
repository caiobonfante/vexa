# Realtime Transcription Test Findings

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Bot joins 3-speaker mock (Google Meet) | 90 | 3 speakers found, all locked permanently at 100% | 2026-03-16 | Retest with fresh stack |
| Per-speaker audio captured | 90 | 3 ScriptProcessors active, audio reaching handlePerSpeakerAudioData | 2026-03-16 | -- |
| Speaker identity locks correctly | 90 | Alice/Bob/Carol all locked (3/3 votes, 100% ratio) | 2026-03-16 | -- |
| Transcription returns text | 90 | HTTP 200 with non-empty text from transcription-service | 2026-03-20 | -- |
| Segments in Redis Hash | 90 | 7 segments in meeting 8791 Redis Hash | 2026-03-16 | -- |
| Segments persist to Postgres | 90 | 7 segments returned via GET /transcripts | 2026-03-16 | -- |
| Pipeline replay (capture) | 100 | 17/17 utterances captured in production-replay | 2026-03-21 | -- |
| Pipeline replay (attribution) | 100 | 17/17 correct speaker in production-replay | 2026-03-21 | -- |
| Live speaker attribution (Teams) | 90 | 3/3 speakers correct in live 3-speaker test, 7/7 in 9-speaker test | 2026-03-21 | -- |
| REST /transcripts delivery | 90 | 14 segments delivered correctly in live test (meeting 324) | 2026-03-21 | -- |
| End-to-end latency | 80 | DRAFT 4.9s, CONFIRMED 10.8s (submitInterval=2, confirmThreshold=2) | 2026-03-21 | Target <5s confirmed |
| Live segments via WebSocket | 0 | Not tested directly via wscat | -- | Connect wscat, verify segments |
| WS and REST consistency | 0 | Not tested | -- | Compare WS segments to REST |
| VAD filters silence | 80 | No empty-text segments in output (indirect) | 2026-03-16 | Feed silent audio, verify zero segments |
| MS Teams pipeline | 90 | 9-speaker live replay with correct attribution, 14 segments delivered | 2026-03-21 | -- |

## Platform Status

| Platform | Gate Status | Bottleneck |
|----------|-----------|------------|
| Google Meet | PASS (degraded: WS untested) | WebSocket live delivery at score 0 |
| MS Teams | PASS (degraded: WS untested) | WebSocket live delivery at score 0 |

## Aggregate: Lowest score = 0 (WS delivery)

Gate verdict: **FAIL** -- WebSocket live delivery untested.

## Sandbox Iteration Results

### Iteration 1 (2026-03-20): 24% -> 88% (+64% speaker attribution)

**Fixes applied to `speaker-streams.ts`:**

1. **Removed carry-forward mechanism** -- Short audio on speaker change is now submitted directly to Whisper instead of being prepended to the next speaker's buffer.

2. **Fixed `windowStartMs` timing** -- Set buffer start time when first audio arrives after reset, not during the reset itself.

3. **Added `carryForwardSamples` tracking** -- Buffer-level tracking of inherited audio to prevent chaining.

**Fixes applied to `production-replay.test.ts`:**

4. **Per-speaker word storage** -- Changed `latestWhisperWords` from a shared global to a per-speaker Map.

5. **Per-speaker audio channels** -- Audio is now fed to each speaker's channel individually.

6. **Fixed keyword comparison** -- Exact word matching (no substring), with relaxed filtering for short GT utterances.

### Iteration 2 (2026-03-21): 88% -> 100% (+12%)

**Fix 1: Mapper single-word boundary merge (`speaker-mapper.ts`)**

Short phrases at speaker boundaries were split by the mapper when one word's Whisper timestamp fell slightly before the caption boundary.

**Fix 2: Stale in-flight response guard (`speaker-streams.ts`)**

Added a `generation` counter to each speaker buffer. Discards responses where the recorded generation is older than the current buffer generation.

**Fix 3: Context tail trim after offset advance (`speaker-streams.ts`)**

After `advanceOffset`, if remaining unconfirmed audio is shorter than `minAudioDuration`, trim it completely.

### Iteration 3 (2026-03-21): Live pipeline fixes

**Fix 4: Caption timestamp domain mismatch (`index.ts`)**

Caption events stored timestamps as absolute wall-clock seconds (~1.77 billion) while Whisper word timestamps were session-relative (~70-100s). The mapper couldn't match any words to boundaries, fell back to nearest-speaker, and always picked the first speaker. Fix: convert caption timestamps to `(timestampMs - sessionStartMs) / 1000`.

**Fix 5: Disabled mapper for Teams per-speaker audio (`index.ts`)**

The mapper was originally needed when carry-forward moved audio between speakers. After removing carry-forward (iteration 1), the mapper only introduced errors by re-attributing words based on caption boundary timing jitter. For Teams, per-speaker audio routing already provides correct attribution. Mapper disabled for Teams; still used in replay tests.

**Fix 6: Retry on HTTP 500 (`transcription-client.ts`)**

CUDA OOM errors (HTTP 500) were not retried. Added 500 to transient error list alongside 503 and 429.

**Fix 7: Latency tuning (`index.ts`, `.env`)**

Reduced `submitInterval` from 3s to 2s and `confirmThreshold` from 3 to 2. Confirmed latency dropped from 16.5s to 10.8s (35% improvement). DRAFT latency ~5s.

### Scoring History

| Iteration | Captured | Speaker | Delta | Fix |
|-----------|----------|---------|-------|-----|
| Baseline (before fixes) | 82% | 18% | -- | Broken comparison + carry-forward + shared words |
| After comparison fix | 71% | 24% | -- | Accurate measurement of real issues |
| Iteration 1 | 88% | 88% | +64% | Core pipeline fixes |
| Iteration 2 | 100% | 100% | +12% | Mapper merge + stale response guard + tail trim |
| Iteration 3 (live) | 100% | 100% | -- | Timestamp domain + mapper disable + retry + latency |

## Action Items

1. Connect wscat during active Teams meeting and verify segments arrive in real-time
2. Compare WS segments to REST /transcripts output for consistency
3. Test with longer meetings (>5 min) to verify buffer stability
