# Zoom Realtime Transcription (Browser-Based) Findings

## Certainty Table (MVP-aligned)

### MVP0 -- Audio Channel Join — Score: 80

| Check | Score | Evidence | Last checked | To reach next level |
|-------|-------|----------|-------------|---------------------|
| Browser navigates to Zoom web client | 90 | `buildZoomWebClientUrl()` converts URLs correctly, page loads | 2026-03-25 | -- |
| Bot joins meeting via browser | 90 | Join flow works: name input, join click, waiting room detection | 2026-03-25 | -- |
| Audio channel joined | 80 | Fix deployed: click "Allow" not "Continue without mic" (join.ts). Per-speaker audio flows in zoom-3sp-fixed collection. | 2026-03-25 | reCAPTCHA blocks after rapid sequential joins from same IP |
| Non-silent audio in `<audio>` elements | 80 | 3 per-speaker streams confirmed with real audio in zoom-3sp-fixed (11 confirmed segments, 2 speakers detected) | 2026-03-25 | SFU 3-stream limit drops speakers when >4 participants |

### MVP1 -- Speaker Identity — Score: 30

| Check | Score | Evidence | Last checked | To reach next level |
|-------|-------|----------|-------------|---------------------|
| DOM polling detects active speaker | 80 | "SPEAKER_START: Dmtiry Grankin" detected via `.speaker-active-container__video-frame`. zoom-3sp-rawcap events.txt shows 12 speaker transitions correctly tracked. | 2026-03-25 | -- |
| `resolveZoomSpeakerName()` returns names | 40 | Path 2 (`queryZoomActiveSpeaker`) works. Path 1 (`traverseZoomDOM`) dead — audio elements not inside participant tiles. | 2026-03-25 | Fix track locking for SFU remapping |
| Speaker tracks lock permanently | 10 | Track locking assigns wrong names. Zoom SFU remaps tracks dynamically (same 3-stream limit as GMeet). Permanent locking is incompatible — need DOM-based attribution per-segment. | 2026-03-25 | Replace track locking with per-segment DOM attribution |
| `isMostRecentlyActiveTrack()` gates voting | 20 | Implemented but SFU remapping invalidates the single-track-per-speaker assumption. Track 0 carried Charlie in one moment, Alice in the next. | 2026-03-25 | Redesign for dynamic track assignment |

### MVP2 -- End-to-End Transcription — Score: 60

| Check | Score | Evidence | Last checked | To reach next level |
|-------|-------|----------|-------------|---------------------|
| Audio reaches TranscriptionClient | 80 | zoom-3sp-rawcap: 11 confirmed segments transcribed from per-speaker ScriptProcessor path | 2026-03-25 | -- |
| Transcription returns non-empty text | 80 | 7% WER measured by score-zoom.py (zoom-3sp-basic post-fix simulation) | 2026-03-25 | -- |
| Segments in Redis with speaker names | 50 | 11 segments confirmed, but only Bob and Charlie attributed. Alice missing (SFU dropped her track). Recorder misattributed as speaker. | 2026-03-25 | Fix speaker attribution (MVP1) |
| WS live delivery | 60 | Segments stream live during meeting (confirmed in zoom-3sp-basic) | 2026-03-25 | Verify with fixed speaker names |
| Dual pipeline resolved | 80 | WhisperLive transcription disabled (~140 lines removed from recording.ts). Single pipeline: per-speaker ScriptProcessor only. | 2026-03-25 | -- |

### MVP3 -- Auto-Admit + TTS Testing — Score: 20

| Check | Score | Evidence | Last checked | To reach next level |
|-------|-------|----------|-------------|---------------------|
| TTS bots join and stay | 40 | Fixed: removal.ts grace period 10->20s + audio-init URL allowlist. Bots survive join. But reCAPTCHA blocks after rapid sequential joins from same IP. | 2026-03-25 | Solve reCAPTCHA or stagger join timing |
| Auto-admit for Zoom | 30 | zoom-auto-admit.js built (polls participants panel, clicks "Admit All"). Untested due to reCAPTCHA blocking automated sessions. | 2026-03-25 | Test with staggered joins or CAPTCHA bypass |
| Zoom meeting creation (automated) | 30 | zoom-host-auto.js built for headless meeting hosting. Untested due to reCAPTCHA. | 2026-03-25 | Test with authenticated session or Zoom API |
| TTS ground truth scoring | 60 | score-zoom.py implemented with --post-fix and --merge modes. Validated on zoom-3sp-basic data. | 2026-03-25 | Run on fresh collection with fixed image |
| TTS connectivity | 60 | tts-service DNS alias added on agentic network. TTS audio reaches PulseAudio virtual_mic -> Zoom WebRTC. | 2026-03-25 | Verify end-to-end in automated collection |

### MVP4 -- Quality Parity

| Check | Score | Evidence | Last checked | To reach next level |
|-------|-------|----------|-------------|---------------------|
| WER < 15% | 60 | 7% WER measured (zoom-3sp-basic post-fix), but only on correctly-attributed segments | 2026-03-25 | Need full pipeline with correct speakers |
| Speaker attribution > 95% | 10 | 2/3 speakers detected. Track locking assigns wrong names due to SFU remapping. | 2026-03-25 | MVP1 fix first |
| Latency < 5s | 0 | Not measured | -- | MVP2 first |
| Segment confirmation works | 70 | 11 confirmed segments in zoom-3sp-fixed (down from 29+43 duplicates pre-fix) | 2026-03-25 | -- |
| Multi-track dedup | 80 | Dual pipeline disabled. No more duplicates (was 43, now 0). | 2026-03-25 | -- |

### MVP5 -- Production Hardening

| Check | Score | Evidence | Last checked | To reach next level |
|-------|-------|----------|-------------|---------------------|
| URL format coverage | 60 | `buildZoomWebClientUrl()` handles standard + regional + events URLs | 2026-03-25 | Test vanity URLs, personal meeting IDs |
| Reconnection resilience | 0 | Not tested | -- | MVP5 |
| Meeting lifecycle edge cases | 0 | Not tested | -- | MVP5 |

## Overall Score: 45/100

**Weighted by MVP:** MVP0=80, MVP1=30, MVP2=60, MVP3=20, MVP4=28, MVP5=20.

**2026-03-25 Session Summary:**
Three collection runs performed (zoom-3sp-basic, zoom-3sp-fixed, zoom-3sp-rawcap).

Key advances:
- Audio channel join FIXED: click "Allow" not "Continue without mic" (join.ts). Audio flows through per-speaker ScriptProcessor.
- Dual pipeline FIXED: WhisperLive transcription disabled (~140 lines removed). Single per-speaker path, zero duplicates.
- Empty speakers FIXED: DOM fallback in handlePerSpeakerAudioData. Zero empty speakers (was 29).
- Raw capture implemented: per-speaker WAV dumping + events.txt for offline analysis.
- Scoring implemented: score-zoom.py with --post-fix and --merge modes.
- 7% WER on correctly-attributed segments. 88% completeness on post-fix simulation.

Key blockers remaining:
- **Zoom SFU 3-stream limit**: Only 3 audio tracks delivered to any client. With 5 participants, 2 speakers get dropped. Same architecture as GMeet. Tracks remap dynamically as speakers change.
- **Track locking incompatible with SFU**: Permanent track-to-speaker locking assigns wrong names because tracks are reused. Need DOM-based per-segment attribution (not per-track locking).
- **reCAPTCHA**: Zoom shows reCAPTCHA (size=normal) after rapid sequential bot joins from same IP. Blocks automated testing.
- **Alice missing**: In zoom-3sp-fixed, Alice never got a track (SFU dropped her). Only Bob and Charlie detected.

## Critical Path

```
MVP0 (audio join) [80] --> MVP1 (speaker names) [30] --> MVP2 (transcription) [60]
                                                              |
                                     FIX: DOM-based attribution instead of track locking
                                                              |
                                                    MVP3 (TTS testing) [20]
                                                              |
                                                       INFLECTION POINT
                                                    (testing becomes cheap)
                                                              |
                                                    MVP4 (quality) --> MVP5 (hardening)
```

**Primary blocker: MVP1 speaker identity.** Track locking is fundamentally incompatible with Zoom's SFU 3-stream architecture. Need to replace with DOM-based per-segment attribution (use active speaker polling to label segments as they arrive, rather than locking tracks to speakers permanently).

## Known Blockers (Priority Order)

1. **Track locking vs SFU remapping** (MVP1) -- Zoom SFU delivers only 3 audio streams, remaps dynamically. Permanent track locking assigns wrong names. Fix: DOM-based per-segment attribution using active speaker CSS polling (already working at 250ms).
2. **reCAPTCHA on rapid joins** (MVP3) -- Zoom shows CAPTCHA after rapid sequential bot joins from same IP. Blocks automated TTS testing. Mitigations: stagger joins (30s+), use authenticated Zoom sessions, or use Zoom API for meeting creation.
3. **SFU 3-stream limit drops speakers** (MVP1/MVP2) -- With recorder + 3 TTS speakers + host = 5 participants, only 3 audio tracks delivered. Alice consistently dropped. Fix: ensure recorder doesn't occupy a track (mute), or accept that only active speakers are captured (may be acceptable for transcription).
4. **Recorder misattributed as speaker** (MVP2) -- Some segments attributed to "Vexa Recorder" in zoom-3sp-rawcap events.txt. Recorder should be filtered from speaker attribution.

## Dead Ends

- **PulseAudio audio capture for Zoom transcription:** Chrome doesn't route Zoom WebRTC audio through PulseAudio. Records all zeros. Per-speaker ScriptProcessor is the only working path.
- **Permanent track locking for Zoom:** SFU remaps tracks dynamically. Track 0 is Charlie one moment, Alice the next. Locking is fundamentally wrong for this architecture.
- **Zoom Web SDK raw audio:** Not exposed. `mediaCapture` only triggers recording consent popup.
- **Testing TTS bots without auto-admit:** Bots stuck in waiting room, always ejected. Must implement auto-admit first.
- **Testing with rapid sequential joins:** reCAPTCHA blocks after 3-4 rapid joins from same IP.

## Comparison with Siblings

| Metric | GMeet | Teams | Zoom (current) |
|--------|-------|-------|----------------|
| Overall score | 70 | 65 | 45 |
| Audio capture | 90 (per-speaker ScriptProcessor) | 90 (mixed + caption routing) | 80 (per-speaker ScriptProcessor, working) |
| Speaker identity | 90 (TTS), 40 (human) | 90 (caption-driven) | 30 (DOM polling works, track locking broken) |
| Transcription | 90 | 90 | 60 (segments flow, wrong speakers) |
| Auto-admit | Yes (gmeet-host-auto.js) | Yes (/host-teams-meeting-auto) | Built, untested (reCAPTCHA) |
| TTS testing | Yes | Yes | Blocked (reCAPTCHA + SFU limits) |
| Testing cost | Cheap (TTS replay) | Cheap (TTS replay) | Medium (raw-capture enables offline, but live collection still expensive) |

## Collection Run Evidence

### zoom-3sp-basic (first run, pre-fix)
- 29 confirmed segments, 13 named, 15 unnamed
- 43 duplicates from dual pipeline
- Speakers found: Alice, Bob, Charlie (via DOM polling)
- Speaker transition bleed: Bob gets start of Charlie utterance
- Hallucinations: Alice gets "We use it.", Charlie gets "I will"

### zoom-3sp-fixed (post dual-pipeline fix)
- 11 confirmed segments (clean, no duplicates)
- Speakers found: Bob, Charlie only
- Alice MISSING -- never got an audio track (SFU 3-stream limit)
- Zero empty speakers (DOM fallback fix working)
- Zero duplicates (WhisperLive disabled)

### zoom-3sp-rawcap (raw capture validation)
- 12 speaker transitions tracked in events.txt
- Correct speaker change detection via DOM polling
- Some segments misattributed to "Vexa Recorder"
- Demonstrates that DOM-based attribution works -- but needs to be wired into pipeline instead of track locking
