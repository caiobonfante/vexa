# /expand — Design new scenarios for post-meeting transcription

You are in **Stage 3: EXPAND** for the post-meeting-transcription feature.

Read the generic stage protocol first: `/.claude/commands/expand.md`

## Feature-specific scenarios to consider

Post-meeting transcription has different failure modes than realtime:

### Recording quality scenarios
- **Long meeting** (30+ min) — does Whisper handle large files? Memory issues?
- **Multiple sessions** — bot disconnects and reconnects, multiple recording fragments
- **Silence gaps** — long pauses → Whisper hallucination (repetition loops)
- **Background noise** — office, music, typing

### Speaker mapping scenarios
- **Rapid speaker changes** (<2s between speakers) — speaker event boundaries too close
- **Simultaneous speech** — two speakers talking at once, events overlap
- **Many speakers** (5+) — overlap algorithm O(segments * ranges) accuracy
- **Speaker with very short utterances** — "Yes", "OK" — tiny segments hard to map
- **Late joiner** — speaker joins mid-meeting, no events for early part

### Platform-specific scenarios
- **Teams caption delay** — speaker events may have 1-2s lag from actual speech
- **Google Meet per-speaker audio** — different event format?
- **Speaker name changes** — participant renames during meeting

### Dashboard playback scenarios
- **Multi-fragment recording** — multiple recording sessions in one meeting
- **Long recording** — seek accuracy at minute 30 vs minute 1
- **Missing recording** — meeting has transcription but no recording file

## After expanding

Save manifest to `features/post-meeting-transcription/tests/collection-manifest-{date}.md`

Then immediately:
1. `/host-teams-meeting-auto` to create fresh meeting
2. `/collect` with new manifest
3. `/iterate` with new dataset
