# MCP Integration Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules
> Development cycle: [features/README.md](../../README.md#spec-driven-features) — research, spec, build & test

## Mission

Build the best meeting MCP server. Not just a REST-to-MCP proxy — a first-class agent interface for meeting intelligence with resources, subscriptions, and interactive tools.

## Development cycle

This is a **spec-driven feature** — see [features/README.md](../../README.md#spec-driven-features).

```
RESEARCH (done)              SPEC                        BUILD & TEST
─────────────                ────                        ────────────
RESEARCH.md exists           Pick priority batch         Implement spec item
Gaps identified              Write expected behavior     make test
Priorities ranked            Write test assertions       Fix, re-run
                             Tests should FAIL           Update findings.md
                                                         Capture responses
```

### Current stage: SPEC (research complete, need specs for P0/P1)

**Research:** `RESEARCH.md` — 2026-03-23, ecosystem analysis + live testing.

**Priority batches:**

| Batch | Items | Effort |
|-------|-------|--------|
| P0-fix | Fix `list_meetings` pagination, fix `get_recording_media_download` internal URL | Hours |
| P1-tools | Expose `send_chat_message`, `read_chat_messages`, `bot_speak` as MCP tools | Days |
| P1-search | Add `search_meetings` tool (keyword, date, participant, pagination) | Days |
| P2-resources | Add MCP Resources for meetings + transcripts | Week |
| P3-subscriptions | Bridge WebSocket to MCP Subscriptions for live transcript | Weeks |

### On entry: determine your stage

1. **Does `RESEARCH.md` exist?** Yes → research is done.
2. **Does `tests/spec-{batch}.md` exist for current batch?** If no → you are in SPEC.
3. **Do test assertions exist and fail?** If yes → you are in BUILD & TEST.
4. **Do all tests pass?** If yes → move to next batch or GATE.

## Scope

You own the MCP protocol layer: tool definitions, resources, prompts, subscriptions, and the gateway proxy. You dispatch to service agents for backend changes.

### Gate (local)

| Check | Pass | Fail |
|-------|------|------|
| Tools list | All tools discoverable via `tools/list` | Tools missing or empty (current: 0 via gateway) |
| Tool calls | Each tool returns valid data | Tool errors or empty response |
| Auth | No-token request returns 401/403 | Unauthenticated access allowed |
| Pagination | `list_meetings` respects limit/offset | Returns unbounded 2.7MB |
| Interactive | Chat/speak tools work on active bot | Tools missing |
| Resources | Meetings/transcripts browsable as MCP resources | `resources/list` returns "method not found" |

### Docs

- [Vexa MCP](../../docs/vexa-mcp.mdx)

### Edges

**Crosses:**
- mcp service (`services/mcp/main.py`) — tool handlers, FastApiMCP
- api-gateway (`services/api-gateway/main.py:835-945`) — /mcp proxy routes
- bot-manager — chat/speak endpoints to expose as tools
- WebSocket stream — live transcript for subscriptions

**Data flow:**
MCP client → api-gateway /mcp → mcp service → api-gateway REST → backend services

### Counterparts
- Service agents: `services/mcp`, `services/api-gateway`, `services/bot-manager`
- Related features: webhooks (event-driven complement to MCP), chat, speaking-bot

## How to test

```bash
cd features/mcp-integration/tests
cp ../.env.example ../.env   # fill in values
make smoke                    # MCP reachable?
make test                     # all assertions
make test-tools               # tool calls
make test-auth                # auth enforcement
```

MCP service runs on port 18898 (direct) or via gateway at :8066/mcp.
Uses Streamable HTTP transport — `Mcp-Session-Id` header required after init.

## Known bugs (from live testing)

1. `get_recording_media_download` returns `http://minio:9000/...` (internal Docker URL)
2. `list_meetings` returns all 211 meetings (2.7MB) with zero pagination/filtering
3. `tools/list` returns 0 tools via gateway proxy (session header stripping?)

## Critical findings
Save to `tests/findings.md`.
