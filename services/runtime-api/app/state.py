"""Container status tracking in Redis.

Stores container metadata so Runtime API can list/query containers
without hitting Docker API every time. Reconciles with Docker on startup.
"""

import json
import logging
import time
from typing import Optional

logger = logging.getLogger("runtime_api.state")

KEY_PREFIX = "runtime:container:"
STOPPED_TTL = 86400  # 24h for stopped/failed entries


async def set_container(redis, name: str, data: dict):
    """Store container metadata."""
    data["updated_at"] = time.time()
    await redis.set(f"{KEY_PREFIX}{name}", json.dumps(data))
    logger.debug(f"State set: {name} -> {data.get('status')}")


async def get_container(redis, name: str) -> Optional[dict]:
    """Get container metadata."""
    raw = await redis.get(f"{KEY_PREFIX}{name}")
    if raw:
        return json.loads(raw)
    return None


async def delete_container(redis, name: str):
    """Remove container from state."""
    await redis.delete(f"{KEY_PREFIX}{name}")


async def set_stopped(redis, name: str, status: str = "stopped"):
    """Mark container as stopped/failed with TTL."""
    data = await get_container(redis, name) or {}
    data["status"] = status
    data["stopped_at"] = time.time()
    await redis.set(f"{KEY_PREFIX}{name}", json.dumps(data), ex=STOPPED_TTL)


async def list_containers(redis, user_id: str = None, profile: str = None) -> list[dict]:
    """List all tracked containers, optionally filtered."""
    results = []
    async for key in redis.scan_iter(f"{KEY_PREFIX}*"):
        raw = await redis.get(key)
        if not raw:
            continue
        data = json.loads(raw)
        if user_id and data.get("user_id") != user_id:
            continue
        if profile and data.get("profile") != profile:
            continue
        data["name"] = key.replace(KEY_PREFIX, "")
        results.append(data)
    return results
