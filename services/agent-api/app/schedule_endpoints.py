"""Schedule API endpoints — create, list, cancel scheduled jobs.

The agent uses `vexa schedule` CLI which calls these endpoints.
The executor (running in-process) polls Redis and fires jobs when due.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shared_models.scheduler import schedule_job, cancel_job, list_jobs, get_job
from app.auth_simple import require_api_key

logger = logging.getLogger("chat_api.schedule")

router = APIRouter(dependencies=[Depends(require_api_key)])

TRIGGER_URL = "http://telegram-bot:8200/internal/trigger"


class ScheduleRequest(BaseModel):
    user_id: str
    action: str  # "chat" or "run-script"
    message: Optional[str] = None
    script_id: Optional[str] = None
    at: Optional[str] = None  # ISO 8601 UTC
    in_: Optional[str] = None  # relative: "5m", "2h", "1d"
    cron: Optional[str] = None  # cron expression (future)
    idempotency_key: Optional[str] = None

    class Config:
        # Allow "in" as field name from JSON
        populate_by_name = True

    def model_post_init(self, __context):
        # Handle "in" from JSON (reserved keyword in Python)
        pass


def _parse_relative(delay: str) -> float:
    """Parse relative delay like '5m', '2h', '1d', '30s' into seconds from now."""
    match = re.match(r"^(\d+)\s*([smhd])$", delay.strip().lower())
    if not match:
        raise ValueError(f"Invalid relative time: {delay}. Use format like 5m, 2h, 1d, 30s")
    value, unit = int(match.group(1)), match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return time.time() + value * multipliers[unit]


def _resolve_execute_at(req: ScheduleRequest, raw_body: dict) -> float:
    """Resolve execute_at from at/in fields."""
    # Check for "in" field (Python keyword, comes from raw JSON)
    in_value = raw_body.get("in") or req.in_
    if req.at:
        dt = datetime.fromisoformat(req.at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    elif in_value:
        return _parse_relative(in_value)
    else:
        raise ValueError("Either 'at' or 'in' is required")


@router.post("/api/schedule")
async def create_schedule(request: Request):
    """Create a scheduled job."""
    raw_body = await request.json()

    # Parse manually because "in" is a Python keyword
    user_id = raw_body.get("user_id")
    action = raw_body.get("action", "chat")
    message = raw_body.get("message", "")
    script_id = raw_body.get("script_id")
    at = raw_body.get("at")
    in_val = raw_body.get("in")
    idempotency_key = raw_body.get("idempotency_key")

    if not user_id:
        raise HTTPException(400, "user_id is required")

    cron_expr = raw_body.get("cron")

    # Resolve execute_at
    try:
        if at:
            dt = datetime.fromisoformat(at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            execute_at = dt.timestamp()
        elif in_val:
            execute_at = _parse_relative(in_val)
        elif cron_expr:
            from croniter import croniter
            cron = croniter(cron_expr, datetime.now(timezone.utc))
            execute_at = cron.get_next(float)
        else:
            raise ValueError("Either 'at', 'in', or 'cron' is required")
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Build job spec
    req_headers = {"Content-Type": "application/json"}

    if action == "chat":
        url = TRIGGER_URL
        body = {"user_id": user_id, "message": message or "Scheduled reminder"}
    elif action == "meeting":
        bot_api_token = os.getenv("BOT_API_TOKEN", "")
        meeting_config = raw_body.get("meeting_config", {})
        url = "http://bot-manager:8080/bots"
        body = {
            "platform": meeting_config.get("platform", "teams"),
            "native_meeting_id": meeting_config.get("native_meeting_id", ""),
            "meeting_url": meeting_config.get("meeting_url", ""),
            "bot_name": meeting_config.get("bot_name", "Vexa Agent"),
            "transcribe_enabled": True,
            "recording_enabled": True,
        }
        req_headers["X-API-Key"] = bot_api_token
    elif action == "run-script":
        raise HTTPException(501, "run-script not yet implemented")
    else:
        raise HTTPException(400, f"Unknown action: {action}")

    metadata = {"user_id": user_id, "action": action, "source": "vexa_schedule"}
    if cron_expr:
        metadata["cron"] = cron_expr

    redis = request.app.state.redis
    try:
        job = await schedule_job(redis, {
            "execute_at": execute_at,
            "request": {
                "method": "POST",
                "url": url,
                "headers": req_headers,
                "body": body,
                "timeout": 120,
            },
            "metadata": metadata,
            "idempotency_key": idempotency_key,
        })
    except ValueError as e:
        raise HTTPException(400, str(e))

    logger.info(f"Scheduled {action} job {job['job_id']} for user {user_id}")
    return {
        "job_id": job["job_id"],
        "execute_at": job["execute_at"],
        "status": job["status"],
    }


@router.get("/api/schedule")
async def list_schedule(request: Request, user_id: str = None):
    """List scheduled jobs, optionally filtered by user_id."""
    redis = request.app.state.redis
    jobs = await list_jobs(redis, source="vexa_schedule")

    if user_id:
        jobs = [j for j in jobs if j.get("metadata", {}).get("user_id") == user_id]

    return [
        {
            "job_id": j["job_id"],
            "execute_at": j["execute_at"],
            "status": j["status"],
            "action": j.get("metadata", {}).get("action"),
            "message": j.get("request", {}).get("body", {}).get("message", ""),
        }
        for j in jobs
    ]


@router.delete("/api/schedule/{job_id}")
async def cancel_schedule(request: Request, job_id: str):
    """Cancel a scheduled job."""
    redis = request.app.state.redis
    job = await cancel_job(redis, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    logger.info(f"Cancelled job {job_id}")
    return {"job_id": job_id, "status": "cancelled"}
