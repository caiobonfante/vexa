# Knowledge Workspace

> **Confidence: 70** — Workspace lifecycle validated end-to-end (2026-04-01). Template init, save→die→restore, git clone init, per-user env vars all passing. Entity extraction and workspace index injection not started.
> **Tested (2026-04-01):** Template deployed and auto-copied on first use, MinIO persistence across container restarts (3 cycles), git clone init from public repos, per-user env vars, scheduler→chat integration, security (SSRF, path traversal, auth).
> **Not tested:** Workspace index injection per chat turn, entity extraction from meeting transcripts, script execution via worker containers, multi-workspace API, git clone with private repos (token auth).
> **Contributions welcome:** Workspace index injection (scan filesystem → inject summary into prompt), entity extraction from transcripts, script execution in worker containers, additional templates (project, meeting-notes).

## Why

File-based persistent memory for agents, where meetings automatically feed a structured knowledge graph. Inspired by OpenClaw's SOUL.md + MEMORY.md system — extended with entity extraction from meeting transcripts, wiki-link graphs, and scheduled workspace audits.

**Design decisions:**
- **Files over databases** — markdown files are the source of truth, not conversation history. Readable by humans and agents alike. Git-backed for version history.
- **Wiki-links over vector search** — `[[Entity Name]]` connections are explicit and inspectable. No embedding drift, no retrieval hallucinations.
- **Meeting-fed** — unlike OpenClaw/Mem0/Obsidian where memory is manually populated, the post-meeting pipeline auto-extracts entities, contacts, and action items from transcripts.

### The post-meeting knowledge pipeline

```
Meeting ends
  → transcript.ready webhook fires
  → Agent container wakes up (scheduler on_success callback)
  → Reads transcript via vexa meeting transcript {id}
  → Extracts entities:
      → knowledge/entities/contacts/brian-steele.md  (created/updated)
      → knowledge/entities/companies/acme-corp.md    (created/updated)
  → Creates meeting minutes:
      → knowledge/meetings/2026-03-24-renewal-call.md
      → All linked with [[Brian Steele]], [[Acme Corp]] wiki-links
  → Extracts action items:
      → knowledge/action-items/2026-03-24-renewal-call.md
      → Schedules follow-ups: vexa schedule --at "2026-03-27T14:00:00Z" chat "Follow up with [[Brian Steele]] on pricing"
  → Updates timeline.md with events mentioned
  → Updates relevant streams/ topics
  → vexa workspace save → persists to MinIO/Git
  → Container dies. Zero cost until next meeting.
```

Nobody triggered this. The meeting produced structured knowledge automatically.

## What

A workspace is a persistent directory structure that teaches the agent what it's for. Each workspace starts from a template. The agent reads `.claude/CLAUDE.md` in the workspace and knows its personality, memory model, and rules.

### The knowledge template

```
.claude/
  CLAUDE.md                    # Agent personality + workspace rules
  settings.local.json          # Tool permissions
  onboarding.json              # Gradual feature introduction tracking
  audit-state.json             # Workspace health state
timeline.md                    # Holistic self-journal (past → now → future)
soul.md                        # Agent's understanding of this specific human
notes.md                       # Inbox/scratchpad for quick thoughts
user.json                      # Timezone, location
streams/                       # Active working topics (flat .md files)
  archive/                     # Archived streams (out of active context)
knowledge/                     # Structured archive from meetings + research
  entities/
    contacts/                  # People profiles — auto-extracted from meetings
    companies/                 # Organization profiles
    products/                  # Product/project profiles
  meetings/                    # Meeting minutes with [[wiki-links]]
  action-items/                # Tracked per meeting
scripts/                       # User automation, scheduled via vexa schedule
```

### Key behaviors

**File-backed memory** — files are the source of truth, not conversation history. Sessions may reset, but the workspace persists. Agent reads relevant files at session start to orient itself.

**Timeline** — logarithmic compaction journal. Recent events are detailed, older events are compressed. Contains past, present, AND future. `[[wiki-links]]` connect to entities and streams. Size-bounded to ~300 lines — git history preserves the detail.

**Streams** — flat `.md` files for active working topics. Created naturally as topics emerge. Max 300 lines each, max ~20-30 active. Archived when stale, re-activated when relevant again.

**Wiki-links** — `[[Entity Name]]` syntax connects everything across the workspace. Like Obsidian, but populated automatically by the agent after meetings.

**Soul** — agent's self-reflection on its relationship with this specific human. What works, what doesn't, experiments to try. Updated when the agent gets explicit feedback or notices patterns.

**Scheduling** — `vexa schedule` for reminders, scripts, follow-ups, audits. One unified path. When a scheduled `chat` job fires, the agent wakes up proactively — reads workspace context, decides what to do, messages the user.

**Audit** — every ~3 days, the agent sweeps the workspace for overdue items, passed reminders, procrastination patterns, approaching deadlines. Surfaces 1-3 observations with suggested actions.

**Scripts** — automation code in `scripts/`, executed in sandboxed worker containers via `vexa schedule --cron`. Agent writes the scripts, scheduler runs them. Output delivered to workspace.

### Prior art

- **OpenClaw** — SOUL.md, memory compaction, WhatsApp portal (Vexa workspace system is inspired by this)
- **Quorum** — predecessor workspace system, ported for Vexa's container architecture
- **Obsidian** — wiki-link knowledge graph pattern

## Workspace Lifecycle (platform layer)

The workspace lifecycle (persist/restore/clone) is a platform feature in agent-api, not specific to the knowledge template. See [agentic-runtime/workspaces/README.md](../agentic-runtime/workspaces/README.md) for full design. Summary:

1. **sync_down** on every new container start — restores `/workspace/` from MinIO
2. **Template init** for first-time users — copies knowledge template into empty workspace
3. **Git clone init** — if `workspace_git.repo` configured, clones repo instead of template
4. **Per-user env vars** — `user.data['env']` injected into container at creation time
5. **sync_up** on `vexa workspace save` — git commit + s3 sync to MinIO

The knowledge template (`.claude/CLAUDE.md`, streams/, knowledge/, etc.) is what gets copied in step 2. After that, the workspace is the user's — the agent evolves it through conversations and meetings.

### Code ownership

```
services/agent-api/agent_api/workspace.py   → sync_down, sync_up, git_commit, workspace_exists
services/agent-api/agent_api/chat.py        → calls sync_down + init before agent exec
services/agent-api/agent_api/container_manager.py → per-user env var injection
features/knowledge-workspace/templates/     → template files copied on first use
```

## Implementation status

| Phase | What | Status |
|-------|------|--------|
| 1 | Knowledge template files (CLAUDE.md, structure, seeds) | **Done** |
| 2 | MinIO workspace persistence (sync_down + sync_up) | **Done** (validated 2026-04-01) |
| 3 | Agent chat with workspace context (Telegram, web) | **Done** |
| 4 | `vexa schedule` CLI + scheduler integration | **Done** |
| 5 | Workspace lifecycle: template init, git clone, per-user env vars | **Done** (validated 2026-04-01) |
| 6 | /internal/chat + /api/schedule endpoints | **Done** (validated 2026-04-01) |
| 7 | Workspace index injection per chat turn | Not started |
| 8 | Entity extraction from meeting transcripts | Not started |
| 9 | Script execution via worker containers | Not started |
| 10 | Multi-workspace support (workspace CRUD API) | Not started |
| 11 | Additional templates (project, meeting-notes, blank) | Not started |

## Development Notes

### Key code locations

| Component | Location | Status |
|-----------|----------|--------|
| Knowledge template | `features/knowledge-workspace/templates/knowledge/` | Done |
| Agent CLAUDE.md | `templates/knowledge/.claude/CLAUDE.md` | Done |
| Workspace sync (sync_down, sync_up) | `services/agent-api/agent_api/workspace.py` | Done |
| Workspace init (template, git clone) | `services/agent-api/agent_api/chat.py` | Done |
| Container env injection | `services/agent-api/agent_api/container_manager.py` | Done |
| Endpoints (/internal/chat, /api/schedule) | `services/agent-api/agent_api/main.py` | Done |
| Config (ADMIN_API_URL, S3, etc.) | `services/agent-api/agent_api/config.py` | Done |
| Entity extraction | TBD | Not started |
| Git integration | TBD | Not started |

### Edges

**Depends on:**
- agentic-runtime (container lifecycle, workspace mounting)
- scheduler (scheduled chat jobs for audits/reminders, script execution)
- post-meeting-transcription (transcript source for entity extraction)
- webhooks (meeting.completed triggers agent wake-up)
- MinIO (workspace storage)
- Redis (session state)

**Provides to:**
- agentic-runtime (workspace templates define agent behavior)
- mcp-integration (future: expose workspace as MCP resources)
