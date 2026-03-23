"""Docker socket operations — create, start, stop, inspect, list containers.

Clean extraction from bot-manager/app/orchestrator_utils.py.
Uses requests_unixsocket for Docker API calls.
"""

import json
import logging
import os
import time
import uuid
from typing import Any, Optional

import requests_unixsocket
from requests.exceptions import ConnectionError, HTTPError

from app import config

logger = logging.getLogger("runtime_api.docker")

# --- Docker socket connection ---

_session: Optional[requests_unixsocket.Session] = None
_socket_url: str = ""


def _init_socket() -> str:
    """Parse DOCKER_HOST into a requests_unixsocket URL."""
    global _socket_url
    if _socket_url:
        return _socket_url
    raw = config.DOCKER_HOST
    path = raw.split("//", 1)[1] if "//" in raw else "/var/run/docker.sock"
    if not path.startswith("/"):
        path = f"/{path}"
    encoded = path.replace("/", "%2F")
    _socket_url = f"http+unix://{encoded}"
    return _socket_url


def get_session() -> requests_unixsocket.Session:
    """Get or create the Docker socket session."""
    global _session
    if _session is not None:
        return _session

    url = _init_socket()
    _session = requests_unixsocket.Session()

    # Verify connection
    try:
        resp = _session.get(f"{url}/version", timeout=5)
        resp.raise_for_status()
        ver = resp.json().get("ApiVersion", "?")
        logger.info(f"Docker connected (API {ver})")
    except Exception as e:
        _session = None
        raise RuntimeError(f"Cannot connect to Docker at {config.DOCKER_HOST}: {e}")

    return _session


def close_session():
    global _session
    if _session:
        _session.close()
        _session = None


# --- Container operations ---


def create_container(
    name: str,
    image: str,
    env: dict[str, str] = None,
    labels: dict[str, str] = None,
    network: str = None,
    ports: dict[str, dict] = None,
    mounts: list[str] = None,
    shm_size: int = 0,
    auto_remove: bool = False,
) -> str:
    """Create a Docker container. Returns container ID."""
    session = get_session()
    url = _init_socket()

    env_list = [f"{k}={v}" for k, v in (env or {}).items()]

    host_config: dict[str, Any] = {
        "NetworkMode": network or config.DOCKER_NETWORK,
        "AutoRemove": auto_remove,
        "ExtraHosts": ["host.docker.internal:host-gateway"],
    }
    if shm_size:
        host_config["ShmSize"] = shm_size
    if ports:
        host_config["PortBindings"] = {
            p: [{"HostPort": "0"}] for p in ports
        }
    if mounts:
        host_config["Binds"] = mounts

    payload = {
        "Image": image,
        "Env": env_list,
        "Labels": labels or {},
        "HostConfig": host_config,
    }
    if ports:
        payload["ExposedPorts"] = {p: {} for p in ports}

    resp = session.post(f"{url}/containers/create?name={name}", json=payload)
    if resp.status_code == 409:
        # Container already exists
        logger.info(f"Container {name} already exists")
        return inspect_container(name).get("Id", "")
    resp.raise_for_status()
    container_id = resp.json().get("Id", "")
    logger.info(f"Created container {name} ({container_id[:12]})")
    return container_id


def start_container(name: str) -> bool:
    """Start a container. Returns True if started."""
    session = get_session()
    url = _init_socket()
    resp = session.post(f"{url}/containers/{name}/start")
    if resp.status_code in (204, 304):  # 204=started, 304=already running
        return True
    logger.warning(f"Start {name} failed: {resp.status_code} {resp.text[:200]}")
    return False


def stop_container(name: str, timeout: int = 10) -> bool:
    """Stop a container. Returns True if stopped."""
    session = get_session()
    url = _init_socket()
    resp = session.post(f"{url}/containers/{name}/stop?t={timeout}")
    if resp.status_code in (204, 304, 404):  # 204=stopped, 304=already stopped, 404=gone
        return True
    logger.warning(f"Stop {name} failed: {resp.status_code}")
    return False


def remove_container(name: str, force: bool = True) -> bool:
    """Remove a container."""
    session = get_session()
    url = _init_socket()
    resp = session.delete(f"{url}/containers/{name}?force={'true' if force else 'false'}")
    if resp.status_code in (204, 404):
        return True
    logger.warning(f"Remove {name} failed: {resp.status_code}")
    return False


def inspect_container(name: str) -> dict:
    """Inspect a container. Returns full Docker inspect JSON or empty dict."""
    session = get_session()
    url = _init_socket()
    resp = session.get(f"{url}/containers/{name}/json")
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


def get_container_state(name: str) -> Optional[str]:
    """Get container state: 'running', 'exited', 'created', or None."""
    info = inspect_container(name)
    if not info:
        return None
    return info.get("State", {}).get("Status")


def get_mapped_ports(name: str) -> dict[str, int]:
    """Get host-mapped ports for a container. Returns {internal_port: host_port}."""
    info = inspect_container(name)
    if not info:
        return {}
    ports = info.get("NetworkSettings", {}).get("Ports", {})
    result = {}
    for internal, bindings in ports.items():
        if bindings and len(bindings) > 0:
            host_port = bindings[0].get("HostPort")
            if host_port:
                # Strip /tcp from "6080/tcp"
                key = internal.split("/")[0]
                result[key] = int(host_port)
    return result


def list_containers(label_filters: dict[str, str] = None) -> list[dict]:
    """List containers with optional label filters."""
    session = get_session()
    url = _init_socket()

    filters = {}
    if label_filters:
        filters["label"] = [f"{k}={v}" for k, v in label_filters.items()]

    params = {}
    if filters:
        params["filters"] = json.dumps(filters)
    params["all"] = "true"

    resp = session.get(f"{url}/containers/json", params=params)
    resp.raise_for_status()
    return resp.json()
