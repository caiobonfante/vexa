"""
Background executor that fires scheduled API calls from the Redis sorted set.

Polls ``scheduler:jobs`` every POLL_INTERVAL seconds for due jobs (score <= now),
pops them atomically, fires the HTTP request, handles retries with exponential
backoff, and stores results in history.

Usage (inside a service startup)::

    from shared_models.scheduler_worker import start_executor, stop_executor

    # on startup
    asyncio.create_task(start_executor(redis_client))

    # on shutdown
    await stop_executor()
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

import httpx

from .scheduler import (
    JOBS_KEY,
    EXECUTING_KEY,
    HISTORY_KEY,
    HISTORY_TTL,
    recover_orphaned_jobs,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5   # seconds between polls
REQUEST_TIMEOUT = 30  # default HTTP timeout

_stop_event: Optional[asyncio.Event] = None


async def _fire_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an HTTP request and return result info."""
    method = request.get("method", "POST")
    url = request["url"]
    headers = request.get("headers", {})
    body = request.get("body")
    timeout = request.get("timeout", REQUEST_TIMEOUT)

    start = time.time()
    async with httpx.AsyncClient(follow_redirects=True) as client:
        if body is not None:
            if "Content-Type" not in headers and "content-type" not in headers:
                headers["Content-Type"] = "application/json"
            resp = await client.request(
                method, url,
                headers=headers,
                content=json.dumps(body).encode() if isinstance(body, dict) else body,
                timeout=timeout,
            )
        else:
            resp = await client.request(method, url, headers=headers, timeout=timeout)

    elapsed_ms = int((time.time() - start) * 1000)

    if resp.status_code >= 500 or resp.status_code == 429:
        raise httpx.HTTPStatusError(
            f"Server error {resp.status_code}",
            request=resp.request,
            response=resp,
        )

    return {
        "status_code": resp.status_code,
        "response_time_ms": elapsed_ms,
        "body_preview": resp.text[:200] if resp.text else None,
    }


async def _notify_callback(job: Dict[str, Any], outcome: str) -> None:
    """Fire a callback URL if configured."""
    callback = job.get("callback", {})
    url = callback.get(f"on_{outcome}")
    if not url:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                json={
                    "job_id": job["job_id"],
                    "status": job["status"],
                    "result": job.get("result"),
                    "error": job.get("error"),
                    "metadata": job.get("metadata", {}),
                },
                timeout=10,
            )
    except Exception as e:
        logger.warning(f"Scheduler: callback {outcome} to {url} failed: {e}")


async def _process_job(redis: Any, job_data: str) -> None:
    """Process a single due job."""
    job = json.loads(job_data)
    job_id = job["job_id"]

    # Atomic remove — if another worker already took it, skip
    removed = await redis.zrem(JOBS_KEY, job_data)
    if not removed:
        return

    # Track as executing
    job["status"] = "executing"
    await redis.hset(EXECUTING_KEY, job_id, json.dumps(job))

    request = job["request"]
    retry = job.get("retry", {})

    try:
        result = await _fire_request(request)
        job["status"] = "completed"
        job["result"] = result
        job["completed_at"] = time.time()
        logger.info(
            f"Scheduler: job {job_id} completed — "
            f"{request['method']} {request['url']} → {result['status_code']} "
            f"({result['response_time_ms']}ms)"
        )
        await _notify_callback(job, "success")

    except Exception as e:
        attempt = retry.get("attempt", 0) + 1
        max_attempts = retry.get("max_attempts", 3)
        backoff = retry.get("backoff", [30, 120, 300])

        if attempt < max_attempts:
            # Re-schedule with backoff
            delay = backoff[min(attempt - 1, len(backoff) - 1)]
            job["retry"]["attempt"] = attempt
            job["status"] = "pending"
            next_time = time.time() + delay
            await redis.zadd(JOBS_KEY, {json.dumps(job): next_time})
            logger.warning(
                f"Scheduler: job {job_id} attempt {attempt}/{max_attempts} failed "
                f"({e}), retry in {delay}s"
            )
        else:
            job["status"] = "failed"
            job["error"] = str(e)
            job["failed_at"] = time.time()
            logger.error(
                f"Scheduler: job {job_id} permanently failed after "
                f"{max_attempts} attempts: {e}"
            )
            await _notify_callback(job, "failure")

    # Remove from executing, store in history
    await redis.hdel(EXECUTING_KEY, job_id)
    await redis.hset(HISTORY_KEY, job_id, json.dumps(job))


async def _executor_loop(redis: Any) -> None:
    """Main executor loop — polls for due jobs and processes them."""
    global _stop_event
    _stop_event = asyncio.Event()

    # Recover orphaned jobs from a previous crash
    recovered = await recover_orphaned_jobs(redis)
    if recovered:
        logger.info(f"Scheduler: recovered {recovered} orphaned jobs on startup")

    logger.info(f"Scheduler: executor started (poll every {POLL_INTERVAL}s)")

    while not _stop_event.is_set():
        try:
            now = time.time()
            # Get all due jobs (score <= now)
            due_jobs = await redis.zrangebyscore(JOBS_KEY, "-inf", now)

            for job_data in due_jobs:
                if _stop_event.is_set():
                    break
                await _process_job(redis, job_data)

        except Exception as e:
            logger.error(f"Scheduler: executor loop error: {e}", exc_info=True)

        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=POLL_INTERVAL)
        except asyncio.TimeoutError:
            pass  # normal — poll again


async def start_executor(redis: Any) -> None:
    """Start the scheduler executor as a background task."""
    await _executor_loop(redis)


async def stop_executor() -> None:
    """Signal the executor to stop gracefully."""
    global _stop_event
    if _stop_event:
        _stop_event.set()
        logger.info("Scheduler: executor stop requested")
