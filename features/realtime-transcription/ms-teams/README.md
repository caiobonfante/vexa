# MS Teams Realtime Transcription

## Why

Teams is the second most important platform. Its audio architecture is fundamentally different from Google Meet: ONE mixed audio stream containing all participants, with speaker identity determined from live captions. This makes speaker attribution harder and overlapping speech lossy.

## What

### Single Mixed Audio Stream

Teams provides a single `<audio>` element whose `srcObject` is a MediaStream from an RTCPeerConnection. This stream contains ALL participants' audio mixed together. There are no per-speaker audio elements.

```
All participants -> single RTCPeerConnection -> single <audio> element -> one mixed MediaStream
```

### Audio Routing Architecture

**File:** `services/vexa-bot/core/src/platforms/msteams/recording.ts`

```
Single <audio> element
  -> AudioContext({ sampleRate: 16000 })
  -> ScriptProcessor(4096, 1, 1)
  -> silence check (maxVal > 0.005)
  -> 1-second delay queue (wait for caption to identify speaker)
  -> flush delayed chunks using speaker timeline lookup
  -> __vexaTeamsAudioData(name, Array.from(data))
```

Key difference from Google Meet: audio is routed by speaker **NAME** (string), not by element **index** (number). The callback signature is `__vexaTeamsAudioData(name: string, data: number[])`.

### Audio Delay Queue

**The core mechanism.** Two independent data streams arrive:
1. **Audio** — real-time, no speaker info
2. **Captions** — speaker name + text, ~1s delayed

By delaying audio by 1s before routing, the caption stream has time to identify the speaker. Each delayed chunk is attributed using a **speaker timeline** — a log of `{timestamp, speaker}` events from captions.

```
Audio arrives at T=0  →  push to queue
Caption fires at T=1  →  records speaker in timeline (backdated to T=0)
Queue flushes at T=1  →  looks up speakerAtTime(T=0) → correct speaker
```

**Speaker timeline backdate:** Caption events are backdated by ~1s (the caption delay) so that the timeline entry aligns with when the speaker actually started. Exception: after a silence gap (>3s since last caption), no backdate — prevents misattributing silence to the previous speaker.

**Consequence:** If 2 speakers are active simultaneously, the same audio chunk routes to whoever the caption says is speaking. Overlapping speech is a known limitation of the single mixed stream.

### Speaker Detection — Live Captions (Primary)

**File:** `recording.ts` (caption observer) + `captions.ts` (enablement)

When live captions are enabled, the bot uses Teams ASR caption output as the speaker signal:

```
[data-tid="closed-caption-renderer-wrapper"]     <- top-level container
  └─ [data-tid="author"]                         <- speaker name (stable atom)
  └─ [data-tid="closed-caption-text"]            <- spoken text (stable atom)
```

#### DOM Variance (Host vs Guest)

**CRITICAL:** Teams renders different container structures for host and guest views:

- **Host:** `wrapper > virtual-list-content > items-renderer > ChatMessageCompact > author + text`
- **Guest (bot):** `wrapper > virtual-list-content > (div) > author + text` (NO items-renderer)

The only stable selectors across both views are `[data-tid="author"]` and `[data-tid="closed-caption-text"]`. The observer finds these directly inside the wrapper and pairs by index. **Do NOT use `closed-captions-v2-items-renderer`** — it only exists in the host view.

Verified 2026-03-19 on both host (authenticated account) and guest (anonymous bot) views.

#### Caption Enablement

Also differs by role:
- **Host:** More (`#callingButtons-showMoreBtn`) → Language and speech → Show live captions (`menuitemcheckbox`)
- **Guest (bot):** More (`#callingButtons-showMoreBtn`) → Captions (`menuitem`, direct toggle)

The bot's `captions.ts` handles both paths: tries guest path first (direct "Captions" item), falls back to host path ("Language and speech" submenu). Uses `page.evaluate` for reliable clicking.

#### Caption Observation

- **MutationObserver** on the wrapper (`childList:true, subtree:true, characterData:true`)
- **500ms polling backup** — Teams may use virtual DOM updates that don't trigger mutations
- Deduplication via `speaker + '::' + text` key — Teams updates caption text in-place as ASR refines

### Why Captions, Not DOM Blue Squares

DOM blue squares (`vdi-frame-occlusion` class) have two fatal problems:
1. **~1.3s delay** — first words of each turn get attributed to the previous speaker
2. **False activations** — any mic noise (breathing, typing) triggers them, routing garbage audio

Captions solve both:
- **No false activations:** Captions only fire on real speech (Teams server-side ASR)
- **100% speaker certainty:** Teams knows exactly who is speaking
- **Caption text as bonus:** Can be stored for segment reconciliation with Whisper output

DOM fallback code exists but is **disabled**. Captions are the primary and only active signal.

### Audio Track Behavior

Teams delivers audio tracks with `muted=true` initially — this is normal WebRTC behavior meaning the remote hasn't sent media yet. Tracks become unmuted when someone speaks. The bot accepts tracks that are `enabled` (even if `muted`) to avoid rejecting valid tracks.

### Quality Gate (Low-Confidence Filtering)

Short noisy audio causes Whisper to hallucinate in wrong languages or produce repetitive garbage. The transcription service returns per-segment quality signals that the bot checks before accepting:

1. `no_speech_prob > 0.5 && avg_logprob < -0.7` → discard (noise, not speech)
2. `avg_logprob < -0.8 && duration < 2s` → discard (short garbage)
3. `compression_ratio > 2.4` → discard (repetitive hallucination)
4. `language_probability < 0.3` → discard (wrong language detection)

### Critical Differences from Google Meet

| Aspect | Google Meet | MS Teams |
|--------|-----------|----------|
| Audio streams | Per-element (N streams for N participants) | Single mixed stream |
| Audio callback | `__vexaPerSpeakerAudioData(index, data)` | `__vexaTeamsAudioData(name, data)` |
| Speaker identity | Voting/locking (3 votes, 70% ratio) | Captions (100% certainty) |
| Audio routing | Immediate (per-speaker streams) | 1s delay queue + speaker timeline |
| Overlapping speech | Handled naturally (separate streams) | Both speakers get same mixed audio |
| Speaking detection | Class mutations on elements | Caption text + author from ASR |
| Browser | Chromium | MS Edge (required, fallback to Chromium) |

### Known Limitations

1. **Overlapping speech** — single mixed stream, no source separation. Both speakers get the same audio routed to whoever caption identifies.
2. **~1s transcription delay** — audio is delayed 1s for correct attribution. Adds 1s latency to the already ~2s Whisper processing time.
3. **Short back-to-back utterances** — if the same speaker has two short utterances with another speaker's reply between them, they may merge or bleed slightly.
4. **Caption delay variance** — the 1s delay is approximate. If Teams caption delay varies (0.5s-1.5s), some transitions may have minor bleed.
5. **Silence gap attribution** — after long silence, the first words of a new speaker may briefly route to nobody (delay queue + no active caption speaker).

### Testing

Testing uses **real live Teams meetings** with TTS-speaking bots. The test conversation script (`test_data/test-conversation.sh`) drives 3 speakers through a realistic meeting dialogue. Results verified on the Vexa Dashboard.

**Test results (2026-03-19):** 13/14 segments cleanly attributed in rapid 3-speaker back-and-forth conversation. 15 speaker transitions detected correctly.

## How

### File Map

| File | Purpose |
|------|---------|
| `recording.ts` | Browser-side: delay queue, speaker timeline, caption observer, audio routing |
| `captions.ts` | Enable live captions after bot joins (guest + host paths) |
| `selectors.ts` | All Teams DOM selectors. Caption atoms: `[data-tid="author"]` + `[data-tid="closed-caption-text"]` |
| `index.ts` | `handleTeamsAudioData()` + `handleTeamsCaptionData()` — Node-side handlers + quality gate |
| `meetingFlow.ts` | Triggers `enableTeamsLiveCaptions()` after admission |
| `browser.ts` | Audio element discovery — accepts initially-muted tracks |

### Bugs Fixed (2026-03-19)

| Bug | Root cause | Fix |
|-----|-----------|-----|
| No audio captured | `track.muted` check rejected all Teams tracks | Accept `enabled` tracks regardless of `muted` |
| Captions not enabling | Guest menu has "Captions" directly, not "Language and speech" submenu | Handle both paths |
| Caption observer sees nothing | Guest DOM has no `items-renderer` wrapper | Find `author`/`text` atoms directly in wrapper |
| Cross-speaker bleed | Audio routed to `lastCaptionSpeaker` immediately (caption ~1s delayed) | 1-second delay queue + speaker timeline |
| Previous speaker's tail in new segment | Ring buffer flushed 5s of previous speaker to new speaker | Removed ring buffer flush, use delay queue instead |
| Wrong speaker after silence gap | Timeline backdate pushed new speaker into silence zone | Conditional backdate: no backdate after >3s silence |
| Wrong-language hallucinations | Low-confidence audio → Whisper picks random language | Quality gate using `avg_logprob`, `no_speech_prob`, `compression_ratio` |
