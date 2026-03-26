# Architecture Refactoring Plan

## Executive Summary

Unify Vexa's container orchestration into a clean layered architecture. Currently bot-manager mixes meeting domain logic with container orchestration, and runtime-api duplicates Docker management separately. The refactoring extracts Meeting API as a domain service, makes Runtime API the single container orchestration layer, and keeps bot-manager as the low-level execution engine.

**Decision: Build, not buy.** Research across 10 OSS/commercial alternatives (Nomad, Knative, Fly Machines, Temporal, Argo, KEDA, Modal, E2B, K8s Jobs, serverless platforms) confirms that domain-specific requirements (meeting lifecycle callbacks, activity-based idle, CDP tracking, per-user concurrency, platform-specific metadata) kill generic solutions. Recall.ai — the market leader processing 8M EC2 instances/month — built fully custom orchestration, validating this approach. Vexa's runtime-api is ~500 lines and already well-architected.

---

## Current State

### What Exists

```
API Gateway (8000) → proxies to all backends
├── Admin API       → users, tokens, analytics
├── Bot Manager     → TANGLED: meeting domain + container orchestration + recordings
├── Agent API       → chat, scheduling, workspaces → calls Runtime API for containers
├── Runtime API     → container lifecycle, profiles, idle management (Docker only)
├── Transcription Collector → Redis streams → DB
├── Transcription Service   → Whisper API (speech-to-text)
├── TTS Service     → text-to-speech
├── MCP Server      → AI tool integration
├── Calendar Service → Google Calendar sync
├── Telegram Bot    → mobile interface
└── Dashboard       → Next.js web UI
```

### The Problem: Bot Manager is 5 Services in 1

Bot manager (3600+ lines in main.py alone) tangles 5 distinct domains:

| Domain | Endpoints | Should Be |
|--------|-----------|-----------|
| Meeting API | POST/DELETE /bots, GET /status, PUT /config | Separate Meeting API service |
| Voice Agent | /speak, /chat, /screen, /avatar | Part of Meeting API |
| Agent Chat | /bots/{id}/agent/chat (Claude CLI streaming) | Stay in bot-manager or agent-api |
| Orchestration | start/stop containers, callbacks, post-meeting hooks | Runtime API (unified) |
| Recording | /recordings/*, upload handlers, transcription triggers | Part of Meeting API or separate |

### The Duplication: Two Container Managers

| Capability | Runtime API | Bot Manager |
|------------|-------------|-------------|
| Docker create/start/stop | ✅ docker_ops.py | ✅ orchestrator_utils.py |
| K8s support | ❌ | ✅ orchestrators/kubernetes.py |
| Process support | ❌ | ✅ orchestrators/process.py |
| Profile system | ✅ (agent, browser, meeting) | ❌ (hardcoded in start_bot_container) |
| Idle management | ✅ (background loop + touch) | ❌ |
| State reconciliation | ✅ (Redis + Docker sync) | ❌ (Docker API direct) |
| Per-user concurrency | ❌ | ✅ (DB check) |
| Meeting token minting | ❌ | ✅ (HS256 JWT) |
| Lifecycle callbacks | ❌ | ✅ (exit, status, admission) |

**Key finding:** Bot manager does NOT use runtime-api. They're completely parallel Docker management implementations.

---

## Target Architecture

```
                      ┌─────────────┐
                      │   Dashboard  │
                      └──────┬───────┘
                             │
                      ┌──────▼───────┐
                      │ API Gateway  │
                      └──────┬───────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
   ┌──────▼─────┐    ┌──────▼──────┐    ┌──────▼─────┐
   │ Admin API  │    │ Meeting API │    │  Agent API  │
   │(users,     │    │(join, stop, │    │(chat, tts,  │
   │ tokens)    │    │ status, wh) │    │ workspace)  │
   └────────────┘    └──────┬──────┘    └──────┬──────┘
                            │                  │
                            └────────┬─────────┘
                                     │
                            ┌────────▼────────┐
                            │   Runtime API   │
                            │ (container CRUD,│
                            │  profiles,      │
                            │  state, health) │
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │   Bot Manager   │
                            │ (Docker / K8s / │
                            │  process)       │
                            └───┬──────┬───┬──┘
                                │      │   │
                       ┌────────▼┐ ┌───▼─┐ ┌▼────────┐
                       │vexa-bot │ │agent│ │ browser  │
                       │(meeting)│ │(CLI)│ │(Chromium)│
                       └─────────┘ └─────┘ └─────────┘
```

### Design Principles

1. **Domain services don't know about containers** — Meeting API knows meetings, Agent API knows chats. They call Runtime API with a profile and config.
2. **Runtime API is the single container authority** — All container lifecycle (create, stop, list, health, idle) goes through one service with pluggable backends.
3. **Profiles replace hardcoded config** — Move bot-manager's env-var building, platform-specific config, port mapping into profile expansion in Runtime API.
4. **Callbacks flow upward** — When a container exits, Runtime API notifies the domain service that created it via webhook.
5. **The bot is not the resource, the meeting is** — API exposes `POST /meetings` (not `/bots`). The container is an implementation detail.

### What Changes

| Component | Current | Target |
|-----------|---------|--------|
| **Meeting API** | Doesn't exist (tangled in bot-manager) | New service: meeting CRUD, voice agent control, recordings, webhooks |
| **Runtime API** | Agent/browser containers only (Docker) | Unified container orchestration for ALL types (Docker, K8s, process) |
| **Bot Manager** | 3600-line monolith | Thin execution engine: receive container spec → run it → report back |
| **Agent API** | Calls runtime-api for containers | Unchanged (already correct pattern) |
| **containers/agent/** | Top-level dir | Moves to services/vexa-agent/ |

### What Stays the Same

- API Gateway routing
- Admin API
- Transcription pipeline (collector + service)
- TTS Service
- MCP Server
- Calendar Service
- Telegram Bot
- Dashboard
- All container images (vexa-bot, agent, browser)

---

## Migration Strategy: Strangler Fig + Branch by Abstraction

Don't rewrite bot-manager. Extract piece by piece while keeping production running.

### Phase 1: Unify Container Backends in Runtime API
**Goal:** Runtime API gains K8s and process backends from bot-manager.

1. Extract `orchestrators/` interfaces from bot-manager into a shared backend abstraction
2. Add K8s and process backends to runtime-api (port from bot-manager)
3. Enrich profile system to handle meeting-specific config (BOT_CONFIG, meeting tokens, GPU passthrough)
4. Add container exit callbacks (webhook to caller)
5. Add per-user concurrency limits to runtime-api

**Validation:** Runtime API can spawn a meeting bot container with full config via `POST /containers {profile: "meeting", config: {...}}`.

**Risk mitigation:** Feature toggle in bot-manager to switch between direct-Docker and runtime-api calls. Run both paths, compare results.

### Phase 2: Extract Meeting API
**Goal:** New service owns meeting domain logic.

1. Create `services/meeting-api/` with meeting CRUD endpoints
2. Move from bot-manager: `POST /bots` → `POST /meetings`, status management, webhook delivery, voice agent control (/speak, /chat, /screen)
3. Meeting API calls Runtime API for container operations
4. API Gateway routes `/meetings/*` to new service, keeps `/bots/*` to bot-manager (backward compat)

**Validation:** Full meeting lifecycle works through Meeting API → Runtime API → container.

### Phase 3: Slim Down Bot Manager
**Goal:** Bot manager becomes a thin container execution engine.

1. Remove meeting domain logic (now in Meeting API)
2. Remove direct Docker operations (now in Runtime API)
3. Bot manager receives container specs from Runtime API, executes them
4. Handles only: low-level container lifecycle callbacks, post-meeting task execution

**Validation:** Bot manager has no meeting/user/recording knowledge. It only knows containers.

### Phase 4: Clean Up
**Goal:** Remove legacy paths and duplication.

1. Remove `/bots/*` backward-compat routes from API Gateway
2. Remove duplicate Docker code from bot-manager
3. Move `containers/agent/` to `services/vexa-agent/`
4. Update all documentation and deployment configs

---

## API Schema Evolution

### Approach: Expand and Contract

1. **Expand**: Add new `/meetings/*` endpoints alongside existing `/bots/*`
2. **Migrate**: Update Dashboard, Telegram Bot, Calendar Service to use new endpoints
3. **Contract**: Remove `/bots/*` endpoints

### Key Schema Changes

```
# Current (bot-manager)
POST /bots
  body: {meeting_url, bot_name, language, ...}
  response: {meeting_id, platform, status, ...}

# Target (meeting-api)
POST /meetings
  body: {meeting_url, bot_name, language, ...}
  response: {meeting_id, platform, status, ...}

# Internal (runtime-api)
POST /containers
  body: {profile: "meeting", config: {meeting_id, platform, ...}, user_id: "..."}
  response: {name, status, ports, metadata}
```

### Backward Compatibility

- `/bots/*` routes continue working during migration (API Gateway proxies to both)
- New fields added alongside old ones, never removed until Phase 4
- Webhook payloads: additive only (new fields OK, no removals)
- Token scopes unchanged (`vxa_user_*`, `vxa_bot_*`, etc.)

---

## Industry Validation

### Recall.ai (Direct Competitor)
- 8M EC2 instances/month, 3 TB/s raw video
- Fully custom container orchestration (no K8s, no Nomad)
- Single `POST /bots` API abstracts all platforms
- **Validates:** Build > buy for meeting bot orchestration

### Fly Machines API (Closest API Pattern)
- `POST /machines` with config object (image, resources, metadata)
- Explicit lifecycle: `/start`, `/stop`, `DELETE`
- Lease-based concurrency, `/wait` for state polling
- **Inspiration:** Runtime API's profile system mirrors this pattern

### Selenium Grid 4 (Architectural Parallel)
- Router → Distributor → Node = Meeting API → Runtime API → Bot Manager
- Distributor selects node by "desired capabilities" = selecting container profile
- Session Map tracks active sessions = Redis state

### Stripe API Versioning (Schema Migration Pattern)
- Date-based versions, per-request override
- Version change modules transform responses backward
- **For Vexa:** Overkill for internal refactoring. Use expand-and-contract instead.

---

## Build vs Buy Decision

### Why Build (Keep Current Approach)

1. **Domain logic is the hard part** — Meeting lifecycle callbacks, activity-based idle, CDP tracking, per-user concurrency, platform-specific metadata. No external tool handles these. You'd build them on top of whatever you adopt.
2. **Runtime API is already 80% there** — ~500 lines of Python, clean profile system, Redis state, Docker reconciliation. Needs K8s backend and richer profiles, not replacement.
3. **Small codebase, low maintenance** — This isn't a distributed system problem. It's a well-defined container lifecycle manager.
4. **Market leader validates** — Recall.ai built fully custom at massive scale.

### What to Adopt Later (If Complexity Grows)

| Tool | When | Why |
|------|------|-----|
| **Temporal** | Meeting lifecycle becomes complex (retries, compensation, sagas) | Durable workflow above Runtime API |
| **Argo Workflows** | Post-meeting pipeline grows (transcribe → analyze → enrich → webhook) | DAG-based processing chain |
| **K8s Operator (CRD)** | K8s becomes primary production backend | Declarative state, kubectl visibility, native health checks |
| **Pre-warm pool** | Startup latency becomes critical (<5s) | Maintain warm container pool like Fly's pre-provisioning |

---

## Effort Estimation

| Phase | Scope | Complexity |
|-------|-------|------------|
| Phase 1: Unify backends in Runtime API | Port K8s/process backends, enrich profiles, add callbacks | Medium — most code exists, needs integration |
| Phase 2: Extract Meeting API | New service, move endpoints, update gateway | Medium — straightforward extraction |
| Phase 3: Slim bot-manager | Remove migrated code, simplify | Low — deletion is easy |
| Phase 4: Clean up | Remove legacy routes, move dirs, update docs | Low |

**Recommended order:** Phase 1 → 2 → 3 → 4, with feature toggles for safe rollback at each step.

---

## Files Referenced

- `services/bot-manager/app/main.py` — 3600+ lines, 35+ endpoints, 5 tangled domains
- `services/bot-manager/app/orchestrator_utils.py` — Docker/container operations
- `services/bot-manager/app/orchestrators/` — K8s, process, Docker backends
- `services/bot-manager/app/tasks/` — post-meeting hooks, webhooks
- `services/bot-manager/app/agent_chat.py` — Claude CLI streaming
- `services/runtime-api/app/main.py` — container CRUD endpoints
- `services/runtime-api/app/docker_ops.py` — Docker socket operations
- `services/runtime-api/app/profiles.py` — agent, browser, meeting profiles
- `services/runtime-api/app/state.py` — Redis state management
- `services/agent-api/app/container_manager.py` — delegates to runtime-api
- `libs/shared-models/shared_models/models.py` — DB models
- `libs/shared-models/shared_models/schemas.py` — Pydantic schemas
- `libs/shared-models/shared_models/scheduler.py` — Redis sorted set scheduler
