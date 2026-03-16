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

## Diagnostic protocol
1. **Read last findings** (`tests/findings.md`) — what failed before? Start there.
2. **Fail fast** — test the riskiest thing first. If a dependency is down, everything above it fails. Check dependencies before dependents.
3. **Isolate** — when something fails, drill into WHY. Is it the service? The dependency? The network? The config? Don't report "bot can't join" — report "bot can't join because name input selector changed because Google updated Meet DOM."
4. **Parallelize** — run independent checks concurrently. Don't wait for join flow before checking selector validity.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

Dependencies to check first: DOM selectors (Google changes these without notice), then admission flow, then WebRTC media elements. If join fails, check selectors.ts against live DOM before anything else.

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
