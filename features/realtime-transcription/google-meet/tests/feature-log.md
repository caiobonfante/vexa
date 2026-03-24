# Feature Log — Google Meet Transcription

Append-only. Records trajectory, decisions, dead ends.

## Trajectory

| Date | Score | Delta | Key change |
|------|-------|-------|------------|
| 2026-03-16 | 90 (mock) | — | 3 speakers locked, 7 segments, GC fix deployed |
| 2026-03-17 | 90 (real join) | — | 3 real meetings joined, auto-admit works, VAD loads |
| 2026-03-23 | 90 (TTS E2E) | — | 9/9 basic (100% speaker), 18/20 stress (100% speaker, 15% WER) |
| 2026-03-23 | 40 (human) | — | Meeting 672: 23/215 unnamed, confirmation failure, multi-track duplication |

## Dead Ends

[DEAD-END] **3-vote threshold for speaker locking** — too slow with overlapping speech. Meeting 672: 585s to lock speaker-0. Reduced to 2 votes + weighted voting. Still insufficient for fast-paced human conversations.

[DEAD-END] **Simple mock HTML** (`tests/mock-meeting/index.html`) — lacks Google Meet DOM structure (no pre-join screen, toolbar, participant tiles). Bot stuck at "find name input." A proper mock at `features/realtime-transcription/mocks/google-meet.html` is needed but the `mocks/` directory does not exist yet — it must be created before mock-based testing can resume.

[DEAD-END] **Prefix-based confirmation (LocalAgreement-2) passes unit tests but fails on real audio (2026-03-24).** 163s gTTS monologue → 1 monolith segment (333 words). Confirmation never triggered mid-stream. Root causes:
1. **wav-test.ts uses `maxBufferDuration: 120`**, not the intended 30s. The production bot (`index.ts:1050`) also uses 120s. The default 30s in speaker-streams.ts is overridden everywhere.
2. **`trimBuffer` is a no-op when `confirmedSamples === 0`** (line 493). The "cap" only trims already-confirmed audio — it does NOT force-flush unconfirmed audio. If prefix confirmation never triggers, the buffer grows unbounded regardless of `maxBufferDuration`.
3. **Whisper changes words, not just segment boundaries**, across submissions with growing buffers. Even word-level prefix comparison fails because early words shift as the attention context expands.
The challenger's recommended fix was LAYERED: prefix + 30s cap + VAD-informed submission. We implemented prefix but the cap value didn't take effect (overridden to 120s), and `trimBuffer` doesn't force-flush. The 30s cap needs to be a FORCE-FLUSH (emit whatever is in the buffer + reset), not a trim of confirmed audio.

[DEAD-END] **False-positive waiting room selectors** — `[role="progressbar"]`, `[aria-label*="loading"]`, `.loading-spinner` present in real DOM but not in waiting room. Removed from `googleWaitingRoomIndicators`.

## Results

[RESULT] **isDuplicateSpeakerName dedup** — primary guard against misattribution. Rejects any speaker name already assigned to another track. Works: 9/9 basic, 18/20 stress with 100% speaker accuracy.

[RESULT] **Per-element ScriptProcessor** — N independent audio pipelines, one per `<audio>` element. Clean single-voice per stream. No diarization needed.

[RESULT] **GC fix** — `window.__vexaAudioStreams` stores refs, preventing garbage collection. 324 onSegmentReady calls confirmed.

## External Research (2026-03-24)

[EXTERNAL] **GMeet "3 loudest" audio architecture explains multi-track duplication (Issue D).**
Google Meet's SFU sends only the 3 loudest participants via 3 fixed WebRTC SSRCs (audio tracks A/B/C).
When speaker activity changes, Meet dynamically remaps which participant's audio flows through each SSRC.
The CSRC (Contributing Source) in RTP headers identifies the true speaker, but the browser exposes this
as separate `<audio>` elements — the same participant CAN appear on multiple elements simultaneously
during remapping transitions. This is by design, not a bug.
**Implication:** Track dedup must use audio fingerprinting or CSRC correlation, not just DOM element identity.
The current per-element ScriptProcessor model (1 pipeline per `<audio>`) will inherently see duplicates
when GMeet remaps the same speaker across SSRCs.
Source: https://www.red5.net/blog/how-google-meet-implements-audio-using-mix-minus-with-webrtc/
Source: https://developers.google.com/workspace/meet/media-api/guides/virtual-streams

[EXTERNAL] **Whisper segment boundaries are inherently unstable with growing buffers (Issue B root cause).**
Whisper's segmentation is not deterministic w.r.t. audio length — the same speech content processed
as part of a longer buffer produces different segment boundaries than when processed as a shorter buffer.
This is because the attention mechanism considers the full 30s mel spectrogram context, and adding more
audio shifts the attention patterns. faster-whisper confirms: changing chunk_length/hop_length changes
segment boundaries for the same audio. Our per-segment confirmation (line 194-248 of speaker-streams.ts)
requires `currentTexts[i] === prevTexts[i]` — exact string match at each segment position. As the buffer
grows by 2s every submission, Whisper re-segments the entire unconfirmed audio, producing different
segment boundaries each time. The text at position i is never identical across submissions.
**This is why confirmation never triggers for some speakers — it's a fundamental design flaw in
exact-match per-segment confirmation with growing buffers.**
Source: https://github.com/SYSTRAN/faster-whisper/issues/456
Source: https://github.com/openai/whisper/discussions/223

[EXTERNAL] **UFAL whisper_streaming solves this with LocalAgreement + sentence-level buffer scrolling.**
The UFAL approach (paper: "Turning Whisper into Real-Time Transcription System", 2307.14743):
1. LocalAgreement-n policy: confirms transcript prefix if n consecutive submissions agree on it
   (operates on the FULL TEXT prefix, not per-segment boundaries)
2. Buffer scrolling: on confirmation, scrolls the audio buffer forward to the timestamp of the
   last confirmed word — confirmed audio is trimmed, only unconfirmed audio is resubmitted
3. Sentence trimming: optionally trims at sentence boundaries so Whisper always starts fresh sentences
Key difference from our approach: UFAL confirms TEXT PREFIXES (word-level), not SEGMENT BOUNDARIES.
Our code (speaker-streams.ts:194) checks `segments.length > 1` and compares segment texts by position.
UFAL doesn't care where Whisper puts segment boundaries — it only checks if the leading words are stable.
**Proposed fix: Replace per-segment confirmation with prefix-based confirmation (LocalAgreement-2).**
Compare word sequences, not segment texts. Confirm when leading N words are identical across 2 submissions.
Source: https://github.com/ufal/whisper_streaming
Source: https://arxiv.org/html/2307.14743

[EXTERNAL] **WhisperLiveKit caps cross-attention tensors to prevent unbounded memory growth.**
WhisperLiveKit (QuentinFuxa) found that SimulStreaming cross-attention tensors accumulated up to ~5GB
during decoding loops. Fix: cap to a rolling window. Our buffer has maxBufferDuration=120s but no
cross-attention cap — the transcription-service may also suffer memory growth on long monologues.
Additionally, WhisperLiveKit uses automatic silence chunking (VAD-based) to limit buffer size,
preventing the buffer-grows-forever problem our system hits when confirmation fails.
Source: https://github.com/QuentinFuxa/WhisperLiveKit

[EXTERNAL] **Speaker locking with overlapping speech — "exclusive mode" diarization alternative.**
Speechmatics and pyannote offer "exclusive" mode diarization where only one speaker is active at
any time. However, our system already has per-speaker audio tracks (from GMeet's 3-track architecture),
so diarization is overkill. The real problem is that our voting system requires "single-speaker windows"
(only 1 person talking) to cast a vote. With 3 humans talking naturally with overlaps, single-speaker
windows are rare in the first minutes.
**Alternative approaches for faster locking:**
1. Use CSRC from RTP headers (if accessible via WebRTC stats API) to directly map track→participant
2. First-name-seen locking: lock on first vote instead of waiting for N votes (accept higher error risk)
3. Audio embedding similarity: compare track audio to known speaker embeddings (no voting needed)
4. Caption-based identity: GMeet may have closed captions with speaker names (like Teams) — check DOM
Source: https://docs.speechmatics.com/speech-to-text/realtime/realtime-diarization

## Adversarial Analysis: UFAL LocalAgreement Hypothesis (2026-03-24, researcher-2)

### Challenge 1: Does word-level prefix work when Whisper changes WORDS too?

**VERDICT: Partially vulnerable, but survivable.**

Whisper is non-deterministic even at temperature=0 — the same audio can produce different words
across runs (whisper.cpp #734, openai/whisper #81). When buffer length changes, the attention
mechanism shifts, and not just segment boundaries move — actual WORDS can change. Example:
"Everyone let me start" → "Everyone, let me begin" across two submissions with different buffer lengths.

However, LocalAgreement-2 handles this by design: if the prefix doesn't match, it simply doesn't
confirm. The unconfirmed buffer grows, and on the NEXT submission pair where words DO agree, the
longest common prefix gets confirmed. The failure mode is increased latency, not wrong output.

**Critical edge case: Whisper hallucination at buffer start.** When silence precedes speech in
the buffer, Whisper can hallucinate different phantom words at the beginning each time
(openai/whisper #679). This poisons the prefix — if word 0 is different, NO prefix matches,
and confirmation never triggers. This is the SAME failure mode as our current system, just
at word level instead of segment level.

**Mitigation in UFAL:** Buffer scrolling + sentence trimming ensures the buffer always starts
at a sentence boundary with actual speech. VAD pre-filtering removes leading silence. Our
system already has Silero VAD, so this edge case is partially covered.

**Risk: MEDIUM.** Word-level instability exists but is less severe than segment-level instability.
Most word changes happen at the END of the transcript (where Whisper is uncertain), not at
the confirmed prefix. The UFAL paper reports 3.3s average latency for English, suggesting
prefix agreement happens frequently enough.

### Challenge 2: Would simply capping buffer at 30s be sufficient?

**VERDICT: Insufficient alone, but SHOULD be combined with any fix.**

The UFAL paper itself notes: "to avoid unacceptably long spikes in latency, the audio buffer
is limited to around 30 seconds." This is NOT the confirmation mechanism — it's a safety valve.

Capping at 30s would help our system because:
- Whisper is trained on 30s mel spectrograms. Buffers >30s force attention over padded/wrapped input.
- Shorter buffers = more stable attention patterns = more stable segment boundaries.
- Our current maxBufferDuration=120s is 4x what Whisper was trained for.

But capping alone does NOT fix confirmation. Even with a 30s buffer, our per-segment comparison
(line 194-248) will still fail because Whisper re-segments the SAME 30s differently as 2s of
new audio is appended each cycle. The text at position [i] still shifts.

**Recommendation: Cap buffer at 30s AND switch to prefix-based confirmation.**
The cap prevents pathological buffer growth; prefix confirmation handles the re-segmentation.

### Challenge 3: Would VAD-based chunking avoid the problem entirely?

**VERDICT: Strong alternative for multi-speaker, but loses context for monologues.**

VAD-based chunking (split on silence, submit each speech segment independently) is used by
WhisperLiveKit and faster-whisper's batched mode. It works well when speakers pause between
sentences (natural speech has 200-500ms pauses).

**Advantages over LocalAgreement:**
- Simpler implementation — no prefix comparison needed
- Each chunk is independent — no growing buffer problem
- Already have Silero VAD loaded and working

**Disadvantages:**
- Long monologues with no pauses: VAD finds no split points, buffer still grows
- Cutting mid-sentence: Whisper loses cross-sentence context, accuracy drops
- Short chunks (<3s): Whisper quality degrades significantly on very short audio
- Our pipeline already submits every 2s regardless — VAD would need to REPLACE the
  fixed-interval submission with event-driven "speech ended" submission

**Risk assessment:** VAD chunking is complementary, not a replacement. It prevents buffer growth
during natural speech but doesn't solve the confirmation problem for continuous speech.
WhisperLiveKit uses BOTH VAD chunking AND LocalAgreement together.

### Challenge 4: Edge cases where prefix comparison fails

**Known failure modes from UFAL issues (whisper_streaming #102, #121):**

1. **Hallucination cascade:** When Whisper hits compression_ratio_threshold failure at temp=0,
   it retries at higher temperatures, producing wildly different output each time. Prefix
   comparison fails indefinitely. The buffer grows until force-flush. UFAL #102 shows latency
   jumping from 1.3s to 7.6s when this happens.

2. **Language confusion:** With multilingual audio, Whisper may transcribe the same speech in
   different languages across submissions. Prefix will never match. UFAL #121 reports constant
   hallucinations with Greek audio producing Japanese/Chinese characters.

3. **"Not enough segments to chunk":** When the buffer grows large but Whisper returns only 1
   segment (no sentence boundaries found), the sentence-trimming strategy can't trim, and the
   buffer keeps growing. This is documented in UFAL #102.

4. **Our specific risk — per-speaker audio quality:** GMeet's "3 loudest" architecture means
   audio quality on a track can degrade when Meet is transitioning speakers between SSRCs.
   Brief audio artifacts during remapping could trigger hallucinations at the buffer boundary.

### Conclusion: UFAL hypothesis HOLDS with caveats

The UFAL LocalAgreement approach is **fundamentally sound** for our confirmation problem.
I could not disprove it — the core insight (compare text prefixes, not segment positions) is
correct and well-validated in production systems (UFAL, WhisperLiveKit).

**However, it is NOT sufficient alone. Recommended layered fix:**

1. **Replace per-segment confirmation with prefix-based (LocalAgreement-2)** — core fix
2. **Cap buffer at 30s** (down from 120s) — safety valve, matches Whisper training
3. **VAD-informed submission** — submit on speech-end events, not just fixed 2s interval
4. **Hallucination filter on prefix** — if prefix starts with known hallucination phrases
   (already have hallucination-filter.ts), skip that submission entirely

Implementing only #1 without #2 risks the same pathological growth when hallucinations
prevent prefix agreement. The 30s cap is the backstop.

### Test Scenarios for Reproducing Confirmation Failure

**Scenario A: 60s+ monologue from single TTS speaker**
- One TTS bot speaks continuously for 90s without pauses (concatenated sentences, no gaps)
- Expected: current system — confirmation never triggers, 1 monolithic segment at force-flush
- Validates: prefix-based confirmation should emit ~3-4 sentence-level segments during the monologue
- Measurement: count confirmed segments emitted BEFORE force-flush timeout

**Scenario B: 3 speakers with deliberate 2-3s overlaps at transitions**
- TTS bot A speaks 15s, bot B starts 2s before A ends, bot C starts 2s before B ends
- Repeat cycle 3x (total ~2min)
- Expected: current system — votes fail during overlaps, confirmation stalls during identity uncertainty
- Validates: whether prefix confirmation works independently of speaker locking delays
- Measurement: time-to-first-confirmed-segment per speaker, count of unnamed segments

**Scenario C: Long monologue + short interjections**
- TTS bot A speaks continuously for 60s
- TTS bot B interjects 3-word phrases at 15s, 30s, 45s ("That's interesting", "I agree", "Good point")
- Expected: current system — A's confirmation fails (growing buffer), B's interjections too short to confirm
- Validates: prefix confirmation handles asymmetric speech patterns
- Measurement: A's segment count (should be >1), B's segment count (should be 3), no cross-attribution

## Fixes

[FIX] **Replace per-segment confirmation with word-level prefix confirmation (LocalAgreement-2)** — 2026-03-24
File: `services/vexa-bot/core/src/services/speaker-streams.ts`
Root cause: Per-segment confirmation (`currentTexts[i] === prevTexts[i]`) fails because Whisper
re-segments the same audio differently as the buffer grows by 2s each cycle. Text at position i
is never identical across submissions → confirmation never triggers → monolithic 100-226s segments.
Fix: Concatenate all Whisper segment texts into words, compare word-by-word with previous submission's
words (longest common prefix). When prefix is stable across 2 consecutive submissions and doesn't cover
ALL current words, map confirmed prefix back to full Whisper segments and emit them with correct timestamps.
This is robust to segment boundary shifts — only leading WORDS need to be stable.
Additionally capped `maxBufferDuration` from 120s to 30s (matches Whisper's 30s mel spectrogram training
window) as a safety valve against pathological buffer growth when hallucinations prevent prefix agreement.
Based on: UFAL whisper_streaming LocalAgreement-2 policy (arxiv 2307.14743).

## Validation (2026-03-24)

[RESULT] **Prefix-based confirmation (LocalAgreement-2) — Level 1 unit test PASS, replay BLOCKED**

**What changed:** `speaker-streams.ts` — replaced per-segment position comparison (`lastSegmentTexts[i] === currentTexts[i]`) with word-level prefix comparison (`lastWords` common prefix). `maxBufferDuration` reduced 120s → 30s.

**Level 1 — Code analysis + unit tests (score cap 60):**
- 9/9 tests PASS in `speaker-streams.test.ts` (Makefile `make unit` target)
- Code trace confirms fix is correct for target failure mode:
  - Submission 1: words ["Hello", "everyone", "let", "me", "start", "with", "the", "update."] → prefixLen=0, no confirm
  - Submission 2 (+2s audio, Whisper re-segments): words ["Hello", "everyone", "let", "me", "start", "with", "the", "update.", "The", "revenue"] → prefixLen=8, 8<10 → 2 segments confirmed ✓
- Edge cases verified: empty result (returns early, no crash ✓), language switch (no prefix match, reset ✓), single-word (falls through to full-text path correctly ✓)
- Pre-existing test failure in `__tests__/speaker-streams.test.ts`: "fuzzy match" test (1/16 FAIL). This test assumed fuzzy string matching that never existed — confirmed pre-existing by `git show HEAD`. NOT a regression.
- **Gap:** No existing test passes `segments` to `handleTranscriptionResult` — the new prefix path has zero direct test coverage.

**Level 2 — Replay: BLOCKED**
- `features/realtime-transcription/data/raw/` does not exist
- `teams-3sp-collection` and `teams-7sp-panel` datasets not found anywhere in repo
- `make play-replay` cannot run without data

**Level 3 — Overlap scenarios: NOT RUNNABLE**
- Challenger scenarios A/B/C require live TTS collection runs (90s monologue, 3-speaker overlap, long+interjections)
- No pre-captured data; need `/collect` run first

**Score change:** Confirmation logic: 40 → 50 (Level 1 ceiling — unit tests executed and passing, cap 50)
**Execution evidence:** `npx ts-node src/services/speaker-streams.test.ts` → "Results: 9 passed, 0 failed"
**Remaining gap to 90:** (1) Collect data to enable replay; (2) Add unit test covering prefix path with segments; (3) Run challenger overlap scenarios

## Force-flush fix validated (2026-03-24)

[RESULT] **Confirmation fix — Level 2 wav-pipeline PASS: 1 monolith → 27 segments**

**What changed:** Added force-flush path in `trySubmit`: when `totalSec > maxBufferDuration` AND `confirmedSamples===0`, emit lastTranscript + fullReset. Changed `maxBufferDuration` from 120 to 30 in production (index.ts) and all 8 test call sites.

**Level 2 — wav-pipeline (163s monologue):**
- 27 confirmed segments (was 1 monolith)
- 96.5% word accuracy (327/339 words, diff is number formatting)
- 56 Whisper calls, avg 262ms, RTF 0.09x
- Force-flush safety net NOT triggered — 30s cap made prefix confirmation work naturally
- Alpha + Beta independently verified identical results

**Key insight:** The 120s maxBufferDuration was 4x Whisper's 30s training window. Reducing to 30s made the prefix confirmation algorithm effective without needing the force-flush. The force-flush is a safety net for pathological cases only.

**Score change:** Confirmation logic: 40 → 80 (Level 2 validated with real Whisper output)

**Level 5 BLOCKED:** Teams browser login needed (one-time human step). vexa-bot:dev rebuilt with fix. All tools ≥80 via Teams path.

## Current Blockers (2026-03-24, updated)

1. **Teams browser login** — Level 5 requires logged-in browser session. New containers start at login page. VNC/noVNC missing from vexa-bot:dev. Need human one-time login.
2. **Human speaker locking (score 40)** — 8+ minutes to lock with overlapping speech. Fix implemented but not tested beyond unit level.
3. **Multi-track duplication** — same participant audio on multiple `<audio>` elements. Not addressed yet.

## Test Infrastructure (for next agent)

| What | Where | Command | Status |
|------|-------|---------|--------|
| Unit tests (speaker-streams) | `services/vexa-bot/core/` | `npx ts-node src/services/speaker-streams.test.ts` | 9/9 PASS |
| Unit tests (speaker-mapper) | `services/vexa-bot/core/` | `npx ts-node src/services/speaker-mapper.test.ts` | Pre-existing failure on 3-speaker |
| Replay (core) | `features/realtime-transcription/tests/` | `make play-replay DATASET=teams-3sp-collection` | BLOCKED — no data |
| Replay (full system) | `features/realtime-transcription/tests/` | `make play-replay-full` | BLOCKED — no data |
| WAV test | `services/vexa-bot/core/` | `npx ts-node src/services/speaker-streams.wav-test.ts <wav>` | Needs WAV file |
| Delivery replay | `features/realtime-transcription/delivery/` | `node replay-delivery-test.js` | Has data (youtube-pipeline) |
| Live TTS meeting (GMeet) | `features/realtime-transcription/scripts/` | `node gmeet-host-auto.js` + `node auto-admit.js` | Needs browser session |
| Live TTS meeting (Teams) | `features/realtime-transcription/scripts/` | `node teams-host-auto.js` | Needs browser session |
