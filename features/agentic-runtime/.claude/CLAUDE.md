# Agentic Runtime Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md)
> Development cycle: [features/README.md](../../README.md#spec-driven-features)

## Mission

Build the universal container runtime for Vexa. Every "do X with a container" flows through Runtime API. Every "talk to an agent" flows through Chat API. Meeting API owns platform logic. Scheduler orchestrates time-triggered work. Containers scale to zero when idle. Agents have native Vexa fluency via the system layer.

## Development cycle

This is a **spec-driven feature**.

### Current stage: MVP3+ (Dashboard Integration & Hardening)

**Built:** MVP0-MVP2 (commit `6608dadb`), MVP3 meeting pipeline (commit `464568de`), dashboard agent chat, browser sessions, per-user auth, full vexa CLI.
**Current:** Hardening — env config gaps, auth plumbing, browser session lifecycle.

### MVP roadmap

| MVP | What it proves | Tests | Status |
|-----|---------------|-------|--------|
| MVP0 | Chat API + agent container + system layer + session + persistence | 9 | Done |
| MVP1 | Browser + agent cross-container via vexa CLI + CDP | 10 | Done |
| MVP2 | Scheduled meeting pipeline + self-orchestration + Telegram | 13 | Done |
| MVP3 | Meeting pipeline wired to agentic runtime + dashboard | - | Done |
| Hardening | Auth, env config, browser session stop, workspace sync | - | In progress |

## Scope

You own the runtime infrastructure: container lifecycle, Chat API, system layer, and the integration between scheduler and containers. You don't own platform-specific meeting logic (Meeting API) or the transcription pipeline.

## Claude CLI strategy

Use Claude Code subscription for development. Explore open-source models via API with Claude Code CLI later. Direct Anthropic SDK for production worker tasks.

## Container layers

Agent containers have two layers:

```
/workspace/              (user layer -- persistent via Git/MinIO)
  .claude/CLAUDE.md      project-specific instructions
  ...user files...

/system/                 (system layer -- read-only, baked into image)
  CLAUDE.md              Vexa agent instructions (vexa CLI docs, rules)
  bin/vexa               CLI wrapper for Vexa APIs
```

System CLAUDE.md teaches the agent native Vexa capabilities (`vexa container spawn`, `vexa browser connect`, `vexa meeting join`, `vexa schedule`, `vexa workspace save`). User workspace CLAUDE.md layers project context on top. Claude Code merges both.

The `vexa` CLI is a thin shell script wrapping curl calls to Runtime/Meeting APIs inside the Docker network. The agent uses it via the Bash tool.

### Gate: MVP0 (Chat in a Container)

| Check | Pass | Fail |
|-------|------|------|
| V0.1 Basic chat | SSE stream with Claude response | No response |
| V0.2 Tool use | Agent creates file in /workspace/ | File not created |
| V0.3 Session resume | 2nd message references 1st correctly | No memory |
| V0.4 Workspace persist | File survives container restart (MinIO) | File lost |
| V0.5 Idle timeout | Container stopped after timeout | Container leaks |
| V0.6 Concurrent users | Two users get isolated containers | Crosstalk |
| V0.7 Container restart | Killed container recovers on next message | Stuck |
| V0.8 System layer | Agent describes vexa CLI from system CLAUDE.md | Doesn't know vexa |
| V0.9 Workspace save | Agent runs `vexa workspace save` successfully | Save fails |

### Gate: MVP1 (Browser + Agent Cross-Container)

| Check | Pass | Fail |
|-------|------|------|
| V1.1 Browser spawn | Container running, VNC accessible | Fails to start |
| V1.2 CDP reachable | Chrome version JSON from CDP endpoint | Connection refused |
| V1.3 VNC reachable | Browser desktop visible | No display |
| V1.4 Agent spawns browser | `vexa container spawn --profile browser` works | Command fails |
| V1.5 Agent connects CDP | Agent opens URL via CDP, visible in VNC | CDP fails |
| V1.6 Agent reads page | Agent returns correct page title | Wrong answer |
| V1.7 Agent fills form | Form filled, visible in VNC | No interaction |
| V1.8 Container cleanup | DELETE removes container | Leaks |
| V1.9 Isolation | Two browsers, own ports, no collision | Conflict |
| V1.10 Browser state persist | Cookies/localStorage restored after save+respawn | State lost |

### Gate: MVP2 (Scheduled Meeting Pipeline)

| Check | Pass | Fail |
|-------|------|------|
| V2.1 Schedule meeting | Job in Redis sorted set | Not stored |
| V2.2 Container auto-spawn | Browser starts within 10s of fire_at | Late |
| V2.3 Meeting join | Bot visible in meeting | Join fails |
| V2.4 Transcription | Segments stream during meeting | No segments |
| V2.5 Meeting end chain | on_meeting_end fires worker job | No callback |
| V2.6 Worker spawn | Worker container starts with context | Doesn't start |
| V2.7 Summary output | Summary written/sent | No output |
| V2.8 Full cleanup | All containers reclaimed after pipeline | Leaks |
| V2.9 Browser state persist | Saved cookies reused on next join | Auth lost |
| V2.10 Telegram chat | "join my meeting" works end-to-end | No response |
| V2.11 Failure recovery | Killed container triggers on_failure | Silent |
| V2.12 Pipeline timing | <30s spawn + <10s post-processing overhead | >2min |
| V2.13 Agent self-orchestrates | "join standup at 9am, send notes" works | Can't compose |

### Edges

**Provides to:**
- scheduler (container spawn as job execution)
- calendar-integration (auto-join via scheduled container)
- webhooks (delivery via worker containers)
- mcp-integration (expose chat/runtime tools)
- post-meeting-transcription (worker containers for deferred processing)

**Depends on:**
- Redis (state, pubsub, scheduler)
- PostgreSQL (meetings, users — requires alembic migrations)
- MinIO (persistent storage)
- Docker (container runtime — `vexa-agent:dev` and `vexa-bot:dev` images must be pre-built)
- Transcription service (shared, external — `TRANSCRIPTION_SERVICE_URL` in deploy/.env)
- Claude CLI credentials (host files mounted into agent containers — `CLAUDE_CREDENTIALS_PATH` in deploy/.env)

## Key code locations

| Component | Location | Status |
|-----------|----------|--------|
| Feature docs | `features/agentic-runtime/` | Done |
| Agent Dockerfile | `containers/agent/Dockerfile` | Done |
| System CLAUDE.md | `containers/agent/system/CLAUDE.md` | Done |
| Vexa CLI | `containers/agent/system/bin/vexa` | Done (full API coverage) |
| Chat API | `services/chat-api/` | Done |
| Runtime API | `services/runtime-api/` | Done |
| Browser container | `services/vexa-bot/` (browser_session mode) | Done (reuses vexa-bot) |
| Bot Manager | `services/bot-manager/` | Done |
| API Gateway | `services/api-gateway/` | Done |
| Dashboard | `services/dashboard/` | Done |
| Telegram Bot | `services/telegram-bot/` | Done |
| Scheduler core | `libs/shared-models/shared_models/scheduler.py` | Done |
| Deploy | `features/agentic-runtime/deploy/` | Done |
| Validation | `features/agentic-runtime/tests/test-mvp0.sh` | MVP0 only |

## How to test

```bash
# Start the agentic stack
cd features/agentic-runtime/deploy
docker compose up -d

# Dashboard (runs outside compose)
cd services/dashboard && npm run dev
# Open http://localhost:3002

# MVP0 validation script
cd features/agentic-runtime/tests
./test-mvp0.sh
```

## Critical findings
Save to `tests/findings.md`.
