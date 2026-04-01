# Meeting-Aware Agent — Implementation Changes

Applied to containers (images built and running), need to be re-committed to branch.

## File 1: services/agent-api/agent_api/chat.py

### Change 1: save_session_meta accepts meeting_aware param
```python
# BEFORE:
async def save_session_meta(redis, user_id: str, session_id: str, name: str):

# AFTER:
async def save_session_meta(redis, user_id: str, session_id: str, name: str, *, meeting_aware: bool | None = None):
    """Save/update session metadata in Redis index."""
    import time
    existing = await redis.hget(f"{SESSIONS_INDEX}{user_id}", session_id)
    meta = json.loads(existing) if existing else {"created_at": time.time()}
    meta["name"] = name
    meta["updated_at"] = time.time()
    if meeting_aware is not None:
        meta["meeting_aware"] = meeting_aware
    await redis.hset(f"{SESSIONS_INDEX}{user_id}", session_id, json.dumps(meta))
    await redis.expire(f"{SESSIONS_INDEX}{user_id}", 86400 * 30)
```

### Change 2: New function get_session_meta
```python
async def get_session_meta(redis, user_id: str, session_id: str) -> dict | None:
    """Get session metadata from Redis index."""
    raw = await redis.hget(f"{SESSIONS_INDEX}{user_id}", session_id)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return None
```

## File 2: services/agent-api/agent_api/main.py

### Change 1: Import get_session_meta
```python
from agent_api.chat import (
    clear_session,
    delete_session_meta,
    get_session_meta,  # NEW
    list_sessions,
    run_chat_turn,
    save_session_meta,
)
```

### Change 2: SessionCreateRequest gets meeting_aware field
```python
class SessionCreateRequest(BaseModel):
    user_id: str
    name: str = "New session"
    meeting_aware: bool = False  # NEW
```

### Change 3: create_session passes meeting_aware
```python
@app.post("/api/sessions", dependencies=[Depends(require_api_key)])
async def create_session(req: SessionCreateRequest):
    """Create a new named session."""
    session_id = str(uuid.uuid4())
    await save_session_meta(
        app.state.redis, req.user_id, session_id, req.name,
        meeting_aware=req.meeting_aware,
    )
    return {"session_id": session_id, "name": req.name, "meeting_aware": req.meeting_aware}
```

### Change 4: chat endpoint reads X-Meeting-Context header
```python
@app.post("/api/chat", dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest, request: Request):
    """Send a message to the agent. Returns SSE stream.
    Retries once with a fresh container if the first attempt fails."""

    # Parse meeting context from gateway-injected header
    meeting_context = ""
    raw_ctx = request.headers.get("x-meeting-context")
    if raw_ctx:
        try:
            ctx = json.loads(raw_ctx)
            meeting_context = _format_meeting_context(ctx)
        except (json.JSONDecodeError, KeyError):
            logger.warning("Invalid X-Meeting-Context header, ignoring")

    async def generate():
        retries = 0
        max_retries = 1
        while retries <= max_retries:
            try:
                async for data in run_chat_turn(
                    app.state.redis, cm,
                    req.user_id, req.message, req.model,
                    req.session_id, req.session_name,
                    context_prefix=meeting_context,
                ):
                    yield data
                return
    # ... rest unchanged
```

### Change 5: _format_meeting_context helper
```python
def _format_meeting_context(ctx: dict) -> str:
    """Format meeting context JSON into a human-readable system prompt prefix."""
    meetings = ctx.get("active_meetings", [])
    if not meetings:
        return ""

    parts = ["You have access to the user's active meetings. Here is the current meeting context:\n"]

    for m in meetings:
        mid = m.get("meeting_id", "unknown")
        platform = m.get("platform", "unknown")
        status = m.get("status", "unknown")
        participants = m.get("participants", [])

        parts.append(f"## Meeting {mid} ({platform}, {status})")
        if participants:
            parts.append(f"Participants: {', '.join(participants)}")

        segments = m.get("latest_segments", [])
        if segments:
            parts.append(f"\nLatest transcript ({len(segments)} segments):")
            for seg in segments[-50:]:
                speaker = seg.get("speaker", "Unknown")
                text = seg.get("text", "")
                ts = seg.get("timestamp", "")
                parts.append(f"  [{ts}] {speaker}: {text}")
        parts.append("")

    parts.append("Use this meeting context to answer the user's questions. "
                 "Reference specific discussion points, speakers, and topics from the transcript.")
    return "\n".join(parts)
```

## File 3: services/api-gateway/main.py

### Change 1: Add AGENT_API_URL env var
```python
AGENT_API_URL = os.getenv("AGENT_API_URL")  # Optional — agent-api for AI chat
```

### Change 2: Add StreamingResponse import
```python
from fastapi.responses import HTMLResponse, StreamingResponse
```

### Change 3: Add _build_meeting_context function + all agent-api proxy routes
(~170 lines of new code between the delete meeting route and user profile routes)

Key components:
- `_build_meeting_context()`: Checks Redis for session meeting_aware flag, fetches /bots/status, fetches /transcripts/{platform}/{id} for each active bot, builds context JSON
- `POST /api/chat`: Streaming proxy with meeting context injection
- `DELETE /api/chat`, `POST /api/chat/reset`: Simple proxy
- `GET/POST/PUT/DELETE /api/sessions`: Simple proxy routes

### Change 4: Compose file
```yaml
# deploy/compose/docker-compose.yml - add to api-gateway environment:
- AGENT_API_URL=${AGENT_API_URL:-}
```

## Deployment

Gateway container: `vexa-restore-api-gateway-new` (running with AGENT_API_URL=http://172.24.0.1:8100)
Agent-api container: `agent-api-live` (running with updated code)
Both images built from worktree code before worktree was deleted.
