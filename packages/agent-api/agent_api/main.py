"""Agent Runtime — generic AI agent runtime.

Containers are ephemeral — they can die at any time. State lives in Redis
(sessions) and S3 (workspaces). If a container dies mid-chat, the next
message recreates it seamlessly.
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import redis.asyncio as aioredis

from agent_api import config
from agent_api.auth import require_api_key
from agent_api.chat import (
    clear_session,
    delete_session_meta,
    list_sessions,
    run_chat_turn,
    save_session_meta,
)
from agent_api.container_manager import ContainerManager
from agent_api import scheduler
from agent_api import workspace

logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("agent_api")

app = FastAPI(title="Agent Runtime", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in config.CORS_ORIGINS],
    allow_methods=["*"],
    allow_headers=["*"],
)

cm = ContainerManager()


# ── Request / response models ──────────────────────────────────────────────


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None
    session_name: Optional[str] = None
    model: Optional[str] = None


class UserIdRequest(BaseModel):
    user_id: str


class SessionCreateRequest(BaseModel):
    user_id: str
    name: str = "New session"


class SessionRenameRequest(BaseModel):
    user_id: str
    name: str


class ScheduleRequest(BaseModel):
    execute_at: Optional[str] = None  # ISO 8601 UTC
    delay: Optional[str] = None  # relative: "5m", "2h", "1d"
    request: dict  # {method, url, headers?, body?, timeout?}
    metadata: Optional[dict] = None
    idempotency_key: Optional[str] = None
    cron: Optional[str] = None


class FileWriteRequest(BaseModel):
    user_id: str
    path: str
    content: str


# ── Lifecycle ──────────────────────────────────────────────────────────────


@app.on_event("startup")
async def startup():
    app.state.redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    logger.info("Redis connected")

    # Scheduler executor (recover_orphaned_jobs runs inside the executor loop)
    app.state.executor_task = asyncio.create_task(
        scheduler.start_executor(app.state.redis)
    )
    logger.info("Scheduler executor started")

    await cm.startup()
    logger.info(f"Agent Runtime ready on port {config.PORT}")


@app.on_event("shutdown")
async def shutdown():
    await scheduler.stop_executor()
    await cm.shutdown()
    await app.state.redis.close()


# ── Health ─────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "containers": len(cm._containers)}


# ── Chat endpoints ─────────────────────────────────────────────────────────


@app.post("/api/chat", dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    """Send a message to the agent. Returns SSE stream.
    Retries once with a fresh container if the first attempt fails."""

    async def generate():
        retries = 0
        max_retries = 1
        while retries <= max_retries:
            try:
                async for data in run_chat_turn(
                    app.state.redis, cm,
                    req.user_id, req.message, req.model,
                    req.session_id, req.session_name,
                ):
                    yield data
                return
            except Exception as e:
                retries += 1
                if retries <= max_retries:
                    logger.warning(f"Chat failed for {req.user_id}, retrying ({retries}/{max_retries}): {e}")
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
    """Interrupt an in-progress chat turn."""
    await cm.interrupt(req.user_id)
    return {"status": "interrupted"}


@app.post("/api/chat/reset", dependencies=[Depends(require_api_key)])
async def reset_chat(req: UserIdRequest):
    """Reset the chat session (keeps workspace files)."""
    await cm.reset_session(req.user_id)
    await clear_session(app.state.redis, req.user_id)
    return {"status": "reset"}


# ── Session management ─────────────────────────────────────────────────────


@app.get("/api/sessions", dependencies=[Depends(require_api_key)])
async def get_sessions(user_id: str):
    """List all sessions for a user."""
    sessions = await list_sessions(app.state.redis, user_id)
    return {"sessions": sessions}


@app.post("/api/sessions", dependencies=[Depends(require_api_key)])
async def create_session(req: SessionCreateRequest):
    """Create a new named session."""
    session_id = str(uuid.uuid4())
    await save_session_meta(app.state.redis, req.user_id, session_id, req.name)
    return {"session_id": session_id, "name": req.name}


@app.delete("/api/sessions/{session_id}", dependencies=[Depends(require_api_key)])
async def delete_session(session_id: str, user_id: str):
    """Delete a session from the index."""
    await delete_session_meta(app.state.redis, user_id, session_id)
    return {"status": "deleted"}


@app.put("/api/sessions/{session_id}", dependencies=[Depends(require_api_key)])
async def rename_session(session_id: str, req: SessionRenameRequest):
    """Rename a session."""
    await save_session_meta(app.state.redis, req.user_id, session_id, req.name)
    return {"status": "renamed", "name": req.name}


# ── Scheduling ─────────────────────────────────────────────────────────────


def _parse_relative_delay(delay: str) -> float:
    """Parse relative delay like '5m', '2h', '1d' into seconds from now."""
    match = re.match(r"^(\d+)\s*([smhd])$", delay.strip().lower())
    if not match:
        raise ValueError(f"Invalid relative time: {delay}. Use format like 5m, 2h, 1d, 30s")
    value, unit = int(match.group(1)), match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return time.time() + value * multipliers[unit]


@app.post("/api/schedule", dependencies=[Depends(require_api_key)])
async def create_schedule(req: ScheduleRequest):
    """Schedule an HTTP request for future execution."""
    try:
        if req.execute_at:
            dt = datetime.fromisoformat(req.execute_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            execute_at = dt.timestamp()
        elif req.delay:
            execute_at = _parse_relative_delay(req.delay)
        elif req.cron:
            from croniter import croniter
            cron = croniter(req.cron, datetime.now(timezone.utc))
            execute_at = cron.get_next(float)
        else:
            raise ValueError("Either 'execute_at', 'delay', or 'cron' is required")
    except ValueError as e:
        raise HTTPException(400, str(e))

    metadata = req.metadata or {}
    if req.cron:
        metadata["cron"] = req.cron

    job = await scheduler.schedule_job(app.state.redis, {
        "execute_at": execute_at,
        "request": req.request,
        "metadata": metadata,
        "idempotency_key": req.idempotency_key,
    })

    return {
        "job_id": job["job_id"],
        "execute_at": job["execute_at"],
        "status": job["status"],
    }


@app.get("/api/schedule", dependencies=[Depends(require_api_key)])
async def list_schedule(source: Optional[str] = None):
    """List scheduled jobs."""
    jobs = await scheduler.list_jobs(app.state.redis, source=source)
    return [
        {
            "job_id": j["job_id"],
            "execute_at": j["execute_at"],
            "status": j["status"],
            "metadata": j.get("metadata", {}),
        }
        for j in jobs
    ]


@app.delete("/api/schedule/{job_id}", dependencies=[Depends(require_api_key)])
async def cancel_schedule(job_id: str):
    """Cancel a scheduled job."""
    job = await scheduler.cancel_job(app.state.redis, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return {"job_id": job_id, "status": "cancelled"}


# ── Workspace endpoints ────────────────────────────────────────────────────


@app.get("/api/workspace/files", dependencies=[Depends(require_api_key)])
async def list_workspace_files(user_id: str):
    """List files in the user's workspace."""
    container = cm.get_container_name(user_id)
    if not container:
        raise HTTPException(404, f"No container for user {user_id}")
    ws = config.WORKSPACE_PATH
    raw = await cm.exec_simple(container, [
        "sh", "-c",
        f"cd {ws} && find . -not -path './.git/*' -not -path './.git' "
        "-not -name '.gitkeep' -type f | sort",
    ])
    if not raw:
        return {"files": []}
    files = [f.lstrip("./") for f in raw.strip().split("\n") if f.strip()]
    return {"files": files}


@app.get("/api/workspace/file", dependencies=[Depends(require_api_key)])
async def get_workspace_file(user_id: str, path: str):
    """Get file content from workspace."""
    _validate_path(path)
    container = cm.get_container_name(user_id)
    if not container:
        raise HTTPException(404, f"No container for user {user_id}")
    content = await cm.exec_simple(container, ["cat", f"{config.WORKSPACE_PATH}/{path}"])
    return {"path": path, "content": content or ""}


@app.post("/api/workspace/file", dependencies=[Depends(require_api_key)])
async def put_workspace_file(req: FileWriteRequest):
    """Write a file to the workspace."""
    _validate_path(req.path)
    container = cm.get_container_name(req.user_id)
    if not container:
        raise HTTPException(404, f"No container for user {req.user_id}")

    import base64 as b64
    parent = os.path.dirname(req.path)
    ws = config.WORKSPACE_PATH
    if parent:
        await cm.exec_simple(container, ["mkdir", "-p", f"{ws}/{parent}"])
    encoded = b64.b64encode(req.content.encode()).decode()
    await cm.exec_with_stdin(
        container,
        ["sh", "-c", f"base64 -d > {ws}/{req.path}"],
        stdin_data=encoded.encode(),
    )
    return {"path": req.path, "status": "written"}


@app.post("/internal/workspace/save", dependencies=[Depends(require_api_key)])
async def workspace_save(req: UserIdRequest):
    """Sync workspace from container to S3."""
    container = cm.get_container_name(req.user_id)
    if not container:
        raise HTTPException(404, f"No container for user {req.user_id}")
    ok = await workspace.sync_up(req.user_id, container)
    if not ok:
        raise HTTPException(500, "Workspace sync failed")
    return {"status": "saved"}


@app.get("/internal/workspace/status", dependencies=[Depends(require_api_key)])
async def workspace_status(user_id: str):
    """Check workspace and container status."""
    exists = await workspace.workspace_exists(user_id)
    container = cm.get_container_name(user_id)
    return {
        "user_id": user_id,
        "workspace_in_storage": exists,
        "container_running": container is not None,
    }


# ── Helpers ────────────────────────────────────────────────────────────────

_SAFE_PATH = re.compile(r"^[a-zA-Z0-9._/\-]+$")


def _validate_path(path: str) -> str:
    """Validate a workspace file path."""
    if not path or ".." in path or path.startswith("/") or not _SAFE_PATH.match(path):
        raise HTTPException(400, "Invalid path")
    return path
