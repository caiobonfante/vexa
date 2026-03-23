# MCP P0 Spec: Pagination + URL Bug

## Items

### 1. list_meetings pagination

**Current behavior:** Returns ALL meetings (211 records, 2.7MB) with zero parameters.

**Expected behavior:**
- Accept `limit` (default 20, max 100), `offset` (default 0)
- Accept `status` filter (active, completed, failed)
- Accept `platform` filter (google_meet, teams, zoom)
- Accept `since` (ISO 8601 datetime, meetings created after)
- Return `{"meetings": [...], "total": N, "limit": L, "offset": O}`

**Test assertions:**
1. `list_meetings` with `limit=5` returns at most 5 meetings
2. `list_meetings` with `limit=5, offset=5` returns different meetings than offset=0
3. Response includes `total` count
4. `list_meetings` with `status=completed` returns only completed meetings
5. Default call (no params) returns at most 20 meetings (not all)

### 2. get_recording_media_download URL fix

**Current behavior:** Returns `http://minio:9000/...` (internal Docker hostname).

**Expected behavior:**
- Download URL is externally accessible (not an internal Docker hostname)
- URL starts with `http://localhost` or the configured gateway URL, not `minio:9000`

**Test assertions:**
1. `get_recording_media_download` URL does not contain `minio:9000`
2. URL is accessible from outside Docker (or proxied through gateway)

## Implementation notes

### list_meetings
- File: `services/mcp/main.py:683-692`
- The MCP endpoint proxies to `GET /meetings` on the gateway
- Gateway proxies to bot-manager's meetings endpoint
- Need to check if bot-manager already supports query params or if we need to add them there too
- If bot-manager doesn't support filtering, add params at bot-manager level first

### get_recording_media_download
- File: `services/mcp/main.py:495-515`
- Already has logic to rewrite relative URLs (line 510-513)
- Bug: `minio:9000` URLs are absolute (start with `http://`) so the relative check (`startswith("/")`) doesn't catch them
- Fix: also rewrite URLs containing internal hostnames (minio, minio:9000)
