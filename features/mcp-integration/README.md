# MCP Integration

> **Confidence: 0** — RESET: major design expansion. Adding 15 new tools, MCP Resources, tool annotations, calendar integration. Previous 17-tool proxy validated but new capabilities untested.
> **Tested:** P0 fixes (pagination, URL rewriting), tools/list, all read tools, auth rejection, gateway proxy.
> **Not tested:** New interactive tools (chat/speak/screen), MCP Resources, calendar tools, tool annotations, structured output.

## Why

MCP server exposing **32+ meeting tools** to AI agents (Claude, Cursor, Windsurf). Unlike other meeting MCP servers (Otter, Fireflies, Read.ai — all read-only SaaS), this provides full **read + write + control** (join, speak, chat, screen share) and is self-hosted.

**Design decision:** Other meeting MCP servers proxy read-only data. Vexa exposes interactive controls as tools — agents can actively participate in meetings, not just query transcripts. No competitor uses MCP Resources, Subscriptions, or tool annotations.

**Competitive edge (from research):**
- Meeting-BaaS: has search + calendar but splits into 2 servers, no resources/subscriptions
- Fireflies/Otter: read-only search, no bot control
- Vexa: single server with full bot control + interactive tools + resources + self-hosted

## What

This feature exposes Vexa meeting data and interactive bot controls through the MCP protocol, allowing AI assistants to use MCP tool calls to access meetings, transcripts, recordings, and actively participate in live meetings.

### Documentation
- [Vexa MCP](../../docs/vexa-mcp.mdx)
- [Research: Ecosystem Analysis](RESEARCH.md)
- [Research: Advanced MCP Features](research/advanced-mcp-features.md)
- [Research: Calendar Integration](RESEARCH-CALENDAR.md)

### Components

- **mcp**: MCP protocol server — tool handlers, resources, prompts
- **api-gateway**: proxies MCP requests to the mcp service

### Data flow

```
MCP client → api-gateway /mcp → mcp service → api-gateway REST → backend services
```

### Key behaviors

- MCP tool calls are JSON-RPC formatted (Streamable HTTP transport)
- Authentication via Bearer token (same API key as REST API)
- Gateway proxies MCP requests transparently via `Mcp-Session-Id` header
- Error responses follow MCP/JSON-RPC error format
- Tool annotations hint at read-only vs destructive operations
- Resources use custom `vexa://` URI scheme

## Design

### Tool Inventory (32 tools across 6 categories)

**Meeting Management (existing, 7 tools)**
| Tool | Method | Annotations |
|------|--------|-------------|
| `parse_meeting_link` | local | readOnly, idempotent |
| `request_meeting_bot` | POST /bots | openWorld |
| `stop_bot` | DELETE /bots/{p}/{id} | destructive |
| `get_bot_status` | GET /bots/status | readOnly |
| `list_meetings` | GET /meetings | readOnly, idempotent |
| `update_meeting_data` | PATCH /meetings/{p}/{id} | — |
| `delete_meeting` | DELETE /meetings/{p}/{id} | destructive |

**Transcripts & Sharing (existing, 3 tools)**
| Tool | Method | Annotations |
|------|--------|-------------|
| `get_meeting_transcript` | GET /transcripts/{p}/{id} | readOnly |
| `get_meeting_bundle` | composite | readOnly |
| `create_transcript_share_link` | POST /transcripts/{p}/{id}/share | — |

**Recordings (existing, 5 tools)**
| Tool | Method | Annotations |
|------|--------|-------------|
| `list_recordings` | GET /recordings | readOnly, idempotent |
| `get_recording` | GET /recordings/{id} | readOnly |
| `get_recording_media_download` | GET /recordings/{id}/media/{mid}/download | readOnly |
| `delete_recording` | DELETE /recordings/{id} | destructive |
| `get_recording_config` | GET /recording-config | readOnly |
| `update_recording_config` | PUT /recording-config | — |

**Bot Config (existing, 1 tool)**
| Tool | Method | Annotations |
|------|--------|-------------|
| `update_bot_config` | PUT /bots/{p}/{id}/config | — |

**Interactive Bot Control (NEW, 7 tools)**
| Tool | Gateway Endpoint | Annotations |
|------|-----------------|-------------|
| `send_chat_message` | POST /bots/{p}/{id}/chat | openWorld |
| `read_chat_messages` | GET /bots/{p}/{id}/chat | readOnly |
| `bot_speak` | POST /bots/{p}/{id}/speak | openWorld |
| `stop_speaking` | DELETE /bots/{p}/{id}/speak | — |
| `bot_screen_share` | POST /bots/{p}/{id}/screen | openWorld |
| `stop_screen_share` | DELETE /bots/{p}/{id}/screen | — |
| `set_bot_avatar` | PUT /bots/{p}/{id}/avatar | — |

**Calendar Integration (NEW, 5 tools)**
| Tool | Gateway Endpoint | Annotations |
|------|-----------------|-------------|
| `calendar_connect` | POST /calendar/connect | openWorld |
| `calendar_status` | GET /calendar/status | readOnly |
| `calendar_disconnect` | DELETE /calendar/disconnect | destructive |
| `list_calendar_events` | GET /calendar/events | readOnly |
| `update_calendar_preferences` | PUT /calendar/preferences | — |

**Webhook & Post-Processing (NEW, 2 tools)**
| Tool | Gateway Endpoint | Annotations |
|------|-----------------|-------------|
| `configure_webhook` | PUT /user/webhook | — |
| `transcribe_recording` | POST /meetings/{id}/transcribe | openWorld |

### MCP Resources (NEW)

Custom `vexa://` URI scheme for browsable meeting data in Claude Desktop sidebar.

**Static Resources:**
| URI | Description |
|-----|-------------|
| `vexa://meetings` | Browsable meeting list (recent 20) |

**Resource Templates (parameterized):**
| URI Template | Description |
|-------------|-------------|
| `vexa://meeting/{platform}/{meeting_id}/transcript` | Full transcript |
| `vexa://meeting/{platform}/{meeting_id}/status` | Bot status + metadata |
| `vexa://meeting/{platform}/{meeting_id}/chat` | Chat messages |
| `vexa://recording/{recording_id}` | Recording metadata |

Resources are **application-controlled** (user browses in sidebar) vs tools which are **model-controlled** (LLM decides when to call). This gives users a natural way to drag meeting context into conversations.

### Tool Annotations (NEW)

All tools annotated with MCP spec hints:
- `readOnlyHint`: true for GET operations (no side effects)
- `destructiveHint`: true for DELETE operations
- `idempotentHint`: true for parse/list operations
- `openWorldHint`: true for tools that affect live meetings

### Prompts (existing 4 + 3 new)

**Existing:**
- `vexa.meeting_prep` — parse link, request bot, store notes
- `vexa.during_meeting` — check status, get transcript snapshot
- `vexa.post_meeting` — fetch bundle, summarize, action items
- `vexa.teams_link_help` — Teams URL troubleshooting

**New:**
- `vexa.chat_with_meeting` — send/read chat messages in a live meeting
- `vexa.speak_in_meeting` — TTS workflow: compose message, speak, monitor
- `vexa.calendar_setup` — connect calendar, set auto-join preferences

### Priority Batches

| Batch | Items | Status |
|-------|-------|--------|
| P0-fix | Pagination + URL rewriting | **DONE** (validated 2026-03-23) |
| P1-interactive | Chat, speak, screen share, avatar tools | **NEXT** |
| P1-calendar | 5 calendar tools | NEXT |
| P1-webhook | Webhook + transcribe tools | NEXT |
| P1-annotations | Tool annotations for all tools | NEXT |
| P2-resources | MCP Resources with `vexa://` scheme | PLANNED |
| P3-subscriptions | Live transcript via resource subscriptions | PLANNED |
| P3-sampling | Real-time meeting intelligence via sampling | PLANNED |

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | MCP tool call requests (JSON-RPC) | MCP clients | mcp service |
| **rendered** | MCP tool responses (meeting data, transcripts) | mcp service | MCP clients |
| **resources** | Meeting/transcript data via `vexa://` URIs | mcp service | MCP client sidebar |

## How

This is a cross-service feature. Testing requires api-gateway and mcp service running.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Run test suite: `cd features/mcp-integration/tests && make all`
3. Individual suites: `make smoke`, `make test-tools`, `make test-auth`

MCP service runs on port 18898 (direct) or via gateway at :8066/mcp.
Uses Streamable HTTP transport — `Mcp-Session-Id` header required after init.

### Known limitations

- MCP Resources require `mcp` SDK (not supported by `fastapi-mcp` alone) — may need hybrid approach
- Resource subscriptions need WebSocket bridge (P3, not in initial implementation)
- Calendar tools depend on calendar-service being deployed and configured
- Sampling requires client support (Claude Desktop supports it, not all clients do)
- `tools/list` returns 0 tools via gateway proxy — session header may be stripped (bug #3)
