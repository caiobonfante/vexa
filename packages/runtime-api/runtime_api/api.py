"""/containers CRUD endpoints.

Provides REST API for container lifecycle management:
  POST   /containers              Create and start a container
  GET    /containers              List containers (?profile=&user_id=)
  GET    /containers/{name}       Inspect container
  DELETE /containers/{name}       Stop and remove container
  POST   /containers/{name}/touch Heartbeat (resets idle timer)
  POST   /containers/{name}/exec  Execute command inside container
  GET    /containers/{name}/wait  Long-poll until target state
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from runtime_api import state
from runtime_api.backends import Backend, ContainerSpec
from runtime_api.profiles import get_profile, get_all_profiles

logger = logging.getLogger("runtime_api.api")

router = APIRouter()


# -- Request/Response Models --


class CreateContainerRequest(BaseModel):
    profile: str
    user_id: str
    config: dict = Field(default_factory=dict)
    callback_url: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    name: Optional[str] = None


class ContainerResponse(BaseModel):
    name: str
    profile: Optional[str] = None
    user_id: Optional[str] = None
    status: Optional[str] = None
    container_id: Optional[str] = None
    ports: dict = Field(default_factory=dict)
    created_at: Optional[float] = None
    metadata: dict = Field(default_factory=dict)


class ExecRequest(BaseModel):
    cmd: list[str]


class WaitRequest(BaseModel):
    target_status: str = "stopped"
    timeout: float = 300


# -- Helpers --


def _get_backend(request: Request) -> Backend:
    return request.app.state.backend


def _get_redis(request: Request):
    return request.app.state.redis


def _container_response(name: str, data: dict) -> dict:
    return {
        "name": name,
        "profile": data.get("profile"),
        "user_id": data.get("user_id"),
        "status": data.get("status"),
        "container_id": data.get("container_id"),
        "ports": data.get("ports", {}),
        "created_at": data.get("created_at"),
        "metadata": data.get("metadata", {}),
    }


# -- Endpoints --


@router.post("/containers", status_code=201)
async def create_container(req: CreateContainerRequest, request: Request):
    """Create and start a container from a profile."""
    backend = _get_backend(request)
    redis = _get_redis(request)

    profile_def = get_profile(req.profile)
    if not profile_def:
        raise HTTPException(400, f"Unknown profile: {req.profile}")

    # Per-user concurrency limit — caller can tighten (not loosen) the profile default
    max_per_user = profile_def.get("max_per_user", 0)
    caller_limit = req.config.get("max_per_user")
    if caller_limit is not None:
        caller_limit = int(caller_limit)
        if max_per_user == 0 or (caller_limit > 0 and caller_limit < max_per_user):
            max_per_user = caller_limit
    if max_per_user > 0:
        current = await state.count_user_containers(redis, req.user_id, profile=req.profile)
        if current >= max_per_user:
            raise HTTPException(
                429,
                f"User {req.user_id} has reached the limit of {max_per_user} "
                f"concurrent '{req.profile}' containers",
            )

    # Generate container name
    if req.name:
        name = req.name
    elif max_per_user == 1:
        # Single-instance profile: deterministic name
        name = f"{req.profile}-{req.user_id}"
        existing = await state.get_container(redis, name)
        if existing and existing.get("status") == "running":
            # Verify with backend
            info = await backend.inspect(name)
            if info and info.status == "running":
                return _container_response(name, existing)
    else:
        suffix = uuid.uuid4().hex[:8]
        name = f"{req.profile}-{req.user_id}-{suffix}"

    # Build env from profile defaults + user config
    env = {**profile_def.get("env", {})}
    user_env = req.config.get("env", {})
    if isinstance(user_env, dict):
        env.update(user_env)

    # Build labels
    labels = {
        "runtime.managed": "true",
        "runtime.profile": req.profile,
        "runtime.user_id": req.user_id,
    }

    # Build mounts from profile + user config
    mounts = list(profile_def.get("mounts", []))
    user_mounts = req.config.get("mounts", [])
    if user_mounts:
        mounts.extend(user_mounts)

    # Build ports from profile
    ports = dict(profile_def.get("ports", {}))

    # Resource config
    resources = profile_def.get("resources", {})

    spec = ContainerSpec(
        name=name,
        image=req.config.get("image") or profile_def["image"],
        command=req.config.get("command") or profile_def.get("command"),
        env=env,
        labels=labels,
        ports=ports,
        mounts=mounts,
        network=req.config.get("network"),
        shm_size=resources.get("shm_size", 0),
        auto_remove=profile_def.get("auto_remove", True),
        cpu_request=resources.get("cpu_request"),
        cpu_limit=resources.get("cpu_limit"),
        memory_request=resources.get("memory_request"),
        memory_limit=resources.get("memory_limit"),
        gpu=profile_def.get("gpu", False),
        gpu_type=profile_def.get("gpu_type"),
        node_selector=profile_def.get("node_selector", {}),
        working_dir=profile_def.get("working_dir"),
        k8s_overrides=profile_def.get("k8s_overrides", {}),
    )

    try:
        container_id = await backend.create(spec)
    except Exception as e:
        logger.error(f"Failed to create container {name}: {e}", exc_info=True)
        raise HTTPException(500, f"Container creation failed: {e}")

    # Get ports from backend
    info = await backend.inspect(name)
    result_ports = info.ports if info else {}

    # Store state
    container_data = {
        "status": "running",
        "profile": req.profile,
        "user_id": req.user_id,
        "image": req.config.get("image") or profile_def["image"],
        "created_at": time.time(),
        "ports": result_ports,
        "container_id": container_id,
        "callback_url": req.callback_url,
        "metadata": req.metadata,
    }
    await state.set_container(redis, name, container_data)

    return _container_response(name, container_data)


@router.get("/containers")
async def list_containers(
    request: Request,
    user_id: Optional[str] = None,
    profile: Optional[str] = None,
):
    """List containers, optionally filtered by user_id and/or profile."""
    redis = _get_redis(request)
    containers = await state.list_containers(redis, user_id=user_id, profile=profile)
    return [_container_response(c.get("name", ""), c) for c in containers]


@router.get("/containers/{name}")
async def get_container(name: str, request: Request):
    """Get container details."""
    redis = _get_redis(request)
    data = await state.get_container(redis, name)
    if not data:
        raise HTTPException(404, f"Container {name} not found")
    return _container_response(name, data)


@router.delete("/containers/{name}")
async def delete_container(name: str, request: Request):
    """Stop and remove a container."""
    backend = _get_backend(request)
    redis = _get_redis(request)

    await backend.stop(name)
    await backend.remove(name)
    await state.set_stopped(redis, name)
    logger.info(f"Stopped and removed {name}")
    return {"name": name, "status": "stopped"}


@router.post("/containers/{name}/touch")
async def touch_container(name: str, request: Request):
    """Update last activity timestamp — keeps container alive during active use."""
    redis = _get_redis(request)
    data = await state.get_container(redis, name)
    if not data:
        raise HTTPException(404, f"Container {name} not found")
    await state.set_container(redis, name, data)  # updates updated_at
    return {"name": name, "status": "touched"}


@router.post("/containers/{name}/exec")
async def exec_in_container(name: str, req: ExecRequest, request: Request):
    """Execute a command inside a running container."""
    backend = _get_backend(request)
    redis = _get_redis(request)

    data = await state.get_container(redis, name)
    if not data:
        raise HTTPException(404, f"Container {name} not found")
    if data.get("status") != "running":
        raise HTTPException(400, f"Container {name} is not running")

    output = b""
    async for chunk in backend.exec(name, req.cmd):
        output += chunk

    # Touch on exec to reset idle timer
    await state.set_container(redis, name, data)

    return {"name": name, "output": output.decode(errors="replace")}


@router.get("/containers/{name}/wait")
async def wait_for_container(
    name: str,
    request: Request,
    target_status: str = "stopped",
    timeout: float = 300,
):
    """Long-poll until container reaches target status or timeout."""
    redis = _get_redis(request)
    deadline = time.time() + timeout

    while time.time() < deadline:
        data = await state.get_container(redis, name)
        if not data:
            return {"name": name, "status": "not_found", "reached": True}
        if data.get("status") == target_status:
            return {
                "name": name,
                "status": target_status,
                "reached": True,
                "exit_code": data.get("exit_code"),
            }
        if data.get("status") in ("stopped", "failed") and target_status != data.get("status"):
            return {
                "name": name,
                "status": data.get("status"),
                "reached": False,
                "exit_code": data.get("exit_code"),
            }
        await asyncio.sleep(2)

    return {"name": name, "status": "timeout", "reached": False}


@router.get("/profiles")
async def list_profiles():
    """List available container profiles."""
    return get_all_profiles()


@router.get("/health")
async def health(request: Request):
    """Health check endpoint."""
    redis = _get_redis(request)
    containers = await state.list_containers(redis)
    running = sum(1 for c in containers if c.get("status") == "running")
    return {"status": "ok", "containers": len(containers), "running": running}
