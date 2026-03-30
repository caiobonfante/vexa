# Mission

Focus: Browser session resolution — "not found or expired" for active sessions
Problem: Dashboard at /meetings/{id} shows "Browser session not found or expired" while the bot is actively running. The VNC iframe fails to load because the session token can't be resolved.
Target: Browser session token is always resolvable for any active bot, regardless of how the dashboard fetches meeting data
Stop-when: root causes identified, all related gaps cataloged, fix design validated, DoD defined

## Symptom

Dashboard URL `/meetings/12` shows `{"detail":"Browser session not found or expired"}` in the VNC iframe area, despite the bot container being active and healthy.

## Known Root Cause (from initial research)

The dashboard merges two data sources for meetings:
1. `GET /bots/status` (meeting-api) — has `data.session_token`
2. `GET /meetings` (transcription-collector) — does NOT have `data.session_token`

If the meeting data comes from the wrong source, or the merge loses the `session_token` field, `browser-session-view.tsx:68` gets `undefined` and the VNC iframe URL is broken.

Additionally:
- Redis key `browser_session:{token}` has 24h TTL (`meetings.py:581`) — can expire while bot is still active
- No TTL refresh mechanism exists
- Gateway `resolve_browser_session()` returns None silently on any failure

## Research Needed

1. **Dashboard data merge logic** — exactly how does `[...path]/route.ts` merge bots/status and /meetings? When does session_token get lost?
2. **Redis TTL lifecycle** — are there bots that run >24h? Is TTL ever refreshed? What happens when it expires?
3. **Token resolution fallbacks** — could the gateway resolve by meeting_id when session_token fails?
4. **Other consumers of browser_session Redis keys** — who else reads/writes them? VNC proxy, CDP proxy, save endpoint, storage delete?
5. **Error handling gaps** — does the dashboard show a useful error or just break silently?
6. **Race conditions** — can the dashboard render before the Redis key is written? (Initial research says no for browser_session mode, but what about regular meeting bots that gain VNC via escalation?)
7. **Related gaps in READMEs** — do any docs describe this flow incorrectly?

## Frozen Contracts

- Redis key pattern `browser_session:{token}` — used by gateway, meeting-api, dashboard
- `/b/{token}` gateway routes — external API contract
- `bm:meeting:{id}:status` Redis channel prefix — frozen

## Research Findings

### 1. Complete Data Flow Trace

**Browser session creation** (`POST /bots` with `mode: "browser_session"`):
1. `meetings.py:530` — generates `session_token = secrets.token_urlsafe(24)`
2. `meetings.py:531-538` — creates Meeting in DB with `data={"mode": "browser_session", "session_token": session_token}`
3. `meetings.py:562-568` — spawns container via runtime-api with `BOT_CONFIG` containing session_token
4. `meetings.py:580-582` — writes TWO Redis keys, both with 24h TTL:
   - `browser_session:{session_token}` → `{container_name, meeting_id, user_id}`
   - `browser_session:{meeting_id}` → same payload

**Dashboard fetches meeting list** (`GET /api/vexa/meetings`):
1. `[...path]/route.ts:26-86` — proxy merges two sources:
   - Source A: `GET /bots/status` (meeting-api) → `_get_running_bots_from_runtime()` (`meetings.py:311-398`)
     - Enriches container list with DB data: `meeting_data = meeting.data or {}` (line 372)
     - Returns `data: meeting_data` which includes `session_token` from DB ✓
   - Source B: `GET /meetings` (transcription-collector) — only for meetings NOT in Source A
   - Merge logic: Source A bots added first with `seenIds`, Source B skips duplicates
2. `route.ts:50` — maps `data: b.data || {}` for each bot

**Dashboard renders meeting detail** (`/meetings/{id}`):
1. `meetings-store.ts:155-191` — `fetchMeeting(id)` calls `getMeetings()` (fetches ALL meetings), finds by ID
2. `api.ts:91-94` — `getMeetings()` → `GET /api/vexa/meetings` → `mapMeeting()` preserves `data` field
3. `[id]/page.tsx:825` — if `data.mode === "browser_session"` → renders `BrowserSessionView`
4. `browser-session-view.tsx:68` — reads `meeting.data?.session_token`
5. `browser-session-view.tsx:91` — builds VNC URL: `/b/${token}/vnc/vnc.html?...`

**Gateway resolves VNC request** (`GET /b/{token}/vnc/...`):
1. `main.py:1427-1449` — `resolve_browser_session(token)`: reads `browser_session:{token}` from Redis
2. If found → extracts `container_name` → proxies to `http://{container_name}:6080/...`
3. If not found → returns `404 "Browser session not found or expired"`

**Regular meeting bot creation** (`POST /bots` with platform):
1. `meetings.py:780-786` — spawns container
2. `meetings.py:814-820` — writes Redis key `browser_session:{meeting_id}` with 24h TTL
3. Dashboard Browser View toggle (`[id]/page.tsx:832-835`) uses `/b/${meetingId}/vnc/...` → works ✓

**Bot escalation** (`needs_human_help` callback):
1. `escalation.ts:43-49` — `triggerEscalation()`: starts VNC stack, calls `callNeedsHumanHelpCallback()`
2. `escalation.ts:56-77` — `startVncStack()`: spawns x11vnc + websockify on :6080. Does NOT write Redis keys.
3. `unified-callback.ts:21-27` — sends status_change callback with status "needs_human_help"
4. `callbacks.py:345-369` — writes escalation data to meeting.data:
   ```python
   d["escalation"] = {"reason": ..., "escalated_at": ..., "vnc_url": f"/b/{meeting.id}"}
   ```
5. `callbacks.py:362-367` — writes Redis key `browser_session:{meeting.id}` with **1-hour TTL** (not 24h!)

### 2. Gaps Found

**GAP-1 (CRITICAL): No Redis TTL refresh for active sessions**
- `meetings.py:581-582` sets `ex=86400` (24h) at creation. No code anywhere refreshes this TTL.
- Browser sessions running >24h will have their Redis keys expire while the container is still active.
- The VNC iframe will fail with 404 "Browser session not found or expired".
- Regular meeting bot keys (`meetings.py:819`, `ex=86400`) also expire after 24h.
- **Affected files**: `meetings.py:581-582`, `meetings.py:819`

**GAP-2 (HIGH): Escalation VNC button broken for regular meeting bots**
- Dashboard (`[id]/page.tsx:1688-1689`) reads:
  ```typescript
  const sessionToken = escalation?.session_token as string || currentMeeting.data?.session_token as string;
  ```
- But escalation data (`callbacks.py:353-357`) contains `{reason, escalated_at, vnc_url}` — NO `session_token` field.
- For regular meeting bots, `currentMeeting.data?.session_token` is also `undefined` (only browser_sessions have it).
- Result: `sessionToken` is `undefined` → `if (!sessionToken) return null` → VNC button never renders.
- The Browser View toggle at `[id]/page.tsx:832-835` DOES work (uses `meetingId` directly), but the escalation banner's "Open Remote Browser" button is dead.
- **Affected files**: `callbacks.py:353-357` (missing `session_token` field), `[id]/page.tsx:1688-1689`

**GAP-3 (HIGH): Escalation Redis key has only 1-hour TTL**
- `callbacks.py:366` uses `ex=3600` (1 hour).
- Escalation grants 5 extra minutes (`escalation.ts:83-84`), but the user may not respond for longer.
- If the escalation Redis key expires while the user is trying to help, VNC breaks mid-intervention.
- Should be at least equal to the bot's remaining lifetime + buffer.
- **Affected file**: `callbacks.py:366`

**GAP-4 (MEDIUM): No Redis key cleanup on bot exit**
- `callbacks.py:90-188` (exit callback) updates meeting status and persists chat, but does NOT delete Redis keys:
  - `browser_session:{session_token}` (browser_session mode)
  - `browser_session:{meeting_id}` (all modes)
- Stale keys linger until TTL (up to 24h). If a new meeting reuses the same ID (unlikely but possible with auto-increment), it could resolve to a dead container.
- **Affected file**: `callbacks.py:90-188`

**GAP-5 (MEDIUM): Silent failures in proxy merge**
- `route.ts:55` and `route.ts:83` have empty `catch {}` blocks.
- If `/bots/status` fails: active meetings are invisible. If `/meetings` fails: only active bots shown.
- No logging, no error indication to the user. The meeting list silently drops entries.
- **Affected file**: `route.ts:55`, `route.ts:83`

**GAP-6 (MEDIUM): Gateway doesn't check container health**
- `resolve_browser_session()` (`main.py:1427-1449`) only checks Redis. Does NOT verify the container is alive.
- If container crashed but Redis key hasn't expired → gateway returns `502 "Failed to reach browser container"`.
- Dashboard shows this as a generic error in the iframe, no specific "container dead" message.
- **Affected file**: `main.py:1427-1449`

**GAP-7 (LOW): No dedicated `/meetings/{id}` endpoint**
- `fetchMeeting(id)` fetches ALL meetings then filters (`meetings-store.ts:155-170`).
- Wasteful for users with many meetings. Creates a race condition where the merge might produce different data on each poll.
- **Affected file**: `meetings-store.ts:155-170`

**GAP-8 (LOW): Bot escalation design.md describes Redis write from bot, but implementation writes from callback**
- `features/bot-escalation/design.md:169` says "Bot writes `browser_session:{token}` to Redis"
- Actual implementation: bot does NOT write to Redis. `callbacks.py:362-367` writes it on the meeting-api side after receiving the status_change callback.
- Doc is misleading but the implementation is correct (centralized Redis writes are better).
- **Affected file**: `features/bot-escalation/design.md`

### 3. Fix Design

**Fix for GAP-1 (TTL refresh):**
Add a periodic TTL refresh. Two options:
- **Option A (recommended)**: In `_get_running_bots_from_runtime()` (`meetings.py:311-398`), after confirming a container is running, refresh the Redis TTL for `browser_session:{meeting_id}`. This piggybacks on the existing status polling, so no new cron/background task needed.
- **Option B**: Add a background task in meeting-api that scans active meetings and refreshes TTLs every 6h.

**Fix for GAP-2 (escalation session_token):**
In `callbacks.py:353-357`, add `session_token` to the escalation data:
```python
d["escalation"] = {
    "reason": escalation_reason,
    "escalated_at": escalated_at,
    "session_token": str(meeting.id),  # matches the Redis key
    "vnc_url": f"/b/{meeting.id}",
}
```

**Fix for GAP-3 (escalation TTL):**
Change `callbacks.py:366` from `ex=3600` to `ex=86400` (match the standard TTL).

**Fix for GAP-4 (cleanup on exit):**
In `callbacks.py` exit callback, after updating status, delete Redis keys:
```python
if redis_client:
    session_token = (meeting.data or {}).get("session_token")
    if session_token:
        await redis_client.delete(f"browser_session:{session_token}")
    await redis_client.delete(f"browser_session:{meeting.id}")
```

**Fix for GAP-5 (silent failures):**
Add logging to the empty catch blocks in `route.ts`:
```typescript
} catch (e) {
  console.error("[proxy] /bots/status failed:", e);
}
```

**Fix for GAP-6 (container health):**
In `resolve_browser_session()`, optionally ping the container's health endpoint. Or: return the container_name in the error so the dashboard can show "Container unreachable" vs "Session expired".

### 4. Historical Context

Git log shows browser_session was introduced as first-class meetings in commit `0ed6c379`, with subsequent fixes for VNC (`fa533ef2`), data merging (`65d4c3ac`), and session sync (`bc889d4e`). No prior reports of the TTL expiry issue — likely because most sessions run <24h. The escalation VNC button issue (GAP-2) appears to have been broken since the escalation feature was added — the design doc describes the session_token field but the implementation omits it.

## DoD (refined)

### Reproduction
1. Create a browser_session via `POST /bots` with `mode: "browser_session"`
2. Navigate to `/meetings/{id}` — VNC should load ✓
3. Wait >24h (or manually `DEL browser_session:{token}` in Redis)
4. Reload `/meetings/{id}` — VNC iframe shows "Browser session not found or expired"

### Fix Verification
- [ ] VNC iframe loads for browser_session meetings (active bot, <24h)
- [ ] VNC iframe loads for browser_session meetings (active bot, >24h — TTL refreshed)
- [ ] VNC iframe shows clear error when session is genuinely stopped (not "not found")
- [ ] Redis keys cleaned up when bot exits (verify with `redis-cli keys "browser_session:*"` after stop)
- [ ] Escalation "Open Remote Browser" button renders for escalated regular meeting bots
- [ ] Escalation VNC works for >1h (TTL increased)
- [ ] Proxy route logs errors when /bots/status or /meetings fails (check dashboard server logs)
- [ ] curl `/b/{token}` returns 404 after bot exits (key cleaned up)
- [ ] curl `/b/{meeting_id}/vnc/vnc.html` returns 200 for active regular meeting bot
