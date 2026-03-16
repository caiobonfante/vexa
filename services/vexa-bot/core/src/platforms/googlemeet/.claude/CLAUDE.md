# Google Meet Platform Agent

## Scope
Google Meet bot integration. Playwright-based join flow, admission waiting, per-speaker audio capture, speaker identity via DOM correlation.

## What you know
- join.ts: goto → name input → "Ask to join" → waiting room → admitted. 5s settle wait after navigation.
- admission.ts: polls for admission, handles org-restricted blocks (unauthenticated guest).
- selectors.ts: DOM selectors for name input, join button, mic/camera toggles. Brittle — Google changes these.
- Per-speaker WebRTC tracks: each participant = separate audio stream via `<audio>`/`<video>` media elements.
- Speaker identity: voting/locking system (speaker-identity.ts) — DOM speaking indicators correlated with audio tracks, LOCK_THRESHOLD=3, LOCK_RATIO=0.7.
- ~7.8% join failure rate ("No active media elements found").

## Critical questions
- Does the bot get past admission? (not just reach waiting room)
- Are per-speaker tracks discovered? (check media element count vs participant count)
- Do selectors still match current Google Meet DOM?
- Does speaker identity lock correctly with 3+ participants?

## After every run
Update findings inline. Note selector breakages and join failure patterns.

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
