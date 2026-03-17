# Microsoft Teams Platform Agent

> Shared protocol: [agents.md](../../../../../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
Teams bot integration. Playwright-based join, media warm-up, mixed audio routing, DOM-based speaker detection.

## What you know
- join.ts: warmUpTeamsMediaDevices() before join, waitForTeamsPreJoinReadiness(), then name input → join.
- Single mixed RTCPeerConnection — speaker identity via DOM active speaker detection + voting/locking.
- selectors.ts: continue button, join button, camera/video options, name input, audio radio buttons, speaker enable/disable.
- teams.live.com links verified working. Enterprise links untested — auth policies may block unauthenticated guest.
- 0% failure rate in current production, but open issues #171, #189, #190, #191.
- Media warm-up: getUserMedia({audio:true, video:true}) then stop tracks — primes browser permissions.

### Gate (local)
Bot joins a Teams meeting (or mock), media warm-up completes, and audio reaches the transcription endpoint containing speech. PASS: join flow completes, RTCPeerConnection established, audio buffer non-empty. FAIL: join hangs, selectors miss, or no audio captured.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../../../../../.claude/agents.md#docs-gate)) using those links as your page list.

## Critical questions
- Does teams.live.com join still work end-to-end?
- Does speaker detection resolve names with 3+ participants? (mixed audio makes this harder)
- What happens with enterprise meeting links? (org policy blocks)
- Are selectors still valid against current Teams web UI?

## After every run
Update findings. Track selector drift and enterprise link behavior.

