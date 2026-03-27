# MCP Integration

> **Confidence: 0** — RESET after architecture refactoring. Gateway auth flow changed (header injection). MCP tool calls route through modified gateway. Needs re-validation.
> **Tested:** tools/list, all read tools (meetings, transcripts, recordings), auth rejection, gateway proxy.
> **Not tested:** list_meetings pagination (returns all 211 meetings, 2.7MB unbounded), interactive tools (speak/chat not yet exposed as MCP tools), MCP Resources and Subscriptions.
> **Contributions welcome:** Pagination fix, expose speak/chat/screen as MCP tools ([#127](https://github.com/Vexa-ai/vexa/issues/127)), MCP Resources for meetings.

## Why

MCP server exposing 17 meeting tools to AI agents (Claude, Cursor, Windsurf). Unlike other meeting MCP servers (Otter, Fireflies, Read.ai — all read-only SaaS), this provides full read + write + control (join, speak, chat, screen share) and is self-hosted.

**Design decision:** Other meeting MCP servers proxy read-only data. Vexa exposes interactive controls as tools — agents can actively participate in meetings, not just query transcripts.

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
