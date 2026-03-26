"""Workspace sync between agent containers and S3-compatible storage.

Runs `aws s3 sync` inside the container via `docker exec`.
Supports both S3/MinIO backends and local filesystem fallback.
"""

import asyncio
import logging
from typing import Protocol

from agent_runtime import config

logger = logging.getLogger("agent_runtime.workspace")


class ExecProtocol(Protocol):
    """Protocol for executing commands in a container."""

    async def exec_simple(self, container: str, cmd: list[str]) -> str | None: ...


# --- Container exec helper ---

async def _exec(container: str, cmd: str, timeout: int = 120) -> tuple[int, str]:
    """Run a shell command inside a container, return (returncode, output)."""
    proc = await asyncio.create_subprocess_exec(
        "docker", "exec", container, "bash", "-c", cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode(errors="replace").strip()
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "timeout"


# --- S3 helpers ---

def _s3_uri(user_id: str) -> str:
    return f"s3://{config.S3_BUCKET}/workspaces/{user_id}/"


def _env_args() -> str:
    parts = []
    if config.S3_ENDPOINT:
        parts.append(f"--endpoint-url {config.S3_ENDPOINT}")
    return " ".join(parts)


_SYNC_EXCLUDES = (
    '--exclude ".claude/.session" '
    '--exclude ".claude/.chat-prompt.txt" '
    '--exclude ".claude/.agent-prompt.txt"'
)


# --- Sync operations ---

async def sync_down(user_id: str, container: str) -> bool:
    """Download workspace from S3 into /workspace/ inside the container."""
    if config.STORAGE_BACKEND != "s3":
        logger.debug(f"Storage backend is {config.STORAGE_BACKEND}, skipping sync_down")
        return True

    s3_uri = _s3_uri(user_id)
    workspace = config.WORKSPACE_PATH
    cmd = f"aws s3 sync {s3_uri} {workspace}/ {_env_args()} {_SYNC_EXCLUDES} 2>&1"
    logger.info(f"Sync down: {s3_uri} -> {workspace}/ in {container}")
    rc, out = await _exec(container, cmd)
    if rc != 0:
        logger.error(f"Sync down FAILED for {user_id} (rc={rc}): {out}")
    return rc == 0


async def sync_up(user_id: str, container: str) -> bool:
    """Git commit then upload workspace to S3."""
    if config.STORAGE_BACKEND != "s3":
        logger.debug(f"Storage backend is {config.STORAGE_BACKEND}, skipping sync_up")
        return True

    committed = await git_commit(user_id, container)
    if not committed:
        logger.warning(f"Git commit failed for {user_id}, proceeding with sync anyway")

    s3_uri = _s3_uri(user_id)
    workspace = config.WORKSPACE_PATH
    cmd = f"aws s3 sync {workspace}/ {s3_uri} {_env_args()} --delete {_SYNC_EXCLUDES} 2>&1"
    logger.info(f"Sync up: {workspace}/ in {container} -> {s3_uri}")
    rc, out = await _exec(container, cmd)
    if rc != 0:
        logger.error(f"Sync up FAILED for {user_id} (rc={rc}): {out}")
    return rc == 0


async def git_commit(user_id: str, container: str) -> bool:
    """Git add + commit inside workspace. Returns True if commit was made."""
    workspace = config.WORKSPACE_PATH
    cmd = (
        f'cd {workspace} && '
        'git add -A && '
        'STATUS=$(git status --porcelain) && '
        'if [ -n "$STATUS" ]; then '
        '  STAMP=$(date -u +%Y-%m-%dT%H-%M-%S); '
        '  git commit -m "save $STAMP"; '
        'fi'
    )
    rc, out = await _exec(container, cmd, timeout=30)
    if rc != 0:
        logger.warning(f"Git commit issue for {user_id}: {out}")
        return False
    if "save" in out:
        logger.info(f"Git commit for {user_id}: {out.splitlines()[-1]}")
    return True


async def workspace_exists(user_id: str) -> bool:
    """Check if a workspace prefix exists in S3."""
    if config.STORAGE_BACKEND != "s3":
        return False
    try:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT or None,
            aws_access_key_id=config.S3_ACCESS_KEY or None,
            aws_secret_access_key=config.S3_SECRET_KEY or None,
            region_name="us-east-1",
        )
        resp = s3.list_objects_v2(
            Bucket=config.S3_BUCKET,
            Prefix=f"workspaces/{user_id}/",
            MaxKeys=1,
        )
        return resp.get("KeyCount", 0) > 0
    except Exception as e:
        logger.warning(f"workspace_exists check failed: {e}")
        return False


# --- File operations for REST API ---

async def sync_to_container(container: str, workspace_path: str,
                            files: dict[str, str]) -> bool:
    """Push files into a container's workspace.

    Args:
        container: Container name.
        workspace_path: Path inside container (e.g. /workspace).
        files: Dict of {relative_path: content}.

    Returns:
        True if all files were written successfully.
    """
    import base64
    import os.path

    for rel_path, content in files.items():
        full_path = f"{workspace_path}/{rel_path}"
        parent = os.path.dirname(full_path)
        if parent:
            await _exec(container, f"mkdir -p {parent}")
        encoded = base64.b64encode(content.encode()).decode()
        rc, _ = await _exec(container, f"echo '{encoded}' | base64 -d > {full_path}")
        if rc != 0:
            logger.error(f"Failed to write {rel_path} to {container}")
            return False
    return True


async def sync_from_container(container: str, workspace_path: str) -> dict[str, str]:
    """Read workspace files from a container.

    Returns:
        Dict of {relative_path: content} for all non-git files.
    """
    rc, listing = await _exec(
        container,
        f"find {workspace_path} -not -path '*/.git/*' -not -name '.git' "
        f"-not -name '.gitkeep' -type f",
    )
    if rc != 0 or not listing:
        return {}

    files = {}
    for filepath in listing.strip().split("\n"):
        filepath = filepath.strip()
        if not filepath:
            continue
        rc, content = await _exec(container, f"cat '{filepath}'")
        if rc == 0:
            rel = filepath.replace(f"{workspace_path}/", "", 1)
            files[rel] = content
    return files
