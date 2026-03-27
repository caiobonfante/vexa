"""Vexa Agent API — message in, agent response out.

Containers are ephemeral — they can die at any time. State lives in Redis
(sessions) and MinIO (workspaces). If a container dies mid-chat, the next
message recreates it seamlessly.
"""

import asyncio
import base64
import json
import logging
import os
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import redis.asyncio as aioredis

from app.container_manager import ContainerManager
from app.stream_parser import parse_event
from app.workspace_context import build_workspace_context
from app.schedule_endpoints import router as schedule_router
from app.workspace_endpoints import router as workspace_router, set_container_manager
from app.auth_simple import require_api_key
from app import config

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("agent_api")

app = FastAPI(title="Vexa Agent API", version="0.2.0")

from admin_models.security_headers import SecurityHeadersMiddleware

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schedule_router)
app.include_router(workspace_router)

cm = ContainerManager()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
SESSION_PREFIX = "agent:session:"
SESSIONS_INDEX = "agent:sessions:"  # hash of session_id -> metadata JSON


# --- Session in Redis (survives container death) ---

async def get_session(user_id: str, session_id: Optional[str] = None) -> Optional[str]:
    """Get Claude CLI session ID. If session_id provided, look up that specific session."""
    if session_id:
        return session_id  # Client provides the session UUID directly
    return await app.state.redis.get(f"{SESSION_PREFIX}{user_id}")


async def save_session(user_id: str, session_id: str):
    await app.state.redis.set(f"{SESSION_PREFIX}{user_id}", session_id, ex=86400 * 7)


async def clear_session(user_id: str):
    await app.state.redis.delete(f"{SESSION_PREFIX}{user_id}")


async def list_sessions(user_id: str) -> list[dict]:
    """List all sessions for a user from Redis index."""
    data = await app.state.redis.hgetall(f"{SESSIONS_INDEX}{user_id}")
    sessions = []
    for sid, meta_json in data.items():
        try:
            meta = json.loads(meta_json)
            meta["id"] = sid
            sessions.append(meta)
        except json.JSONDecodeError:
            sessions.append({"id": sid, "name": sid[:8]})
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


async def save_session_meta(user_id: str, session_id: str, name: str):
    """Save/update session metadata in Redis index."""
    import time
    existing = await app.state.redis.hget(f"{SESSIONS_INDEX}{user_id}", session_id)
    meta = json.loads(existing) if existing else {"created_at": time.time()}
    meta["name"] = name
    meta["updated_at"] = time.time()
    await app.state.redis.hset(f"{SESSIONS_INDEX}{user_id}", session_id, json.dumps(meta))
    await app.state.redis.expire(f"{SESSIONS_INDEX}{user_id}", 86400 * 30)  # 30 day TTL


async def delete_session_meta(user_id: str, session_id: str):
    """Remove a session from the index."""
    await app.state.redis.hdel(f"{SESSIONS_INDEX}{user_id}", session_id)


# --- Startup / Shutdown ---

@app.on_event("startup")
async def startup():
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    logger.info("Redis connected")

    from runtime_api.scheduler import recover_orphaned_jobs, _executor_loop
    recovered = await recover_orphaned_jobs(app.state.redis)
    if recovered:
        logger.info(f"Recovered {recovered} orphaned jobs")
    app.state.executor_task = asyncio.create_task(_executor_loop(app.state.redis))
    logger.info("Scheduler executor started")

    await cm.startup()
    set_container_manager(cm)

    # Subscribe to bot-manager meeting status events via Redis Pub/Sub
    app.state.meeting_subscriber_task = asyncio.create_task(_meeting_status_subscriber())
    logger.info("Meeting status subscriber started")

    logger.info(f"Agent API ready on port {config.CHAT_API_PORT}")


@app.on_event("shutdown")
async def shutdown():
    from runtime_api.scheduler import stop_executor
    await stop_executor()
    if hasattr(app.state, "meeting_subscriber_task"):
        app.state.meeting_subscriber_task.cancel()
        try:
            await app.state.meeting_subscriber_task
        except asyncio.CancelledError:
            pass
    await cm.shutdown()
    await app.state.redis.close()


# --- Redis Pub/Sub: meeting status events from bot-manager ---

async def _meeting_status_subscriber():
    """Subscribe to bm:meeting:*:status channel pattern from bot-manager.

    bot-manager publishes ALL meeting status transitions there. We wake the
    user's agent on 'active' (meeting started) and 'completed' (meeting ended).
    Other statuses (joining, awaiting_admission, failed) are logged but ignored
    to avoid noisy agent interruptions.
    """
    # Use a dedicated Redis connection for blocking pubsub — don't share with main client
    pubsub_redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = pubsub_redis.pubsub()
    await pubsub.psubscribe("bm:meeting:*:status")
    logger.info("Subscribed to bm:meeting:*:status pattern")

    try:
        async for message in pubsub.listen():
            if message["type"] not in ("pmessage", "message"):
                continue

            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                logger.debug(f"Non-JSON meeting status message: {message['data']!r}")
                continue

            status = data.get("payload", {}).get("status", "")
            meeting_id = data.get("meeting", {}).get("id")
            user_id = str(data.get("user_id", ""))
            platform = data.get("meeting", {}).get("platform", "unknown")
            duration_seconds = data.get("duration_seconds", 0)

            logger.info(f"Meeting status event: meeting={meeting_id} user={user_id} status={status} platform={platform}")

            if status == "active":
                message_text = (
                    f"Meeting {meeting_id} ({platform}) just started. "
                    f"You've joined and are transcribing. "
                    f"Use `vexa meeting status --platform {platform} --id {meeting_id}` to check state, "
                    f"`vexa meeting transcript {meeting_id}` to read what's been said."
                )
            elif status == "completed":
                mins = duration_seconds // 60
                secs = duration_seconds % 60
                duration_str = f"{mins}m{secs}s" if mins else f"{secs}s"
                message_text = (
                    f"Meeting {meeting_id} ({platform}) just ended (duration: {duration_str}). "
                    f"Fetch the transcript with `vexa meeting transcript {meeting_id}` and summarize the key points."
                )
            else:
                # joining, awaiting_admission, failed — too noisy, skip
                logger.debug(f"Ignoring status={status} for meeting {meeting_id}")
                continue

            if not user_id or not meeting_id:
                logger.warning(f"Meeting status event missing user_id or meeting_id: {data}")
                continue

            # Fire-and-forget: wake the agent in the background
            asyncio.create_task(_wake_agent(user_id, meeting_id, message_text))

    except asyncio.CancelledError:
        logger.info("Meeting status subscriber cancelled")
    except Exception as e:
        logger.error(f"Meeting status subscriber crashed: {e}", exc_info=True)
    finally:
        await pubsub.punsubscribe("bm:meeting:*:status")
        await pubsub_redis.close()


async def _wake_agent(user_id: str, meeting_id: str, message: str):
    """Wake user's agent with the given message. Silently no-ops if no container exists."""
    try:
        async for _ in _run_chat_turn(user_id, message):
            pass  # consume the stream; we don't forward it
        logger.info(f"Agent woken for user={user_id} meeting={meeting_id}")
    except Exception as e:
        logger.warning(f"Agent wakeup failed for user={user_id} meeting={meeting_id}: {e}")


# --- Models ---

class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None  # Claude CLI session UUID (omit for default)
    session_name: Optional[str] = None  # Human-readable name for new sessions
    model: Optional[str] = None
    bot_token: Optional[str] = None  # User's API token for bot-manager calls


class UserIdRequest(BaseModel):
    user_id: str


# --- Core chat logic ---

async def _run_chat_turn(user_id: str, message: str, model: Optional[str] = None,
                         bot_token: Optional[str] = None, session_id: Optional[str] = None,
                         session_name: Optional[str] = None):
    """Run a single chat turn. Yields SSE data strings.
    If container dies, raises exception — caller can retry."""

    cm._new_container = False
    container = await cm.ensure_container(user_id, bot_token=bot_token)

    # If a user-specific bot token was provided, write it to the container
    # so vexa CLI reads it for bot-manager calls (meetings belong to this user)
    if bot_token:
        await cm.exec_with_stdin(container,
            ["sh", "-c", "cat > /tmp/.vexa-bot-token"],
            stdin_data=bot_token.encode(),
        )

    # Signal frontend if container was recreated (stale messages should be cleared)
    if cm._new_container:
        yield f"data: {json.dumps({'type': 'session_reset', 'reason': 'Container was recreated. Previous session context is no longer available.'})}\n\n"

    # Session from Redis — but skip if container was just recreated
    # (session IDs are tied to Claude CLI processes, not portable across containers)
    if not cm._new_container:
        session_id = await get_session(user_id, session_id)
        # Validate session file exists in container (stale IDs cause silent failures)
        if session_id:
            check = await cm.exec_simple(container, [
                "sh", "-c", f"test -f /root/.claude/projects/-workspace/{session_id}.jsonl && echo OK || echo MISSING"
            ])
            if check and "MISSING" in check:
                logger.warning(f"Session {session_id[:12]} not found in container, starting fresh")
                await clear_session(user_id)
                session_id = None
    else:
        session_id = None

    # Workspace context injection
    ws_context = await build_workspace_context(cm.exec_simple, container)
    full_prompt = f"{ws_context}\n\n---\n\n{message}"
    encoded = base64.b64encode(full_prompt.encode()).decode()
    await cm.exec_with_stdin(container,
        ["sh", "-c", "base64 -d > /tmp/.chat-prompt.txt"],
        stdin_data=encoded.encode(),
    )

    # Claude CLI command
    allowed_tools = "Read,Write,Edit,Bash,Glob,Grep"
    parts = [
        "claude",
        "--verbose", "--output-format", "stream-json",
        "--allowedTools", f"'{allowed_tools}'",
    ]
    if session_id:
        parts.extend(["--resume", session_id])
    if model:
        parts.extend(["--model", model])
    parts.extend(["-p", '"$(cat /tmp/.chat-prompt.txt)"'])
    cmd = f"cd /workspace && {' '.join(parts)}"

    logger.info(f"Chat for {user_id} (session={session_id or 'new'}, model={model or 'default'})")

    proc = await cm.exec_stream(container, cmd)
    new_session_id = None
    buffer = b""

    try:
        async for chunk in proc.stdout:
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue

                for event in parse_event(parsed):
                    if event.get("type") == "done" and event.get("session_id"):
                        new_session_id = event["session_id"]
                    yield f"data: {json.dumps(event)}\n\n"

        # Remaining buffer
        if buffer.strip():
            try:
                parsed = json.loads(buffer.strip())
                for event in parse_event(parsed):
                    if event.get("type") == "done" and event.get("session_id"):
                        new_session_id = event["session_id"]
                    yield f"data: {json.dumps(event)}\n\n"
            except json.JSONDecodeError:
                pass
    finally:
        await proc.wait()

    # Save session to Redis (not /tmp)
    if new_session_id:
        await save_session(user_id, new_session_id)
        await save_session_meta(user_id, new_session_id, session_name or f"Session {new_session_id[:8]}")
        logger.info(f"Session saved to Redis: {new_session_id[:12]}... for {user_id}")

    yield f"data: {json.dumps({'type': 'stream_end', 'session_id': new_session_id or session_id})}\n\n"


# --- Endpoints ---

@app.get("/health")
async def health():
    return {"status": "ok", "containers": len(cm._containers)}


@app.post("/api/chat", dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    """Send a message to Claude inside an agent container. Returns SSE stream.
    If container dies mid-stream, retries once with a fresh container."""

    async def generate():
        retries = 0
        max_retries = 1

        while retries <= max_retries:
            try:
                async for data in _run_chat_turn(req.user_id, req.message, req.model, req.bot_token, req.session_id, req.session_name):
                    yield data
                return  # Success
            except Exception as e:
                retries += 1
                if retries <= max_retries:
                    logger.warning(f"Chat failed for {req.user_id}, retrying ({retries}/{max_retries}): {e}")
                    # Invalidate cached container — force fresh one
                    cm._containers.pop(req.user_id, None)
                    yield f"data: {json.dumps({'type': 'reconnecting'})}\n\n"
                else:
                    logger.error(f"Chat failed for {req.user_id} after {max_retries} retries: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete("/api/chat", dependencies=[Depends(require_api_key)])
async def interrupt_chat(req: UserIdRequest):
    await cm.interrupt(req.user_id)
    return {"status": "interrupted"}


@app.post("/api/chat/reset", dependencies=[Depends(require_api_key)])
async def reset_chat(req: UserIdRequest):
    await cm.reset_session(req.user_id)
    await clear_session(req.user_id)
    return {"status": "reset"}


# --- Session management endpoints ---

@app.get("/api/sessions", dependencies=[Depends(require_api_key)])
async def get_sessions(user_id: str):
    """List all sessions for a user."""
    sessions = await list_sessions(user_id)
    return {"sessions": sessions}


@app.post("/api/sessions", dependencies=[Depends(require_api_key)])
async def create_session(user_id: str, name: str = "New session"):
    """Create a new named session. Returns the session_id (UUID)."""
    import uuid
    session_id = str(uuid.uuid4())
    await save_session_meta(user_id, session_id, name)
    return {"session_id": session_id, "name": name}


@app.delete("/api/sessions/{session_id}", dependencies=[Depends(require_api_key)])
async def delete_session(session_id: str, user_id: str):
    """Delete a session from the index."""
    await delete_session_meta(user_id, session_id)
    return {"status": "deleted"}


@app.put("/api/sessions/{session_id}", dependencies=[Depends(require_api_key)])
async def rename_session(session_id: str, user_id: str, name: str):
    """Rename a session."""
    await save_session_meta(user_id, session_id, name)
    return {"status": "renamed", "name": name}


# --- Webhook receiver (called by bot-manager post-meeting hooks) ---

@app.post("/api/webhooks/meeting-completed", dependencies=[Depends(require_api_key)])
async def on_meeting_completed(event: dict, background_tasks: BackgroundTasks):
    """Receive meeting.completed webhook from bot-manager POST_MEETING_HOOKS.
    Wakes the user's agent with a message to process the meeting."""
    data = event.get("data", {}).get("meeting", {})
    user_id = str(data.get("user_id", ""))
    meeting_id = data.get("id")
    platform = data.get("platform", "unknown")
    duration = data.get("duration_seconds", 0)

    if not user_id or not meeting_id:
        raise HTTPException(400, "Missing user_id or meeting id in event")

    message = (
        f"Meeting {meeting_id} ({platform}) ended after {duration // 60}m{duration % 60}s. "
        f"Process it now:\n"
        f"1. Fetch transcript: `vexa meeting transcript {meeting_id}`\n"
        f"2. For each person with a clear role: create/update `knowledge/entities/contacts/{{first-last}}.md`\n"
        f"3. For each company/org mentioned: create/update `knowledge/entities/companies/{{name}}.md`\n"
        f"4. Write meeting minutes: `knowledge/meetings/YYYY-MM-DD-{meeting_id}.md` (replace YYYY-MM-DD with today)\n"
        f"5. Write action items: `knowledge/action-items/YYYY-MM-DD-{meeting_id}.md` (replace YYYY-MM-DD with today)\n"
        f"6. Update `timeline.md` with any dates, deadlines, or future events\n"
        f"7. Run `vexa workspace save`\n"
        f"Reply with a 2-sentence summary when done."
    )

    logger.info(f"Meeting completed webhook: meeting {meeting_id} for user {user_id}")

    # Fire-and-forget: run the chat turn in background so we return 200 immediately
    async def _process():
        try:
            async for _ in _run_chat_turn(user_id, message):
                pass  # consume the stream, we don't need to deliver it
        except Exception as e:
            logger.error(f"Post-meeting processing failed for meeting {meeting_id}: {e}")

    background_tasks.add_task(_process)
    return {"status": "accepted", "meeting_id": meeting_id}


@app.post("/internal/webhooks/meeting-completed")
async def on_meeting_completed_internal(event: dict, background_tasks: BackgroundTasks):
    """Internal (no-auth) meeting-completed webhook for bot-manager post_meeting_hooks.

    post_meeting_hooks.py delivers without X-API-Key (it's internal traffic).
    This endpoint accepts the same payload as the authenticated version without
    requiring the header, since all callers are internal services on the Docker
    network and cannot reach this endpoint from outside.
    """
    data = event.get("data", {}).get("meeting", {})
    user_id = str(data.get("user_id", ""))
    meeting_id = data.get("id")
    platform = data.get("platform", "unknown")
    duration = data.get("duration_seconds", 0)

    if not user_id or not meeting_id:
        raise HTTPException(400, "Missing user_id or meeting id in event")

    message = (
        f"Meeting {meeting_id} ({platform}) ended after {duration // 60}m{duration % 60}s. "
        f"Process it now:\n"
        f"1. Fetch transcript: `vexa meeting transcript {meeting_id}`\n"
        f"2. For each person with a clear role: create/update `knowledge/entities/contacts/{{first-last}}.md`\n"
        f"3. For each company/org mentioned: create/update `knowledge/entities/companies/{{name}}.md`\n"
        f"4. Write meeting minutes: `knowledge/meetings/YYYY-MM-DD-{meeting_id}.md` (replace YYYY-MM-DD with today)\n"
        f"5. Write action items: `knowledge/action-items/YYYY-MM-DD-{meeting_id}.md` (replace YYYY-MM-DD with today)\n"
        f"6. Update `timeline.md` with any dates, deadlines, or future events\n"
        f"7. Run `vexa workspace save`\n"
        f"Reply with a 2-sentence summary when done."
    )

    logger.info(f"Internal meeting-completed webhook: meeting {meeting_id} for user {user_id}")

    async def _process():
        try:
            async for _ in _run_chat_turn(user_id, message):
                pass
        except Exception as e:
            logger.error(f"Post-meeting processing failed for meeting {meeting_id}: {e}")

    background_tasks.add_task(_process)
    return {"status": "accepted", "meeting_id": meeting_id}


# --- Internal endpoints (called by vexa CLI inside containers) ---

@app.post("/internal/workspace/save", dependencies=[Depends(require_api_key)])
async def workspace_save(req: UserIdRequest):
    from app import workspace_sync
    container = cm.get_container_name(req.user_id)
    if not container:
        raise HTTPException(404, f"No container for user {req.user_id}")
    ok = await workspace_sync.sync_up(req.user_id, container)
    if not ok:
        raise HTTPException(500, "Workspace sync failed")
    return {"status": "saved"}


@app.get("/internal/workspace/status", dependencies=[Depends(require_api_key)])
async def workspace_status(user_id: str):
    from app import workspace_sync
    exists = await workspace_sync.workspace_exists(user_id)
    container = cm.get_container_name(user_id)
    return {
        "user_id": user_id,
        "workspace_in_storage": exists,
        "container_running": container is not None,
    }
