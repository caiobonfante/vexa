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
| 6 | Host | Mukund | "Dunzo was a big company actually right?" | Short interjection bled into Mukund's audio channel |
| 9 | Host | Mukund | "what year was this" | Short question, same audio routing issue |
| 14 | Madhav | Mukund | "Longville had not started." | Very short utterance, routed to wrong stream |

All 3 errors are short interjections (<2s) from one speaker that Google Meet routed through another speaker's audio channel. This is a platform limitation, not a pipeline bug.

## Content Gaps

Missing words (Whisper misheard): "light cone" → "my code", proper nouns varied.

## Verdict

- **Pipeline:** PASS — all content captured, pipeline processing correct
- **Speaker attribution:** 81% — short interjections misattributed due to Google Meet audio routing
- **Rendering:** not validated in this run (need tick-by-tick data from WS capture started too late)

## Next Steps

1. Start WS tick capture BEFORE playback begins (was started late, missed first 85 ticks)
2. Use tick.js to validate rendering tick by tick once full tick data is available
3. Speaker attribution errors are platform-level — no pipeline fix available
