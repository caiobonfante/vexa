# Knowledge Workspace Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md)
> Development cycle: [features/README.md](../../README.md#spec-driven-features)

## Mission

Build the self-maintaining knowledge workspace — a file-based knowledge OS where meetings automatically feed a structured graph of entities, streams, and timelines. The workspace persists across sessions, grows with every meeting, and audits itself on schedule.

## Development cycle

This is a **spec-driven feature**.

### Current stage: BUILD & TEST (Phase 5-6)

**Done:** Template structure, MinIO persistence, agent chat with workspace context, scheduler integration.
**Current:** Need git-backed workspace init and workspace index injection per chat turn.

### Priority batches

| Batch | Items | Status |
|-------|-------|--------|
| Template | Knowledge template files, CLAUDE.md, seeds, .gitignore | Done |
| Persistence | MinIO workspace sync (save/restore) | Done |
| Agent chat | Claude CLI in container with workspace mounted | Done |
| Scheduling | `vexa schedule` CLI, scheduled chat jobs wake agent | Done |
| Git backing | Git init on workspace creation, commit on save | Not started |
| Index injection | Scan workspace → inject summary into each chat prompt | Not started |
| Entity extraction | Parse meeting transcripts → create/update entity files | Not started |
| Script execution | Worker containers run scripts from scripts/ directory | Not started |
| Multi-workspace | CRUD API, workspace selection per session | Not started |
| Templates | Additional templates: project, meeting-notes, blank | Not started |

## Scope

You own the workspace system: templates, knowledge structure, entity extraction, streams lifecycle, timeline compaction, wiki-link graph, audit cycles, and script execution. You don't own container orchestration (agentic-runtime), meeting transcription (realtime-transcription/post-meeting-transcription), or scheduling infrastructure (scheduler).

### Gate (local)

| Check | Pass | Fail |
|-------|------|------|
| Template deploys | New workspace has full knowledge structure | Missing files or directories |
| Agent reads workspace | Agent references timeline, streams, entities in responses | Agent ignores workspace files |
| Entity extraction | Meeting transcript → new entity file in knowledge/entities/ | No entity files created |
| Wiki-links | Entity files contain `[[Name]]` links, cross-referenced | No links or broken links |
| Timeline updated | Meeting events appear in timeline.md with correct dates | Timeline stale |
| Streams lifecycle | Active streams < 30, archived when stale, compacted when > 300 lines | Stream overflow |
| Audit fires | Scheduled audit surfaces overdue items, stale streams | Audit silent or missing |
| Persistence | Workspace survives container restart (MinIO round-trip) | Files lost |
| Git history | `vexa workspace save` creates git commit | No commit |
| Script execution | Scheduled script runs in worker, output in workspace | Script fails or no output |

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

### Counterparts
- Service agents: `services/agent-api` (mounts workspace, injects context)
- Related features: agentic-runtime (container infra), scheduler (job execution), post-meeting-transcription (transcript source)

## Key code locations

| Component | Location | Status |
|-----------|----------|--------|
| Knowledge template | `features/knowledge-workspace/templates/knowledge/` | Done |
| Agent CLAUDE.md | `templates/knowledge/.claude/CLAUDE.md` | Done |
| Workspace sync | `services/agent-api/app/workspace_sync.py` | Done |
| Workspace endpoints | `services/agent-api/app/workspace_endpoints.py` | Done |
| Workspace context | `services/agent-api/app/workspace_context.py` | Done |
| Entity extraction | TBD | Not started |
| Git integration | TBD | Not started |

## How to test

```bash
# Start the agentic stack
cd features/agentic-runtime/deploy
docker compose up -d

# Send a message to agent via Telegram or dashboard
# Verify agent reads workspace files (mentions timeline, streams)
# Create a meeting, let it complete, verify agent extracts entities

# Check workspace persistence
# 1. Save: agent runs `vexa workspace save`
# 2. Kill container
# 3. Send new message (container respawns)
# 4. Verify workspace files survived
```

## Critical findings
Save to `tests/findings.md`.
