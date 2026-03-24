"""Workspace API endpoints — file browsing, editing, git operations.

These run `docker exec` in the agent container to access workspace files.
The dashboard uses these to show workspace contents and approve changes.
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.container_manager import ContainerManager
from app.auth_simple import require_api_key

logger = logging.getLogger("agent_api.workspace")

router = APIRouter(prefix="/api/workspace", dependencies=[Depends(require_api_key)])

# Reference to container manager — set from main.py
_cm: Optional[ContainerManager] = None

# Strict path validation: alphanumeric, hyphens, underscores, dots, slashes only
_SAFE_PATH = re.compile(r"^[a-zA-Z0-9._/\-]+$")


def _validate_path(path: str) -> str:
    """Validate and sanitize a workspace file path."""
    if not path or ".." in path or path.startswith("/") or not _SAFE_PATH.match(path):
        raise HTTPException(400, "Invalid path")
    return path


def set_container_manager(cm: ContainerManager):
    global _cm
    _cm = cm


async def _exec(user_id: str, cmd: list[str]) -> Optional[str]:
    """Run command in user's agent container. Returns stdout or None."""
    if not _cm:
        raise HTTPException(500, "Container manager not initialized")
    container = _cm.get_container_name(user_id)
    if not container:
        raise HTTPException(404, f"No agent container for user {user_id}")
    return await _cm.exec_simple(container, cmd)


@router.get("/tree")
async def get_tree(user_id: str):
    """Get workspace file tree."""
    raw = await _exec(user_id, [
        "sh", "-c",
        "cd /workspace && find . -not -path './.git/*' -not -path './.git' "
        "-not -name '.gitkeep' -type f | sort"
    ])
    if not raw:
        return {"files": []}
    files = [f.lstrip("./") for f in raw.strip().split("\n") if f.strip()]
    return {"files": files}


@router.get("/file")
async def get_file(user_id: str, path: str):
    """Get file content from workspace."""
    path = _validate_path(path)
    content = await _exec(user_id, ["cat", f"/workspace/{path}"])
    return {"path": path, "content": content or ""}


class FileWriteRequest(BaseModel):
    user_id: str
    path: str
    content: str


@router.put("/file")
async def put_file(req: FileWriteRequest):
    """Write file to workspace."""
    path = _validate_path(req.path)
    if not _cm:
        raise HTTPException(500, "Container manager not initialized")
    container = _cm.get_container_name(req.user_id)
    if not container:
        raise HTTPException(404, f"No agent container for user {req.user_id}")

    import base64
    import os.path
    # mkdir for parent dir — list-form, no shell
    parent = os.path.dirname(path)
    if parent:
        await _cm.exec_simple(container, ["mkdir", "-p", f"/workspace/{parent}"])
    # Write via base64 — path is validated to safe chars only
    encoded = base64.b64encode(req.content.encode()).decode()
    await _cm.exec_with_stdin(container,
        ["sh", "-c", f"base64 -d > /workspace/{path}"],
        stdin_data=encoded.encode(),
    )
    return {"path": path, "status": "written"}


@router.get("/diff")
async def get_diff(user_id: str):
    """Get git diff of uncommitted changes."""
    # Stage everything first to include new files
    await _exec(user_id, ["git", "-C", "/workspace", "add", "-A"])
    diff = await _exec(user_id, [
        "git", "-C", "/workspace", "diff", "--cached"
    ])
    # Also get summary
    summary = await _exec(user_id, [
        "git", "-C", "/workspace", "diff", "--cached", "--stat"
    ])
    return {
        "diff": diff or "",
        "summary": summary or "No changes",
        "has_changes": bool(diff and diff.strip()),
    }


@router.get("/log")
async def get_log(user_id: str, limit: int = 20):
    """Get git commit history."""
    limit = max(1, min(limit, 100))  # Clamp to safe range
    raw = await _exec(user_id, [
        "git", "-C", "/workspace", "log", "--oneline",
        f"--format=%h %ai %s", f"-{limit}"
    ])
    if not raw:
        return {"commits": []}
    commits = []
    for line in raw.strip().split("\n"):
        if line.strip():
            parts = line.split(" ", 3)
            if len(parts) >= 4:
                commits.append({
                    "hash": parts[0],
                    "date": f"{parts[1]} {parts[2]}",
                    "message": parts[3] if len(parts) > 3 else "",
                })
    return {"commits": commits}


class CommitRequest(BaseModel):
    user_id: str
    message: str = "Manual save"


@router.post("/commit")
async def commit(req: CommitRequest):
    """Git add + commit (user-approved save)."""
    if not _cm:
        raise HTTPException(500, "Container manager not initialized")
    container = _cm.get_container_name(req.user_id)
    if not container:
        raise HTTPException(404, f"No agent container for user {req.user_id}")

    # Validate commit message length
    message = req.message[:500] if req.message else "Manual save"

    # Stage all changes
    await _cm.exec_simple(container, ["git", "-C", "/workspace", "add", "-A"])

    # Check if there are staged changes via --stat (returns file list if changes exist)
    stat = await _cm.exec_simple(container, [
        "git", "-C", "/workspace", "diff", "--cached", "--stat"
    ])
    if not stat or not stat.strip():
        return {"status": "no_changes"}

    # Commit with message as argument — no shell interpolation
    await _cm.exec_simple(container, [
        "git", "-C", "/workspace", "commit", "-m", message
    ])

    # Also sync to MinIO
    from app import workspace_sync
    await workspace_sync.sync_up(req.user_id, container)

    return {"status": "committed", "message": message}
