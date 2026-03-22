#!/usr/bin/env python3
"""Score a speaker identity test phase.

Parses recorder bot logs to extract track-to-speaker mappings,
validates against expected speakers.

Google Meet uses direct element→name resolution (not voting/locking).
The relevant log patterns are:
  [SpeakerIdentity] Element N → "Name" (platform: googlemeet)
  [SPEAKER MAPPED] Track N: "old" → "new"
  [SPEAKER ACTIVE] Track N → "Name"
  [SpeakerIdentity] Participant count changed: N → M. Invalidating
  [SpeakerIdentity] All track mappings cleared.

Usage:
  python3 score.py <phase_dir> <expected_speakers_csv>

Example:
  python3 score.py results/run-2026-03-22/phase-1 Alice,Bob,Charlie
"""

import json
import re
import sys
from pathlib import Path


def parse_events(log_file: Path) -> dict:
    """Parse all speaker identity events from recorder logs."""
    invalidations = []
    new_speakers = []
    mappings = []
    element_resolutions = []
    media_element_counts = []
    confirmed_segments = []

    invalidation_pat = re.compile(
        r'\[SpeakerIdentity\] Participant count changed: (\d+) → (\d+)\. Invalidating'
    )
    cleared_pat = re.compile(r'\[SpeakerIdentity\] All track mappings cleared')
    new_speaker_pat = re.compile(r'NEW SPEAKER.*Track (\d+)')
    mapped_pat = re.compile(r'SPEAKER MAPPED.*Track (\d+): "([^"]*)" → "([^"]*)"')
    active_pat = re.compile(r'SPEAKER ACTIVE.*Track (\d+) → "([^"]*)"')
    element_pat = re.compile(r'\[SpeakerIdentity\] Element (\d+) → "([^"]+)" \(platform: googlemeet\)')
    per_speaker_pat = re.compile(r'\[PerSpeaker\] Found (\d+) media elements')
    confirmed_pat = re.compile(r'CONFIRMED\] (\S+) \| (\S+) \| [^|]+ \| ([^ ]+) \| "(.*)"')

    if not log_file.exists():
        return {"invalidations": [], "new_speakers": [], "mappings": [],
                "element_resolutions": [], "media_element_counts": [], "confirmed_segments": []}

    with open(log_file) as f:
        for i, line in enumerate(f):
            m = invalidation_pat.search(line)
            if m:
                invalidations.append({
                    "line": i, "from": int(m.group(1)), "to": int(m.group(2)),
                })
                continue

            if cleared_pat.search(line):
                invalidations.append({"line": i, "type": "cleared"})
                continue

            m = new_speaker_pat.search(line)
            if m:
                new_speakers.append({"line": i, "track": int(m.group(1))})
                continue

            m = mapped_pat.search(line)
            if m:
                mappings.append({
                    "line": i, "track": int(m.group(1)),
                    "from": m.group(2), "to": m.group(3),
                })
                continue

            m = active_pat.search(line)
            if m:
                # SPEAKER ACTIVE also establishes a mapping
                mappings.append({
                    "line": i, "track": int(m.group(1)),
                    "from": "", "to": m.group(2),
                })
                continue

            m = element_pat.search(line)
            if m:
                name = m.group(2)
                if name:  # skip empty resolutions
                    element_resolutions.append({
                        "line": i, "element": int(m.group(1)), "name": name,
                    })
                continue

            m = per_speaker_pat.search(line)
            if m:
                media_element_counts.append({"line": i, "count": int(m.group(1))})
                continue

            m = confirmed_pat.search(line)
            if m:
                confirmed_segments.append({
                    "line": i, "speaker": m.group(1), "lang": m.group(2),
                    "segment_id": m.group(3), "text": m.group(4),
                })

    return {
        "invalidations": invalidations,
        "new_speakers": new_speakers,
        "mappings": mappings,
        "element_resolutions": element_resolutions,
        "media_element_counts": media_element_counts,
        "confirmed_segments": confirmed_segments,
    }


def score_phase(phase_dir: Path, expected_speakers: list[str]) -> dict:
    """Score a single phase."""
    log_file = phase_dir / "speaker-events.log"
    full_log = phase_dir / "recorder-full.log"

    # Parse from both logs, use the one with more element data
    events = parse_events(log_file)
    full_events = parse_events(full_log)
    if len(full_events["element_resolutions"]) > len(events["element_resolutions"]):
        events = full_events
    # Always merge confirmed segments from full log (speaker-events.log filters them out)
    if len(full_events["confirmed_segments"]) > len(events["confirmed_segments"]):
        events["confirmed_segments"] = full_events["confirmed_segments"]

    invalidations = events["invalidations"]
    element_resolutions = events["element_resolutions"]
    mappings = events["mappings"]

    result = {
        "expected_speakers": expected_speakers,
        "invalidations": invalidations,
        "new_speakers": events["new_speakers"],
        "mappings": mappings,
        "element_resolutions": element_resolutions,
        "media_element_counts": events["media_element_counts"],
        "confirmed_segments": events["confirmed_segments"],
        "checks": {},
    }

    # Build current element→speaker mapping from SPEAKER MAPPED/ACTIVE events
    # These represent actual accepted state changes (after dedup check),
    # unlike Element→Name logs which include rejected resolutions.
    last_invalidation_line = max((inv["line"] for inv in invalidations), default=-1)

    # Get accepted mappings after last invalidation
    current_accepted = [m for m in mappings if m["line"] > last_invalidation_line and m["to"]]

    # Build final mapping: keep last accepted mapping per track
    latest_by_track = {}
    for m in current_accepted:
        latest_by_track[m["track"]] = {"element": m["track"], "name": m["to"], "line": m["line"]}

    # If no accepted mappings found, fall back to element resolutions
    if not latest_by_track:
        current_resolutions = [r for r in element_resolutions if r["line"] > last_invalidation_line]
        for r in current_resolutions:
            latest_by_track[r["element"]] = r

    current_mappings = list(latest_by_track.values())
    result["current_mappings"] = current_mappings

    # Check: all expected speakers are mapped
    mapped_speakers = {m["name"] for m in current_mappings}
    expected_set = set(expected_speakers)
    result["checks"]["all_mapped"] = {
        "pass": expected_set <= mapped_speakers,
        "expected": sorted(expected_set),
        "mapped": sorted(mapped_speakers),
        "missing": sorted(expected_set - mapped_speakers),
        "extra": sorted(mapped_speakers - expected_set),
    }

    # Check: no duplicate elements (1:1 mapping)
    elements = [m["element"] for m in current_mappings]
    result["checks"]["unique_elements"] = {
        "pass": len(elements) == len(set(elements)),
        "elements": elements,
    }

    # Check: no duplicate speakers (each speaker on exactly one element)
    speakers = [m["name"] for m in current_mappings]
    result["checks"]["unique_speakers"] = {
        "pass": len(speakers) == len(set(speakers)),
        "speakers": speakers,
    }

    # Check: mapping stability — no speaker was remapped to a different track
    # Uses accepted mappings only (after dedup check), not raw element resolutions
    speaker_tracks = {}
    remaps = []
    for m in current_accepted:
        name = m["to"]
        track = m["track"]
        if name in speaker_tracks and speaker_tracks[name] != track:
            remaps.append({"speaker": name, "from_track": speaker_tracks[name], "to_track": track})
        speaker_tracks[name] = track
    result["checks"]["mapping_stability"] = {
        "pass": len(remaps) == 0,
        "remaps": remaps,
    }

    # Check: confirmed segments include all expected speakers (most important check)
    # Note: snapshots are cumulative — earlier phase speakers may still appear
    confirmed_speakers = {s["speaker"] for s in events["confirmed_segments"]}
    missing_confirmed = expected_set - confirmed_speakers
    result["checks"]["confirmed_attribution"] = {
        "pass": expected_set <= confirmed_speakers,
        "confirmed_speakers": sorted(confirmed_speakers),
        "expected": sorted(expected_set),
        "missing": sorted(missing_confirmed),
        "segment_count": len(events["confirmed_segments"]),
    }

    # Overall — confirmed_attribution is the definitive check (ground truth).
    # After invalidation, all_mapped may be incomplete (lazy re-resolution).
    # mapping_stability is informational (flicker during overlap is expected).
    has_invalidations = len(invalidations) > 0
    if has_invalidations:
        hard_checks = ["confirmed_attribution", "unique_elements", "unique_speakers"]
    else:
        hard_checks = ["confirmed_attribution", "all_mapped", "unique_elements", "unique_speakers"]
    all_hard_pass = all(result["checks"][c]["pass"] for c in hard_checks if c in result["checks"])
    result["overall"] = "PASS" if all_hard_pass else "FAIL"

    return result


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <phase_dir> <expected_speakers_csv>")
        sys.exit(1)

    phase_dir = Path(sys.argv[1])
    expected_speakers = [s.strip() for s in sys.argv[2].split(",")]

    result = score_phase(phase_dir, expected_speakers)

    # Save JSON
    with open(phase_dir / "score.json", "w") as f:
        json.dump(result, f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Expected: {result['expected_speakers']}  ->  {result['overall']}")
    print(f"{'='*60}")

    if result["invalidations"]:
        print(f"Invalidations: {len(result['invalidations'])}")
        for inv in result["invalidations"]:
            if "from" in inv:
                print(f"  Participant count: {inv['from']} -> {inv['to']}")
            else:
                print(f"  All mappings cleared")

    print(f"\nCurrent mappings ({len(result['current_mappings'])}):")
    for m in result["current_mappings"]:
        print(f"  Element {m['element']} -> \"{m['name']}\"")

    if result["confirmed_segments"]:
        speakers = sorted({s["speaker"] for s in result["confirmed_segments"]})
        print(f"\nConfirmed transcription speakers: {speakers}")

    hard_check_names = {"confirmed_attribution", "all_mapped", "unique_elements", "unique_speakers"}
    print()
    for name, check in result["checks"].items():
        status = "PASS" if check["pass"] else "FAIL"
        kind = "" if name in hard_check_names else " (info)"
        detail = ""
        if name == "all_mapped" and check.get("missing"):
            detail = f" — missing: {check['missing']}"
        elif name == "all_mapped" and check.get("extra"):
            detail = f" — extra: {check['extra']}"
        elif name == "mapping_stability" and check.get("remaps"):
            unique_remaps = set((r["speaker"], r.get("from_track", r.get("from_element")), r.get("to_track", r.get("to_element"))) for r in check["remaps"])
            detail = f" — {len(check['remaps'])} flips across {len(unique_remaps)} unique transitions"
        elif name == "confirmed_attribution" and check.get("missing"):
            detail = f" — missing: {check['missing']}"
        print(f"  [{status}] {name}{kind}{detail}")
    print()


if __name__ == "__main__":
    main()
