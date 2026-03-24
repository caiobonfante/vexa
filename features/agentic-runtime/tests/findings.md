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
