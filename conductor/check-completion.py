#!/usr/bin/env python3
"""
check-completion.py — Parse findings files, check mission completion, report status.

Modes:
  --seed                          Scan findings, generate conductor-state.json
  --check --mission FILE          Check if mission target is met (exit 0=done, 1=not done)
  --status                        Print human-readable summary
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FEATURES_DIR = REPO / "features"
CONDUCTOR_DIR = REPO / "conductor"
STATE_FILE = CONDUCTOR_DIR / "state.json"


def find_findings_files():
    """Find all features/*/tests/findings.md files."""
    findings = {}
    for path in sorted(FEATURES_DIR.glob("*/tests/findings.md")):
        feature_name = path.parent.parent.name
        findings[feature_name] = path
    # Also check one level deeper (e.g., multi-platform/zoom)
    for path in sorted(FEATURES_DIR.glob("*/*/tests/findings.md")):
        rel = path.relative_to(FEATURES_DIR)
        feature_name = f"{rel.parts[0]}/{rel.parts[1]}"
        findings[feature_name] = path
    return findings


def extract_score(findings_path):
    """Extract the overall score from a findings.md file.

    Priority order:
      1. Explicit overall line: "Overall score: 85", "Overall: 85", "## Score: 85"
      2. Certainty table median (not min — one aspirational row at 0 shouldn't tank the score)
    """
    try:
        content = findings_path.read_text()
    except (OSError, IOError):
        return 0

    # Pattern 1: "Overall score: **N**" or "Overall score: N"
    m = re.search(r"[Oo]verall\s+score:\s*\*?\*?(\d+)\*?\*?", content)
    if m:
        return int(m.group(1))

    # Pattern 1b: "**Overall: N**" or "Overall: N" (without the word "score")
    m = re.search(r"[Oo]verall:\s*\*?\*?(\d+)\*?\*?", content)
    if m:
        return int(m.group(1))

    # Pattern 2: "## Score: N" or "Score: N" at start of line
    m = re.search(r"^#+\s*Score:\s*(\d+)", content, re.MULTILINE)
    if m:
        return int(m.group(1))
    m = re.search(r"^Score:\s*(\d+)", content, re.MULTILINE)
    if m:
        return int(m.group(1))

    # Pattern 3: Certainty table — find rows with a Score column, use median
    scores = []
    lines = content.split("\n")
    score_col = None
    for i, line in enumerate(lines):
        if "|" in line and "Score" in line and "Check" in line:
            cells = [c.strip() for c in line.split("|")]
            for j, cell in enumerate(cells):
                if cell == "Score":
                    score_col = j
                    break
            continue
        if score_col is not None and "|" in line and not line.strip().startswith("|--"):
            cells = [c.strip() for c in line.split("|")]
            if len(cells) > score_col:
                try:
                    score = int(cells[score_col])
                    if 0 <= score <= 100:
                        scores.append(score)
                except (ValueError, IndexError):
                    pass
    if scores:
        # Use median — one aspirational row at 0 shouldn't tank the whole feature
        sorted_scores = sorted(scores)
        mid = len(sorted_scores) // 2
        if len(sorted_scores) % 2 == 0:
            return (sorted_scores[mid - 1] + sorted_scores[mid]) // 2
        return sorted_scores[mid]

    return 0


def extract_mission_target(mission_path):
    """Parse mission.md for target and focus."""
    content = mission_path.read_text()
    mission = {}
    for line in content.split("\n"):
        line = line.strip()
        if line.lower().startswith("focus:"):
            mission["focus"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("target:"):
            mission["target"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("stop-when:"):
            mission["stop_when"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("problem:"):
            mission["problem"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("constraint:"):
            mission["constraint"] = line.split(":", 1)[1].strip()
    return mission


def check_mission_met(state, mission):
    """Check if the mission target is met based on state and mission definition.

    For score-based targets (e.g., "score >= 80"), check the relevant feature score.
    For descriptive targets, require explicit completion evidence in the evaluator
    verdict file — not generic positive words scattered across findings files.
    """
    target = mission.get("target", "")
    focus = mission.get("focus", "")

    # Check for score-based targets: "score >= N" or "score > N"
    score_match = re.search(r"score\s*>=?\s*(\d+)", target)
    if score_match:
        target_score = int(score_match.group(1))
        for name, info in state.get("features", {}).items():
            if focus.lower() in name.lower():
                current = info.get("score", 0) if isinstance(info, dict) else info
                if current >= target_score:
                    return True
        return False

    # For descriptive targets: check the evaluator verdict file for explicit
    # completion signals. We do NOT scan all findings files for generic words
    # like "pass" or "working" — those cause false positives.
    verdict_file = CONDUCTOR_DIR / "evaluator-verdict.md"
    completion_patterns = [
        r"mission\s+(target\s+)?met",
        r"mission\s+accomplished",
        r"all\s+targets?\s+met",
        r"definition\s+of\s+done\s*:?\s*(met|satisfied|complete)",
        r"target\s+(is\s+)?met",
        r"accept\s+\d+",  # validator accept with score
    ]

    # Only check the verdict file — the single authoritative source
    if verdict_file.exists():
        content = verdict_file.read_text()
        content_lower = content.lower()
        for pattern in completion_patterns:
            if re.search(pattern, content_lower):
                return True

    return False


def check_stop_condition(state, mission):
    """Check stop-when conditions."""
    stop_when = mission.get("stop_when", "")
    iteration = state.get("iteration", 0)

    # Parse "N iterations" from stop-when
    iter_match = re.search(r"(\d+)\s*iterations?", stop_when)
    if iter_match:
        max_iter = int(iter_match.group(1))
        if iteration >= max_iter:
            return True, f"iteration limit ({iteration}/{max_iter})"

    # Check "target met"
    if "target met" in stop_when.lower():
        if check_mission_met(state, mission):
            return True, "target met"

    return False, None


def seed_state():
    """Generate conductor-state.json from current findings."""
    findings = find_findings_files()
    features = {}
    for name, path in findings.items():
        score = extract_score(path)
        features[name] = {"score": score}

    state = {
        "iteration": 0,
        "status": "pending",
        "mission": None,
        "last_batch": None,
        "features": features,
        "score_history": [],
        "plateau_counter": 0,
    }
    return state


def snapshot_scores(state):
    """Take a snapshot of current scores and append to score_history.

    Merges findings-parsed scores with batch-written scores in state.json,
    keeping the HIGHER value. This prevents snapshots from overwriting
    scores that the orchestrator wrote directly to state.json.
    """
    findings = find_findings_files()
    snapshot = {}
    for name, path in findings.items():
        parsed_score = extract_score(path)
        # Keep the higher of: parsed from findings vs already in state (batch-written)
        existing = 0
        if name in state.get("features", {}):
            info = state["features"][name]
            existing = info.get("score", 0) if isinstance(info, dict) else info
        snapshot[name] = max(parsed_score, existing)

    # Update state features with merged scores
    for name, score in snapshot.items():
        if name in state.get("features", {}):
            if isinstance(state["features"][name], dict):
                state["features"][name]["score"] = score
            else:
                state["features"][name] = {"score": score}

    entry = {
        "iteration": state.get("iteration", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scores": snapshot,
    }
    if "score_history" not in state:
        state["score_history"] = []
    state["score_history"].append(entry)

    return state


def check_plateau(state, threshold=3):
    """Check if scores are unchanged for `threshold` consecutive iterations.

    Returns ("plateau", stuck_features) or ("ok", None).
    """
    history = state.get("score_history", [])
    if len(history) < threshold:
        return "ok", None

    recent = history[-threshold:]
    first_scores = recent[0]["scores"]
    stuck_features = []

    for name, first_score in first_scores.items():
        all_same = all(
            snap["scores"].get(name, 0) == first_score
            for snap in recent
        )
        if all_same and first_score < 80:
            stuck_features.append((name, first_score))

    if stuck_features:
        return "plateau", stuck_features
    return "ok", None


def print_status(state, mission=None, plateau_threshold=3):
    """Print human-readable status."""
    print(f"=== Conductor Status ===")
    print(f"Iteration: {state.get('iteration', 0)}")
    print(f"Status:    {state.get('status', 'unknown')}")
    print(f"Last batch: {state.get('last_batch', 'never')}")

    if mission:
        print(f"\n--- Mission ---")
        print(f"Focus:   {mission.get('focus', 'none')}")
        print(f"Problem: {mission.get('problem', 'none')}")
        print(f"Target:  {mission.get('target', 'none')}")
        met = check_mission_met(state, mission)
        print(f"Met:     {'YES' if met else 'NO'}")

    print(f"\n--- Feature Scores ---")
    features = state.get("features", {})
    for name in sorted(features.keys()):
        info = features[name]
        score = info.get("score", 0) if isinstance(info, dict) else info
        print(f"  {name:40s} {score:3d}")

    # Plateau info
    plateau_status, stuck = check_plateau(state, plateau_threshold)
    history = state.get("score_history", [])
    print(f"\n--- Loop Health ---")
    print(f"Snapshots:  {len(history)}")
    if plateau_status == "plateau" and stuck:
        print(f"PLATEAU:    scores unchanged for {plateau_threshold}+ iterations")
        for name, score in stuck:
            print(f"  STUCK: {name:40s} {score:3d}")
    else:
        print(f"Plateau:    none detected")


def main():
    parser = argparse.ArgumentParser(description="Conductor completion checker")
    parser.add_argument("--seed", action="store_true", help="Seed conductor-state.json from findings")
    parser.add_argument("--check", action="store_true", help="Check if mission is met (exit 0=done, 1=not)")
    parser.add_argument("--status", action="store_true", help="Print human-readable status")
    parser.add_argument("--snapshot", action="store_true", help="Take score snapshot, append to history")
    parser.add_argument("--plateau-check", action="store_true", help="Check for plateau (prints 'plateau' or 'ok')")
    parser.add_argument("--plateau-threshold", type=int, default=3,
                        help="Consecutive unchanged iterations to trigger plateau (default: 3)")
    parser.add_argument("--mission", type=str, default=str(CONDUCTOR_DIR / "mission.md"),
                        help="Path to mission.md")
    parser.add_argument("--state", type=str, default=str(STATE_FILE),
                        help="Path to conductor-state.json")
    args = parser.parse_args()

    state_path = Path(args.state)
    mission_path = Path(args.mission)

    if args.seed:
        state = seed_state()
        # If mission exists, include it
        if mission_path.exists():
            mission = extract_mission_target(mission_path)
            state["mission"] = mission.get("focus")
        state_json = json.dumps(state, indent=2)
        print(state_json)
        # Also write to file
        state_path.write_text(state_json + "\n")
        print(f"\nWritten to {state_path}", file=sys.stderr)
        return

    # Load state
    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        print(f"No state file at {state_path}. Run with --seed first.", file=sys.stderr)
        sys.exit(2)

    # Load mission
    mission = None
    if mission_path.exists():
        mission = extract_mission_target(mission_path)

    if args.snapshot:
        state = snapshot_scores(state)
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        n = len(state.get("score_history", []))
        print(f"Snapshot #{n} taken (iteration {state.get('iteration', 0)})")
        return

    if args.plateau_check:
        plateau_status, stuck = check_plateau(state, args.plateau_threshold)
        if plateau_status == "plateau" and stuck:
            print("plateau")
            for name, score in stuck:
                print(f"  STUCK: {name} at {score}", file=sys.stderr)
        else:
            print("ok")
        return

    if args.status:
        print_status(state, mission, args.plateau_threshold)
        return

    if args.check:
        if not mission:
            print("No mission file found. Nothing to check.", file=sys.stderr)
            sys.exit(2)

        # Special-case: test-loop mission checks file directly
        mission_name = mission_path.stem
        if mission_name == "test-loop":
            conductor_dir = state_path.parent
            output = conductor_dir / "test-loop-output.md"
            if not output.exists():
                print("NOT DONE: conductor/test-loop-output.md does not exist yet")
                sys.exit(1)
            text = output.read_text()
            attempts = re.findall(r"## Attempt (\d+)", text)
            found = sorted(set(attempts))
            if found == ["1", "2", "3"]:
                timestamps = re.findall(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", text)
                if len(set(timestamps)) >= 3:
                    print("DONE: all 3 attempts present with distinct timestamps")
                    sys.exit(0)
                else:
                    print(f"NOT DONE: need 3 different timestamps, found {len(set(timestamps))} unique")
                    sys.exit(1)
            else:
                missing = [str(i) for i in [1, 2, 3] if str(i) not in found]
                print(f"NOT DONE: missing Attempt section(s): {', '.join(missing)}. Found so far: {found}")
                sys.exit(1)

        # Check stop conditions
        should_stop, reason = check_stop_condition(state, mission)
        if should_stop:
            print(f"STOP: {reason}")
            sys.exit(0)

        # Check mission met independently
        if check_mission_met(state, mission):
            print("DONE: mission target met")
            sys.exit(0)

        print(f"CONTINUE: mission not yet met (iteration {state.get('iteration', 0)})")
        sys.exit(1)

    # Default: print status
    print_status(state, mission, args.plateau_threshold)


if __name__ == "__main__":
    main()
