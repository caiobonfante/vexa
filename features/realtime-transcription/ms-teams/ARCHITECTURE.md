# Teams Speaker Attribution — Architecture

## System Overview

```
═══════════════════════════════════════════════════════════════
                    TEAMS MEETING SERVER
═══════════════════════════════════════════════════════════════

  Karl speaks    Francesco speaks    Alberto speaks
      │                │                  │
      ▼                ▼                  ▼
  ┌─────────────────────────────────────────┐
  │     Single Mixed Audio Stream           │
  │     (RTCPeerConnection)                 │
  └──────────────────┬──────────────────────┘
                     │
                     │ ~0ms (real-time)
                     ▼
  ┌─────────────────────────────────────────┐
  │     Teams ASR (server-side)             │
  │     Generates live captions             │
  └──────┬──────────────────────┬───────────┘
         │                      │
         │ ~0ms                 │ ~1s delay
         ▼                      ▼

═══════════════════════════════════════════════════════════════
                    BOT BROWSER
═══════════════════════════════════════════════════════════════

  AUDIO PATH                        CAPTION PATH
  (real-time)                       (~1s delayed)

  <audio> element                   [data-tid="author"]
  MediaStream                       [data-tid="closed-caption-text"]
       │                                  │
       ▼                                  ▼
  AudioContext(16kHz)               processCaptions()
  ScriptProcessor(4096)             polled every 200ms
       │                                  │
       │ chunk every ~256ms               │ on text change:
       ▼                                  ▼
  ┌──────────┐                     ┌─────────────────┐
  │ Silence  │                     │ Update:          │
  │ gate     │                     │ lastCaptionSpeaker│
  │ >0.005   │                     │ lastCaptionTimestamp│
  └────┬─────┘                     └─────────────────┘
       │                                  │
       ▼                                  │
  ┌──────────────────┐                    │
  │ DELAY QUEUE      │                    │
  │                  │                    │
  │ Holds chunks     │                    │
  │ for 1 second     │                    │
  │                  │                    │
  │ [T+0.0] ▒▒▒▒    │                    │
  │ [T+0.3] ▒▒▒▒    │                    │
  │ [T+0.5] ▒▒▒▒    │                    │
  │ [T+0.8] ▒▒▒▒    │                    │
  └────┬─────────────┘                    │
       │                                  │
       │ flush when age >= 1s             │
       ▼                                  │
  ┌───────────────────────────────────────┐
  │          STALENESS CHECK              │
  │                                       │
  │ captionAge = now - lastCaptionTimestamp│
  │                                       │
  │ < 1500ms → ROUTE to speaker ──────►  Node.js
  │ ≥ 1500ms → DROP (speaker stopped)    │
  └───────────────────────────────────────┘

═══════════════════════════════════════════════════════════════
                    NODE.JS
═══════════════════════════════════════════════════════════════

  handleTeamsAudioData(speakerName, audioData)
       │
       ▼
  SpeakerManager → SpeakerStream → TranscriptionClient
       │                                │
       │                          POST to Whisper
       │                                │
       │                          Quality Gate:
       │                          • no_speech_prob > 0.5 → drop
       │                          • avg_logprob < -0.8  → drop
       │                          • compression > 2.4   → drop
       │                                │
       ▼                                ▼
  SegmentPublisher → Redis → Dashboard
```

## Why the 1-Second Delay

Two streams arrive at different times for the same speech event:

```
Source event:  Karl says "hello" at real time T=10s

Audio path:   chunk arrives at T=10s    (real-time)
Caption path: "Karl: hello" at T≈11s    (~1s ASR delay)

Without delay:
  T=10s: audio arrives, lastCaptionSpeaker=previous speaker → WRONG

With 1s delay:
  T=10s: audio arrives, pushed to queue
  T=11s: caption fires, lastCaptionSpeaker=Karl
  T=11s: queue flushes T=10 chunk, routes to Karl → CORRECT
```

## Speaker Transition

```
Time:     10s    11s    12s    13s    14s    15s
          ┊      ┊      ┊      ┊      ┊      ┊
Karl:     ██████████████─┤      ┊      ┊      ┊
                         ┊ gap  ┊      ┊      ┊
Francesco:               ┊      ├──████████████████
                         ┊      ┊      ┊      ┊
Audio:    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
          routed→Karl    drop   routed→Francesco
                         ┊      ┊
Captions: Karl:...───────┘      └───Francesco:...
          updating                  updating
                    ┊           ┊
                    ┊ stale     ┊ fresh
                    ┊ >1500ms   ┊ <1500ms
                    ▼           ▼
                   DROP        ROUTE
```

The gap between speakers: caption stops updating → `captionAge` grows past 1500ms → audio dropped. When new speaker's caption fires → `captionAge` resets to 0 → audio routes to new speaker.

## Staleness Check Detail

```
captionAge = flush_time - lastCaptionTimestamp

During active speech:
  Caption updates every ~200ms
  captionAge at flush time ≈ 1000ms + 200ms = 1200ms
  1200 < 1500 → ROUTE ✅

After speaker stops (1s silence):
  No caption updates
  captionAge at flush time ≈ 1000ms + 1000ms = 2000ms
  2000 > 1500 → DROP ✅

After speaker stops (0.3s silence — tight transition):
  captionAge at flush time ≈ 1000ms + 300ms = 1300ms
  1300 < 1500 → ROUTE (to old speaker) ⚠️ minor bleed

The 1500ms threshold = AUDIO_DELAY (1000ms) + tolerance (500ms)
Active speech: ~1200ms (under threshold) ✅
Stopped >0.5s ago: >1500ms (over threshold, dropped) ✅
Tight transition <0.5s: <1500ms (slight bleed) ⚠️ acceptable
```

## Caption DOM Structure

Teams renders **different DOM** for host vs guest:

```
HOST VIEW:                          GUEST (BOT) VIEW:
wrapper                             wrapper
 └─ window-wrapper                   └─ window-wrapper
     └─ virtual-list-content             └─ virtual-list-content
         └─ items-renderer                   └─ (div)
             └─ ChatMessageCompact               ├─ author ★
                 ├─ author ★                     └─ text ★
                 └─ text ★

★ = stable atoms: [data-tid="author"] + [data-tid="closed-caption-text"]
    Found directly in wrapper, paired by index.
    items-renderer is HOST ONLY — do not use.
```

## Caption Enablement

Also differs by role:

```
HOST:   More (#callingButtons-showMoreBtn)
         └─ Language and speech (menuitem)
              └─ Show live captions (menuitemcheckbox)

GUEST:  More (#callingButtons-showMoreBtn)
         └─ Captions (menuitem, direct toggle)

Bot handles both paths in captions.ts.
```

## Quality Gate

Whisper returns per-segment confidence signals. Short noisy audio → wrong language → garbage text. Filtered before publishing:

```
Signal              Threshold    Meaning
─────────────────────────────────────────────
no_speech_prob      > 0.5        Not speech (noise/silence)
avg_logprob         < -0.8       Low confidence (garbage)
compression_ratio   > 2.4        Repetitive (hallucination)
language_probability < 0.3       Wrong language detection
```

## Known Limitations

1. **Overlapping speech**: single mixed stream, both voices route to whoever caption identifies
2. **~1s transcription delay**: audio delayed for correct attribution
3. **Tight transitions (<0.5s gap)**: minor bleed of 2-4 words from previous speaker
4. **Caption latency variance**: if Teams ASR takes >1s, some opening words route to previous speaker
5. **TTS bot audio**: Teams captions TTS speech but with slightly different timing than human speech
