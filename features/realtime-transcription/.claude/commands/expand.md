# /expand — Design new scenarios for realtime transcription

You are in **Stage 3: EXPAND** for the realtime-transcription feature.

Read the generic stage protocol first: `/.claude/commands/expand.md`

## Feature-specific context

### Known weaknesses to target

Based on findings from previous collection runs:

| Weakness | Current data | What's missing |
|----------|-------------|----------------|
| Short phrase loss (sub-1s utterances) | 5 lost in diverse scenario | Dedicated scenario with 10+ short phrases, varying gaps |
| Caption boundary delay (~1.5s) | Observed but few rapid transitions | Scenario with many <1s speaker changes |
| Overlap handling | One 2s overlap in session 2 | Scenario with sustained overlaps, multiple speakers |
| 5+ speaker meetings | Max 3 speakers tested | Large meeting scenario |
| Google Meet behavior | No GMeet collected data | Full GMeet collection run needed |
| Multilingual | Tested informally (Russian) | Formal multilingual scenario with scoring |
| Long silence gaps | 15s gap in diverse test | Scenario with 30s+ gaps, intermittent speech |

### Script design guidelines for this feature

**Speakers:** Use TTS bots (Alice, Bob, Charlie, etc.) via the speaking-bot feature. Each bot gets a unique voice (alloy, echo, fable, onyx, nova, shimmer).

**Timing:** Account for:
- TTS generation time (~1-2s per utterance)
- Network delay to meeting (~0.5s)
- Caption delay from platform (~1.5-2.5s for Teams)
- Pipeline processing time (~3-6s for confirmation)

**Scenarios to always include as controls:**
- Normal turns (>2s gaps) — should be ~100% accuracy
- Medium paragraph (single speaker, ~14s) — should be ~92%+ content accuracy

**Platform-specific considerations:**
- **Teams:** Caption events are the speaker signal. Script must trigger caption author changes. Single-word utterances may not generate caption events at all.
- **GMeet:** Per-speaker audio channels. No caption dependency. But speaker identity relies on DOM voting — need enough speech per speaker to lock.

### Previous scripts for reference

| Script | File | Speakers | Scenarios |
|--------|------|----------|-----------|
| Normal conversation | `test_data/test-conversation.sh` | 3 (Alice, Bob, Charlie) | Normal turns, rapid exchange |
| Diverse test | `tests/diverse-test-ground-truth.txt` | 3 | 7 rounds: monologue, back-to-back, short phrases, silence, overlap |
| Real meeting replay | `test_data/replay-meeting.js` | 6 (from the consortium transcript) | Natural conversation, many speakers |

### Manifest output location

Save to: `features/realtime-transcription/tests/collection-manifest-{YYYY-MM-DD}.md`

### After expand

The manifest tells you what `.env` config is needed. If it differs from current:
1. `/env-setup` to align infra
2. `/collect` to run the collection

If infra is already correct:
1. `/collect` directly
