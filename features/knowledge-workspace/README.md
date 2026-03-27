# Knowledge Workspace

> **Confidence: 0** — RESET after architecture refactoring. agent-api renamed from agent-runtime. Workspace module moved. Storage imports changed.
> **Tested:** Template structure deployed, agent CLAUDE.md instructions working, MinIO workspace sync, vexa schedule integration, streams/entities/timeline structure.
> **Not tested:** Git-backed workspace init, workspace index injection per chat turn, entity extraction from meeting transcripts, script execution via worker containers, multi-workspace API.
> **Contributions welcome:** Git init on workspace creation, workspace index injection (scan filesystem → inject summary into prompt), entity extraction from transcripts, script execution in worker containers, additional templates (project, meeting-notes).

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

## Implementation status

| Phase | What | Status |
|-------|------|--------|
| 1 | Knowledge template files (CLAUDE.md, structure, seeds) | **Done** |
| 2 | MinIO workspace persistence | **Done** |
| 3 | Agent chat with workspace context (Telegram, web) | **Done** |
| 4 | `vexa schedule` CLI + scheduler integration | **Done** |
| 5 | Git init on workspace creation | Not started |
| 6 | Workspace index injection per chat turn | Not started |
| 7 | Entity extraction from meeting transcripts | Not started |
| 8 | Script execution via worker containers | Not started |
| 9 | Multi-workspace support (workspace CRUD API) | Not started |
| 10 | Additional templates (project, meeting-notes, blank) | Not started |
