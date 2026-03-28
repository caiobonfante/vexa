#!/usr/bin/env python3
"""
Conductor Dashboard — single-view observability for all missions.

Usage:
  python3 conductor/dashboard.py          # one-shot
  python3 conductor/dashboard.py --watch  # refresh every 5s
  python3 conductor/dashboard.py --json   # machine-readable
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONDUCTOR_DIR = REPO / "conductor"
WORKTREE_DIR = REPO / ".worktrees"


def find_missions():
    """Find all mission directories (worktrees + main conductor)."""
    missions = {}

    # Worktree missions
    if WORKTREE_DIR.exists():
        for wt in sorted(WORKTREE_DIR.iterdir()):
            if wt.is_dir() and (wt / "conductor" / "mission.md").exists():
                missions[wt.name] = wt / "conductor"

    # Main conductor (if it has a real mission, not template)
    main_mission = CONDUCTOR_DIR / "mission.md"
    if main_mission.exists():
        content = main_mission.read_text()
        if "<what to work on>" not in content:
            missions["(default)"] = CONDUCTOR_DIR

    return missions


def parse_mission(mission_path):
    """Parse mission.md for focus/problem/target."""
    content = mission_path.read_text()
    info = {}
    for line in content.split("\n"):
        line = line.strip()
        for key in ("focus", "problem", "target", "stop-when", "constraint"):
            if line.lower().startswith(f"{key}:"):
                info[key] = line.split(":", 1)[1].strip()
    return info


def parse_state(state_path):
    """Parse state.json."""
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text())


def parse_log(log_path):
    """Extract key events from conductor.log."""
    if not log_path.exists():
        return {"status": "no log", "events": []}

    content = log_path.read_text()
    lines = content.strip().split("\n")

    status = "unknown"
    start_time = None
    end_time = None

    for line in lines:
        if "CONDUCTOR START" in line:
            m = re.match(r"\[([^\]]+)\]", line)
            if m:
                start_time = m.group(1)
        if "CONDUCTOR END" in line:
            m = re.match(r"\[([^\]]+)\]", line)
            if m:
                end_time = m.group(1)
        if "MISSION ACCOMPLISHED" in line:
            status = "COMPLETED"
        elif "PLATEAU DETECTED" in line:
            status = "PLATEAU"
        elif "Iteration limit" in line:
            status = "LIMIT"
        elif "Stop signal" in line:
            status = "STOPPED"
        elif "spawning orchestrator" in line:
            status = "RUNNING"
        elif "running skeptical evaluator" in line:
            status = "EVALUATING"

    duration = None
    if start_time and end_time:
        try:
            t0 = datetime.fromisoformat(start_time)
            t1 = datetime.fromisoformat(end_time)
            duration = (t1 - t0).total_seconds()
        except (ValueError, TypeError):
            pass

    return {"status": status, "start": start_time, "end": end_time, "duration": duration}


def collect_batch_meta(conductor_path):
    """Collect metadata from all batch meta files."""
    batches_dir = conductor_path / "batches"
    if not batches_dir.exists():
        return []

    metas = []
    for meta_file in sorted(batches_dir.glob("meta-*.json")):
        try:
            metas.append(json.loads(meta_file.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return metas


def parse_evaluator(conductor_path):
    """Parse evaluator verdict."""
    verdict_path = conductor_path / "evaluator-verdict.md"
    if not verdict_path.exists():
        return "no verdict"
    content = verdict_path.read_text()
    if re.search(r"REJECT", content, re.IGNORECASE):
        return "REJECTED"
    elif re.search(r"ACCEPT", content, re.IGNORECASE):
        return "ACCEPTED"
    return "unknown"


def format_duration(seconds):
    """Format seconds as Xm Ys."""
    if seconds is None:
        return "—"
    m = int(seconds) // 60
    s = int(seconds) % 60
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def format_cost(usd):
    """Format cost."""
    if usd is None or usd == 0:
        return "—"
    return f"${usd:.2f}"


def build_dashboard():
    """Build the dashboard data structure."""
    missions = find_missions()
    # Read global state for phase info
    global_state = parse_state(CONDUCTOR_DIR / "state.json")

    dashboard = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "phase": global_state.get("phase", "unknown"),
        "status": global_state.get("status", "unknown"),
        "mission": global_state.get("mission"),
        "iteration": global_state.get("iteration", 0),
        "missions": [],
        "totals": {"cost": 0, "duration": 0, "count": 0},
        "scores": {},
    }

    for name, path in missions.items():
        mission_info = parse_mission(path / "mission.md") if (path / "mission.md").exists() else {}
        state = parse_state(path / "state.json")
        log_info = parse_log(path / "conductor.log")
        batch_metas = collect_batch_meta(path)
        evaluator = parse_evaluator(path)

        cost = sum(m.get("cost_usd", 0) for m in batch_metas)
        tokens_in = sum(m.get("input_tokens", 0) for m in batch_metas)
        tokens_out = sum(m.get("output_tokens", 0) for m in batch_metas)
        turns = sum(m.get("num_turns", 0) for m in batch_metas)

        iteration = state.get("iteration", 0)
        status = state.get("status", log_info.get("status", "unknown"))

        mission_data = {
            "name": name,
            "focus": mission_info.get("focus", "—"),
            "target": mission_info.get("target", "—"),
            "iteration": iteration,
            "status": status,
            "cost": cost,
            "duration": log_info.get("duration"),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "turns": turns,
            "evaluator": evaluator,
            "batches": len(batch_metas),
        }
        dashboard["missions"].append(mission_data)
        dashboard["totals"]["cost"] += cost
        dashboard["totals"]["duration"] += (log_info.get("duration") or 0)
        dashboard["totals"]["count"] += 1

        # Collect scores from mission state
        for feat, info in state.get("features", {}).items():
            score = info.get("score", 0) if isinstance(info, dict) else info
            if feat not in dashboard["scores"] or score > dashboard["scores"][feat]:
                dashboard["scores"][feat] = score

    # Always include scores from global state (even with no active missions)
    for feat, info in global_state.get("features", {}).items():
        score = info.get("score", 0) if isinstance(info, dict) else info
        if feat not in dashboard["scores"] or score > dashboard["scores"][feat]:
            dashboard["scores"][feat] = score

    # Include plan log if in PLAN phase
    if dashboard.get("phase") == "plan":
        dashboard["plan_log"] = get_plan_log()

    return dashboard


def render_text(dashboard):
    """Render the dashboard as formatted text."""
    w = 66
    lines = []
    lines.append("=" * w)
    lines.append(f"  CONDUCTOR DASHBOARD{dashboard['timestamp']:>{w - 22}}")
    lines.append("=" * w)
    lines.append("")

    # Missions
    lines.append("  MISSIONS")
    lines.append("  " + "─" * (w - 4))

    if not dashboard["missions"]:
        lines.append("  (no active missions)")
    else:
        for m in dashboard["missions"]:
            status_color = m["status"].upper()
            cost_str = format_cost(m["cost"])
            dur_str = format_duration(m["duration"])
            lines.append(f"  {m['name']:<20s} iter {m['iteration']}  {status_color:<12s} {cost_str:>7s}  {dur_str:>8s}")
            lines.append(f"    focus: {m['focus']}")
            if m["evaluator"] != "no verdict":
                lines.append(f"    evaluator: {m['evaluator']}")
            if m["tokens_in"] or m["tokens_out"]:
                lines.append(f"    tokens: {m['tokens_in']:,} in / {m['tokens_out']:,} out  turns: {m['turns']}")
            lines.append("")

    # Totals
    t = dashboard["totals"]
    lines.append(f"  TOTALS  {t['count']} missions  {format_cost(t['cost'])}  {format_duration(t['duration'])}")
    lines.append("")

    # Scores
    scores = dashboard["scores"]
    if scores:
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = [(n, s) for n, s in sorted_scores if s >= 80][:5]
        needs_work = [(n, s) for n, s in sorted_scores if s < 80][:5]

        lines.append("  FEATURE SCORES")
        lines.append("  " + "─" * (w - 4))

        if top or needs_work:
            lines.append(f"  {'TOP SCORES':<33s} {'NEEDS WORK'}")
            max_rows = max(len(top), len(needs_work))
            for i in range(max_rows):
                left = ""
                right = ""
                if i < len(top):
                    left = f"  {top[i][0]:<25s} {top[i][1]:3d}"
                else:
                    left = " " * 31
                if i < len(needs_work):
                    right = f"  {needs_work[i][0]:<25s} {needs_work[i][1]:3d}"
                lines.append(f"{left}{right}")

    lines.append("")
    lines.append("=" * w)
    return "\n".join(lines)


def render_json(dashboard):
    """Render as JSON."""
    return json.dumps(dashboard, indent=2)


# =============================================================================
# Web server
# =============================================================================
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
import webbrowser


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress request logs

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text, status=200):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html, status=200):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            html_path = CONDUCTOR_DIR / "dashboard.html"
            if html_path.exists():
                self._html(html_path.read_text())
            else:
                self._text("dashboard.html not found", 404)

        elif path == "/api/dashboard":
            self._json(build_dashboard())

        elif path == "/api/plan-log":
            self._text(get_plan_log())

        elif path.startswith("/api/logs/"):
            mission_name = unquote(path[len("/api/logs/"):])
            log_text = get_mission_logs(mission_name)
            self._text(log_text)

        elif path.startswith("/api/batch/"):
            mission_name = unquote(path[len("/api/batch/"):])
            batch_text = get_mission_batch(mission_name)
            self._text(batch_text)

        elif path.startswith("/api/evaluator/"):
            mission_name = unquote(path[len("/api/evaluator/"):])
            eval_text = get_mission_evaluator(mission_name)
            self._text(eval_text)

        elif path.startswith("/api/team-messages/"):
            mission_name = unquote(path[len("/api/team-messages/"):])
            messages = get_team_messages(mission_name)
            self._json(messages)

        else:
            self._text("not found", 404)


def get_mission_logs(name, lines=50):
    """Get last N lines of a mission's conductor.log."""
    paths = [
        WORKTREE_DIR / name / "conductor" / "conductor.log",
        CONDUCTOR_DIR / "conductor.log",
    ]
    for p in paths:
        if p.exists():
            all_lines = p.read_text().strip().split("\n")
            return "\n".join(all_lines[-lines:])
    return f"No logs found for mission '{name}'"


def get_mission_batch(name):
    """Get the latest batch output for a mission.

    Prefers parsed batch-*.log. If not available (still running),
    parses stream-*.jsonl on the fly.
    """
    paths = [
        WORKTREE_DIR / name / "conductor" / "batches",
        CONDUCTOR_DIR / "batches",
    ]
    for batches_dir in paths:
        if not batches_dir.exists():
            continue

        # First try parsed log
        batch_files = sorted(batches_dir.glob("batch-*.log"), reverse=True)
        if batch_files and batch_files[0].stat().st_size > 0:
            return batch_files[0].read_text()

        # Fall back to live stream parsing
        stream_files = sorted(batches_dir.glob("stream-*.jsonl"), reverse=True)
        if stream_files and stream_files[0].stat().st_size > 0:
            return parse_stream_live(stream_files[0])

    return f"No batch output found for mission '{name}'"


def parse_stream_live(stream_path):
    """Parse a stream-json file into human-readable activity log (live, no file write)."""
    lines = []
    try:
        raw = stream_path.read_text().strip()
    except (OSError, FileNotFoundError):
        return "(no stream data)"

    for line in raw.split("\n"):
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue

        evt_type = evt.get("type", "")

        if evt_type == "result":
            result_text = evt.get("result", "")
            if result_text:
                lines.append("")
                lines.append("═══ FINAL RESULT ═══")
                lines.append(result_text)
            continue

        if evt_type == "assistant":
            msg = evt.get("message", {})
            for block in msg.get("content", []):
                bt = block.get("type", "")
                if bt == "text":
                    text = block.get("text", "").strip()
                    if text:
                        lines.append(text)
                elif bt == "tool_use":
                    name = block.get("name", "?")
                    inp = block.get("input", {})
                    if name == "Bash":
                        cmd = inp.get("command", "")[:200]
                        lines.append(f"\n▶ BASH: {cmd}")
                    elif name == "Read":
                        fp = inp.get("file_path", "")
                        short = fp.split("/")[-1] if "/" in fp else fp
                        lines.append(f"\n◀ READ: {short}")
                    elif name == "Edit":
                        fp = inp.get("file_path", "")
                        short = fp.split("/")[-1] if "/" in fp else fp
                        old = inp.get("old_string", "")[:80]
                        new = inp.get("new_string", "")[:80]
                        lines.append(f"\n✎ EDIT: {short}")
                        lines.append(f"  - {old}...")
                        lines.append(f"  + {new}...")
                    elif name == "Write":
                        fp = inp.get("file_path", "")
                        short = fp.split("/")[-1] if "/" in fp else fp
                        lines.append(f"\n✎ WRITE: {short}")
                    elif name == "Grep":
                        lines.append(f"\n🔍 GREP: {inp.get('pattern', '')}")
                    elif name == "Glob":
                        lines.append(f"\n🔍 GLOB: {inp.get('pattern', '')}")
                    elif name == "Agent":
                        lines.append(f"\n🤖 AGENT: {inp.get('description', '')}")
                    else:
                        lines.append(f"\n⚙ {name}")
            continue

        if evt_type == "tool_result":
            content = evt.get("content", "")
            if isinstance(content, str) and content.strip():
                preview = content[:300]
                if len(content) > 300:
                    preview += f"\n  ... ({len(content)} chars)"
                lines.append(f"  → {preview}")
            continue

    if not lines:
        size = stream_path.stat().st_size
        return f"(streaming... {size // 1024}KB received, parsing events)"

    return "\n".join(lines)


def get_team_messages(name):
    """Extract team messages from the latest stream JSONL for a mission."""
    paths = [
        WORKTREE_DIR / name / "conductor" / "batches",
        CONDUCTOR_DIR / "batches",
    ]
    messages = []

    for batches_dir in paths:
        if not batches_dir.exists():
            continue

        stream_files = sorted(batches_dir.glob("stream-*.jsonl"), reverse=True)
        if not stream_files:
            continue

        try:
            raw = stream_files[0].read_text().strip()
        except (OSError, FileNotFoundError):
            continue

        # Track which tool_use IDs are Agent/TeamCreate calls and their agent names
        agent_tool_ids = {}  # tool_use_id -> agent name

        for line in raw.split("\n"):
            if not line.strip():
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue

            evt_type = evt.get("type", "")
            timestamp = evt.get("timestamp", "")

            if evt_type == "assistant":
                msg = evt.get("message", {})
                for block in msg.get("content", []):
                    bt = block.get("type", "")

                    if bt == "tool_use":
                        tool_name = block.get("name", "")
                        inp = block.get("input", {})
                        tool_id = block.get("id", "")

                        if tool_name == "TeamCreate":
                            team = inp.get("team_name", "")
                            desc = inp.get("description", "")
                            messages.append({
                                "role": "conductor",
                                "text": f"Created team '{team}': {desc}",
                                "timestamp": timestamp,
                                "type": "team",
                            })

                        elif tool_name == "Agent":
                            agent_name = inp.get("name", "agent")
                            desc = inp.get("description", "")
                            agent_tool_ids[tool_id] = agent_name
                            messages.append({
                                "role": "conductor",
                                "text": f"Spawned {agent_name}: {desc}",
                                "timestamp": timestamp,
                                "type": "spawn",
                            })

                        elif tool_name == "SendMessage":
                            to = inp.get("to", "?")
                            msg_text = inp.get("message", "")
                            if isinstance(msg_text, dict):
                                msg_type = msg_text.get("type", "")
                                msg_text = f"[{msg_type}]"
                            messages.append({
                                "role": "conductor",
                                "text": f"To {to}: {msg_text}" if len(str(msg_text)) < 500 else f"To {to}: {str(msg_text)[:500]}...",
                                "timestamp": timestamp,
                                "type": "message",
                            })

                    elif bt == "text":
                        text = block.get("text", "").strip()
                        # Conductor coordination messages
                        if text and any(kw in text.lower() for kw in [
                            "team", "dev", "validator", "agent", "mission",
                            "iteration", "spawning", "created", "checking",
                            "entry protocol", "shutdown", "verdict",
                        ]):
                            messages.append({
                                "role": "conductor",
                                "text": text[:500],
                                "timestamp": timestamp,
                                "type": "coordination",
                            })

            elif evt_type == "tool_result":
                # Check if this is a result from an Agent call
                content = evt.get("content", "")
                tool_use_id = ""
                # tool_result doesn't always have the tool_use_id at top level
                # but we can check if content mentions agent results
                if isinstance(content, str) and content.strip():
                    # Look for agent completion patterns
                    preview = content[:1000]
                    if any(kw in preview.lower() for kw in ["completed", "finished", "done", "verdict", "accept", "reject", "score"]):
                        messages.append({
                            "role": "agent",
                            "text": content[:500],
                            "timestamp": timestamp,
                            "type": "result",
                        })

        break  # Only process the first found batches dir

    return messages


def get_mission_evaluator(name):
    """Get the evaluator verdict for a mission."""
    paths = [
        WORKTREE_DIR / name / "conductor" / "evaluator-verdict.md",
        CONDUCTOR_DIR / "evaluator-verdict.md",
    ]
    for p in paths:
        if p.exists():
            return p.read_text()
    return f"No evaluator verdict found for mission '{name}'"


def get_plan_log(lines=50):
    """Get the latest PLAN stage activity from plan-log.jsonl."""
    plan_log = CONDUCTOR_DIR / "plan-log.jsonl"
    if not plan_log.exists():
        return "(no plan activity yet)"
    all_lines = plan_log.read_text().strip().split("\n")
    result = []
    for line in all_lines[-lines:]:
        try:
            import json as _json
            entry = _json.loads(line)
            rule = entry.get("rule", "")
            doing = entry.get("doing", "")
            why = entry.get("why", "")
            finding = entry.get("finding", "")
            parts = []
            if rule:
                parts.append(f"RULE: {rule}")
            if doing:
                parts.append(f"DOING: {doing}")
            if why:
                parts.append(f"WHY: {why}")
            if finding:
                parts.append(f"FINDING: {finding}")
            result.append("\n".join(parts))
        except Exception:
            result.append(line)
    return "\n\n".join(result) if result else "(no plan activity yet)"


def run_web(port=8899):
    """Start the web dashboard server."""
    import socket
    # Kill any existing dashboard on this port
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        if s.connect_ex(("localhost", port)) == 0:
            os.system(f"fuser {port}/tcp 2>/dev/null | xargs -r kill 2>/dev/null")
            time.sleep(0.5)
        s.close()
    except Exception:
        pass
    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Conductor Dashboard: http://localhost:{port}")
    webbrowser.open(f"http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Conductor Dashboard")
    parser.add_argument("--watch", action="store_true", help="Auto-refresh terminal every 5s")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--web", action="store_true", help="Start web dashboard server")
    parser.add_argument("--port", type=int, default=8899, help="Web server port (default: 8899)")
    parser.add_argument("--interval", type=int, default=5, help="Refresh interval for --watch")
    args = parser.parse_args()

    if args.web:
        run_web(args.port)
    elif args.watch and not args.json:
        try:
            while True:
                os.system("clear")
                dashboard = build_dashboard()
                print(render_text(dashboard))
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass
    else:
        dashboard = build_dashboard()
        if args.json:
            print(render_json(dashboard))
        else:
            print(render_text(dashboard))


if __name__ == "__main__":
    main()
