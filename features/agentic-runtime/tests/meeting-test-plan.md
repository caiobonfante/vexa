# Live Meeting E2E Test Plan

**Date:** 2026-03-24
**Scope:** MVP1 event-driven triggers -- agent joins meeting, gets notified on start/end, processes transcript
**Current score:** 85 (MVP0 PASS, MVP1 implemented but untested live)

---

## Critical Bug Found: Redis Pub/Sub Payload Mismatch

**This MUST be fixed before live testing.** The agent-api Redis subscriber will silently fail to extract any fields from meeting-api events.

### What meeting-api publishes (`publish_meeting_status_change` in services/meeting-api/meeting_api/meetings.py)

```json
{
  "type": "meeting.status",
  "meeting": {"id": 123, "platform": "google_meet", "native_id": "xxx-yyy-zzz"},
  "payload": {"status": "active"},
  "ts": "2026-03-24T10:00:00"
}
```

**Note:** `user_id` is passed as a parameter but is **NOT included in the published JSON payload**.

### What agent-api subscriber expects (agent-api/app/main.py:175-179)

```python
status = data.get("status", "")                        # WRONG: actual path is data["payload"]["status"]
meeting_id = data.get("meeting_id") or data.get("id")  # WRONG: actual path is data["meeting"]["id"]
user_id = str(data.get("user_id", ""))                  # MISSING: not in payload at all
platform = data.get("platform", "unknown")              # WRONG: actual path is data["meeting"]["platform"]
duration_seconds = data.get("duration_seconds", 0)      # MISSING: not in payload
```

### Result

- `status` will always be `""` -- no events match "active" or "completed"
- `user_id` will always be `""` -- guard at line 203 drops the event
- Even if status matched, `meeting_id` would be `None`
- The subscriber will log `Ignoring status= for meeting None` for every event

### Fix required (for implementer)

Either fix the subscriber to read the nested structure:
```python
status = data.get("payload", {}).get("status", "")
meeting_id = data.get("meeting", {}).get("id")
user_id = str(data.get("user_id", ""))  # Still missing from payload!
platform = data.get("meeting", {}).get("platform", "unknown")
```

AND add `user_id` to the meeting-api's publish payload:
```python
payload = {
    "type": "meeting.status",
    "meeting": {"id": meeting_id, "platform": platform, "native_id": native_meeting_id},
    "payload": {"status": new_status},
    "user_id": user_id,  # ADD THIS
    "ts": datetime.utcnow().isoformat()
}
```

Or flatten the meeting-api payload to match what the subscriber expects.

### Second notification path (webhook) works correctly

The POST_MEETING_HOOKS webhook path (`/internal/webhooks/meeting-completed`) receives a different payload format from meeting-api's `post_meeting_hooks.py` via `build_envelope("meeting.completed", {...})` and correctly reads `event.data.meeting.user_id`, `event.data.meeting.id`, etc. **This path should work for meeting-completed events only** (not meeting-started).

---

## Pre-requisites

### 1. Services running (docker compose)

```bash
cd /home/dima/dev/vexa-agentic-runtime/features/agentic-runtime/deploy
docker compose up -d
```

All these must be healthy:

| Service | Internal port | Host port | Health check |
|---------|--------------|-----------|-------------|
| redis | 6379 | 6389 | `redis-cli -p 6389 ping` |
| postgres | 5432 | 5458 | `pg_isready -p 5458` |
| minio | 9000 | 9010 | `curl http://localhost:9010/minio/health/live` |
| agent-api | 8100 | 8100 | `curl http://localhost:8100/health` |
| runtime-api | 8090 | 8090 | `curl http://localhost:8090/health` |
| meeting-api | 8080 | 8070 | `curl http://localhost:8070/` |
| api-gateway | 8000 | 8066 | `curl http://localhost:8066/` |
| admin-api | 8001 | 8067 | `curl http://localhost:8067/` |
| transcription-collector | 8000 | 8060 | `curl http://localhost:8060/health` |

### 2. Environment validation

```bash
bash /home/dima/dev/vexa-agentic-runtime/features/agentic-runtime/deploy/check-env.sh
```

Must pass all checks. Key vars:
- `BOT_API_TOKEN` -- must match across agent-api, runtime-api, and dashboard
- `CLAUDE_CREDENTIALS_PATH` and `CLAUDE_JSON_PATH` -- host files must exist
- `TRANSCRIPTION_SERVICE_URL` -- external transcription service must be reachable
- `ADMIN_TOKEN` -- must match between meeting-api and admin-api

### 3. Docker images built

```bash
# Agent container image (use immutable YYMMDD-HHMM tags)
docker build -t vexaai/vexa-agent:$(date +%y%m%d-%H%M) -f containers/agent/Dockerfile .

# Bot container image
docker build -t vexaai/vexa-bot:$(date +%y%m%d-%H%M) -f services/vexa-bot/Dockerfile .
```

### 4. Database migrated

The `db-migrate` service in compose runs `alembic upgrade head` automatically. Verify:
```bash
docker compose logs db-migrate
# Should show "Running upgrade ... -> ..."
```

### 5. User exists in database

The recorder bot must use user_id=5 (2280905@gmail.com) per project convention. Verify:
```bash
docker exec vexa-agentic-postgres-1 psql -U postgres -d vexa_agentic -c "SELECT id, email FROM users WHERE id=5;"
```

If no user exists, create one via admin-api.

### 6. Meeting URL ready

Create a Google Meet (or Teams/Zoom) meeting URL. Have a second browser/device ready to be in the meeting as a real participant.

---

## Test Plan

### Phase 0: Verify Redis Pub/Sub wiring (before live meeting)

**Purpose:** Confirm meeting-api publishes to Redis and agent-api subscribes, independent of a real meeting.

```bash
# Terminal 1: Watch agent-api logs for subscriber activity
docker logs -f vexa-agentic-agent-api-1 2>&1 | grep -i "meeting status"

# Terminal 2: Manually publish a test event to Redis
docker exec vexa-agentic-redis-1 redis-cli PUBLISH "bm:meeting:999:status" '{"type":"meeting.status","meeting":{"id":999,"platform":"google_meet","native_id":"test"},"payload":{"status":"active"},"user_id":"5","ts":"2026-03-24T10:00:00"}'
```

**Expected (after bug fix):** agent-api logs show `Meeting status event: meeting=999 user=5 status=active platform=google_meet`

**Expected (before bug fix):** agent-api logs show `Ignoring status= for meeting None` (confirming the bug)

### Phase 1: Join meeting via agent chat

**Purpose:** Verify agent can use vexa CLI to join a meeting.

```bash
# Send chat message to agent asking it to join
TOKEN="<BOT_API_TOKEN from deploy/.env>"
curl -X POST http://localhost:8100/api/chat \
  -H "X-API-Key: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "5",
    "message": "Join this Google Meet: https://meet.google.com/xxx-yyy-zzz and wait until active"
  }'
```

**Expected behavior:**
1. Agent container starts (or reuses existing)
2. Agent reads system CLAUDE.md, knows `vexa meeting join` command
3. Agent runs: `vexa meeting join --platform google_meet --url https://meet.google.com/xxx-yyy-zzz`
4. Agent runs: `vexa meeting wait-active --platform google_meet --id xxx-yyy-zzz`
5. Bot appears in meeting within ~15s

**Verification:**
```bash
# Check meeting-api for active meetings
curl http://localhost:8070/bots/status -H "X-API-Key: $TOKEN"

# Check Redis for meeting status publications
docker exec vexa-agentic-redis-1 redis-cli SUBSCRIBE "bm:meeting:*:status"
# (Note: SUBSCRIBE blocks; use PSUBSCRIBE pattern in a monitoring terminal)
```

**Watch for:**
- Bot container starts (check `docker ps | grep vexa-bot`)
- Bot-manager logs show joining/active transitions
- Agent-api logs show meeting status subscriber events

### Phase 2: Verify "meeting started" notification (Redis path)

**Purpose:** Confirm agent-api wakes the agent when meeting goes active.

```bash
# Watch agent-api logs
docker logs -f vexa-agentic-agent-api-1 2>&1 | grep -E "meeting|agent.*woken|wake"
```

**Expected (after bug fix):**
- Log: `Meeting status event: meeting={id} user=5 status=active platform=google_meet`
- Log: `Agent woken for user=5 meeting={id}`
- Agent receives message: "Meeting {id} (google_meet) just started..."

**Risk:** If bug is not fixed, this step will silently fail. The subscriber will log the event but not match "active" status.

**Note:** meeting-api publishes status changes to Redis; agent-api subscribes.

### Phase 3: Meeting in progress -- verify transcription

**Purpose:** Confirm live transcript is accessible during the meeting.

```bash
# From host, check transcription segments
curl http://localhost:8060/internal/transcripts/{meeting_id} -H "X-API-Key: $TOKEN"

# Or via agent chat
curl -X POST http://localhost:8100/api/chat \
  -H "X-API-Key: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "5",
    "message": "Check the meeting status and read the latest transcript"
  }'
```

**Expected:** Agent uses `vexa meeting transcript {meeting_id}` to fetch segments.

### Phase 4: End meeting -- verify "meeting completed" notification

**Purpose:** Test both notification paths fire when meeting ends.

1. End the meeting (leave from the real participant side, or stop via API)
2. Watch both notification paths:

```bash
# Path A: Redis pub/sub subscriber (agent-api logs)
docker logs -f vexa-agentic-agent-api-1 2>&1 | grep -E "completed|webhook|wake"

# Path B: POST_MEETING_HOOKS webhook (agent-api logs)
# Should see: "Internal meeting-completed webhook: meeting {id} for user {user_id}"
```

**Expected:**
- Meeting-api detects meeting end, publishes `completed` status to Redis
- Meeting-api fires POST_MEETING_HOOKS to `http://agent-api:8100/internal/webhooks/meeting-completed`
- Agent-api receives BOTH notifications (Redis sub + webhook)
- Agent is woken with processing instructions
- Agent fetches transcript, summarizes, saves to workspace

**Key difference between the two paths:**
- Redis path: fires for both `active` and `completed` status changes. Currently broken (payload mismatch). Published by meeting-api.
- Webhook path: fires only on `completed`. Should work correctly (uses `build_envelope` with structured `data.meeting` payload). Sent by meeting-api.

### Phase 5: Verify post-meeting processing

**Purpose:** Confirm agent actually processes the transcript.

```bash
# Check agent's workspace for output files
CONTAINER=$(docker ps --filter "name=vexa-agent" --format "{{.Names}}" | head -1)
docker exec $CONTAINER ls -la /workspace/knowledge/meetings/
docker exec $CONTAINER cat /workspace/knowledge/meetings/*.md
```

**Expected:** Agent creates meeting summary with:
- Key points
- Action items
- Decisions
- Timeline entries

---

## Known Gaps and Risks

### Critical (blocks test)

1. **Redis pub/sub payload mismatch** (described above) -- the Redis subscriber path will silently fail. The webhook path should work for `completed` only.

### High risk

2. **No `user_id` in Redis payload** -- even after fixing the field extraction, `user_id` is not included in meeting-api's publish payload. The subscriber guard at line 203 (`if not user_id`) will drop the event. Must be added to the payload in meeting-api.

3. **Duplicate notifications** -- both Redis subscriber AND webhook fire on meeting completion. The agent may receive two "meeting ended" messages and process twice. Need to add deduplication or disable one path.

4. **`duration_seconds` not in Redis payload** -- the subscriber reads `data.get("duration_seconds", 0)` but this field doesn't exist in meeting-api's published JSON. Will always show "0s" duration.

### Medium risk

5. **Agent container may not exist** -- `_wake_agent` calls `_run_chat_turn` which calls `cm.ensure_container()`. If no container exists, it creates one. But the new container has no session context. The agent will not know the meeting history unless it reads workspace files.

6. **Bot admission** -- Google Meet may require the real participant to admit the bot. Status will be `awaiting_admission`, which the subscriber ignores. If not admitted, the test stalls.

7. **Transcription service external dependency** -- `TRANSCRIPTION_SERVICE_URL` points to an external service. If it's down, transcription works (live segments via bot) but post-meeting processing may fail.

### Low risk

8. **Session reuse** -- if the agent already has an active session from a previous chat, the meeting notification arrives in that session's context. This is fine but means the agent already has prior conversation context.

---

## Monitoring Commands

Run these in separate terminals during the test:

```bash
# Terminal 1: Agent API logs (subscriber events + webhook + agent wakeups)
docker logs -f vexa-agentic-agent-api-1 2>&1

# Terminal 2: Meeting API logs (meeting lifecycle, status publishes)
docker logs -f vexa-agentic-meeting-api-1 2>&1

# Terminal 3: Redis pub/sub monitor (see all messages)
docker exec vexa-agentic-redis-1 redis-cli -p 6379 PSUBSCRIBE "bm:meeting:*"

# Terminal 4: Agent container logs (Claude CLI output)
AGENT_CONTAINER=$(docker ps --filter "name=vexa-agent" --format "{{.Names}}" | head -1)
docker logs -f $AGENT_CONTAINER 2>&1
```

---

## Summary

| Step | What | Depends on | Risk |
|------|------|-----------|------|
| Phase 0 | Redis pub/sub wiring test | Bug fix | CRITICAL -- test first |
| Phase 1 | Agent joins meeting via chat | Services running, bot image built | Medium (bot admission) |
| Phase 2 | Meeting-started notification | Phase 0 bug fix | HIGH (payload mismatch) |
| Phase 3 | Live transcript access | Phase 1 | Low |
| Phase 4 | Meeting-completed notification | Meeting ends naturally | HIGH (dual notification) |
| Phase 5 | Post-meeting processing | Phase 4 | Medium (container state) |

**Recommendation:** Fix the Redis payload mismatch in meeting-api first, then run Phase 0 to validate the fix, then proceed with live testing. The webhook path (`/internal/webhooks/meeting-completed`) can serve as fallback for the completed event even without the Redis fix, but the "meeting started" notification has no fallback.
