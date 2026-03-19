# MS Teams Realtime Transcription

## Why

Teams is the second most important platform. Its audio architecture is fundamentally different from Google Meet: ONE mixed audio stream containing all participants, with speaker identity determined from DOM signals. This makes speaker attribution harder and overlapping speech lossy.

## What

### Single Mixed Audio Stream

Teams provides a single `<audio>` element whose `srcObject` is a MediaStream from an RTCPeerConnection. This stream contains ALL participants' audio mixed together. There are no per-speaker audio elements.

```
All participants -> single RTCPeerConnection -> single <audio> element -> one mixed MediaStream
```

The bot hooks this single stream with one AudioContext + ScriptProcessor, then routes audio chunks to speaker buffers based on who the DOM says is currently speaking.

### Audio Routing Architecture

**File:** `services/vexa-bot/core/src/platforms/msteams/recording.ts`

Teams audio routing uses two speaker detection signals with automatic fallback:

```
Single <audio> element
  -> AudioContext({ sampleRate: 16000 })
  -> ScriptProcessor(4096, 1, 1)
  -> silence check (maxVal > 0.005)
  -> CAPTION MODE (primary, when live captions enabled):
       -> write to ring buffer (5s, ~20 chunks)
       -> caption MutationObserver detects new [data-tid="author"] + [data-tid="closed-caption-text"]
       -> on speaker change: flush ring buffer lookback to new speaker
       -> ongoing audio routes to current caption speaker
       -> __vexaTeamsAudioData(name, Array.from(data))
  -> FALLBACK MODE (when captions unavailable):
       -> lookup speakingStates map (populated by DOM MutationObserver)
       -> for each active speaker NAME:
            __vexaTeamsAudioData(name, Array.from(data))
```

Key difference from Google Meet: audio is routed by speaker **NAME** (string), not by element **index** (number). The callback signature is `__vexaTeamsAudioData(name: string, data: number[])`.

**Consequence:** If 2 speakers are active simultaneously, the same audio chunk is sent to BOTH speaker buffers. There is no way to separate overlapping speech from a mixed stream.

### Speaker Detection

**File:** `services/vexa-bot/core/src/platforms/msteams/recording.ts`

Teams speaker detection uses two signals with automatic fallback:

#### Primary Signal: Live Captions (caption-driven)

**File:** `recording.ts` (caption observer section) + `captions.ts`

When live captions are enabled (bot enables them automatically after joining via More → Captions), the bot uses Teams ASR caption output as the primary speaker signal:

```
[data-tid="closed-caption-renderer-wrapper"]     <- top-level container (MutationObserver + 500ms poll)
  └─ [data-tid="author"]                         <- speaker name (stable atom)
  └─ [data-tid="closed-caption-text"]            <- spoken text (stable atom)
```

**DOM variance (host vs guest):** Teams renders different container structures around the caption atoms:
- **Host:** `wrapper > virtual-list-content > items-renderer > ChatMessageCompact > author + text`
- **Guest (bot):** `wrapper > virtual-list-content > (div) > author + text` (NO items-renderer)

The only stable selectors are `[data-tid="author"]` and `[data-tid="closed-caption-text"]`. The observer finds these directly inside the wrapper and pairs them by index. Do NOT rely on `closed-captions-v2-items-renderer` — it only exists in the host view.

**Caption enablement also differs by role:**
- **Host:** More → Language and speech → Show live captions (`menuitemcheckbox`)
- **Guest (bot):** More → Captions (`menuitem`, direct toggle)

**Why captions are better than DOM blue squares:**
- **No false activations:** Captions only fire when Teams ASR detects **real speech** — not mic noise, breathing, or keyboard typing. Blue squares activate on any mic input, routing garbage audio to wrong speaker buffers and producing hallucinated transcription.
- **100% speaker certainty:** Teams ASR knows exactly who is speaking from the server side. No guessing, no voting.
- **Known activation time:** Each caption entry marks the exact moment Teams confirmed speech from a specific speaker — gives us a precise timestamp for when to start routing audio.
- **Caption text as bonus:** Text can be stored for future segment reconciliation with Whisper output.

**Ring buffer lookback:** A 5-second ring buffer stores non-silent audio chunks. When a caption arrives (with inherent ~1s delay), the ring buffer is flushed retroactively to the correct speaker. This solves the "eaten first seconds" problem.

Captions are per-user and always available — the bot enables them for itself regardless of meeting settings.

#### Fallback Signal: `voice-level-stream-outline` (DOM blue squares)

```typescript
// From teamsSpeakingIndicators (selectors.ts:212-214)
'[data-tid="voice-level-stream-outline"]'
```

The `voice-level-stream-outline` element exists inside participant video tiles. The bot checks whether this element (or any of its ancestors) has the `vdi-frame-occlusion` class:

```
vdi-frame-occlusion class PRESENT  -> participant IS speaking
vdi-frame-occlusion class ABSENT   -> participant is NOT speaking
```

**File:** `recording.ts` lines 478-500 (`TeamsSpeakingDetector.detectSpeakingState`)

```typescript
detectSpeakingState(element: HTMLElement): { isSpeaking: boolean; hasSignal: boolean } {
  const voiceOutline = element.querySelector('[data-tid="voice-level-stream-outline"]');
  if (!voiceOutline) return { isSpeaking: false, hasSignal: false };

  // Walk up parent chain checking for vdi-frame-occlusion
  let current = voiceOutline;
  while (current) {
    if (current.classList.contains('vdi-frame-occlusion')) {
      return { isSpeaking: true, hasSignal: true };
    }
    current = current.parentElement;
  }
  return { isSpeaking: false, hasSignal: true };
}
```

#### State Machine

**File:** `recording.ts` lines 423-460 (`SpeakerStateMachine`)

```
MIN_STATE_CHANGE_MS = 200ms (debounce)

States: 'speaking' | 'silent' | 'unknown'
Transitions only occur after 200ms to prevent flickering.
If signal disappears (hasSignal=false), state becomes 'unknown'.
```

#### MutationObserver

The bot observes each participant tile for class attribute changes:

```typescript
observer.observe(voiceOutline, {
  attributes: true,
  attributeFilter: ['class'],
  subtree: true
});
```

On mutation, the `TeamsSpeakingDetector.detectSpeakingState()` is called, the state machine is updated, and `speakingStates` map is refreshed.

#### Participant Discovery

Participant tiles found via `teamsParticipantSelectors`:
- `[data-tid*="participant"]`
- `[data-tid*="video-tile"]` / `[data-tid*="videoTile"]`
- `[data-tid*="roster"]` / `[data-tid*="roster-item"]`

A participant is only observed if it has the `voice-level-stream-outline` signal element. No signal = no observation (no fallback detection).

### Audio Routing by Speaker Name

**File:** `recording.ts`

When the ScriptProcessor fires with non-silent audio:

**Caption mode (primary):**
1. Store audio chunk in ring buffer (5s window)
2. If `lastCaptionSpeaker` is set, route current audio to them
3. On caption speaker change, flush unflushed ring buffer entries to new speaker (lookback)

**Fallback mode (DOM blue squares):**
1. Check `speakingStates` map for all entries where `state === 'speaking'`
2. Get name from `ParticipantRegistry` (cached DOM name extraction)
3. Filter out bot's own name
4. For each active speaker name: `__vexaTeamsAudioData(name, audioArray)`

**Node-side handlers** (`index.ts`):

```typescript
// Audio handler (both modes)
async function handleTeamsAudioData(speakerName: string, audioDataArray: number[]): Promise<void> {
  const speakerId = `teams-${speakerName.replace(/\s+/g, '_')}`;
  // Name is already known from DOM/caption -- no voting/locking needed
  if (!speakerManager.hasSpeaker(speakerId)) {
    speakerManager.addSpeaker(speakerId, speakerName);
    segmentPublisher.publishSpeakerEvent({ speaker: speakerName, type: 'joined', timestamp: Date.now() });
  }
  // VAD check, then feed audio to buffer
}

// Caption handler (stores caption text for reconciliation)
async function handleTeamsCaptionData(speakerName: string, captionText: string, timestampMs: number): Promise<void> {
  // Publish speaker event, log caption text for future fuzzy matching
}
```

No voting/locking for Teams -- the speaker name comes directly from DOM/caption detection, so the name is known immediately.

### Name Extraction

**File:** `recording.ts` lines 368-410 (`ParticipantRegistry.extractName`)

Priority order:
1. `[data-tid*="display-name"]`, `[data-tid*="participant-name"]` descendants
2. `.participant-name`, `.display-name`, `.user-name`, `.roster-item-name` descendants
3. `span[title]` descendants
4. `.ms-Persona-primaryText` descendants
5. `aria-label` containing "name" pattern
6. Fallback: `Teams Participant ({data-acc-element-id})`

Forbidden substrings filtered: `more_vert`, `mic_off`, `mic`, `videocam`, `camera`, `share`, `chat`, `participant`, `user`.

### Key Selectors (from `selectors.ts`)

| Selector | Purpose | Constant |
|----------|---------|----------|
| `[data-tid="voice-level-stream-outline"]` | Fallback speaking signal (DOM blue squares) | `teamsSpeakingIndicators`, `teamsVoiceLevelSelectors` |
| `.vdi-frame-occlusion` | Speaking = present, silent = absent | `teamsOcclusionSelectors` |
| `[data-tid="closed-caption-renderer-wrapper"]` | Caption container (primary speaker signal) | `teamsCaptionSelectors.rendererWrapper` |
| `[data-tid="closed-captions-v2-items-renderer"]` | Individual caption entries | `teamsCaptionSelectors.captionItem` |
| `[data-tid="author"]` | Speaker name in caption | `teamsCaptionSelectors.authorName` |
| `[data-tid="closed-caption-text"]` | Spoken text in caption | `teamsCaptionSelectors.captionText` |
| `button[id="hangup-button"]` | Primary leave/hangup button | `teamsPrimaryHangupButtonSelector` |
| `button[data-tid="hangup-main-btn"]` | Alternative hangup button | `teamsPrimaryLeaveButtonSelectors` |
| `div[class*="___2u340f0"]` | Name div class pattern | `teamsNameSelectors` |
| `[data-tid*="video-tile"]` | Participant video tile | `teamsParticipantSelectors` |
| `[role="menuitem"]` with `img` descendant | Roster participant (for counting) | inline in `collectAriaParticipants()` |

Full selector lists: `services/vexa-bot/core/src/platforms/msteams/selectors.ts`

### Critical Differences from Google Meet

| Aspect | Google Meet | MS Teams |
|--------|-----------|----------|
| Audio streams | Per-element (N streams for N participants) | Single mixed stream |
| Audio callback | `__vexaPerSpeakerAudioData(index, data)` | `__vexaTeamsAudioData(name, data)` |
| Speaker identity | Voting/locking (3 votes, 70% ratio) | Direct from DOM (name known immediately) |
| Overlapping speech | Handled naturally (separate streams) | Audio duplicated to all active speakers |
| Speaking detection | Class mutations (`Oaajhc`/`gjg47c`) + indicators | `voice-level-stream-outline` + `vdi-frame-occlusion` |
| Browser | Chromium | MS Edge (required, fallback to Chromium) |
| Media warm-up | Not needed | Required before pre-join |

### Testing

Testing uses **real live Teams meetings** created on-demand via browser sessions. No mock meetings needed — real platform behavior, real audio, real speaker detection, real captions.

### Out of scope
- Org-only meetings (authenticated users only) — bot joins as anonymous guest, gets rejected
- Teams Live Events / Webinars — different URL format, untested

## How

### File Map

| File | Purpose |
|------|---------|
| `services/vexa-bot/core/src/platforms/msteams/recording.ts` | Browser-side: caption observer, ring buffer, speaker detection, audio routing, participant counting |
| `services/vexa-bot/core/src/platforms/msteams/captions.ts` | Enable live captions after bot joins (More → Language and speech → Show live captions) |
| `services/vexa-bot/core/src/platforms/msteams/selectors.ts` | All Teams DOM selectors including caption selectors |
| `services/vexa-bot/core/src/index.ts` | `handleTeamsAudioData()` + `handleTeamsCaptionData()` -- Node-side handlers |
| `services/vexa-bot/core/src/platforms/shared/meetingFlow.ts` | Triggers `enableTeamsLiveCaptions()` after admission |
| `services/vexa-bot/core/src/services/segment-publisher.ts` | TranscriptionSegment with `source`, `caption_text`, `speaker_source` fields |
| `services/vexa-bot/core/src/services/speaker-identity.ts` | `resolveTeamsSpeakerName()` -- DOM traversal + voting/locking (used for fallback) |
