"""Container manager — delegates CRUD to Runtime API, keeps exec local.

Container lifecycle (create/stop/list) goes through Runtime API.
Container exec (docker exec for Claude CLI streaming) stays as local Docker CLI
subprocess — streaming exec through HTTP would add latency for no benefit.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from app import config
from app import workspace_sync

logger = logging.getLogger("chat_api.container_manager")

RUNTIME_API = config.RUNTIME_API_URL


@dataclass
class ContainerInfo:
    name: str
    user_id: str
    last_activity: float = field(default_factory=time.time)


class ContainerManager:
    def __init__(self):
        self._containers: dict[str, ContainerInfo] = {}  # user_id -> info
        self._http: Optional[httpx.AsyncClient] = None

    # --- Lifecycle ---

    async def startup(self):
        """Initialize HTTP client for Runtime API."""
        bot_token = os.getenv("BOT_API_TOKEN", "")
        headers = {"X-API-Key": bot_token} if bot_token else {}
        self._http = httpx.AsyncClient(base_url=RUNTIME_API, timeout=30, headers=headers)
        # Discover existing agent containers from Runtime API
        try:
            resp = await self._http.get("/containers", params={"profile": "agent"})
            if resp.status_code == 200:
                for c in resp.json():
                    if c.get("status") == "running":
                        uid = c.get("user_id", "")
                        self._containers[uid] = ContainerInfo(name=c["name"], user_id=uid)
                        logger.info(f"Discovered agent container {c['name']} for user {uid}")
        except Exception as e:
            logger.warning(f"Could not discover containers from Runtime API: {e}")
        logger.info(f"Container manager started (runtime={RUNTIME_API})")

    async def shutdown(self):
        """Sync workspaces before shutdown."""
        for user_id, info in list(self._containers.items()):
            try:
                await workspace_sync.sync_up(user_id, info.name)
            except Exception as e:
                logger.warning(f"Sync failed for {user_id}: {e}")
        if self._http:
            await self._http.aclose()
        logger.info("Container manager shut down")

    # --- Container operations ---

    async def _is_alive(self, name: str) -> bool:
        """Check if container is actually running in Docker (not just Redis)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", "--format", "{{.State.Status}}", name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0 and stdout.decode().strip() == "running"
        except Exception:
            return False

    def _auth_headers(self, bot_token: Optional[str] = None) -> dict:
        """Return auth headers, preferring per-request bot_token over env default."""
        token = bot_token or os.getenv("BOT_API_TOKEN", "")
        return {"X-API-Key": token} if token else {}

    async def ensure_container(self, user_id: str, bot_token: Optional[str] = None) -> str:
        """Ensure a running agent container exists. Returns container name."""
        # Check local cache first
        info = self._containers.get(user_id)
        if info:
            # Verify it's actually running in Docker (not stale Redis state)
            if await self._is_alive(info.name):
                info.last_activity = time.time()
                await self._touch(info.name)
                return info.name
            # Container gone — remove from cache
            self._containers.pop(user_id, None)

        # Create via Runtime API
        logger.info(f"Requesting agent container for user {user_id}")
        resp = await self._http.post("/containers", json={
            "user_id": user_id,
            "profile": "agent",
            "config": {"claude_credentials": True},
        }, headers=self._auth_headers(bot_token))
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Runtime API failed: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        name = data["name"]

        # Workspace init + sync — Agent API's responsibility
        await self._init_workspace(user_id, name)
        await workspace_sync.sync_down(user_id, name)

        self._containers[user_id] = ContainerInfo(name=name, user_id=user_id)
        self._new_container = True  # Signal to caller: don't resume stale session
        return name

    async def _touch(self, container: str):
        """Tell Runtime API this container is actively in use."""
        try:
            await self._http.post(f"/containers/{container}/touch")
        except Exception:
            pass

    async def exec_stream(self, container: str, cmd: str) -> asyncio.subprocess.Process:
        """Run a shell command in the container, return subprocess for streaming.
        Stays as local Docker CLI — streaming exec can't go through HTTP."""
        await self._touch(container)
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", container, "bash", "-c", cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=16 * 1024 * 1024,
        )
        return proc

    async def exec_simple(self, container: str, cmd: list[str]) -> Optional[str]:
        """Run a command in the container, return stdout or None."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", container, *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0 and stdout.strip():
                return stdout.decode(errors="replace").strip()
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"exec_simple failed: {e}")
        return None

    async def exec_with_stdin(self, container: str, cmd: list[str],
                              stdin_data: bytes) -> Optional[str]:
        """Run a command in the container with stdin piped. Returns stdout or None."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", "-i", container, *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=stdin_data), timeout=30
            )
            if proc.returncode == 0 and stdout.strip():
                return stdout.decode(errors="replace").strip()
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"exec_with_stdin failed: {e}")
        return None

    async def stop_container(self, user_id: str):
        """Sync workspace and stop via Runtime API."""
        info = self._containers.get(user_id)
        if not info:
            return
        logger.info(f"Stopping container {info.name}")
        try:
            await workspace_sync.sync_up(user_id, info.name)
            await self._http.delete(f"/containers/{info.name}")
        except Exception as e:
            logger.warning(f"Error stopping {info.name}: {e}")
        self._containers.pop(user_id, None)

    async def interrupt(self, user_id: str):
        """Kill active Claude process in user's container."""
        info = self._containers.get(user_id)
        if not info:
            return
        try:
            await self.exec_simple(info.name, [
                "sh", "-c", "pkill -f 'claude.*stream-json' || true"
            ])
        except Exception as e:
            logger.warning(f"Interrupt failed for {user_id}: {e}")

    async def reset_session(self, user_id: str):
        """Delete session file and interrupt any active process."""
        await self.interrupt(user_id)
        info = self._containers.get(user_id)
        if info:
            await self.exec_simple(info.name, ["rm", "-f", "/tmp/.claude-session"])

    def get_container_name(self, user_id: str) -> Optional[str]:
        info = self._containers.get(user_id)
        return info.name if info else None

    # --- Internal ---

    async def _init_workspace(self, user_id: str, container: str):
        """Initialize workspace from knowledge template if empty."""
        check = await self.exec_simple(container, ["test", "-f", "/workspace/.claude/CLAUDE.md"])
        if check is not None:
            logger.info(f"Workspace already initialized for {user_id}")
            return

        logger.info(f"Initializing workspace from knowledge template for {user_id}")
        await self.exec_simple(container, [
            "sh", "-c", "cp -a /templates/knowledge/. /workspace/"
        ])
        await self.exec_simple(container, [
            "sh", "-c",
            "cd /workspace && git init && git add -A && "
            "git commit -m 'init from knowledge template' --allow-empty"
        ])
        logger.info(f"Workspace initialized for {user_id}")
