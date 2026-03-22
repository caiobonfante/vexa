# Multi-Speaker Pipeline Validation Results

## Setup

- **Source:** YC Light Cone podcast (Emergent founders), first 3 minutes
- **URL:** https://www.youtube.com/watch?v=8SVocWnDHwE
- **Speakers:** 3 (Host, Mukund, Madhav)
- **GT segments:** 16 (from offline Whisper + AI speaker assignment)
- **Platform:** Google Meet
- **Bots:** 3 speaker bots + 1 recorder bot
- **Meeting:** muc-yuco-tgz
- **Date:** 2026-03-22

## Results

| Metric | Score |
|--------|-------|
| Captured | 16/16 (100%) |
| Speaker correct | 13/16 (81%) |
| Content coverage | 191/219 words (87%) |
| Pipeline segments | 32 confirmed |

## Speaker Attribution Errors

| GT# | GT Speaker | Got | Text | Cause |
|-----|-----------|-----|------|-------|
| 6 | Host | Mukund | "Dunzo was a big company actually right?" | Audio content swapped between channels (see analysis) |
| 9 | Host | Mukund | "what year was this" | Absorbed into Mukund's streaming buffer (see analysis) |
| 14 | Madhav | (correct) | "Longville had not started." -> "No, let not solve it." | Speaker correct, text garbled by Whisper on 0.8s audio |

### Detailed error analysis

Google Meet provides physically separate audio streams per participant via WebRTC. Each bot's audio element has its own `MediaStream`. The recorder bot creates an independent `AudioContext` + `ScriptProcessor` per element. Audio from one speaker **cannot** leak to another speaker's channel at the browser level.

**Error GT#6 — "Dunzo was a big company actually right?"**

The Host bot played `06-103.6-108.5.wav` on its own channel. The Mukund bot was silent (gap 103.6-108.5s). Yet the pipeline shows this text on Mukund's track (`speaker-0:10`), merged seamlessly with Mukund's preceding sentence: "...which was a hyper-local quick commerce company. Dunzo was a big company, actually, right?"

Meanwhile, the Host track (`speaker-1:8`) at the same pipeline time shows "it was really big...almost a verb in india" — which is Mukund's GT#7 content.

The content is **swapped** between channels at this boundary. Track assignments are stable throughout (`speaker-0` = Mukund for all 20 segments, `speaker-1` = Host for all 11 segments). No track swap or re-locking occurred.

Root cause needs investigation — possible explanations:
1. The `document.querySelectorAll('audio, video')` element ordering at setup time does not correspond to the participant ordering assumed by the voting/locking system
2. Google Meet reassigned which `MediaStream` feeds which DOM audio element without changing the element itself (stream swap without element swap)
3. The Whisper prompt conditioning (previous confirmed text) caused context leakage — Mukund's buffer ended with "...called Dunzo, which was" and Whisper continued the sentence from whatever audio arrived next

**Error GT#9 — "what year was this"**

The Host bot played `09-128.8-130.0.wav` (1.2s). The pipeline captured it on **both** channels:
- Mukund `speaker-0:12` (225.2-237.2): absorbed into "...That was the first idea. What year was this? This was 23 end..."
- Host `speaker-1:9` (232.1-249.0): "what year was this" — correct speaker but inflated to 17s duration for 4 words

Same channel swap pattern as GT#6. The Host audio arrived on Mukund's channel and got merged into his continuous transcription stream.

**Error GT#14 — Madhav: "Longville had not started."**

Speaker attribution is **correct** (`speaker-2` = Madhav). The error is transcription accuracy only: 0.8s of audio produced "No, let not solve it." instead of "Longville had not started." The 16s segment duration (281.5-297.7) for 0.8s of speech indicates massive silence padding in the buffer, causing Whisper to hallucinate.

### Additional finding: Host channel contains Mukund's words

Host `speaker-1:8` (207.0-215.0): "it was it was really big uh and and we we are almost a verb in india so when people should think they say" — this is Mukund's GT#7 response about Dunzo being a verb. This appeared on the Host channel at the same time Mukund's channel shows Host's words. Confirms the swap is bidirectional.

## Content Gaps

- "light cone" -> "my code" (proper noun misheard by streaming Whisper)
- "Thank you." hallucination at 138.8-142.7s on Mukund's channel (silence between speakers)
- Proper nouns varied throughout

## Verdict

- **Pipeline:** Content capture works — all 16 GT segments have matching pipeline output
- **Speaker attribution:** 81% — 2 errors from a channel content swap between Host and Mukund around GT offset 103-130s; 1 error is text-only (speaker correct)
- **Rendering:** Not validated (tick capture started too late, only 15 ticks from tail end)

## Next steps

1. Investigate the channel swap: add logging to trace which `MediaStream.id` feeds each element index, and whether streams get reassigned mid-meeting
2. Start WS tick capture BEFORE playback begins (was started late, missed first ~85 ticks)
3. Test with longer Host utterances around the swap boundary to confirm it's not just short-utterance specific
4. For Madhav's 0.8s segment: consider minimum audio length threshold before submitting to Whisper
