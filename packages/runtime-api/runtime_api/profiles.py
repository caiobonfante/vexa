"""YAML-based profile loader with hot-reload via SIGHUP.

Profiles are declarative container templates. Callers reference them by name
when creating containers. The runtime resolves the profile to an image, resource
limits, idle timeout, and other defaults.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
from pathlib import Path
from typing import Optional

import yaml

from runtime_api import config

logger = logging.getLogger("runtime_api.profiles")

_profiles: dict[str, dict] = {}
_lock = threading.Lock()
_mtime: float = 0.0

# Default profile schema with all supported fields
PROFILE_DEFAULTS = {
    "image": "",
    "command": None,
    "resources": {
        "cpu_request": None,
        "cpu_limit": None,
        "memory_request": None,
        "memory_limit": None,
        "shm_size": 0,
    },
    "idle_timeout": 300,
    "auto_remove": True,
    "ports": {},
    "mounts": [],
    "env": {},
    "gpu": False,
    "gpu_type": None,
    "node_selector": {},
    "max_per_user": 0,  # 0 = unlimited
    "working_dir": None,
    "k8s_overrides": {},  # opaque K8s-specific: tolerations, affinity, annotations
}


def load_profiles(path: str | None = None) -> dict[str, dict]:
    """Load profiles from YAML file. Thread-safe."""
    global _profiles, _mtime
    path = path or config.PROFILES_PATH

    if not Path(path).exists():
        logger.warning(f"Profiles file not found: {path} — using empty profiles")
        return {}

    try:
        current_mtime = Path(path).stat().st_mtime
        with _lock:
            if current_mtime == _mtime and _profiles:
                return _profiles

        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        profiles = {}
        for name, spec in raw.get("profiles", raw).items():
            merged = {**PROFILE_DEFAULTS}
            merged.update(spec)
            # Merge resources sub-dict
            if "resources" in spec:
                merged["resources"] = {**PROFILE_DEFAULTS["resources"], **spec["resources"]}
            profiles[name] = merged

        with _lock:
            _profiles = profiles
            _mtime = current_mtime

        logger.info(f"Loaded {len(profiles)} profiles from {path}: {list(profiles.keys())}")
        return profiles

    except Exception as e:
        logger.error(f"Failed to load profiles from {path}: {e}", exc_info=True)
        return _profiles  # return previous on error


def get_profile(name: str) -> Optional[dict]:
    """Get a profile by name. Returns None if not found."""
    with _lock:
        if not _profiles:
            load_profiles()
        return _profiles.get(name)


def get_all_profiles() -> dict[str, dict]:
    """Get all loaded profiles."""
    with _lock:
        if not _profiles:
            load_profiles()
        return dict(_profiles)


def _sighup_handler(signum, frame):
    """Reload profiles on SIGHUP."""
    logger.info("SIGHUP received — reloading profiles")
    load_profiles()


def install_sighup_handler():
    """Install SIGHUP handler for hot-reloading profiles."""
    if os.name != "nt":  # SIGHUP not available on Windows
        signal.signal(signal.SIGHUP, _sighup_handler)
        logger.info("SIGHUP handler installed for profile hot-reload")
