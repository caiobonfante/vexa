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

[DEAD-END] **Simple mock HTML** (`tests/mock-meeting/index.html`) — lacks Google Meet DOM structure (no pre-join screen, toolbar, participant tiles). Bot stuck at "find name input." Must use `features/realtime-transcription/mocks/google-meet.html`.

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

## Current Blockers (2026-03-23)

1. **Human speaker locking (score 40)** — 8+ minutes to lock with overlapping speech. Needs alternative identity mechanism or faster voting.
2. **Confirmation failure on long monologues** — per-segment stability never triggers for some speakers. Buffer grows → 100-226s monolithic segments.
3. **Multi-track duplication** — same participant audio on multiple `<audio>` elements. Needs track dedup/merge logic.
