#!/usr/bin/env python3
"""
Parse claude --output-format stream-json into a human-readable activity log.

Usage: python3 parse-stream.py stream.jsonl output.log meta.json iteration

The stream JSONL contains events like:
  {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
  {"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"..."}}]}}
  {"type":"tool_result","content":"..."}
  {"type":"result","subtype":"success","total_cost_usd":0.42,...}
"""

import json
import sys
from pathlib import Path


def parse_stream(stream_path, log_path, meta_path, iteration):
    lines = []
    result_data = {}
    tool_calls = 0
    files_read = []
    files_edited = []
    bash_commands = []
    current_tool = None

    try:
        raw = Path(stream_path).read_text().strip()
    except (OSError, FileNotFoundError):
        Path(log_path).write_text("(no stream output)\n")
        Path(meta_path).write_text(json.dumps({"iteration": int(iteration), "cost_usd": 0}, indent=2))
        return

    for line in raw.split("\n"):
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue

        evt_type = evt.get("type", "")

        # Final result event — has cost, tokens, etc.
        if evt_type == "result":
            result_data = evt
            result_text = evt.get("result", "")
            if result_text:
                lines.append("")
                lines.append("═══ FINAL RESULT ═══")
                lines.append(result_text)
            continue

        # Assistant message with content blocks
        if evt_type == "assistant":
            msg = evt.get("message", {})
            for block in msg.get("content", []):
                block_type = block.get("type", "")

                if block_type == "text":
                    text = block.get("text", "").strip()
                    if text:
                        lines.append(text)

                elif block_type == "tool_use":
                    tool_calls += 1
                    name = block.get("name", "?")
                    inp = block.get("input", {})
                    current_tool = name

                    if name == "Bash":
                        cmd = inp.get("command", "")
                        bash_commands.append(cmd)
                        # Show first 200 chars of command
                        display = cmd[:200] + ("..." if len(cmd) > 200 else "")
                        lines.append(f"\n▶ BASH: {display}")

                    elif name == "Read":
                        fp = inp.get("file_path", "")
                        files_read.append(fp)
                        short = fp.split("/")[-1] if "/" in fp else fp
                        lines.append(f"\n◀ READ: {short}")

                    elif name == "Edit":
                        fp = inp.get("file_path", "")
                        old = inp.get("old_string", "")[:80]
                        new = inp.get("new_string", "")[:80]
                        files_edited.append(fp)
                        short = fp.split("/")[-1] if "/" in fp else fp
                        lines.append(f"\n✎ EDIT: {short}")
                        lines.append(f"  - {old}...")
                        lines.append(f"  + {new}...")

                    elif name == "Write":
                        fp = inp.get("file_path", "")
                        files_edited.append(fp)
                        short = fp.split("/")[-1] if "/" in fp else fp
                        content_preview = inp.get("content", "")[:100]
                        lines.append(f"\n✎ WRITE: {short}")
                        lines.append(f"  {content_preview}...")

                    elif name == "Glob":
                        pattern = inp.get("pattern", "")
                        lines.append(f"\n🔍 GLOB: {pattern}")

                    elif name == "Grep":
                        pattern = inp.get("pattern", "")
                        lines.append(f"\n🔍 GREP: {pattern}")

                    elif name == "Agent":
                        desc = inp.get("description", "")
                        lines.append(f"\n🤖 AGENT: {desc}")

                    else:
                        lines.append(f"\n⚙ {name}: {json.dumps(inp)[:150]}")

            continue

        # Tool result
        if evt_type == "tool_result":
            content = evt.get("content", "")
            if isinstance(content, str) and content.strip():
                # Show first 500 chars of tool output
                preview = content[:500]
                if len(content) > 500:
                    preview += f"\n  ... ({len(content)} chars total)"
                lines.append(f"  → {preview}")
            continue

    # Write activity log
    header = []
    header.append(f"═══ Conductor Batch — Iteration {iteration} ═══")
    header.append(f"Tool calls: {tool_calls}")
    if files_read:
        header.append(f"Files read: {len(files_read)}")
    if files_edited:
        header.append(f"Files edited: {', '.join(set(f.split('/')[-1] for f in files_edited))}")
    if bash_commands:
        header.append(f"Bash commands: {len(bash_commands)}")
    header.append("")

    Path(log_path).write_text("\n".join(header + lines) + "\n")

    # Write metadata
    usage = result_data.get("usage", {})
    meta = {
        "iteration": int(iteration),
        "cost_usd": result_data.get("total_cost_usd", 0),
        "duration_ms": result_data.get("duration_ms", 0),
        "num_turns": result_data.get("num_turns", 0),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_create_tokens": usage.get("cache_creation_input_tokens", 0),
        "session_id": result_data.get("session_id", ""),
        "stop_reason": result_data.get("stop_reason", ""),
        "is_error": result_data.get("is_error", False),
        "tool_calls": tool_calls,
        "files_read": len(files_read),
        "files_edited": list(set(files_edited)),
        "bash_commands": len(bash_commands),
    }
    Path(meta_path).write_text(json.dumps(meta, indent=2) + "\n")

    # Print summary
    cost = meta["cost_usd"]
    dur = meta["duration_ms"] / 1000
    turns = meta["num_turns"]
    print(f"cost=${cost:.2f}  duration={dur:.0f}s  turns={turns}  tools={tool_calls}  edits={len(files_edited)}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} stream.jsonl output.log meta.json iteration")
        sys.exit(1)
    parse_stream(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
