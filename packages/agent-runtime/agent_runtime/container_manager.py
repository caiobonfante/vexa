"""Container manager — delegates lifecycle to Runtime API, keeps exec local.

Container lifecycle (create/stop/list) goes through Runtime API.
Container exec (docker exec for agent CLI streaming) stays as local Docker CLI
subprocess — streaming exec through HTTP would add latency for no benefit.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from agent_runtime import config

logger = logging.getLogger("agent_runtime.container_manager")


@dataclass
class ContainerInfo:
    name: str
    user_id: str
    last_activity: float = field(default_factory=time.time)


class ContainerManager:
    """Manages agent containers via Runtime API + local docker exec."""

    def __init__(self, runtime_api_url: str = "", api_key: str = ""):
        self._runtime_api = runtime_api_url or config.RUNTIME_API_URL
        self._api_key = api_key or config.API_KEY
        self._containers: dict[str, ContainerInfo] = {}  # user_id -> info
        self._http: Optional[httpx.AsyncClient] = None
        self._new_container: bool = False

    async def startup(self):
        """Initialize HTTP client for Runtime API and discover existing containers."""
        headers = {"X-API-Key": self._api_key} if self._api_key else {}
        self._http = httpx.AsyncClient(
            base_url=self._runtime_api, timeout=30, headers=headers,
        )
        # Discover existing agent containers
        try:
            resp = await self._http.get("/containers", params={"profile": "agent"})
            if resp.status_code == 200:
                for c in resp.json():
                    if c.get("status") == "running":
                        uid = c.get("user_id", "")
                        self._containers[uid] = ContainerInfo(name=c["name"], user_id=uid)
                        logger.info(f"Discovered container {c['name']} for user {uid}")
        except Exception as e:
            logger.warning(f"Could not discover containers from Runtime API: {e}")
        logger.info(f"Container manager started (runtime={self._runtime_api})")

    async def shutdown(self):
        """Close HTTP client."""
        if self._http:
            await self._http.aclose()
        logger.info("Container manager shut down")

    # --- Container operations ---

    async def _is_alive(self, name: str) -> bool:
        """Check if container is actually running via docker inspect."""
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

    async def ensure_container(self, user_id: str, **create_kwargs) -> str:
        """Ensure a running agent container exists. Returns container name.

        Additional kwargs are passed to the Runtime API POST /containers body.
        """
        self._new_container = False

        # Check local cache
        info = self._containers.get(user_id)
        if info:
            if await self._is_alive(info.name):
                info.last_activity = time.time()
                await self._touch(info.name)
                return info.name
            self._containers.pop(user_id, None)

        # Create via Runtime API
        logger.info(f"Requesting container for user {user_id}")
        body = {"user_id": user_id, "profile": "agent", **create_kwargs}
        resp = await self._http.post("/containers", json=body)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Runtime API failed: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        name = data["name"]
        self._containers[user_id] = ContainerInfo(name=name, user_id=user_id)
        self._new_container = True
        logger.info(f"Container {name} created for user {user_id}")
        return name

    async def start_agent(self, session_id: str, agent_config: dict = None,
                          callback_url: str = None) -> str:
        """Create an agent container via Runtime API. Returns container name."""
        body = {"user_id": session_id, "profile": "agent"}
        if agent_config:
            body["config"] = agent_config
        if callback_url:
            body["callback_url"] = callback_url
        resp = await self._http.post("/containers", json=body)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Runtime API failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        name = data["name"]
        self._containers[session_id] = ContainerInfo(name=name, user_id=session_id)
        return name

    async def stop_agent(self, container_id: str):
        """Stop a container via Runtime API."""
        try:
            await self._http.delete(f"/containers/{container_id}")
        except Exception as e:
            logger.warning(f"Error stopping {container_id}: {e}")
        # Remove from cache if present
        for uid, info in list(self._containers.items()):
            if info.name == container_id:
                self._containers.pop(uid, None)
                break

    async def get_status(self, container_id: str) -> dict:
        """Get container status from Runtime API."""
        resp = await self._http.get(f"/containers/{container_id}")
        if resp.status_code == 404:
            return {"name": container_id, "status": "not_found"}
        resp.raise_for_status()
        return resp.json()

    async def stop_user_container(self, user_id: str):
        """Stop the container for a specific user."""
        info = self._containers.get(user_id)
        if not info:
            return
        await self.stop_agent(info.name)

    async def _touch(self, container: str):
        """Tell Runtime API this container is actively in use."""
        try:
            await self._http.post(f"/containers/{container}/touch")
        except Exception:
            pass

    # --- Exec operations (local docker CLI) ---

    async def exec_stream(self, container: str, cmd: str) -> asyncio.subprocess.Process:
        """Run a shell command in the container, return subprocess for streaming."""
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
                proc.communicate(input=stdin_data), timeout=30,
            )
            if proc.returncode == 0 and stdout.strip():
                return stdout.decode(errors="replace").strip()
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"exec_with_stdin failed: {e}")
        return None

    async def interrupt(self, user_id: str, process_pattern: str = "claude.*stream-json"):
        """Kill active agent process in user's container."""
        info = self._containers.get(user_id)
        if not info:
            return
        try:
            await self.exec_simple(info.name, [
                "sh", "-c", f"pkill -f '{process_pattern}' || true",
            ])
        except Exception as e:
            logger.warning(f"Interrupt failed for {user_id}: {e}")

    async def reset_session(self, user_id: str):
        """Kill active process and clear session state in container."""
        await self.interrupt(user_id)
        info = self._containers.get(user_id)
        if info:
            await self.exec_simple(info.name, ["rm", "-f", "/tmp/.agent-session"])

    def get_container_name(self, user_id: str) -> Optional[str]:
        info = self._containers.get(user_id)
        return info.name if info else None
