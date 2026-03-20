# Google Meet Realtime Transcription

## Why

Google Meet provides the cleanest audio pipeline of any supported platform. Each participant gets a separate `<audio>` element with its own MediaStream — true **multi-channel audio**. No diarization needed, no mixed audio, no cross-talk. This is the equivalent of multichannel transcription, the industry gold standard for accuracy.

## What

### Architecture: N Independent Pipelines

```
Participant A ──→ <audio> A ──→ AudioContext A ──→ ScriptProcessor A ──→ SpeakerStreamManager A ──→ Whisper ──→ segments A
Participant B ──→ <audio> B ──→ AudioContext B ──→ ScriptProcessor B ──→ SpeakerStreamManager B ──→ Whisper ──→ segments B
Participant C ──→ <audio> C ──→ AudioContext C ──→ ScriptProcessor C ──→ SpeakerStreamManager C ──→ Whisper ──→ segments C
```

Each participant has its own:
- Audio element with isolated MediaStream
- AudioContext at 16kHz
- ScriptProcessor (4096 buffer)
- SpeakerStreamManager instance (offset-based sliding window)
- Independent Whisper submissions

The callback `__vexaPerSpeakerAudioData(index, data)` routes by element index. Each index maps to one SpeakerStreamManager identified as `speaker-{index}`.

### Audio Capture

**File:** `services/vexa-bot/core/src/index.ts` (`startPerSpeakerAudioCapture`)

1. `page.evaluate()` discovers active media elements: `<audio>` and `<video>` filtered by `!el.paused && srcObject.getAudioTracks().length > 0`
2. Retries up to 10 times (20s total)
3. Per element: `new AudioContext({ sampleRate: 16000 })` → `createScriptProcessor(4096, 1, 1)`
4. Silence filter: `maxVal > 0.005` before sending
5. References stored on `window.__vexaAudioStreams` to prevent GC

### Speaker Identity: Voting/Locking

**The problem:** Google Meet doesn't expose which audio element belongs to which participant.

**The solution:** Correlate "which track has audio" with "which DOM tile shows speaking."

**Files:**
- `speaker-identity.ts` — voting/locking logic
- `googlemeet/recording.ts` — browser-side speaking detection

**Flow:**
1. Audio arrives on track N → `handlePerSpeakerAudioData(N, data)`
2. Query browser: `__vexaGetAllParticipantNames()` → `{ names: {id: name}, speaking: [name] }`
3. If exactly 1 speaker active: `recordTrackVote(N, speakerName)`
4. After `LOCK_THRESHOLD=3` votes with `LOCK_RATIO=0.7`: mapping locks permanently
5. Constraints: one-name-per-track, one-track-per-name

**Speaking detection (browser-side):**
- MutationObserver on class changes within `[data-participant-id]` containers
- Watches for speaking classes: `Oaajhc`, `HX2H7`, `wEsLMd`, `OgVli`
- Silence class: `gjg47c`
- 500ms polling fallback for cases where mutations don't fire

### Buffer Management

Uses the same offset-based sliding window as Teams (see [parent README](../README.md)):

- Each speaker gets independent `SpeakerStreamManager` instance
- `submitBuffer` sends only unprocessed audio
- Completed Whisper segments advance the offset
- VAD (Silero, when available) filters silence before buffer — reduces Whisper calls
- Speaker leaving/muting triggers idle timeout → clean buffer flush

### GC Prevention

**Critical:** Web Audio API `ScriptProcessor` nodes are garbage collected if no JavaScript reference holds them. All references stored on `window.__vexaAudioStreams`:

```typescript
(window as any).__vexaAudioStreams.push({ ctx, source, processor });
```

Without this, audio capture silently stops within seconds.

### Differences from MS Teams

| Aspect | Google Meet | MS Teams |
|--------|-----------|----------|
| Audio | N per-speaker streams | 1 mixed stream |
| SpeakerStreamManager | N instances (one per channel) | 1 instance (mixed) |
| Speaker identity | DOM voting/locking (inferred) | Caption author (explicit) |
| Diarization | Not needed | Caption boundaries |
| Overlapping speech | Natural separation | Both in same stream |
| VAD | Silero per stream (when available) | Browser-side RMS filter |
| Silence filter | `maxVal > 0.005` per element | `RMS < 0.01` on mixed stream |

### Key Selectors

| Selector | Purpose |
|----------|---------|
| `[data-participant-id]` | Participant tile |
| `span.notranslate` | Participant name |
| `.Oaajhc` | Speaking animation class |
| `.gjg47c` | Silence class |
| `button[aria-label="Leave call"]` | Leave button |
| `[jsname="BOHaEe"]` | Meeting container |

These are obfuscated Google Meet class names. They change with UI updates — `selectors.ts` must be updated.

### Known Limitations

1. **Obfuscated class names** — Google Meet uses compiled class names that change with deployments
2. **First seconds** — speaker identity requires 3 votes to lock; first audio may be unnamed
3. **Domain-restricted meetings** — bot joins as unauthenticated guest, may be rejected by org policy
4. **Multiple speakers simultaneously** — voting only works when exactly 1 speaker is active; during overlap, no votes cast, existing locks used

## How

### File Map

| File | Purpose |
|------|---------|
| `index.ts` (`startPerSpeakerAudioCapture`) | Browser-side AudioContext/ScriptProcessor per element |
| `index.ts` (`handlePerSpeakerAudioData`) | Node-side: speaker resolution, VAD, buffer feed |
| `speaker-identity.ts` | Track→speaker voting/locking, browser state queries |
| `speaker-streams.ts` | SpeakerStreamManager — offset-based sliding window (shared) |
| `googlemeet/recording.ts` | Browser-side speaker detection, MutationObserver, participant counting |
| `googlemeet/selectors.ts` | All Google Meet DOM selectors |

### Testing

Real live Google Meet meetings. No mocks — real platform behavior, real audio, real speaker detection. Test with 2+ participants speaking and verify speaker attribution locks correctly within first few seconds.
