# Google Meet: Caption-based speaker identity

## Problem

DOM-based speaker voting fails when:
- Human and TTS bot share the same audio track (Google Meet reassigns tracks dynamically)
- Multiple speakers active simultaneously (voting can't disambiguate)
- Track 2 locked to "Dmitriy Grankin" (human), then Bob's audio arrived on same track

Result: 26 segments attributed to wrong speaker in a 3-person meeting.

## Solution: Use Google Meet captions as primary speaker source

Same approach as Teams. Google Meet has live captions with speaker name in the UI.

### How Teams does it (reference)

```
platforms/msteams/recording.ts:
  - Enable captions button click
  - MutationObserver on [data-tid="closed-caption-text"]
  - Read [data-tid="author"] for speaker name
  - Caption text + speaker name → speaker boundary events
```

### What Google Meet needs

1. **Enable captions** — click the CC button or use keyboard shortcut
2. **Observe caption DOM** — find caption elements with speaker name
3. **Extract speaker name** — from caption author element
4. **Feed to speaker identity** — use caption speaker as primary source, DOM voting as fallback

### Google Meet caption DOM structure (to investigate)

Need to inspect the Google Meet caption UI to find:
- Caption container selector
- Speaker name element within caption
- Caption text element
- How speaker changes are indicated

### Implementation plan

1. Add caption selectors to `googlemeet/selectors.ts`
2. Add `enableGoogleMeetCaptions(page)` function (similar to `enableTeamsLiveCaptions`)
3. Add caption MutationObserver in `googlemeet/recording.ts`
4. Feed caption speaker events into speaker identity (primary source)
5. Keep DOM voting as fallback for pre-caption period

### Voting still needed

Captions have ~1-2s delay from speech. During that window, DOM voting provides
early attribution. Once caption confirms the speaker, it overrides the vote.

Priority: caption speaker > locked vote > unlocked vote > unmapped
