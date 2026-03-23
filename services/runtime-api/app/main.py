"""Runtime API — single authority for container lifecycle.

Creates, tracks, and manages containers of all profiles (agent, browser, meeting).
Doesn't know about workspaces or meetings — those are Agent API and Meeting API concerns.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import config, state
from app.docker_ops import (
    close_session,
    create_container,
    get_container_state,
    get_mapped_ports,
    get_session,
    list_containers as docker_list,
    remove_container,
    start_container,
    stop_container,
)
from app.profiles import get_profile

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("runtime_api")

app = FastAPI(title="Vexa Runtime API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---


class CreateContainerRequest(BaseModel):
    user_id: str
    profile: str  # agent, browser, meeting
    config: dict = {}


# --- Startup / Shutdown ---


@app.on_event("startup")
async def startup():
    app.state.redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    logger.info("Redis connected")

    # Verify Docker connection
    get_session()
    logger.info("Docker connected")

    # Reconcile state: discover existing managed containers
    await _reconcile_state()

    # Start idle checker
    app.state.idle_task = asyncio.create_task(_idle_loop())
    logger.info("Runtime API ready")


@app.on_event("shutdown")
async def shutdown():
    if hasattr(app.state, "idle_task"):
        app.state.idle_task.cancel()
    close_session()
    await app.state.redis.close()


# --- Endpoints ---


@app.get("/health")
async def health():
    containers = await state.list_containers(app.state.redis)
    running = sum(1 for c in containers if c.get("status") == "running")
    return {"status": "ok", "containers": len(containers), "running": running}


@app.post("/containers", status_code=201)
async def create(req: CreateContainerRequest):
    """Create and start a container."""
    profile_def = get_profile(req.profile)
    user_config = req.config

    # Generate container name
    if req.profile == "agent":
        # Agent: one per user (deterministic name)
        name = f"vexa-agent-{req.user_id}"
        # Check if already exists and running
        existing = await state.get_container(app.state.redis, name)
        if existing and existing.get("status") == "running":
            docker_state = get_container_state(name)
            if docker_state == "running":
                return _container_response(name, existing)
            # State says running but Docker disagrees — fix state
    else:
        # Browser/meeting/worker: unique name with UUID
        suffix = uuid.uuid4().hex[:8]
        name = f"vexa-{req.profile}-{req.user_id}-{suffix}"

    # Build environment variables
    env = {
        "VEXA_USER_ID": req.user_id,
        **(user_config.get("env") or {}),
    }

    # Profile-specific env
    if req.profile == "browser":
        env["BOT_MODE"] = "browser_session"
        env["DISPLAY"] = ":99"
        # Build BOT_CONFIG for browser_session mode
        bot_config = {
            "mode": "browser_session",
            "redisUrl": "redis://redis:6379/0",
            "container_name": name,
        }
        # S3/MinIO config for browser profile persistence
        s3_path = user_config.get("s3_path")
        if s3_path:
            s3_endpoint = config.MINIO_ENDPOINT
            if not s3_endpoint.startswith("http"):
                s3_endpoint = f"http://{s3_endpoint}"
            bot_config.update({
                "userdataS3Path": s3_path,
                "s3Endpoint": s3_endpoint,
                "s3Bucket": config.MINIO_BUCKET,
                "s3AccessKey": config.MINIO_ACCESS_KEY,
                "s3SecretKey": config.MINIO_SECRET_KEY,
            })
        env["BOT_CONFIG"] = json.dumps(bot_config)

    elif req.profile == "meeting":
        # Meeting API passes the full bot_config
        bot_config = user_config.get("bot_config", {})
        if bot_config:
            env["BOT_CONFIG"] = json.dumps(bot_config)

    elif req.profile == "agent":
        env["VEXA_AGENT_API"] = user_config.get("env", {}).get(
            "VEXA_AGENT_API", "http://chat-api:8100"
        )
        env["AWS_ACCESS_KEY_ID"] = config.MINIO_ACCESS_KEY
        env["AWS_SECRET_ACCESS_KEY"] = config.MINIO_SECRET_KEY
        if config.BOT_API_TOKEN:
            env["VEXA_BOT_API_TOKEN"] = config.BOT_API_TOKEN
        env["AWS_DEFAULT_REGION"] = "us-east-1"

    # Build mounts
    mounts = user_config.get("mounts") or []
    if req.profile == "agent" and user_config.get("claude_credentials", True):
        if config.CLAUDE_CREDENTIALS_PATH:
            mounts.append(f"{config.CLAUDE_CREDENTIALS_PATH}:/root/.claude/.credentials.json:ro")
        if config.CLAUDE_JSON_PATH:
            mounts.append(f"{config.CLAUDE_JSON_PATH}:/root/.claude.json:ro")

    # Create and start
    labels = {
        "vexa.managed": "true",
        "vexa.profile": req.profile,
        "vexa.user_id": req.user_id,
    }

    try:
        # Check if container exists but stopped
        docker_state = get_container_state(name)
        if docker_state in ("exited", "created"):
            logger.info(f"Restarting existing container {name}")
            start_container(name)
        elif docker_state == "running":
            logger.info(f"Container {name} already running")
        else:
            # Create new
            container_id = create_container(
                name=name,
                image=profile_def["image"],
                env=env,
                labels=labels,
                ports=profile_def.get("ports"),
                mounts=mounts if mounts else None,
                shm_size=profile_def["resources"].get("shm_size", 0),
                auto_remove=profile_def.get("auto_remove", False),
            )
            start_container(name)
            # Wait for startup
            await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"Failed to create container {name}: {e}", exc_info=True)
        raise HTTPException(500, f"Container creation failed: {e}")

    # Get port mappings
    ports = get_mapped_ports(name)

    # Build CDP URL for browser containers (internal network)
    cdp_url = None
    if req.profile == "browser":
        cdp_url = f"http://{name}:9223"

    # Store state in Redis
    container_data = {
        "status": "running",
        "profile": req.profile,
        "user_id": req.user_id,
        "image": profile_def["image"],
        "created_at": time.time(),
        "ports": ports,
        "cdp_url": cdp_url,
    }
    await state.set_container(app.state.redis, name, container_data)

    return _container_response(name, container_data)


@app.get("/containers")
async def list_all(user_id: str = None, profile: str = None):
    """List containers, optionally filtered."""
    containers = await state.list_containers(app.state.redis, user_id=user_id, profile=profile)
    return [
        {
            "name": c.get("name", ""),
            "profile": c.get("profile"),
            "user_id": c.get("user_id"),
            "status": c.get("status"),
            "ports": c.get("ports", {}),
            "cdp_url": c.get("cdp_url"),
            "created_at": c.get("created_at"),
        }
        for c in containers
    ]


@app.get("/containers/{name}")
async def get_one(name: str):
    """Get container details."""
    data = await state.get_container(app.state.redis, name)
    if not data:
        raise HTTPException(404, f"Container {name} not found")
    return _container_response(name, data)


@app.delete("/containers/{name}")
async def delete(name: str):
    """Stop and remove a container."""
    data = await state.get_container(app.state.redis, name)
    stop_container(name)
    remove_container(name)
    await state.set_stopped(app.state.redis, name)
    logger.info(f"Stopped and removed {name}")
    return {"name": name, "status": "stopped"}


@app.post("/containers/{name}/touch")
async def touch(name: str):
    """Update last activity timestamp — keeps container alive during active use."""
    data = await state.get_container(app.state.redis, name)
    if not data:
        raise HTTPException(404, f"Container {name} not found")
    await state.set_container(app.state.redis, name, data)  # set_container updates updated_at
    return {"name": name, "status": "touched"}


@app.get("/containers/{name}/cdp")
async def get_cdp(name: str):
    """Get CDP URL for a browser container."""
    data = await state.get_container(app.state.redis, name)
    if not data:
        raise HTTPException(404, f"Container {name} not found")
    if data.get("profile") != "browser":
        raise HTTPException(400, f"Container {name} is not a browser (profile={data.get('profile')})")
    return {
        "cdp_url": data.get("cdp_url"),
        "ports": data.get("ports", {}),
    }


# --- Helpers ---


def _container_response(name: str, data: dict) -> dict:
    return {
        "name": name,
        "profile": data.get("profile"),
        "user_id": data.get("user_id"),
        "status": data.get("status"),
        "ports": data.get("ports", {}),
        "cdp_url": data.get("cdp_url"),
        "created_at": data.get("created_at"),
    }


async def _reconcile_state():
    """On startup, reconcile Redis state with Docker reality.
    Mark containers that exist in Redis but not in Docker as stopped."""
    try:
        # Get truth from Docker
        docker_containers = docker_list(label_filters={"vexa.managed": "true"})
        docker_names = set()
        count = 0

        for c in docker_containers:
            name = c.get("Names", [""])[0].lstrip("/")
            docker_names.add(name)
            labels = c.get("Labels", {})
            docker_state = c.get("State", "").lower()

            data = {
                "status": "running" if docker_state == "running" else docker_state,
                "profile": labels.get("vexa.profile", "unknown"),
                "user_id": labels.get("vexa.user_id", "unknown"),
                "image": c.get("Image", ""),
                "created_at": c.get("Created", 0),
                "ports": {},
            }

            if docker_state == "running":
                data["ports"] = get_mapped_ports(name)
                if labels.get("vexa.profile") == "browser":
                    data["cdp_url"] = f"http://{name}:9223"

            await state.set_container(app.state.redis, name, data)
            count += 1

        # Mark Redis entries not in Docker as stopped
        redis_containers = await state.list_containers(app.state.redis)
        stale = 0
        for rc in redis_containers:
            rname = rc.get("name", "")
            if rname and rname not in docker_names and rc.get("status") == "running":
                await state.set_stopped(app.state.redis, rname)
                stale += 1

        if count or stale:
            logger.info(f"Reconciled: {count} from Docker, {stale} stale entries cleaned")
    except Exception as e:
        logger.warning(f"State reconciliation failed: {e}")


async def _idle_loop():
    """Background task: stop idle containers."""
    while True:
        await asyncio.sleep(config.IDLE_CHECK_INTERVAL)
        try:
            containers = await state.list_containers(app.state.redis)
            now = time.time()
            for c in containers:
                if c.get("status") != "running":
                    continue
                profile = c.get("profile", "agent")
                profile_def = get_profile(profile)
                timeout = profile_def.get("idle_timeout", 300)
                if timeout == 0:
                    continue  # No idle timeout (meeting bots)
                created = c.get("created_at", now)
                updated = c.get("updated_at", created)
                if now - updated > timeout:
                    name = c.get("name", "")
                    logger.info(f"Container {name} idle >{timeout}s, stopping")
                    stop_container(name)
                    remove_container(name)
                    await state.set_stopped(app.state.redis, name)
        except Exception:
            logger.debug("Idle check error", exc_info=True)
