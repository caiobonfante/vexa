#!/usr/bin/env python3
"""Score post-meeting transcription against ground truth.

Usage:
    python3 score.py --gt ground-truth.txt --meeting-id 648 [--db-url postgresql://...]
    python3 score.py --gt ground-truth.txt --segments segments.json
"""
import argparse
import json
import re
import sys
from typing import List, Tuple, Optional


def parse_gt(path: str) -> List[Tuple[float, str, str]]:
    """Parse ground truth file into (timestamp, speaker, text) tuples."""
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line.startswith("[GT]"):
                continue
            # [GT] 1774222620.172614 Alice "Good morning everyone."
            m = re.match(r'\[GT\]\s+([\d.]+)\s+(\S+)\s+"(.+)"', line)
            if m:
                entries.append((float(m.group(1)), m.group(2), m.group(3)))
    return entries


def parse_segments_json(path: str) -> List[dict]:
    """Parse segments from JSON file."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("segments", [])


def fetch_segments_db(meeting_id: int, db_url: str) -> List[dict]:
    """Fetch segments from Postgres."""
    import subprocess
    # Use psql via docker to avoid needing psycopg2
    cmd = [
        "docker", "exec", "-i",
        subprocess.check_output(
            ["docker", "ps", "-q", "-f", "name=postgres"],
            text=True
        ).strip(),
        "psql", "-U", "postgres", "-d", "vexa_restore", "-t", "-A", "-F", "|",
        "-c", f"SELECT start_time, end_time, speaker, text FROM transcriptions WHERE meeting_id = {meeting_id} ORDER BY start_time"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    segments = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            segments.append({
                "start_time": float(parts[0]),
                "end_time": float(parts[1]),
                "speaker": parts[2].strip(),
                "text": parts[3].strip(),
            })
    return segments


def normalize_text(text: str) -> List[str]:
    """Normalize text for comparison: lowercase, strip punctuation, split into words."""
    text = text.lower()
    # Remove punctuation except apostrophes within words
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.split()


def normalize_speaker(speaker: str) -> str:
    """Strip platform suffixes: 'Alice (Guest)' -> 'alice'."""
    speaker = re.sub(r"\s*\(.*\)\s*$", "", speaker)
    return speaker.strip().lower()


def word_edit_distance(ref: List[str], hyp: List[str]) -> Tuple[int, int, int, int]:
    """Compute word-level edit distance. Returns (substitutions, insertions, deletions, distance)."""
    n, m = len(ref), len(hyp)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])
    # Backtrace to count S, I, D
    i, j = n, m
    s = ins = d = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i - 1] == hyp[j - 1]:
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            s += 1
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            ins += 1
            j -= 1
        else:
            d += 1
            i -= 1
    return s, ins, d, dp[n][m]


def compute_wer(ref_words: List[str], hyp_words: List[str]) -> float:
    """Word Error Rate."""
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    _, _, _, dist = word_edit_distance(ref_words, hyp_words)
    return dist / len(ref_words)


def match_segments(gt_entries, segments) -> List[dict]:
    """Match each GT utterance to best transcript segment by WER. Greedy best-first."""
    results = []
    used_seg_indices = set()

    for gt_ts, gt_speaker, gt_text in gt_entries:
        gt_words = normalize_text(gt_text)
        best_idx = None
        best_wer = 1.0
        best_seg = None

        for i, seg in enumerate(segments):
            if i in used_seg_indices:
                continue
            seg_words = normalize_text(seg["text"])
            wer = compute_wer(gt_words, seg_words)
            if wer < best_wer:
                best_wer = wer
                best_idx = i
                best_seg = seg

        matched = best_wer < 0.50 and best_idx is not None
        if matched:
            used_seg_indices.add(best_idx)

        results.append({
            "gt_timestamp": gt_ts,
            "gt_speaker": gt_speaker,
            "gt_text": gt_text,
            "matched": matched,
            "wer": best_wer if matched else None,
            "tx_speaker": best_seg["speaker"] if matched else None,
            "tx_text": best_seg["text"] if matched else None,
            "tx_start": best_seg["start_time"] if matched else None,
            "tx_end": best_seg["end_time"] if matched else None,
            "speaker_correct": (
                normalize_speaker(best_seg["speaker"]) == normalize_speaker(gt_speaker)
                if matched else False
            ),
        })

    return results


def score(results: List[dict]) -> dict:
    """Compute all metrics from match results."""
    total = len(results)
    matched = [r for r in results if r["matched"]]
    matched_count = len(matched)
    correct_speaker = sum(1 for r in matched if r["speaker_correct"])
    avg_wer = sum(r["wer"] for r in matched) / matched_count if matched_count else 0

    # Timing: anchor on first match
    timing_within_5s = 0
    if matched:
        first = matched[0]
        recording_start = first["gt_timestamp"] - first["tx_start"]
        for r in matched:
            expected = r["gt_timestamp"] - recording_start
            offset = abs(r["tx_start"] - expected)
            r["timing_offset"] = offset
            if offset < 5.0:
                timing_within_5s += 1
    else:
        for r in results:
            r["timing_offset"] = None

    return {
        "total": total,
        "matched": matched_count,
        "capture_rate": matched_count / total * 100 if total else 0,
        "speaker_correct": correct_speaker,
        "speaker_accuracy": correct_speaker / matched_count * 100 if matched_count else 0,
        "wer_avg": avg_wer * 100,
        "timing_within_5s": timing_within_5s,
        "timing_accuracy": timing_within_5s / matched_count * 100 if matched_count else 0,
    }


def print_report(results: List[dict], scores: dict, meeting_id: Optional[int] = None):
    """Print formatted scoring report."""
    print(f"\n{'=' * 60}")
    print(f"Post-Meeting Transcription Score")
    if meeting_id:
        print(f"Meeting: {meeting_id}")
    print(f"{'=' * 60}")

    # Metrics
    cap = scores["capture_rate"]
    spk = scores["speaker_accuracy"]
    wer = scores["wer_avg"]
    tim = scores["timing_accuracy"]

    cap_status = "PASS" if cap >= 90 else ("PASS*" if cap >= 80 else "FAIL")
    spk_status = "PASS" if spk >= 70 else "FAIL"
    wer_status = "PASS" if wer <= 25 else ("PASS*" if wer <= 30 else "FAIL")
    tim_status = "PASS" if tim >= 80 else ("PASS*" if tim >= 70 else "FAIL")

    print(f"\n  Capture:  {scores['matched']}/{scores['total']} ({cap:.0f}%)  threshold: >=90%  {cap_status}")
    print(f"  Speaker:  {scores['speaker_correct']}/{scores['matched']} ({spk:.0f}%)  threshold: >=70%  {spk_status}")
    print(f"  WER:      {wer:.1f}%  threshold: <=25%  {wer_status}")
    print(f"  Timing:   {scores['timing_within_5s']}/{scores['matched']} ({tim:.0f}%)  threshold: >=80%  {tim_status}")

    # Per-segment detail
    print(f"\nPer-segment detail:")
    for i, r in enumerate(results, 1):
        if r["matched"]:
            spk_mark = "OK" if r["speaker_correct"] else "WRONG"
            offset_str = f"{r.get('timing_offset', 0):.1f}s" if r.get("timing_offset") is not None else "?"
            print(f"  #{i}  GT: {r['gt_speaker']:10s} \"{r['gt_text'][:40]}...\"")
            print(f"       TX: {r['tx_speaker']:10s} \"{r['tx_text'][:40]}...\"")
            print(f"       speaker={spk_mark}  wer={r['wer']*100:.0f}%  offset={offset_str}")
        else:
            print(f"  #{i}  GT: {r['gt_speaker']:10s} \"{r['gt_text'][:40]}...\"")
            print(f"       MISSED — no matching segment found")

    # Gates
    g1 = scores["matched"] > 0
    g2 = cap >= 90 and spk >= 70 and wer <= 25 and tim >= 80
    g3 = cap >= 80 and spk >= 70 and wer <= 30 and tim >= 70

    print(f"\n  Gate 1 (pipeline):  {'PASS' if g1 else 'FAIL'}")
    print(f"  Gate 2 (baseline):  {'PASS' if g2 else 'FAIL'}")
    print(f"  Gate 3 (stress):    {'PASS' if g3 else 'FAIL'}")
    print(f"  Gate 4 (serving):   NOT TESTED (requires manual dashboard check)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Score post-meeting transcription")
    parser.add_argument("--gt", required=True, help="Path to ground-truth.txt")
    parser.add_argument("--meeting-id", type=int, help="Meeting ID to fetch from Postgres")
    parser.add_argument("--segments", help="Path to segments JSON file (alternative to --meeting-id)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    gt_entries = parse_gt(args.gt)
    if not gt_entries:
        print("ERROR: No GT entries found", file=sys.stderr)
        sys.exit(1)

    if args.meeting_id:
        segments = fetch_segments_db(args.meeting_id, "")
    elif args.segments:
        segments = parse_segments_json(args.segments)
    else:
        print("ERROR: --meeting-id or --segments required", file=sys.stderr)
        sys.exit(1)

    if not segments:
        print("ERROR: No segments found", file=sys.stderr)
        sys.exit(1)

    results = match_segments(gt_entries, segments)
    scores = score(results)

    if args.json:
        print(json.dumps({"results": results, "scores": scores}, indent=2))
    else:
        print_report(results, scores, args.meeting_id)

    # Exit code: 0 if Gate 2 passes, 1 otherwise
    g2 = (scores["capture_rate"] >= 90 and scores["speaker_accuracy"] >= 70
          and scores["wer_avg"] <= 25 and scores["timing_accuracy"] >= 80)
    sys.exit(0 if g2 else 1)


if __name__ == "__main__":
    main()
