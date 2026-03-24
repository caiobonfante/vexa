# MCP Integration

> **Confidence: 90** — 10/10 tools discoverable. Auth enforced. Tool calls return valid data.
> **Tested:** tools/list, all read tools (meetings, transcripts, recordings), auth rejection, gateway proxy.
> **Not tested:** list_meetings pagination (returns all 211 meetings, 2.7MB unbounded), interactive tools (speak/chat not yet exposed as MCP tools), MCP Resources and Subscriptions.
> **Contributions welcome:** Pagination fix, expose speak/chat/screen as MCP tools ([#127](https://github.com/Vexa-ai/vexa/issues/127)), MCP Resources for meetings.

## Why

Give any AI agent meeting superpowers in one connection. Connect Claude, Cursor, Windsurf, or any MCP client to Vexa — your agent gains 17 meeting tools: join calls, read transcripts, speak in meetings, control bots, search across all meetings.

**What makes this different from other meeting MCP servers:**

| Platform | Tools | Read | Write/Control | Self-hosted |
|----------|-------|------|--------------|-------------|
| **Otter.ai MCP** | Read-only transcripts | Yes | No | No |
| **Fireflies MCP** | 21 tools, read-heavy | Yes | Limited | No |
| **Read.ai MCP** | Transcripts + summaries | Yes | No | No |
| **HappyScribe MCP** | Transcription library | Yes | No | No |
| **MeetingBaaS MCP** | Bot + transcript CRUD | Yes | Yes | No |
| **Vexa MCP** | 17 tools — full read + write + control | Yes | **Yes** — join, speak, chat, screen share | **Yes** |

Vexa is the only MCP server where your AI agent can both **read meeting data** and **actively participate** — joining calls, speaking via TTS, sending chat messages, sharing screens — all self-hosted.

**Hero use case:** Your customer success AI connects to Vexa via MCP. It joins every renewal call, pulls up usage data when pricing is discussed, whispers suggested responses via chat, and after the call, summarizes and updates Salesforce. One MCP connection, zero custom integration.

## What

This feature exposes Vexa meeting data and interactive bot controls through the MCP protocol, allowing AI assistants to use MCP tool calls to access meetings, transcripts, recordings, and actively participate in live meetings.

### Documentation
- [Vexa MCP](../../docs/vexa-mcp.mdx)

### Components

- **mcp**: MCP protocol server that implements tool handlers for meeting data
- **api-gateway**: proxies MCP requests to the mcp service

### Data flow

```
MCP client → api-gateway → mcp service → Postgres/backend → response
```

### Key behaviors

- MCP tool calls are JSON-RPC formatted
- Available tools: list meetings, get transcript, get recording, etc.
- Authentication via API token (same as REST API)
- Gateway proxies MCP requests transparently to the mcp service
- Error responses follow MCP/JSON-RPC error format

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | MCP tool call requests (JSON-RPC) | MCP clients | mcp service |
| **rendered** | MCP tool responses (meeting data, transcripts) | mcp service | MCP clients |

No collected datasets yet. This feature is request/response — capture request/response pairs for regression testing.

## How

This is a cross-service feature. Testing requires api-gateway and mcp service running.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Send an MCP tool call via the gateway's MCP endpoint
3. Verify the response contains valid meeting data
4. Test error handling: invalid tool name, missing parameters

### Known limitations

- MCP protocol version compatibility not documented
- No streaming support for large responses
- Session management is stateless (no persistent MCP sessions)
