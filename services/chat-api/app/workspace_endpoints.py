"""Workspace API endpoints — file browsing, editing, git operations.

These run `docker exec` in the agent container to access workspace files.
The dashboard uses these to show workspace contents and approve changes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.container_manager import ContainerManager

logger = logging.getLogger("agent_api.workspace")

router = APIRouter(prefix="/api/workspace")

# Reference to container manager — set from main.py
_cm: Optional[ContainerManager] = None


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
    if ".." in path or path.startswith("/"):
        raise HTTPException(400, "Invalid path")
    content = await _exec(user_id, ["cat", f"/workspace/{path}"])
    return {"path": path, "content": content or ""}


class FileWriteRequest(BaseModel):
    user_id: str
    path: str
    content: str


@router.put("/file")
async def put_file(req: FileWriteRequest):
    """Write file to workspace."""
    if ".." in req.path or req.path.startswith("/"):
        raise HTTPException(400, "Invalid path")
    if not _cm:
        raise HTTPException(500, "Container manager not initialized")
    container = _cm.get_container_name(req.user_id)
    if not container:
        raise HTTPException(404, f"No agent container for user {req.user_id}")

    # Write via base64 to avoid shell escaping
    import base64
    encoded = base64.b64encode(req.content.encode()).decode()
    result = await _cm.exec_simple(container, [
        "sh", "-c",
        f"mkdir -p /workspace/$(dirname '{req.path}') && "
        f"echo '{encoded}' | base64 -d > /workspace/{req.path}"
    ])
    return {"path": req.path, "status": "written"}


@router.get("/diff")
async def get_diff(user_id: str):
    """Get git diff of uncommitted changes."""
    # Stage everything first to include new files
    await _exec(user_id, ["sh", "-c", "cd /workspace && git add -A"])
    diff = await _exec(user_id, [
        "sh", "-c", "cd /workspace && git diff --cached"
    ])
    # Also get summary
    summary = await _exec(user_id, [
        "sh", "-c", "cd /workspace && git diff --cached --stat"
    ])
    return {
        "diff": diff or "",
        "summary": summary or "No changes",
        "has_changes": bool(diff and diff.strip()),
    }


@router.get("/log")
async def get_log(user_id: str, limit: int = 20):
    """Get git commit history."""
    raw = await _exec(user_id, [
        "sh", "-c",
        f"cd /workspace && git log --oneline --format='%h %ai %s' -{limit}"
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

    result = await _cm.exec_simple(container, [
        "sh", "-c",
        f"cd /workspace && git add -A && "
        f"git diff --cached --quiet && echo 'NO_CHANGES' || "
        f"git commit -m '{req.message}'"
    ])

    if result and "NO_CHANGES" in result:
        return {"status": "no_changes"}

    # Also sync to MinIO
    from app import workspace_sync
    await workspace_sync.sync_up(req.user_id, container)

    return {"status": "committed", "message": req.message}
