# Mission: Multi-Workspace — Upload Local, Multiple Per User

Focus: agent-api (container_manager, workspace, chat, main)
Problem: 1 user = 1 container = 1 workspace. Can't run multiple agents per user. Can't upload a workspace from local without a running container. Sessions exist but don't own containers or workspaces.
Target: Sessions own containers and workspaces. Users can upload named workspaces. Sessions start with a specific workspace.
Stop-when: target met OR hard blocker identified with diagnosis

---

## Why This Matters

### The stack problem

We have workspace definitions (stacks) — `.claude/CLAUDE.md` + `settings.json` — for different agent types: browser research, meeting assistant, etc. Today there's no way to:
1. Upload a stack from local as a named workspace
2. Start an agent session with that workspace
3. Run multiple agents (different workspaces) for the same user

### Current constraint

```python
# container_manager.py
self._containers: dict[str, ContainerInfo] = {}  # user_id -> info
```

One dict, keyed by `user_id`. One container per user. One workspace per user (S3: `users/{user_id}/`).

### Target state

```
1 user → N sessions → N containers → N workspaces

S3: workspaces/{user_id}/{workspace_name}/
```

---

## System Design Constraints

Inherited from 260401-workspace-lifecycle (still apply):

1. **Vexa is generic infrastructure** — zero application knowledge
2. **Runtime API is untouched** — doesn't know about workspaces
3. **Agent-api owns workspace logic** — executes via docker exec
4. **Minimal API surface** — if agent can do it from bash, don't add an endpoint
5. **Fail safe on sync errors** — don't run with wrong workspace

New constraints:

6. **Sessions are the agent identity** — not users. Users own sessions. Sessions own containers and workspaces.
7. **Backward compatible** — existing single-session users keep working. Default session = current behavior.
8. **Workspace upload is pre-container** — you upload a workspace template, then start sessions that use it. The workspace exists in S3 before any container runs.

---

## API Surface

### New endpoints

```
# Workspace templates (stored in S3, pre-container)
POST   /api/workspaces                          → upload workspace (tar.gz body)
       params: user_id, name
       Stores to S3: workspaces/{user_id}/{name}/

GET    /api/workspaces                           → list user's named workspaces
       params: user_id
       Returns: [{name, created_at, file_count}]

DELETE /api/workspaces/{name}                    → delete workspace
       params: user_id

GET    /api/workspaces/{name}/files              → list files in workspace
       params: user_id

POST   /api/workspaces/{name}/file               → write single file
       body: {user_id, path, content}
```

### Modified endpoints

```
# Sessions now reference a workspace
POST   /api/sessions
       body: {user_id, name, workspace?}
       workspace = name of uploaded workspace. If omitted: "default" (current behavior).

# Chat now routes by session
POST   /api/chat
       body: {user_id, message, session_id?}
       session_id determines which container. If omitted: default session (backward compat).
```

### Workspace sources

Three modes — all persist to S3, git remote is optional:

1. **GitHub remote** — clone from repo, remote set. Agent can push/pull.
2. **Upload from local** — files pushed to S3, no git remote. Local git repo for commits, no remote.
3. **Upload + remote later** — start without remote, optionally add one via agent (`git remote add origin ...`).

S3 is the persistence layer in all cases. Git remote is for collaboration/backup, not required.

### Flow: upload from local

```bash
# 1. Upload stack as named workspace
cd stacks/agent-browser
tar czf - . | curl -X POST "$AGENT_API/api/workspaces?user_id=1&name=agent-browser" \
  -H "X-API-Key: $TOKEN" \
  -H "Content-Type: application/gzip" \
  --data-binary @-

# 2. Create session using that workspace
curl -X POST "$AGENT_API/api/sessions" \
  -H "X-API-Key: $TOKEN" \
  -d '{"user_id": "1", "name": "research", "workspace": "agent-browser"}'
# → {"session_id": "abc-123", "workspace": "agent-browser"}

# 3. Chat — container spawns, workspace synced, agent has .claude/CLAUDE.md
curl -X POST "$AGENT_API/api/chat" \
  -H "X-API-Key: $TOKEN" \
  -d '{"user_id": "1", "session_id": "abc-123", "message": "go research Reddit"}'
```

### Flow: GitHub remote

```bash
# Set workspace_git on user or session
curl -X PATCH "$ADMIN_API/admin/users/1" \
  -H "X-Admin-API-Key: $ADMIN_TOKEN" \
  -d '{"data": {"workspace_git": {"repo": "https://github.com/user/workspace.git", "branch": "main"}}}'

# Create session — first chat clones the repo
curl -X POST "$AGENT_API/api/sessions" \
  -d '{"user_id": "1", "name": "dev", "workspace": "my-project"}'
```

### Flow: add remote later (agent does it)

```bash
# Agent already has workspace from upload. Tell it to set a remote:
curl -X POST "$AGENT_API/api/chat" \
  -d '{"user_id": "1", "session_id": "abc-123", "message": "run: git remote add origin https://github.com/user/repo.git && git push -u origin main"}'
```

---

## Key Changes

### container_manager.py

```
Before: _containers: dict[str, ContainerInfo]           # user_id -> info
After:  _containers: dict[tuple[str,str], ContainerInfo] # (user_id, session_id) -> info
```

- `ensure_container(user_id, session_id)` — key by both
- Multiple containers per user (one per active session)
- Backward compat: if no session_id, use "default"

### workspace.py

```
Before: S3 path = users/{user_id}/
After:  S3 path = workspaces/{user_id}/{workspace_name}/
```

- New: `upload_workspace(user_id, name, tar_bytes)` — extract tar to S3
- New: `list_workspaces(user_id)` — list S3 prefixes
- New: `delete_workspace(user_id, name)` — delete S3 prefix
- Modified: `sync_down` uses workspace name from session metadata
- Modified: `sync_up` saves to session's workspace path

### chat.py

- `_workspace_init` reads workspace name from session metadata (Redis)
- If workspace name specified: sync_down from `workspaces/{user_id}/{name}/`
- If workspace name not specified: current behavior (default workspace)

### main.py

- 5 new endpoints for workspace CRUD
- `POST /api/sessions` accepts `workspace` param
- `POST /api/chat` passes `session_id` to container_manager

---

## DoD

### Core: Multi-workspace

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 1 | **Upload workspace from local.** `tar czf` a directory, POST to `/api/workspaces`. Files appear in S3. | 20 | 0 | `GET /api/workspaces` lists the uploaded workspace. `GET /api/workspaces/{name}/files` shows correct files. |
| 2 | **Session starts with uploaded workspace.** Create session with `workspace: "my-stack"`. Chat. Agent has the files from the upload. | 20 | 0 | Agent reads `.claude/CLAUDE.md` from the uploaded workspace. Content matches what was uploaded. |
| 3 | **Two sessions, two workspaces, same user.** User has session A (workspace "research") and session B (workspace "meetings"). Both run simultaneously. Independent containers, independent files. | 15 | 10 | Chat to session A, agent sees research CLAUDE.md. Chat to session B, agent sees meetings CLAUDE.md. Different content. |
| 4 | **Workspace persists across container restarts.** Agent writes file, saves, container dies. New chat to same session: file still there. | 15 | 5 | Three-cycle test: write, kill, restore, verify accumulated content. |
| 5 | **Backward compat.** Existing users with no session_id specified: everything works as before. Single container, single workspace. | 10 | 0 | Chat without session_id. Same behavior as before this change. |

### Workspace management

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 6 | **List workspaces.** `GET /api/workspaces?user_id=1` returns uploaded workspace names. | 5 | 30 | Response includes all uploaded workspaces with names. |
| 7 | **Delete workspace.** `DELETE /api/workspaces/{name}` removes from S3. | 5 | 40 | Workspace no longer in list after delete. |
| 8 | **Write single file to workspace.** `POST /api/workspaces/{name}/file` writes without needing a running container. | 5 | 40 | File appears in `GET /api/workspaces/{name}/files`. |

### Safety

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 9 | **Can't access other user's workspaces.** User A uploads workspace. User B can't list, read, or delete it. | 5 | 20 | 403 or empty list when user B queries user A's workspaces. |

---

## Files to modify

| File | What |
|------|------|
| `services/agent-api/agent_api/container_manager.py` | Key by `(user_id, session_id)`, ensure_container takes session_id |
| `services/agent-api/agent_api/workspace.py` | Upload/list/delete workspace ops, S3 paths include workspace name |
| `services/agent-api/agent_api/chat.py` | _workspace_init reads workspace from session, passes to sync_down |
| `services/agent-api/agent_api/main.py` | 5 new workspace endpoints, session/chat pass session_id through |
| `services/agent-api/agent_api/session.py` | Session metadata stores workspace name |

## Files NOT modified

| File | Why |
|------|-----|
| `services/runtime-api/*` | Doesn't know about workspaces or sessions |
| `services/admin-api/*` | User management unchanged |
| `services/meeting-api/*` | Meeting bots unchanged |
| `services/vexa-agent/*` | Agent image unchanged — vexa CLI already works |
