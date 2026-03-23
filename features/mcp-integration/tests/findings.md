# MCP Integration Test Findings

## Gate verdict: PASS (10/10)

## Test run: 2026-03-23 (post-rebuild)

All tests pass against rebuilt containers. P0 fixes (pagination + URL rewrite) validated live.

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| MCP reachable via gateway | 90 | HTTP 200 on GET /mcp | 2026-03-23 (live) | — |
| Session initialization | 90 | Mcp-Session-Id returned, 17 tools discoverable | 2026-03-23 (live) | — |
| parse_meeting_link | 90 | Returns `google_meet` for GMeet URL | 2026-03-23 (live) | — |
| list_meetings returns data | 90 | Returns meeting records | 2026-03-23 (live) | — |
| list_meetings pagination | 90 | `limit=5` returns exactly 5 meetings | 2026-03-23 (live, rebuilt) | — |
| Recording download URL | 90 | Returns `http://api-gateway:8000/...` (no minio:9000) | 2026-03-23 (live, rebuilt) | — |
| Auth enforcement | 80 | Invalid token returns error in tool result | 2026-03-23 (live) | Test 401 at HTTP level |
| Error handling | 90 | Nonexistent tool returns `isError=true` | 2026-03-23 (live) | — |
| 17 tools discoverable | 90 | tools/list returns 17 tools with session | 2026-03-23 (live) | — |
| Invalid JSON-RPC | 90 | Returns -32602 validation error | 2026-03-23 (live) | — |

## How to reproduce

```bash
cd features/mcp-integration/tests
make test   # 10 PASS, 0 FAIL
```

## P0 fixes validated

1. **list_meetings pagination** — `limit`, `offset`, `status`, `platform` params work end-to-end (MCP → gateway → collector → DB)
2. **get_recording_media_download** — internal `minio:9000` URLs rewritten to gateway URLs

## Next steps
- P1 spec: expose chat/speak as MCP tools, add `search_meetings`
- P2: MCP Resources for meetings/transcripts
