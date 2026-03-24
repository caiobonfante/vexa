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

## Current Blockers (2026-03-23)

1. **Human speaker locking (score 40)** — 8+ minutes to lock with overlapping speech. Needs alternative identity mechanism or faster voting.
2. **Confirmation failure on long monologues** — per-segment stability never triggers for some speakers. Buffer grows → 100-226s monolithic segments.
3. **Multi-track duplication** — same participant audio on multiple `<audio>` elements. Needs track dedup/merge logic.
