# MCP Integration Tests

## Testing approach

MCP integration is a **request/response** feature. The MCP service (fastapi-mcp) auto-generates MCP tools from FastAPI endpoints. Tests send JSON-RPC tool calls through the gateway proxy and validate responses.

### Test types

| Test | What it validates | Needs |
|------|------------------|-------|
| `make smoke` | MCP endpoint reachable (direct + via gateway) | mcp service, api-gateway |
| `make test-proxy` | Gateway proxies /mcp requests correctly | mcp service, api-gateway |
| `make test-tools` | MCP tool calls return valid data | mcp service, api-gateway, postgres |
| `make test-auth` | Auth enforced (401/403 without token) | mcp service, api-gateway |
| `make test-errors` | Error handling (invalid tool, bad JSON-RPC) | mcp service, api-gateway |

### Available MCP tools

Auto-generated from FastAPI endpoints:

| Tool | Endpoint | Description |
|------|----------|-------------|
| `parse_meeting_link` | POST | Parse a meeting URL into platform + meeting ID |
| `request_meeting_bot` | POST /bots | Start a bot in a meeting |
| `get_meeting_transcript` | GET /transcripts/{id} | Get meeting transcript |
| `list_meetings` | GET /meetings | List user's meetings |
| `list_recordings` | GET /recordings | List recordings |
| `get_recording` | GET /recordings/{id} | Get recording details |
| `get_bot_status` | GET /bots | Get running bots |
| `stop_bot` | DELETE /bots/{id} | Stop a running bot |

### How to run

```bash
cd features/mcp-integration/tests

# Setup
cp ../.env.example ../.env  # fill in values

# Run
make smoke           # quick check
make test            # all tests
make test-tools      # just tool calls
```

### MCP protocol

Requests use JSON-RPC 2.0 format:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "parse_meeting_link",
    "arguments": {"meeting_url": "https://meet.google.com/abc-defg-hij"}
  },
  "id": 1
}
```

Auth: `Authorization: Bearer <token>` or `X-API-Key: <token>`

### What to look for

- PASS: MCP service reachable directly and via gateway
- PASS: `parse_meeting_link` returns correct platform for known URL
- PASS: `list_meetings` returns data
- PASS: requests without token are rejected (401/403)
- PASS: nonexistent tools return JSON-RPC error
