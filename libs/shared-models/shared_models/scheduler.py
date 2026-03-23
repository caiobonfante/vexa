"""
Scheduled API call execution via Redis sorted sets.

Schedule HTTP calls for future execution with retry and idempotency.
The executor (scheduler_worker.py) polls for due jobs and fires them.

Usage::

    from shared_models.scheduler import schedule_job, cancel_job, list_jobs

    # Schedule a bot to join a meeting in 5 minutes
    job = await schedule_job(redis, {
        "execute_at": time.time() + 300,
        "request": {
            "method": "POST",
            "url": "http://api-gateway:8000/bots",
            "headers": {"X-API-Key": "vxa_user_..."},
            "body": {"meeting_url": "https://meet.google.com/abc-defg-hij"}
        },
        "idempotency_key": "cal_evt123_bot",
        "metadata": {"source": "calendar", "user_id": 1}
    })
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

JOBS_KEY = "scheduler:jobs"              # Sorted set: score=execute_at, member=job_json
EXECUTING_KEY = "scheduler:executing"    # Hash: job_id -> job_json (in-flight tracking)
HISTORY_KEY = "scheduler:history"        # Hash: job_id -> job_json (completed/failed)
IDEMPOTENCY_PREFIX = "scheduler:idem:"   # String keys for dedup
HISTORY_TTL = 86400 * 7                  # 7 days

DEFAULT_RETRY = {
    "max_attempts": 3,
    "backoff": [30, 120, 300],
    "attempt": 0,
}


def _make_job(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Build a complete job from a user-provided spec."""
    now = time.time()
    execute_at = spec.get("execute_at")
    if isinstance(execute_at, str):
        from datetime import datetime, timezone
        execute_at = datetime.fromisoformat(execute_at).timestamp()
    if execute_at is None:
        raise ValueError("execute_at is required")

    request = spec.get("request")
    if not request or not request.get("url"):
        raise ValueError("request.url is required")

    return {
        "job_id": f"job_{uuid4().hex[:16]}",
        "execute_at": execute_at,
        "created_at": now,
        "status": "pending",
        "request": {
            "method": request.get("method", "POST"),
            "url": request["url"],
            "headers": request.get("headers", {}),
            "body": request.get("body"),
            "timeout": request.get("timeout", 30),
        },
        "retry": {**DEFAULT_RETRY, **(spec.get("retry") or {})},
        "metadata": spec.get("metadata", {}),
        "callback": spec.get("callback", {}),
        "idempotency_key": spec.get("idempotency_key"),
    }


async def schedule_job(redis: Any, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Schedule an API call for future execution.

    Args:
        redis: Async Redis client.
        spec: Job specification with execute_at, request, and optional
            retry/metadata/callback/idempotency_key.

    Returns:
        The created job dict (or existing job if idempotency_key matches).

    Raises:
        ValueError: If required fields are missing.
    """
    job = _make_job(spec)

    # Idempotency check
    idem_key = job.get("idempotency_key")
    if idem_key:
        idem_redis_key = f"{IDEMPOTENCY_PREFIX}{idem_key}"
        existing = await redis.get(idem_redis_key)
        if existing:
            logger.info(f"Scheduler: duplicate idempotency_key={idem_key}, returning existing job")
            return json.loads(existing)
        await redis.set(idem_redis_key, json.dumps(job), ex=HISTORY_TTL)

    job_json = json.dumps(job)
    await redis.zadd(JOBS_KEY, {job_json: job["execute_at"]})
    logger.info(
        f"Scheduler: job {job['job_id']} scheduled for "
        f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(job['execute_at']))} UTC "
        f"[{job['request']['method']} {job['request']['url']}]"
    )
    return job


async def cancel_job(redis: Any, job_id: str) -> Optional[Dict[str, Any]]:
    """Cancel a scheduled job by ID.

    Scans the sorted set for the job and removes it. Returns the job
    if found and cancelled, None if not found.
    """
    # Scan pending jobs
    all_jobs = await redis.zrange(JOBS_KEY, 0, -1)
    for job_json in all_jobs:
        job = json.loads(job_json)
        if job.get("job_id") == job_id:
            removed = await redis.zrem(JOBS_KEY, job_json)
            if removed:
                job["status"] = "cancelled"
                await redis.hset(HISTORY_KEY, job_id, json.dumps(job))
                logger.info(f"Scheduler: job {job_id} cancelled")
                return job
    return None


async def get_job(redis: Any, job_id: str) -> Optional[Dict[str, Any]]:
    """Get a job by ID from pending, executing, or history."""
    # Check executing
    executing = await redis.hget(EXECUTING_KEY, job_id)
    if executing:
        return json.loads(executing)

    # Check history
    history = await redis.hget(HISTORY_KEY, job_id)
    if history:
        return json.loads(history)

    # Check pending (scan sorted set)
    all_jobs = await redis.zrange(JOBS_KEY, 0, -1)
    for job_json in all_jobs:
        job = json.loads(job_json)
        if job.get("job_id") == job_id:
            return job

    return None


async def list_jobs(
    redis: Any,
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List scheduled jobs, optionally filtered by status or metadata source."""
    results = []

    if status is None or status == "pending":
        pending = await redis.zrange(JOBS_KEY, 0, -1)
        for job_json in pending:
            job = json.loads(job_json)
            if source and job.get("metadata", {}).get("source") != source:
                continue
            results.append(job)

    if status is None or status == "executing":
        executing = await redis.hgetall(EXECUTING_KEY)
        for job_json in executing.values():
            job = json.loads(job_json)
            if source and job.get("metadata", {}).get("source") != source:
                continue
            results.append(job)

    # Sort by execute_at
    results.sort(key=lambda j: j.get("execute_at", 0))
    return results[:limit]


async def recover_orphaned_jobs(redis: Any) -> int:
    """Re-queue jobs that were executing when the service crashed.

    Call this on startup. Returns the number of recovered jobs.
    """
    executing = await redis.hgetall(EXECUTING_KEY)
    recovered = 0
    for job_id, job_json in executing.items():
        job = json.loads(job_json)
        job["status"] = "pending"
        # Re-schedule immediately (it was already due)
        await redis.zadd(JOBS_KEY, {json.dumps(job): time.time()})
        await redis.hdel(EXECUTING_KEY, job_id)
        logger.warning(f"Scheduler: recovered orphaned job {job_id}")
        recovered += 1
    return recovered
