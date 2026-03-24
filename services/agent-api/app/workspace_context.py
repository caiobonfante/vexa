"""Build workspace context injected into every chat turn.

Scans the workspace filesystem inside the container and produces a compact
summary: active streams, knowledge counts, file sizes, compliance warnings.
Ported from Quorum's build_chat_system_prompt() pattern.
"""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("chat_api.workspace_context")


async def build_workspace_context(exec_fn, container: str) -> str:
    """Build workspace context string. exec_fn is container_manager.exec_simple."""

    lines = []

    # Current time
    now = datetime.now(timezone.utc)
    lines.append(f"Current time: {now.strftime('%Y-%m-%d %H:%M UTC')} ({now.strftime('%A')})")

    # User timezone
    user_json = await exec_fn(container, ["cat", "/workspace/user.json"])
    if user_json:
        try:
            user = json.loads(user_json)
            tz = user.get("timezone", "")
            loc = user.get("location", "")
            if tz:
                lines.append(f"User timezone: {tz}" + (f" ({loc})" if loc else ""))
        except json.JSONDecodeError:
            pass

    lines.append("")

    # Active streams
    streams_raw = await exec_fn(container, [
        "sh", "-c",
        "find /workspace/streams -maxdepth 1 -name '*.md' -printf '%f\\n' 2>/dev/null | sort"
    ])
    if streams_raw:
        stream_files = [f for f in streams_raw.strip().split("\n") if f]
        lines.append(f"── Active Streams ({len(stream_files)}) ──")
        for sf in stream_files[:30]:
            name = sf.replace(".md", "").replace("-", " ").title()
            # Get first line (title) and line count
            info = await exec_fn(container, [
                "sh", "-c",
                f"wc -l < /workspace/streams/{sf}"
            ])
            lc = info.strip() if info else "?"
            lines.append(f"  {name} [{lc} lines] [streams/{sf}]")
            if info and info.strip().isdigit() and int(info.strip()) > 300:
                lines.append(f"    ⚠ Stream too large (>300 lines) — consider compacting")
        if len(stream_files) > 30:
            lines.append(f"  ⚠ Too many active streams ({len(stream_files)}) — consider archiving")
    else:
        lines.append("── Active Streams (0) ──")
        lines.append("  No streams yet. Create them in streams/ as topics emerge.")

    lines.append("")

    # Knowledge counts
    knowledge_raw = await exec_fn(container, [
        "sh", "-c",
        "for d in contacts companies products meetings action-items; do "
        "  count=$(find /workspace/knowledge/entities/$d /workspace/knowledge/$d -name '*.md' 2>/dev/null | wc -l); "
        "  echo \"$d:$count\"; "
        "done"
    ])
    if knowledge_raw:
        lines.append("── Knowledge ──")
        for kline in knowledge_raw.strip().split("\n"):
            if ":" in kline:
                name, count = kline.split(":", 1)
                if count.strip() != "0":
                    lines.append(f"  {name}: {count.strip()} files")
    else:
        lines.append("── Knowledge ──")
        lines.append("  Empty. Will grow as you discuss topics, meetings, people.")

    lines.append("")

    # Workspace files
    file_sizes = await exec_fn(container, [
        "sh", "-c",
        "for f in notes.md timeline.md soul.md; do "
        "  if [ -f /workspace/$f ]; then "
        "    lc=$(wc -l < /workspace/$f); echo \"$f:$lc\"; "
        "  fi; "
        "done"
    ])
    if file_sizes:
        lines.append("── Workspace ──")
        for fline in file_sizes.strip().split("\n"):
            if ":" in fline:
                fname, lc = fline.split(":", 1)
                lines.append(f"  {fname} ({lc.strip()} lines)")
                if lc.strip().isdigit() and int(lc.strip()) > 300:
                    lines.append(f"    ⚠ File too large (>300 lines) — consider compacting")

    # Git status
    git_info = await exec_fn(container, [
        "sh", "-c", "cd /workspace && git log --oneline -1 2>/dev/null || echo 'no git'"
    ])
    if git_info and "no git" not in git_info:
        lines.append(f"  Last commit: {git_info.strip()}")

    return "\n".join(lines)
