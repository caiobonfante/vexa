"""SSE chat streaming via container exec.

Routes user messages to an AI agent CLI running inside a container.
Streams the response back as Server-Sent Events.
"""

import base64
import json
import logging
from typing import AsyncGenerator, Optional

from agent_api import config
from agent_api.container_manager import ContainerManager
from agent_api.stream_parser import parse_event

logger = logging.getLogger("agent_api.chat")

# Redis key prefixes for session state
SESSION_PREFIX = "agent:session:"
SESSIONS_INDEX = "agent:sessions:"


# --- Session helpers (Redis-backed) ---

async def get_session(redis, user_id: str, session_id: Optional[str] = None) -> Optional[str]:
    """Get agent CLI session ID from Redis."""
    if session_id:
        return session_id
    return await redis.get(f"{SESSION_PREFIX}{user_id}")


async def save_session(redis, user_id: str, session_id: str):
    """Save session ID to Redis with 7-day TTL."""
    await redis.set(f"{SESSION_PREFIX}{user_id}", session_id, ex=86400 * 7)


async def clear_session(redis, user_id: str):
    """Clear session ID from Redis."""
    await redis.delete(f"{SESSION_PREFIX}{user_id}")


async def list_sessions(redis, user_id: str) -> list[dict]:
    """List all sessions for a user from Redis index."""
    data = await redis.hgetall(f"{SESSIONS_INDEX}{user_id}")
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


async def save_session_meta(redis, user_id: str, session_id: str, name: str):
    """Save/update session metadata in Redis index."""
    import time
    existing = await redis.hget(f"{SESSIONS_INDEX}{user_id}", session_id)
    meta = json.loads(existing) if existing else {"created_at": time.time()}
    meta["name"] = name
    meta["updated_at"] = time.time()
    await redis.hset(f"{SESSIONS_INDEX}{user_id}", session_id, json.dumps(meta))
    await redis.expire(f"{SESSIONS_INDEX}{user_id}", 86400 * 30)


async def delete_session_meta(redis, user_id: str, session_id: str):
    """Remove a session from the index."""
    await redis.hdel(f"{SESSIONS_INDEX}{user_id}", session_id)


# --- Core chat turn ---

async def run_chat_turn(
    redis,
    cm: ContainerManager,
    user_id: str,
    message: str,
    model: Optional[str] = None,
    session_id: Optional[str] = None,
    session_name: Optional[str] = None,
    context_prefix: str = "",
) -> AsyncGenerator[str, None]:
    """Run a single chat turn. Yields SSE data strings.

    Args:
        redis: Async Redis client.
        cm: Container manager instance.
        user_id: User identifier.
        message: User message text.
        model: Optional model override.
        session_id: Optional specific session to resume.
        session_name: Human-readable name for new sessions.
        context_prefix: Optional text prepended to the prompt (workspace context, etc).
    """
    cm._new_container = False
    container = await cm.ensure_container(user_id)

    # Signal frontend if container was recreated
    if cm._new_container:
        yield f"data: {json.dumps({'type': 'session_reset', 'reason': 'Container was recreated. Previous session context is no longer available.'})}\n\n"

    # Session from Redis — skip if container was just recreated
    if not cm._new_container:
        session_id = await get_session(redis, user_id, session_id)
        if session_id:
            check = await cm.exec_simple(container, [
                "sh", "-c",
                f"test -f /root/.claude/projects/-workspace/{session_id}.jsonl && echo OK || echo MISSING",
            ])
            if check and "MISSING" in check:
                logger.warning(f"Session {session_id[:12]} not found in container, starting fresh")
                await clear_session(redis, user_id)
                session_id = None
    else:
        session_id = None

    # Build prompt (with optional context prefix)
    full_prompt = f"{context_prefix}\n\n---\n\n{message}" if context_prefix else message
    encoded = base64.b64encode(full_prompt.encode()).decode()
    await cm.exec_with_stdin(
        container,
        ["sh", "-c", "base64 -d > /tmp/.chat-prompt.txt"],
        stdin_data=encoded.encode(),
    )

    # Agent CLI command
    cli = config.AGENT_CLI
    allowed_tools = config.AGENT_ALLOWED_TOOLS
    parts = [
        cli,
        "--verbose", "--output-format", "stream-json",
        "--allowedTools", f"'{allowed_tools}'",
    ]
    if session_id:
        parts.extend(["--resume", session_id])
    if model or config.DEFAULT_MODEL:
        parts.extend(["--model", model or config.DEFAULT_MODEL])
    parts.extend(["-p", '"$(cat /tmp/.chat-prompt.txt)"'])

    workspace = config.WORKSPACE_PATH
    cmd = f"cd {workspace} && {' '.join(parts)}"

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

    # Save session to Redis
    if new_session_id:
        await save_session(redis, user_id, new_session_id)
        await save_session_meta(
            redis, user_id, new_session_id,
            session_name or f"Session {new_session_id[:8]}",
        )
        logger.info(f"Session saved: {new_session_id[:12]}... for {user_id}")

    yield f"data: {json.dumps({'type': 'stream_end', 'session_id': new_session_id or session_id})}\n\n"
