# Agentic Runtime

An agentic runtime with first-class support for meeting attendance and transcription. Users can chain containers and scale them with near-zero idle resources and any amount of resources available on demand.

## Concept

One universal container image, three profiles activated by config:

| Profile | Contents | RAM | Use case |
|---------|----------|-----|----------|
| **browser** | Chromium, Playwright, VNC, SSH, audio | ~1.5GB | Meeting attendance, browser sessions |
| **agent** | Claude Code CLI, workspace, Python/Node | ~200MB | Summarization, automation, chat |
| **worker** | Python/Node, Anthropic SDK, minimal | ~50MB | Webhook delivery, file processing |

Containers are ephemeral but state is persistent (MinIO/Git). Spin-up ~5s, idle cost zero.

## Architecture

```
Clients (stateless protocol bridges)
  Telegram Bot, Web Dashboard, Slack Bot, MCP Server, Scheduler
      |
      | POST /api/chat    POST /api/meetings
      v
Core APIs (the backbone)
  Chat API                     Meeting API
  - ensure container           - meeting CRUD
  - inject prompt              - platform logic
  - stream Claude CLI          - transcription config
  - session resume             - speaker mapping
      |                             |
      +-------------+---------------+
                    v
              Runtime API
              - container CRUD
              - Docker lifecycle
              - port mapping, networking
              - idle timeout, health checks
              - MinIO sync
                    |
                    v
         Ephemeral Containers
  browser-xxx | agent-xxx | worker-xxx
```

## Container layers

Agent and worker containers have two layers: a read-only **system layer** providing native Vexa capabilities, and a user-owned **workspace layer** with persistent project files.

```
┌─────────────────────────────────────────────────┐
│  /workspace/                    (user layer)     │
│    .claude/CLAUDE.md  -- project context          │
│    ...user files...   -- persistent (Git/MinIO)  │
├─────────────────────────────────────────────────┤
│  /system/                       (system layer)   │
│    CLAUDE.md          -- Vexa agent instructions │
│    bin/vexa           -- Vexa CLI                │
│    (read-only, baked into image)                 │
└─────────────────────────────────────────────────┘
```

### System layer (`/system/`)

Read-only, baked into the container image. Gives the agent native Vexa capabilities without the user having to teach it anything.

**`/system/CLAUDE.md`** -- loaded automatically, teaches the agent what it can do:

```markdown
# System: Vexa Agentic Runtime

You are an agent running inside a Vexa container. You have native
access to the Vexa platform via the `vexa` CLI in your PATH.

## Container orchestration
- `vexa container spawn --profile {browser|agent|worker}` -- spawn a sibling
- `vexa container list` -- list running containers
- `vexa container stop {id}` -- stop a container

## Browser control
- `vexa browser connect {id}` -- get CDP URL for Playwright connectOverCDP
- `vexa browser save {id}` -- trigger browser state sync to MinIO

## Meetings
- `vexa meeting join --platform {teams|gmeet} --url {url}` -- join a meeting
- `vexa meeting list` -- list active meetings
- `vexa meeting transcript {id}` -- get current transcript segments

## Scheduling
- `vexa schedule --at {iso8601} {any vexa command}` -- run later
- `vexa schedule --in {duration} {any vexa command}` -- relative delay
- `vexa schedule list` -- show pending jobs

## Workspace
- `vexa workspace save` -- sync workspace to Git/MinIO
- `vexa workspace status` -- show sync state

## Rules
- Always `vexa workspace save` before stopping
- Spawn browsers via `vexa container spawn --profile browser`, don't run Chromium locally
- Connect to browsers via CDP, not by sharing a display
- Meeting transcripts stream via `vexa meeting transcript {id}`
```

**`/system/bin/vexa`** -- thin CLI wrapping curl calls to Runtime/Chat/Meeting APIs inside the Docker network. The agent uses it via the Bash tool naturally. Example implementation:

```bash
#!/bin/bash
# vexa CLI -- thin wrapper over Vexa APIs
RUNTIME_API="${VEXA_RUNTIME_API:-http://runtime-api:8090}"
MEETING_API="${VEXA_MEETING_API:-http://meeting-api:8080}"

case "$1" in
  container)
    case "$2" in
      spawn)  curl -s -X POST "$RUNTIME_API/containers" -H 'Content-Type: application/json' -d "{\"profile\":\"$4\"}" ;;
      list)   curl -s "$RUNTIME_API/containers" ;;
      stop)   curl -s -X DELETE "$RUNTIME_API/containers/$3" ;;
    esac ;;
  browser)
    case "$2" in
      connect) curl -s "$RUNTIME_API/containers/$3/cdp" ;;
      save)    curl -s -X POST "$RUNTIME_API/containers/$3/save" ;;
    esac ;;
  meeting)
    case "$2" in
      join) curl -s -X POST "$MEETING_API/meetings" -H 'Content-Type: application/json' -d "{\"platform\":\"$4\",\"url\":\"$6\"}" ;;
      list) curl -s "$MEETING_API/meetings?active=true" ;;
      transcript) curl -s "$MEETING_API/meetings/$3/transcript" ;;
    esac ;;
  workspace)
    case "$2" in
      save)   curl -s -X POST "$RUNTIME_API/workspace/save" ;;
      status) curl -s "$RUNTIME_API/workspace/status" ;;
    esac ;;
  schedule)
    # Forward to scheduler API
    shift; curl -s -X POST "$RUNTIME_API/schedule" -H 'Content-Type: application/json' -d "{\"args\":\"$*\"}" ;;
  *) echo "Usage: vexa {container|browser|meeting|workspace|schedule} ..." ;;
esac
```

### User workspace layer (`/workspace/`)

User-owned, persistent via Git (preferred) or MinIO. This is where project files, custom CLAUDE.md, and domain knowledge live. Synced on container start and on `vexa workspace save`.

The user's `/workspace/.claude/CLAUDE.md` layers on top of the system CLAUDE.md -- Claude Code merges instructions from both. The user can customize agent behavior without touching the system layer.

```
/workspace/
  .claude/CLAUDE.md    -- "you are working on project X, use these conventions"
  knowledge/           -- domain docs, reference material
  scripts/             -- user automation scripts
  notes.md             -- agent scratchpad
```

## Key design decisions

### Specialist containers, not fat stacks

The agent doesn't need to BE in the browser -- it connects via CDP over the network. `auto-admit.js` already proves this pattern. A post-meeting summary doesn't need Chromium (1.5GB RAM).

### System layer gives agents native Vexa fluency

Agents don't discover Vexa via curl or documentation. The system CLAUDE.md and `vexa` CLI are built into the image. An agent can `vexa container spawn --profile browser` and `vexa browser connect {id}` as naturally as it reads files. User workspaces layer project context on top.

### Chat API is the backbone

Borrowed from Quorum: message in, agent response out, container lifecycle, session management. Telegram/Slack/Web are thin clients that translate their protocol into Chat API calls.

### Scheduler as orchestrator

Not just "fire HTTP at time T." Spawns, chains, and reclaims containers:

```
T-5min: spawn browser container (meeting mode)
T+0:   meeting starts, transcription streams
T+end: sync state, reclaim browser container
T+5min: spawn worker container (summarize, deliver)
T+6min: reclaim worker container
```

### Container chaining via callbacks

No special pipeline DSL. Scheduler's existing `on_success`/`on_failure` callbacks trigger the next job:

```
meeting-bot on_meeting_end -> scheduler -> post-processing agent
post-processing on_success -> scheduler -> webhook delivery worker
```

## Container config

```json
{
  "profile": "agent",
  "config": {
    "system_layer": true,
    "workspace": {
      "git_repo": "https://github.com/user/project.git",
      "git_branch": "main",
      "git_token": "ghp_..."
    }
  },
  "resources": { "memory": "512m", "cpus": 1 },
  "idle_timeout": 60,
  "network": "vexa_agentic"
}
```

Browser container config:

```json
{
  "profile": "browser",
  "config": {
    "vnc": true,
    "cdp": true,
    "persistent_context": true,
    "meeting": { "platform": "teams", "join_url": "..." }
  },
  "resources": { "memory": "2g", "cpus": 1, "shm": "2g" },
  "storage": { "s3_path": "users/5/browser-data" },
  "idle_timeout": 300,
  "network": "vexa_agentic"
}
```

## Claude CLI strategy

Start with Claude Code subscription (free for development). Explore open-source models via API with Claude Code CLI later. For production worker tasks, direct Anthropic SDK is cheaper.

| Approach | Cost | Best for |
|----------|------|----------|
| Claude Code subscription | Flat monthly | Development, iteration, complex agent tasks |
| Open-source models via API | Varies (often cheaper) | Commodity tasks, high volume |
| Anthropic Python SDK | ~$3/$15 per M tokens (Sonnet) | Production worker tasks: summarize, extract |
| Claude CLI with API key | Same + CLI overhead | Production agent tasks: tool use, multi-step |

## Edges

**Depends on:**
- Redis (scheduler sorted sets, pubsub, session state)
- PostgreSQL (meetings, users, transcripts)
- MinIO (browser profiles, workspaces, recordings)
- Transcription service (shared, external -- not owned by this feature)

**Provides to:**
- All features that need scheduled execution
- All features that need agent capabilities
- All features that need container orchestration

**Replaces / subsumes:**
- bot-manager container orchestration -> Runtime API
- scheduler HTTP executor -> Runtime API container spawn
- quorum ContainerManager + ChatManager -> Chat API + Runtime API

---

## MVP Plan

### MVP0: Chat in a Container

**Goal:** Prove the core loop -- send a message to an API, it spawns a container with Claude Code CLI, streams back the response, and the session persists across requests. Agent has system layer with `vexa` CLI.

**What we build:**
- Agent container Dockerfile (Claude Code CLI + system layer + workspace sync)
- System layer: `/system/CLAUDE.md` + `/system/bin/vexa` CLI
- Chat API (FastAPI): `POST /api/chat` with SSE streaming
- Container manager: ensure/create/exec/idle-stop
- Workspace persistence: Git or MinIO sync on start/stop (reuse browser-session.ts pattern)
- Session resume: Claude CLI `--resume` with session file

**What we DON'T build:**
- No browser containers, no meetings, no CDP
- No scheduler, no chaining
- No Telegram/Slack -- just raw HTTP
- `vexa` CLI stubs for container/browser/meeting commands (return "not available in MVP0")

**Validation:**

| Test | Command | Pass | Fail |
|------|---------|------|------|
| V0.1 Basic chat | `curl -N POST /api/chat -d '{"message":"hello"}'` | SSE stream with Claude response | No response or error |
| V0.2 Tool use | Ask agent to create a file in workspace | File exists in container at `/workspace/` | File not created |
| V0.3 Session resume | Send 2nd message referencing 1st | Agent remembers context | Fresh session, no memory |
| V0.4 Workspace persist | Stop container, restart, check file | File still there (restored from MinIO) | File lost |
| V0.5 Idle timeout | Wait >idle_timeout seconds | Container stopped automatically | Container leaks |
| V0.6 Concurrent users | Two different user_ids chat simultaneously | Each gets own container, isolated workspaces | Crosstalk or failure |
| V0.7 Container restart | Kill container mid-session, send new message | New container created, workspace restored | Error or stuck |
| V0.8 System layer | Ask agent "what vexa commands do you have?" | Agent describes vexa CLI from system CLAUDE.md | Agent doesn't know about vexa |
| V0.9 Workspace save | Chat: "save your workspace" | Agent runs `vexa workspace save`, sync completes | Save fails or command unknown |

**Deliverables:**
- `containers/agent/Dockerfile` -- Claude Code CLI image with system layer
- `containers/agent/system/CLAUDE.md` -- system instructions
- `containers/agent/system/bin/vexa` -- CLI wrapper
- `services/chat-api/` -- FastAPI service
- `features/agentic-runtime/tests/test-mvp0.sh` -- validation script
- All 9 tests passing

---

### MVP1: Browser + Agent Cross-Container

**Goal:** Prove specialist containers can collaborate -- an agent container controls a browser container via CDP over the Docker network, using the `vexa` CLI natively.

**Depends on:** MVP0 passing

**What we build:**
- Browser container Dockerfile (Chromium + VNC + CDP, from existing vexa-bot browser_session mode)
- Runtime API: `POST/GET/DELETE /runtime/containers` -- generic container CRUD
- Agent-to-browser CDP connection via `vexa browser connect {id}`
- System layer upgraded: `vexa container spawn` and `vexa browser connect` now functional
- Browser state persistence: MinIO sync for Chromium profiles

**What we DON'T build:**
- No meeting attendance yet (just raw browser control)
- No scheduler, no chaining

**Validation:**

| Test | Command | Pass | Fail |
|------|---------|------|------|
| V1.1 Browser spawn | `POST /runtime/containers {"profile":"browser"}` | Container running, VNC accessible on returned port | Container fails to start |
| V1.2 CDP reachable | `curl http://localhost:{cdp_port}/json/version` | Returns Chrome version JSON | Connection refused |
| V1.3 VNC reachable | Open `http://localhost:{vnc_port}/vnc.html` | See browser desktop | No display |
| V1.4 Agent spawns browser | Chat: "spawn a browser container" | Agent runs `vexa container spawn --profile browser`, gets ID | Command fails |
| V1.5 Agent connects CDP | Chat: "open https://example.com in the browser" | Agent uses `vexa browser connect`, then Playwright CDP | CDP connection fails |
| V1.6 Agent reads page | Chat: "what's the title of the page in the browser?" | Agent returns "Example Domain" | Wrong answer or error |
| V1.7 Agent fills form | Chat: "go to a form site and fill in name=Test" | Visible in VNC: form filled | No interaction |
| V1.8 Container cleanup | `DELETE /runtime/containers/{id}` | Container stopped and removed | Container leaks |
| V1.9 Isolation | Spawn 2 browser containers | Each has own Chromium, own ports, no collision | Port conflict or shared state |
| V1.10 Browser state persist | `vexa browser save {id}`, stop, respawn | Cookies/localStorage restored | State lost |

**Deliverables:**
- `services/runtime-api/` -- FastAPI service (container CRUD)
- `containers/browser/Dockerfile` -- Chromium + VNC + CDP image (extracted from vexa-bot)
- System layer: `vexa container` and `vexa browser` commands now live
- `features/agentic-runtime/tests/test-mvp1.sh` -- validation script
- All 10 tests passing

---

### MVP2: Scheduled Meeting Pipeline

**Goal:** End-to-end automated meeting attendance. Scheduler spawns browser container before meeting, agent joins and transcribes, post-meeting worker summarizes and delivers. Full chain, zero human intervention. Agent orchestrates everything via `vexa` CLI.

**Depends on:** MVP1 passing

**What we build:**
- Scheduler wired to Runtime API (container spawn as job type)
- Meeting profile: browser container that joins Teams/GMeet
- Post-meeting worker: spawned by callback, summarizes transcript
- Container chaining: `on_meeting_end` -> scheduler -> worker container
- System layer fully live: all `vexa` commands functional including `vexa schedule` and `vexa meeting`
- Telegram bot: thin client on Chat API (first real interface)

**What we DON'T build:**
- No calendar integration (manual schedule via API)
- No dashboard UI changes
- No multi-tenant (single user is fine)

**Validation:**

| Test | Command | Pass | Fail |
|------|---------|------|------|
| V2.1 Schedule meeting | `POST /api/schedule {"fire_at":"T-2min", "action":"join_meeting", ...}` | Job created in Redis sorted set | Job not stored |
| V2.2 Container auto-spawn | Wait for fire_at | Browser container starts within 10s of scheduled time | Late or no container |
| V2.3 Meeting join | Browser container joins Teams meeting URL | Bot visible in meeting participants | Join fails |
| V2.4 Transcription | Speak in meeting | Transcript segments stream via existing pipeline | No segments |
| V2.5 Meeting end chain | End meeting | `on_meeting_end` fires, scheduler creates worker job | No callback or no job |
| V2.6 Worker spawn | Worker job fires | Worker container starts, receives transcript context | Worker doesn't start |
| V2.7 Summary output | Worker processes transcript | Summary written to workspace and/or sent via webhook | No output |
| V2.8 Full cleanup | Wait for idle timeout after pipeline completes | All containers (browser + worker) reclaimed, zero running | Containers leak |
| V2.9 Browser state persist | Use authenticated browser session, stop, reschedule | Next meeting join reuses saved cookies (no re-auth) | Auth state lost |
| V2.10 Telegram chat | Send "join my meeting {url}" via Telegram | Bot schedules join, reports back when meeting ends with summary | No response |
| V2.11 Failure recovery | Kill browser container mid-meeting | Scheduler detects failure, fires `on_failure` callback | Silent failure |
| V2.12 Pipeline timing | Schedule meeting for T+5min, full pipeline | Total overhead: <30s (spawn) + <10s (post-processing) | Pipeline takes >2min |
| V2.13 Agent self-orchestrates | Chat: "join my standup at 9am tomorrow and send me notes" | Agent uses `vexa schedule` + `vexa meeting join`, pipeline runs autonomously | Agent can't compose commands |

**Deliverables:**
- Scheduler wired to Runtime API
- Meeting join logic in browser container
- Worker container with Anthropic SDK for summarization
- Container chaining via scheduler callbacks
- System layer: all `vexa` commands live
- Telegram bot (thin client)
- `features/agentic-runtime/tests/test-mvp2.sh` -- validation script
- All 13 tests passing

---

## Success criteria

| Milestone | Gate | Evidence |
|-----------|------|----------|
| MVP0 done | 9/9 tests pass | Chat works, sessions persist, containers auto-reclaim, agent knows vexa CLI |
| MVP1 done | 10/10 tests pass | Agent spawns and controls browser cross-container via vexa CLI + CDP |
| MVP2 done | 13/13 tests pass | Full scheduled meeting pipeline, agent self-orchestrates, zero idle, Telegram |

## Current status: MVP3+ (Hardening)

MVP0-MVP2 built, MVP3 wired meeting pipeline + dashboard. Currently hardening auth, env config, and meeting lifecycle.

### Verified agent capabilities

**Meeting control** (via `vexa` CLI inside agent container):

| Capability | Command | Status |
|-----------|---------|--------|
| Join meeting | `vexa meeting join --platform teams --url {url}` | Works |
| Fetch live transcript | `vexa meeting transcript {id}` | Works (Redis+Postgres merge) |
| Bot speaks (TTS) | `vexa meeting speak --text "Hello"` | Works (async, Redis pub/sub) |
| Bot sends chat | `vexa meeting chat --text "Notes coming"` | Works |
| Bot shares screen | `vexa meeting screen --type url --url {url}` | Works |
| Stop bot | `vexa meeting stop --platform {p} --id {id}` | Works |
| Check events | `vexa meeting events --platform {p} --id {id}` | Works |

**Container orchestration:**

| Capability | Command | Status |
|-----------|---------|--------|
| Spawn browser | `vexa container spawn --profile browser` | Works (needs `BOT_API_TOKEN`) |
| Connect via CDP | `vexa browser connect {name}` | Works |
| Spawn sibling agent | `vexa container spawn --profile agent` | Works (needs `BOT_API_TOKEN`) |
| Schedule future work | `vexa schedule --at {time} chat "message"` | Works |
| Workspace persistence | `vexa workspace save` | Works (MinIO sync) |

**Scheduler** (Redis sorted sets, crash-safe):

| Capability | Command | Status |
|-----------|---------|--------|
| Schedule at time | `vexa schedule --at "2026-03-25T09:00:00Z" chat "reminder"` | Works |
| Schedule relative | `vexa schedule --in 5m chat "check status"` | Works |
| Schedule recurring | `vexa schedule --every 3d chat "audit workspace"` | Works |
| Job callbacks | `on_success` / `on_failure` URLs in job spec | Works |
| Cancel job | `vexa schedule cancel {job_id}` | Works |

### Meeting lifecycle (end-to-end flow)

```
User: "Join my meeting"
  → Agent: vexa meeting join --platform teams --url {url}
    → Bot-manager spawns bot container → joins meeting → transcribes
      → Segments: bot → Redis stream → TC → Postgres + Redis hash
      → Live WS: bot PUBLISH tc:meeting:{id}:mutable → api-gateway → dashboard
    → Meeting ends: bot exit callback → status=completed
      → post_meeting_hooks.py fires (if POST_MEETING_HOOKS configured)
      → aggregate_transcription.py extracts participants/languages
      → send_webhook.py delivers to user's webhook URL
    → Container auto-removed (AutoRemove=True)
```

### What's wired but not configured

| Gap | What's needed | Impact |
|-----|---------------|--------|
| `BOT_API_TOKEN` empty | Create service token, set in deploy/.env | Agent can't spawn containers or call Runtime API |
| `POST_MEETING_HOOKS` empty | Set to `http://chat-api:8100/api/webhooks/meeting-completed` | No auto-trigger of agent after meeting ends |
| Webhook receiver endpoint | ~20 lines in chat-api: receive meeting.completed → POST /api/chat | Agent doesn't auto-wake on meeting end |

### What's not built yet

| Feature | Effort | Description |
|---------|--------|-------------|
| Server-side chat history | Small | Store messages in Redis alongside session ID |
| Global 401 interceptor | Small | Dashboard redirects to login on any auth failure |
| Live meeting polling loop | None (prompt pattern) | Agent schedules `vexa schedule --in 30s chat "check transcript"` in a loop |
| Agent-to-agent delegation | Medium | Shared workspace protocol, inter-agent messaging via scheduler |
| Idle timeout callbacks | Medium | Notify downstream when container stops |

## Setup

### Prerequisites (external)

- **Transcription service** (Whisper) running on host — not in this compose stack
- **Claude Code CLI** credentials on host (`~/.claude/.credentials.json`, `~/.claude.json`)
- Docker with compose v2

### Quick start

```bash
# 1. Configure environment
cp features/agentic-runtime/deploy/.env.example features/agentic-runtime/deploy/.env
# Edit .env: set CLAUDE_CREDENTIALS_PATH, CLAUDE_JSON_PATH, TRANSCRIPTION_SERVICE_URL

# 2. Build container images (agent + bot)
docker build -t vexa-agent:dev -f containers/agent/Dockerfile .
docker build -t vexa-bot:dev -f services/vexa-bot/Dockerfile services/vexa-bot/

# 3. Start the stack
cd features/agentic-runtime/deploy
docker compose up -d

# 4. Run DB migrations
docker compose run --rm db-migrate

# 5. Start dashboard (outside compose)
cd services/dashboard
cp .env.example .env  # Edit: verify VEXA_ADMIN_API_URL=http://localhost:8067
npm install && npm run dev
# Open http://localhost:3002
```

### Required environment variables

| Variable | Where | Example | Purpose |
|----------|-------|---------|---------|
| `CLAUDE_CREDENTIALS_PATH` | deploy/.env | `/home/user/.claude/.credentials.json` | Claude CLI auth for agent containers |
| `CLAUDE_JSON_PATH` | deploy/.env | `/home/user/.claude.json` | Claude CLI config for agent containers |
| `TRANSCRIPTION_SERVICE_URL` | deploy/.env | `http://172.17.0.1:8083` | Whisper service (external) |
| `VEXA_ADMIN_API_URL` | dashboard/.env | `http://localhost:8067` | Admin API (NOT api-gateway) |
| `VEXA_API_URL` | dashboard/.env | `http://localhost:8066` | API gateway |
| `AGENT_API_URL` | dashboard/.env | `http://localhost:8100` | Chat API for agent sessions |

### Port map

| Service | Container port | Host port |
|---------|---------------|-----------|
| API Gateway | 8000 | 8066 |
| Admin API | 8001 | 8067 |
| Bot Manager | 8080 | 8070 |
| Runtime API | 8090 | 8090 |
| Chat API | 8100 | 8100 |
| Transcription Collector | 8000 | 8060 |
| PostgreSQL | 5432 | 5458 |
| Redis | 6379 | 6389 |
| MinIO | 9000/9001 | 9010/9011 |
| Dashboard | 3000 | 3002 |
