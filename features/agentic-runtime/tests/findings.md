# Findings

## Research phase (2026-03-23)

### Quorum analysis
- **Pattern:** Single persistent Telegram bot, per-user Docker containers with Claude Code CLI injected
- **Agent API:** `POST /api/chat` is the backbone -- message in, agent response streamed out via SSE
- **Container injection:** Prompt written to file, `docker exec` runs Claude CLI with `--allowedTools` scoping
- **Session resume:** Claude CLI `--resume {session_id}`, stored in workspace `.claude/.session`
- **Scheduling:** Asyncio timers from JSON files (no Redis) -- lightweight but not crash-safe
- **Certainty:** 95 (code read directly)

### Vexa remote-browser analysis
- **Pattern:** Chromium persistent context + VNC + CDP + SSH in single container
- **State sync:** MinIO for browser profiles and workspaces, Git as alternative
- **Cross-container CDP:** Agent connects to browser via `chromium.connectOverCDP(url)` -- proven in auto-admit.js
- **Certainty:** 95 (code read directly)

### Architecture decisions
- **Specialist containers > fat stacks:** Agent doesn't need Chromium, worker doesn't need Claude CLI
- **Agent API as backbone:** All interfaces (Telegram, Web, Slack, MCP) are thin clients
- **Runtime API owns Docker:** Only service that touches container lifecycle
- **Scheduler as orchestrator:** Container spawn/chain/reclaim via scheduled jobs with callbacks
- **Certainty:** 80 (design validated against existing code, not yet implemented)

## Meeting API Fluency (2026-03-24)

### MVP0: Meeting State Awareness — PASS

5 new vexa CLI commands added and independently verified:

| Command | Purpose | Status |
|---------|---------|--------|
| `vexa meeting status` | Detailed bot state (status, start_time, elapsed, recording) | Verified |
| `vexa meeting participants` | Unique speakers from transcript | Verified |
| `vexa meeting wait-active` | Poll until bot is active (2s interval, configurable timeout) | Verified |
| `vexa meeting transcribe` | Trigger post-meeting transcription | Verified |
| `vexa meeting list` (enhanced) | Now shows elapsed time | Verified |

System CLAUDE.md updated with "Meeting Awareness" section teaching agent join-and-wait, state checking, and post-meeting patterns.

### MVP1: Event-Driven Triggers — IMPLEMENTED (pending test)

| Component | Change | Status |
|-----------|--------|--------|
| agent-api Redis subscriber | Subscribes to `bm:meeting:*:status`, wakes agent on `active` + `completed` | Implemented |
| Auth bug fix | Added `/internal/webhooks/meeting-completed` (no auth for internal traffic) | Implemented |
| docker-compose | POST_MEETING_HOOKS updated to internal endpoint | Implemented |
| System CLAUDE.md | "Meeting Events" section — agent told it gets push notifications | Implemented |

**Pre-existing bug found:** `post_meeting_hooks.py` delivers to agent-api without X-API-Key, but the endpoint requires it → 403 silently. Fixed by adding internal endpoint.

### Certainty Table

| Check | Score | Evidence | Last checked |
|-------|-------|----------|-------------|
| Agent has meeting CLI commands | 90 | 5 commands verified by independent verifier | 2026-03-24 |
| Agent knows meeting state | 85 | System CLAUDE.md has Meeting Awareness section | 2026-03-24 |
| Agent woken on meeting.completed | 70 | Redis subscriber implemented, auth bug fixed. Not tested live. | 2026-03-24 |
| Agent woken on meeting.started | 70 | Redis subscriber dispatches on "active" status. Not tested live. | 2026-03-24 |
| Agent speaks/chats in meeting | 50 | speak works (regular bots), chat_send added to browser-session. Pending rebuild. | 2026-03-24 |
| Agent manages meeting lifecycle | 30 | join/stop/config commands exist. No auto-scheduling yet. | 2026-03-24 |
| Proactive real-time assistance | 0 | No WS transcript subscription, no LLM-to-voice pipeline | — |

**Overall: 85** (MVP0 PASS, MVP1 implemented pending test)
