"""Workspace sync via awscli inside agent containers.

Runs `aws s3 sync` inside the container via `docker exec`.
Git commit before upload to preserve history.
"""

import asyncio
import logging

from app import config

logger = logging.getLogger("chat_api.workspace_sync")


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


def _s3_uri(user_id: str) -> str:
    return f"s3://{config.MINIO_BUCKET}/workspaces/{user_id}/"


def _env_args() -> str:
    return f"--endpoint-url {config.MINIO_ENDPOINT}"


_SYNC_EXCLUDES = (
    '--exclude ".claude/.session" '
    '--exclude ".claude/.chat-prompt.txt" '
    '--exclude ".claude/.agent-prompt.txt"'
)


async def sync_down(user_id: str, container: str) -> bool:
    """Download workspace from MinIO into /workspace/ inside the container."""
    s3_uri = _s3_uri(user_id)
    cmd = f"aws s3 sync {s3_uri} /workspace/ {_env_args()} {_SYNC_EXCLUDES} 2>&1"
    logger.info(f"Sync down: {s3_uri} -> /workspace/ in {container}")
    rc, out = await _exec(container, cmd)
    if rc != 0:
        logger.error(f"Sync down FAILED for {user_id} (rc={rc}): {out}")
    return rc == 0


async def git_commit(user_id: str, container: str) -> bool:
    """Git add + commit inside workspace. Returns True if commit was made."""
    cmd = (
        'cd /workspace && '
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


async def sync_up(user_id: str, container: str) -> bool:
    """Git commit then upload workspace to MinIO."""
    committed = await git_commit(user_id, container)
    if not committed:
        logger.warning(f"Git commit failed for {user_id}, proceeding with sync anyway")
    s3_uri = _s3_uri(user_id)
    cmd = f"aws s3 sync /workspace/ {s3_uri} {_env_args()} --delete {_SYNC_EXCLUDES} 2>&1"
    logger.info(f"Sync up: /workspace/ in {container} -> {s3_uri}")
    rc, out = await _exec(container, cmd)
    if rc != 0:
        logger.error(f"Sync up FAILED for {user_id} (rc={rc}): {out}")
    return rc == 0


async def workspace_exists(user_id: str) -> bool:
    """Check if a workspace prefix exists in MinIO."""
    try:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url=config.MINIO_ENDPOINT,
            aws_access_key_id=config.MINIO_ACCESS_KEY,
            aws_secret_access_key=config.MINIO_SECRET_KEY,
            region_name="us-east-1",
        )
        resp = s3.list_objects_v2(
            Bucket=config.MINIO_BUCKET,
            Prefix=f"workspaces/{user_id}/",
            MaxKeys=1,
        )
        return resp.get("KeyCount", 0) > 0
    except Exception as e:
        logger.warning(f"workspace_exists check failed: {e}")
        return False
