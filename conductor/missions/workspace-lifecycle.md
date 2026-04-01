# Mission: Workspace Lifecycle — Persist, Restore, Clone

Focus: agent-api + workspace.py
Problem: Workspaces don't survive container restarts. `sync_down` exists but is never called. No template init, no git clone init, no per-user env vars. Every new container starts with empty `/workspace/`.
Target: Complete workspace lifecycle — restore on start, template init for new users, git clone from remote, per-user env vars, internal chat endpoint for scheduler.
Stop-when: target met OR hard blocker identified with diagnosis

---

## Why This Matters

Agent containers are ephemeral — start, run, idle out, die. That's by design (scale to zero). But `/workspace/` dies with the container. Every new container starts empty.

### Flow 1: The scheduled agent

An automated agent runs daily via scheduler. Each time, a fresh container starts, the agent does work, saves, container dies. Next day: everything should still be there.

```
Day 1: Agent runs task → writes files to /workspace/ → saves → container dies
Day 2: New container → workspace RESTORED → agent reads prior files, adds more → saves
Day 30: Workspace has accumulated 30 days of work
```

**Fails today:** sync_down never called. Day 2 starts empty. Day 30 = Day 1.

### Flow 2: The interactive user

A user chats via Telegram. Agent learns their context, writes to workspace files. Container idles out. Next conversation: agent should remember.

```
Session 1: Agent writes user preferences to soul.md → saves
Session 2: Agent reads soul.md → knows the user → answers in context
```

**Fails today:** Session 2 starts with empty workspace. Agent doesn't know the user.

### Flow 3: Workspace from a git repo

Instead of the built-in template, a workspace starts by cloning a git repo. The repo provides the CLAUDE.md and initial content. After cloning, the workspace persists independently in MinIO. The agent handles upstream pulls via CLAUDE.md instructions — that's an agentic workflow, not a platform feature.

```
Platform: git clone {repo} → /workspace/ (on first container start, generic)
Agent:    git pull (for updates), merge logic (instructed by CLAUDE.md, app-specific)
```

**Fails today:** No git clone init. Only empty workspace or template copy.

---

## What's Built vs What's Missing

| Capability | Status | Location |
|-----------|--------|----------|
| sync_up (save to MinIO) | **Works** | `workspace.py:77-94` |
| sync_down (restore from MinIO) | **Code exists, never called** | `workspace.py:61-74` — 0 callers |
| git_commit (local) | **Works** | `workspace.py:97-115` |
| Template files in image | **Exist** | `/templates/knowledge/` in agent image |
| Template copy to workspace | **Missing** | Nothing copies template on empty workspace |
| git clone from remote | **Missing** | No function. BUT `PUT /user/workspace-git` already stores `{repo, token, branch}` in user.data |
| Per-user env vars | **Partially exists** | `user.data` JSONB in Postgres stores arbitrary config. Need agent-api to read and inject into container env. |
| Scheduler→agent-api auth | **Missing** | No internal chat endpoint |
| vexa schedule → agent-api → scheduler | **Missing** | vexa CLI sends `POST /api/schedule` but endpoint doesn't exist in agent-api. Scheduler is in runtime-api. Need bridge. |

---

## System Design Constraints

These are non-negotiable. Any implementation that violates these is wrong regardless of whether it passes DoD.

### 1. Vexa is generic infrastructure — zero application knowledge

Vexa must not contain any reference to CALM, FINOS, TraderX, GitHub sync, RSS feeds, or any specific workspace application. If you find yourself adding an `if user_id == "calm-traderx"` or importing a CALM schema, you've violated the boundary. Every feature built here must work for ANY workspace user.

### 2. Runtime API is untouched

Runtime API owns containers and scheduling. It does NOT know about workspaces, templates, git repos, user config, or MinIO workspace paths. All changes are in agent-api. If you're editing files under `services/runtime-api/`, stop and reconsider.

### 3. Agent-api owns workspace logic, executes via docker exec

All new workspace operations (sync_down, template init, git clone) run inside the agent container via `docker exec` — same pattern as existing `sync_up` and `git_commit` in `workspace.py`. Agent-api is the orchestrator. It does NOT copy files onto the host or mount new volumes.

### 4. Minimal API surface — agent does the work

If the agent can do it from bash inside the container (git push, git pull, file operations), don't add an endpoint. Endpoints are for things that must happen BEFORE the agent runs (sync_down, template init) or that external services need to trigger (scheduler → /internal/chat). The agent is capable — trust it.

### 5. Per-user config and secrets are internal to Vexa

Applications declare what they need ("I need GITHUB_TOKEN in my container"). How Vexa stores and delivers that (Redis, env files, admin API) is Vexa's internal business. Application missions must not reference Redis, MinIO paths, or internal storage details.

### 6. Two-tier workspace persistence

Workspace persistence has two tiers:
- **Explicit save** (`vexa workspace save` / `POST /internal/workspace/save`): git commit + S3 sync. Agent-initiated, meaningful commit messages. This is the primary save path.
- **Periodic S3 sync** (background task, every 60s): S3-only, no git commit. Safety net that catches changes if the agent forgets to save or the SSE stream is cancelled. Configurable via `WORKSPACE_SYNC_INTERVAL` env var.

Git push to a remote (GitHub) is entirely the agent's responsibility — the platform never pushes. The agent does it from bash when CLAUDE.md instructs.

### 7. Fail safe on sync_down errors

If sync_down fails (MinIO down, network error):
- **Existing user** (MinIO has content): abort with error. Don't run agent with empty workspace — user has data to lose. The agent would create duplicate files, overwrite with template, or produce garbage.
- **First-time user** (MinIO empty): continue with template/clone init. Nothing to lose.
- Log the error either way. Never silently ignore a failed restore.

### 7. The scheduler is generic — it fires HTTP callbacks

Scheduler jobs are `{url, method, body, cron}`. The scheduler doesn't know it's triggering a chat or a workspace operation. It just fires HTTP. Don't add scheduler-specific workspace logic.

### Service boundary diagram

```
Clients (Telegram, Web, Scheduler)
       │  POST /api/chat, POST /internal/chat
       ▼
   Agent API (agent-api:8100)     ← workspace logic: sync, templates, config
       │  POST /containers
       ▼
   Runtime API (runtime-api:8090) ← container lifecycle, scheduler (UNCHANGED)
       │  docker create/start/exec
       ▼
   Agent containers               ← ephemeral, /workspace/ mounted
```

---

## API Surface — Minimal

### New endpoints

```
POST /internal/chat      # Same as /api/chat, no X-API-Key. For scheduler.
POST /api/schedule       # Bridge: vexa CLI → agent-api → runtime-api scheduler.
                         # Translates {action:"chat", message, cron} into scheduler job spec.
```

`/api/schedule` exists because the vexa CLI inside containers POSTs to agent-api (it doesn't know about runtime-api). Agent-api translates and forwards to `POST /scheduler/jobs` on runtime-api. This is the same delegation pattern as container creation.

### Automatic operations (no endpoint, internal to agent-api)

When `_new_container=True`, before agent CLI runs:

```
1. sync_down       → restore from MinIO
2. if empty + git_repo_url configured → git clone {repo} into /workspace/
3. if empty + no git_repo_url         → copy /templates/{template}/ into /workspace/
4. inject per-user env vars from Redis user_env:{user_id}
```

### Per-user config (already partially exists)

User config is stored in PostgreSQL `users.data` JSONB column — the existing pattern used by webhooks (`user.data['webhook_url']`), recording config (`user.data['recording_config']`), and workspace git (`user.data['workspace_git']`).

For this mission, agent-api reads:
- `user.data['workspace_git']` — `{repo, token, branch}` for git clone init. **Already stored** via `PUT /user/workspace-git`.
- `user.data['env']` — arbitrary env vars injected into the user's container. **New field**, set via `PATCH /admin/users/{user_id}` (existing endpoint, just a new key in data).

No Redis config needed. No new admin API endpoints. Storage and write endpoints already exist.

**How agent-api reads user.data:** Agent-api calls admin-api on the internal network: `GET /admin/users/{user_id}` → returns user.data. Same delegation pattern as agent-api → runtime-api for containers. This adds admin-api as a dependency for agent-api (acceptable — agent-api already depends on runtime-api and Redis). Agent-api caches the result for the container's lifetime — config doesn't change mid-session.

New dependency: `agent-api → admin-api (internal HTTP, for user.data)`

---

## DoD

### Flow 1: Workspace persists across container restarts

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 1 | **Full cycle: save → die → restore.** Chat as user, agent writes file to `/workspace/`, calls `vexa workspace save`. Stop container. Chat again. File still there. Third cycle: file has content from all runs. | 25 | 0 | Three sequential chat→save→kill→restore cycles. `docker exec cat /workspace/test.md` shows accumulated content. |
| 2 | **First-time user gets template.** Chat as never-seen user_id (no git_repo_url configured). Agent finds knowledge template structure: `.claude/`, `knowledge/entities/`, `streams/`, `notes.md`. | 10 | 20 | `POST /api/chat {user_id: "test-{uuid}"}`. Agent responds. `docker exec ls /workspace/` shows template. |
| 3 | **Existing workspace not clobbered.** User has custom notes.md. Container restarts. Custom content preserved, not overwritten by template. | 10 | 5 | Modify notes.md, save, stop, restart. Content is custom, not template default. |

### Flow 2: Per-user env vars and scheduler auth

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 4 | **Per-user env vars injected.** Set `user_env:test-user` in Redis with `{"MY_VAR": "secret123"}`. Chat as test-user. Agent runs `echo $MY_VAR` → prints `secret123`. Different user: empty. | 10 | 25 | Verified via agent bash output. Different user doesn't see the var. |
| 5 | **Env vars not leaked to workspace files.** After container runs with user env vars: no values in `/workspace/` files, `.git/config`, or MinIO. | 5 | 10 | `docker exec grep -r "secret123" /workspace/` returns nothing. |
| 6 | **Scheduler reaches agent via /internal/chat.** Register job with `execute_at` now+30s targeting `/internal/chat`. Job fires. Agent receives message, writes to workspace. | 10 | 15 | `POST /scheduler/jobs` with target `/internal/chat`. After firing: workspace has new file from agent. |
| 6b | **vexa schedule from inside container works.** Agent runs `vexa schedule --in 1m chat "test"` from bash. Job appears in scheduler. After 1 minute, agent receives the "test" message. | 10 | 20 | `vexa schedule --in 1m chat "test"` succeeds. `vexa schedule list` shows the job. After firing: agent logs show "test" message received. |

### Flow 3: Workspace from git repo

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 7 | **Git clone as initial workspace.** Configure git_repo_url for test user. First container: workspace cloned from repo, not template. Agent reads cloned CLAUDE.md and files. | 15 | 15 | Create test repo with known file. Configure user. Chat. Agent reads the file — content matches repo. |
| 8 | **Two users clone same repo, diverge.** User A and B clone same repo. A writes to notes.md. B writes different content. Both save. Workspaces are independent. | 10 | 40 | Read notes.md from both — different content. |

### Documentation

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 9 | **Pre-delivery: READMEs explain design.** `features/knowledge-workspace/README.md` and `features/agentic-runtime/workspaces/README.md` updated BEFORE implementation with: (a) three user flows with API call sequences, (b) container lifecycle diagram showing where sync_down/template-init/git-clone fire, (c) WHY each design decision. | 5 | 30 | Diff shows README sections committed before implementation code. |
| 10 | **Post-delivery: READMEs reflect reality.** Same READMEs updated with actual config vars, actual behavior, known limitations. State section updated by validator. | 5 | 60 | State section shows tested evidence. |

**Ceiling mechanics:** #1 fails (persistence broken) → cap 0. #3 fails (clobbers existing) → cap 5. #5 fails (env var leak) → cap 10. #6 fails (scheduler can't reach agent) → cap 15. #7 fails (git clone broken) → cap 15. #4 fails (no per-user env vars) → cap 25. #9 fails (no design docs) → cap 30.

---

## Call Flows

### Scheduled agent (container lifecycle)

```
STEP 1: Scheduler polls Redis, finds due job
        → POST http://agent-api:8100/internal/chat
          body: {"user_id": "my-automated-agent", "message": "[scheduled:daily-task]"}

STEP 2: Agent API: ensure_container("my-automated-agent")
        → POST http://runtime-api:8090/containers
          body: {"user_id": "my-automated-agent", "profile": "agent"}
        ← {"name": "agent-my-automated-agent-a1b2c3d4"}
        → _new_container = True
        → Inject per-user env vars from Redis user_env:my-automated-agent

STEP 3: Workspace init (internal, no HTTP)
        → sync_down → aws s3 sync from MinIO into /workspace/
        → NOT empty (has prior content) → skip template/clone init

STEP 4: Run agent CLI
        → docker exec claude -p "[scheduled:daily-task]"
        → Agent reads CLAUDE.md, does work, updates files

STEP 5: Agent saves
        → vexa workspace save → POST /internal/workspace/save → git commit + S3 sync

STEP 6: Container idles out (300s) → runtime-api removes it
```

### New user with git repo

```
STEP 1: POST /api/chat {user_id: "new-user-123", message: "hello"}

STEP 2: ensure_container → new container, _new_container = True
        → Per-user env vars injected

STEP 3: Workspace init
        → sync_down → MinIO empty (first time)
        → git_repo_url configured? YES → git clone {repo} into /workspace/
        → git_repo_url configured? NO  → cp -r /templates/knowledge/. /workspace/

STEP 4: Agent CLI runs → reads CLAUDE.md from cloned repo or template

STEP 5: Save → workspace persists in MinIO for next time
```

---

## Implementation

### Files to modify (all in agent-api)

| File | What |
|------|------|
| `services/agent-api/agent_api/chat.py` | Call sync_down + init before agent exec when `_new_container=True` |
| `services/agent-api/agent_api/workspace.py` | Add: `init_from_template()`, `git_clone_init()`, `get_user_data()` |
| `services/agent-api/agent_api/config.py` | Add `ADMIN_API_URL` for internal calls to admin-api |
| `services/agent-api/agent_api/container_manager.py` | Read `user.data['env']` via admin-api, inject into container env on create |
| `services/agent-api/agent_api/main.py` | Add: `POST /internal/chat`, `POST /api/schedule` (bridge to runtime-api scheduler) |

### Files NOT modified

| File | Why |
|------|-----|
| `services/runtime-api/*` | Doesn't know about workspaces. Unchanged. |
| `profiles.yaml` | Container profiles don't change. |
| `services/runtime-api/runtime_api/scheduler.py` | Fires HTTP callbacks. Doesn't know about chat or workspaces. |
