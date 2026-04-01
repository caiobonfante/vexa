# Workspaces — Knowledge That Builds Itself From Meetings

> **Confidence: 75** — Workspace lifecycle (persist/restore/clone) validated end-to-end. 8/8 DoD checks passed, 8/8 security checks passed. Missing: workspace index injection, entity extraction, script execution, multi-workspace API.
> **Tested (2026-04-01):** Template init on first-time user, save→die→restore cycle (3 cycles), git clone init (public repos), per-user env vars injected into container, /internal/chat with INTERNAL_API_SECRET, /api/schedule bridge to scheduler, SSRF protection, path traversal blocked.
> **Not tested:** Workspace index injection per chat turn, entity extraction from meeting transcripts, script execution via worker containers, multi-workspace API, git clone with private repos (token auth).
> **Contributions welcome:** Workspace index injection (scan filesystem → inject into prompt), additional templates (project, meeting-notes), script execution in worker containers.

## Why

Otter gives you a transcript. Fireflies gives you a summary. Neither remembers who [[Brian Steele]] is, that he's the VP of Engineering at [[Acme Corp]], that you discussed pricing in last Tuesday's call, or that you have a follow-up scheduled for Thursday.

Vexa workspaces give agents a **file-based knowledge OS** where meetings automatically feed a structured knowledge graph. After every meeting, the agent extracts contacts, decisions, and action items into linked markdown files — like Obsidian, but populated automatically by your meetings.

**How this compares to other agent memory systems:**

| Platform | Memory model | Meetings feed it? | Entity graph | Self-hosted |
|----------|-------------|-------------------|-------------|-------------|
| **OpenClaw** | MEMORY.md + SOUL.md + daily logs | No | No | Yes |
| **Mem0** (48K stars) | Vector + graph + KV store (API) | No | API-based graph | No (SaaS) |
| **Zep** | Temporal knowledge graph | No | Yes (graph DB) | Partial |
| **Letta** | Virtual context management | No | No | Yes |
| **Fast.io** | File storage for agents (MCP) | No | No | No (SaaS) |
| **Obsidian + AI** | Markdown + wiki-links + templates | Manual note-taking | Manual | Yes (local) |
| **Clay/Attio** | CRM with AI enrichment | Via integrations | Yes | No |
| **Vexa Workspaces** | Markdown + wiki-links + entities + streams + timeline + soul + scripts | **Yes — automatic** | **Yes — contacts, companies, products** | **Yes** |

The key difference: every other memory system is disconnected from meetings. You have to manually feed information in. Vexa's workspace is populated by the meeting pipeline — meeting ends → agent extracts entities, decisions, action items → knowledge graph grows automatically.

## Current state

MVP0: bare `/workspace/` directory, MinIO sync, knowledge template deployed, no Git backing yet.

## Architecture

### Templates

A workspace starts from a template. Templates define:
- Directory structure (what folders exist)
- `.claude/CLAUDE.md` (agent personality + rules for this workspace type)
- Seed files (notes.md, timeline.md, user.json, etc)
- `.gitignore` (what not to track)

| Template | Purpose | Default |
|----------|---------|---------|
| **knowledge** | Personal knowledge base, streams, meeting notes, reminders, scripts. Ported from Quorum. | Yes |
| **project** | Code project workspace. Agent assists with a specific codebase. | Future |
| **meeting-notes** | Focused on meeting transcription, summaries, action items. | Future |
| **blank** | Empty workspace with minimal CLAUDE.md. | Future |

### Git-backed

Every workspace is a Git repo:
- Initialized on creation from template
- Committed on every `vexa workspace save`
- Optionally pushed to a remote (GitHub, GitLab)
- Full history preserved — compaction is safe because git log has the detail

### Multi-workspace per user

Users can have multiple workspaces:
- `POST /api/workspaces` — create workspace from template
- `GET /api/workspaces` — list user's workspaces
- Agent API's `user_id` becomes `workspace_id` (or user_id + workspace name)

### Workspace index injection

Each chat turn, the Agent API scans the workspace filesystem and injects a compact summary into the prompt (from Quorum's `build_chat_system_prompt()`):
- Active streams count and names
- Knowledge file counts by subdirectory
- Compliance warnings (oversized files, stale streams)
- Current time in user's timezone
- Upcoming scheduled jobs

## Scheduler integration

One path. The agent uses `vexa schedule` to schedule anything. No separate reminders.json or scripts.json watched by different systems.

### How it works

```
Agent calls `vexa schedule`
  |
  vexa schedule --at "2026-03-24T10:00:00Z" chat "Reminder: prepare pitch deck"
  vexa schedule --cron "0 8 * * *" run-script daily-summary
  vexa schedule --in 3h chat "Check if Brian replied"
  vexa schedule --every 3d chat "Run workspace audit"
  |
  POST /api/schedule → scheduler
  |
  Redis sorted set (crash-safe, persistent)
  |
  At fire_at / cron tick:
    action=chat    → POST /api/chat {internal: true, message: "..."}
    action=script  → spawn worker container, run script, deliver output
    action=http    → fire HTTP request (webhooks, external APIs)
```

### Job types

| Action | What happens | Example |
|--------|-------------|---------|
| `chat` | Internal message to agent — agent wakes up, reads context, messages user proactively | Reminders, audits, follow-ups |
| `script` | Spawn worker container, run script, deliver stdout to workspace | Daily summaries, API polling, data collection |
| `http` | Fire HTTP request to external URL | Webhooks, integrations |

### What replaces what

| Quorum (old) | Vexa (new) |
|-------------|------------|
| `reminders.json` + asyncio timer | `vexa schedule --at {time} chat "{message}"` + Redis sorted set |
| `scripts.json` + cron via asyncio | `vexa schedule --cron "{expr}" run-script {id}` + Redis sorted set |
| Workspace audit every 3 days (in-process) | `vexa schedule --every 3d chat "Run workspace audit"` |

One scheduler, one format, one path. The agent doesn't maintain JSON files for scheduling — it calls a CLI command that talks to the scheduler API.

### Agent experience

The agent's CLAUDE.md teaches it to use `vexa schedule`:

```
# Set a reminder
vexa schedule --at "2026-03-24T14:00:00Z" chat "Reminder: call Brian about the proposal"

# Run a script daily at 8am
vexa schedule --cron "0 8 * * * Europe/Lisbon" run-script oura-health

# Follow up in 3 hours
vexa schedule --in 3h chat "Check if the deploy succeeded"

# List scheduled jobs
vexa schedule list

# Cancel a job
vexa schedule cancel job-abc123
```

When a `chat` job fires, the agent is invoked with the message as if the user typed it — but marked `internal: true` so the agent knows it's a scheduled prompt, not a user message. The agent reads workspace context, decides what to do, and messages the user proactively.

## Template: knowledge (default)

### Directory structure

```
.claude/
  CLAUDE.md                    # Agent personality + workspace rules
  settings.local.json          # Tool permissions
  onboarding.json              # Feature introduction tracking
  audit-state.json             # Audit health state
streams/                       # Active working topics (flat .md files)
  archive/                     # Archived streams
knowledge/                     # Structured archive
  entities/
    contacts/                  # People profiles
    companies/                 # Organization profiles
    products/                  # Product/project profiles
  meetings/                    # Meeting minutes
  action-items/                # Action items per meeting
scripts/                       # Automation scripts (code only, scheduling via vexa schedule)
notes.md                       # Inbox/scratchpad
timeline.md                    # Holistic self-journal (past, present, future)
soul.md                        # Agent's understanding of this user
user.json                      # Timezone, location
.gitignore                     # Excludes secrets, session files, images
```

### CLAUDE.md

See `templates/knowledge/.claude/CLAUDE.md` — full agent instructions ported from Quorum, adapted for Vexa's container architecture and `vexa` CLI.

### Key behaviors

1. **File-backed memory** — files are the source of truth, not conversation history
2. **Streams** — flat .md files for active topics, max 300 lines, archive when stale
3. **Timeline** — logarithmic compaction journal (recent=detailed, old=compressed)
4. **Wiki-links** — `[[Entity Name]]` connects everything
5. **Scheduling** — `vexa schedule` for reminders, scripts, audits — one unified path
6. **Scripts** — user automation in `scripts/`, execution via `vexa schedule`
7. **Audit** — periodic workspace health sweep via scheduled chat job
8. **Soul** — agent's self-reflection on the relationship
9. **Onboarding** — gradual feature introduction over weeks

## Workspace Lifecycle — Persist, Restore, Clone

Workspaces are ephemeral in memory but persistent in storage. Every container start restores the workspace; every save persists it. This section documents the three core user flows and how the platform delivers them.

### Two-tier workspace persistence

Workspace persistence has two tiers, each serving a different purpose:

| Tier | Trigger | What it does | Git commit? | When |
|------|---------|-------------|-------------|------|
| **Explicit save** | Agent calls `vexa workspace save` | `git add -A && git commit` + `aws s3 sync` | Yes — meaningful commit message | Agent decides (CLAUDE.md instructs) |
| **Periodic S3 sync** | Background task every 60s | `aws s3 sync` only | No | Automatic while container is alive |

**Why two tiers:** SSE streaming responses (used for chat) have unreliable cleanup — code after the stream ends may not execute if the client disconnects (scheduler timeout, browser close). The periodic sync catches workspace changes even if the agent forgets to save or the stream is cancelled. The explicit save creates meaningful git commits for history.

**Git push to a remote** (e.g., GitHub) is the agent's responsibility. The platform never pushes — the agent runs `git push` from bash when CLAUDE.md instructs it. This keeps the platform generic (no knowledge of remotes) and gives the agent control over push frequency.

`WORKSPACE_SYNC_INTERVAL` env var controls the periodic sync interval (default: 60 seconds).

### Why sync_down before agent runs

Containers are ephemeral — they die on idle timeout, scale-to-zero, or restart. The workspace directory `/workspace/` dies with them. Without sync_down, every new container starts empty — the agent loses all prior work. sync_down restores from MinIO before the agent CLI runs, so the agent sees accumulated state from all prior sessions.

### Why template init for first-time users

A first-time user has no MinIO content. Without a template, the agent starts in an empty directory with no CLAUDE.md, no structure, no personality. The template provides the workspace skeleton that teaches the agent what it is and how to behave.

### Why git clone as workspace init

Some workspaces start from a git repository instead of the built-in template. The repo provides its own CLAUDE.md and initial content. After cloning, the workspace persists independently in MinIO — the agent handles upstream pulls via CLAUDE.md instructions (that's agentic, not platform).

### Why per-user env vars

Different users need different secrets (API keys, tokens) injected into their containers. These come from `user.data['env']` in PostgreSQL (via admin-api), not from shared env files. Secrets never touch workspace files or MinIO.

### Container lifecycle diagram

```
POST /api/chat or /internal/chat
       │
       ▼
ensure_container(user_id)
       │
       ├── container exists & alive? → touch, return
       │
       └── create new container via runtime-api
              │
              ▼
         _new_container = True
              │
              ├── 1. Fetch user.data from admin-api
              │      └── inject user.data['env'] into container env
              │
              ├── 2. sync_down from MinIO → /workspace/
              │      ├── content found → workspace restored, skip init
              │      └── empty (first time) ──┐
              │                                │
              ├── 3a. git_repo_url configured?─┤── YES → git clone {repo} into /workspace/
              │                                └── NO  → copy /templates/{template}/ into /workspace/
              │
              ▼
         4. Run agent CLI (claude -p "...")
              │
              ▼
         5. Agent calls `vexa workspace save` (explicit, from CLAUDE.md)
              └── git commit + aws s3 sync → MinIO
              │
              ▼
         6. Periodic S3 sync (every 60s, background task)
              └── S3-only, no git commit — safety net
              │
              ▼
         7. Container idles out (300s) → runtime-api removes it
```

### Flow 1: Returning user — scheduled agent

```
Day 1:
  Scheduler fires → POST /internal/chat {user_id: "agent-x", message: "[scheduled:daily]"}
  agent-api: ensure_container → new container, _new_container=True
  agent-api: sync_down → MinIO empty (first time) → template init
  agent CLI runs → writes files → vexa workspace save → MinIO
  container idles out, dies

Day 2:
  Scheduler fires → POST /internal/chat {user_id: "agent-x", message: "[scheduled:daily]"}
  agent-api: ensure_container → new container, _new_container=True
  agent-api: sync_down → MinIO has Day 1 content → restored
  agent CLI runs → reads prior files, adds more → vexa workspace save
  container dies

Day 30:
  Workspace has 30 days of accumulated work. Each sync_down restores everything.
```

### Flow 2: Interactive user via Telegram

```
Session 1:
  User sends message → POST /api/chat {user_id: "alice", message: "hello"}
  New container → sync_down → empty → template init
  Agent reads CLAUDE.md, writes soul.md with user preferences → save

Session 2 (next day, container died):
  User sends message → POST /api/chat {user_id: "alice", message: "what did we discuss?"}
  New container → sync_down → restores soul.md, notes.md, etc.
  Agent reads workspace → remembers user context → responds
```

### Flow 3: Workspace from git repo

```
Admin sets: PATCH /admin/users/traderx {data: {workspace_git: {repo: "https://github.com/org/traderx-knowledge", branch: "main"}}}

First chat:
  POST /api/chat {user_id: "traderx", message: "start"}
  New container → sync_down → empty → workspace_git configured → git clone
  Agent reads cloned CLAUDE.md and project files → works

Subsequent chats:
  sync_down restores from MinIO (not re-cloned)
  Agent uses `git pull` from bash if it needs upstream updates (agentic, not platform)
```

### API surface

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /internal/chat` | `X-Internal-Secret` header (INTERNAL_API_SECRET) | Scheduler → agent-api. Same as /api/chat, no X-API-Key. |
| `POST /api/schedule` | X-API-Key | vexa CLI → agent-api → runtime-api scheduler. Translates `{action, message, cron}` into scheduler job spec. SSRF-protected: rejects private/internal URLs. |

### Per-user env var flow

```
Admin sets user env: PATCH /admin/users/{id} {data: {env: {MY_TOKEN: "secret"}}}
       │
       ▼
ensure_container → GET /admin/users/{id} → reads user.data['env']
       │
       ▼
Injects {MY_TOKEN: "secret"} into container environment
       │
       ▼
Agent runs `echo $MY_TOKEN` → prints "secret"
```

Env vars are injected at container creation time. They live only in the container's environment — never written to workspace files, never synced to MinIO.

### Fail-safe behavior

| Scenario | Behavior |
|----------|----------|
| sync_down fails, existing user (MinIO has content) | **Abort.** Don't run agent with empty workspace — user has data to lose. |
| sync_down fails, first-time user (MinIO empty) | Continue with template/clone init. Nothing to lose. |
| admin-api unreachable | Continue without per-user env vars. Log warning. |
| git clone fails | Abort. Log error. Don't fall back to template — user configured git for a reason. |

## Implementation plan

| Phase | What | Status |
|-------|------|--------|
| 1 | Knowledge template files (CLAUDE.md, structure, .gitignore) | Done |
| 2 | Workspace persistence: sync_down on container start | **Done** (2026-04-01) |
| 3 | Template init for first-time users | **Done** (2026-04-01) |
| 4 | Git clone init from configured repo | **Done** (2026-04-01) |
| 5 | Per-user env var injection from user.data | **Done** (2026-04-01) |
| 6 | `vexa schedule` CLI + scheduler API integration | Done |
| 7 | Internal chat endpoint for scheduler | **Done** (2026-04-01) |
| 8 | `/api/schedule` bridge endpoint | **Done** (2026-04-01) |
| 9 | Workspace index injection per chat turn | Not started |
| 10 | Script execution via worker containers | Not started |
| 11 | Multi-workspace support (workspace CRUD API) | Not started |
| 12 | Additional templates (project, meeting-notes, blank) | Not started |

---

## State (validated 2026-04-01)

### DoD results — 8/8 passed

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| 1 | Save → die → restore (3 cycles) | **PASS** | User writes file, saves, container killed, new container restores file from MinIO. Repeated 3x — content accumulates. |
| 2 | First-time user gets template | **PASS** | New user_id → sync_down returns empty → template 'knowledge' copied → `.claude/CLAUDE.md`, `notes.md`, `soul.md`, `timeline.md`, `streams/`, `knowledge/` present. |
| 3 | Existing workspace not clobbered | **PASS** | Modified notes.md, saved, container killed, restored → custom content preserved, not template default. |
| 4 | Per-user env vars injected | **PASS** | `user.data['env']` fetched from admin-api, injected as container env vars at creation time. |
| 5 | Env vars not leaked to workspace | **PASS** | `grep -r` inside /workspace/ returns no secrets. Git config clean. |
| 6 | Scheduler reaches agent via /internal/chat | **PASS** | Scheduler job fires → POST /internal/chat with X-Internal-Secret → agent responds. |
| 7 | Git clone as initial workspace | **PASS** | Configured user.data['workspace_git'] → first container clones repo → agent reads cloned files. Tested with github.com/octocat/Hello-World. |
| 8 | Two users clone same repo, diverge | **PASS** | User 20 and 21 clone same repo, write different content, save → independent workspaces in MinIO. |

### Security results — 8/8 passed

| Check | Result |
|-------|--------|
| /internal/chat without X-Internal-Secret | 403 Forbidden |
| /internal/chat with wrong secret | 403 Forbidden |
| /api/schedule action=http to internal service (admin-api:8001) | 400 rejected |
| /api/schedule action=http to localhost | 400 rejected |
| /api/schedule action=http to private IP (10.x) | 400 rejected |
| Path traversal (../../../etc/passwd) | 400 Bad Request |
| Absolute path (/etc/passwd) | 400 Bad Request |
| Git clone with non-https URL | Rejected (https-only) |

### Config vars (actual, in compose)

```
STORAGE_BACKEND=s3
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=${MINIO_ACCESS_KEY:-vexa-access-key}
S3_SECRET_KEY=${MINIO_SECRET_KEY:-vexa-secret-key}
S3_BUCKET=${MINIO_BUCKET:-vexa-agentic}
ADMIN_API_URL=http://admin-api:8001
ADMIN_API_TOKEN=${ADMIN_TOKEN:-vexa-admin-token}
INTERNAL_API_SECRET=${INTERNAL_API_SECRET:-vexa-internal-secret}
AGENT_API_INTERNAL_URL=http://agent-api:8100
```

### Known limitations

- Per-user env vars only work for numeric user_ids (admin-api requires integer primary key)
- Git clone only supports https:// URLs (ssh/git:// rejected for security)
- User data cache not invalidated until container dies — admin changes require container restart
- No SSE progress events during workspace init (client waits silently during slow git clones)
