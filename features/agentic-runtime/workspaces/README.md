# Workspaces

Workspaces are the agent's persistent memory and working environment. Each workspace is a Git-backed directory with a predefined structure that teaches the agent what it's for.

## Current state

MVP0: bare `/workspace/` directory, MinIO sync, no structure, no Git.

## Where we're going

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

## Implementation plan

| Phase | What | Status |
|-------|------|--------|
| 1 | Knowledge template files (CLAUDE.md, structure, .gitignore) | Done |
| 2 | Git init on workspace creation (instead of bare MinIO) | Not started |
| 3 | Workspace index injection per chat turn | Not started |
| 4 | `vexa schedule` CLI + scheduler API integration | Done |
| 5 | Internal chat messages (scheduled jobs fire as agent prompts) | Done |
| 6 | Script execution via worker containers | Not started |
| 7 | Multi-workspace support (workspace CRUD API) | Not started |
| 8 | Additional templates (project, meeting-notes, blank) | Not started |
