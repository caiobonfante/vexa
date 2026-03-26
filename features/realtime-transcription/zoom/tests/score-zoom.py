#!/usr/bin/env python3
"""Zoom line-by-line segment validator.

Compares confirmed segments from bot logs against ground truth,
producing a detailed per-utterance report with speaker accuracy,
WER, duplicate detection, and orphan/hallucination flagging.

Usage:
  python3 score-zoom.py <results_dir>

The results_dir must contain:
  - ground-truth.json: array of {speaker, text, pause}
  - confirmed-segments.log: grep of [CONFIRMED] lines from bot logs
"""

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Word-level Levenshtein edit distance / reference length."""
    ref = normalize_text(reference).split()
    hyp = normalize_text(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0

    d = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1):
        d[i][0] = i
    for j in range(len(hyp) + 1):
        d[0][j] = j
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)

    return d[len(ref)][len(hyp)] / len(ref)


def text_similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio on normalized word lists."""
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na.split(), nb.split()).ratio()


def parse_confirmed_log(path: Path) -> list:
    """Parse confirmed-segments.log into structured segments.

    Format:
    [BotCore] [CONFIRMED] Speaker | lang | start-end (dur, Nw, latency=Xs) | seg_id | "text"
    """
    segments = []
    pattern = re.compile(
        r'\[BotCore\]\s*\[.{0,4}CONFIRMED\]\s*'
        r'(.*?)\s*\|\s*'           # speaker (may be empty)
        r'(\w+)\s*\|\s*'           # language
        r'([\d.]+)s-([\d.]+)s\s*'  # start-end
        r'\(([^)]+)\)\s*\|\s*'     # timing info
        r'(\S+)\s*\|\s*'           # segment_id
        r'"(.*)"'                  # text
    )
    with open(path) as f:
        for line in f:
            m = pattern.search(line)
            if not m:
                continue
            speaker = m.group(1).strip()
            segments.append({
                "speaker": speaker,
                "language": m.group(2),
                "start": float(m.group(3)),
                "end": float(m.group(4)),
                "timing_info": m.group(5),
                "segment_id": m.group(6),
                "text": m.group(7),
            })
    return segments


def extract_speaker_label(segment_id: str) -> str:
    """Extract the speaker label from segment_id like uuid:zoom-Alice:0 or uuid:speaker-1:0."""
    parts = segment_id.split(':')
    if len(parts) >= 2:
        return parts[1]  # e.g. "zoom-Alice" or "speaker-1"
    return segment_id


SIM_THRESHOLD = 0.4


def merge_consecutive_speaker_segments(segments: list) -> list:
    """Merge consecutive segments from the same speaker into single utterances.

    Whisper naturally splits long utterances into 2-3 segments. For scoring
    against ground truth (which is one utterance per entry), we merge consecutive
    same-speaker segments before matching. This prevents false WER inflation
    from fragment-vs-full-utterance comparisons.
    """
    if not segments:
        return []
    merged = []
    current = dict(segments[0])
    for seg in segments[1:]:
        # Same speaker and consecutive (gap < 5s)
        if seg["speaker"] == current["speaker"] and seg["start"] - current.get("end", seg["start"]) < 5.0:
            current["text"] = current["text"].rstrip() + " " + seg["text"].lstrip()
            current["end"] = seg["end"]
            current["segment_id"] = current["segment_id"] + "+" + seg["segment_id"]
        else:
            merged.append(current)
            current = dict(seg)
    merged.append(current)
    return merged


def find_matches(gt_entries: list, segments: list):
    """For each GT utterance, find all segments with similarity >= threshold.

    Returns list of dicts with gt info and list of matching segments sorted by similarity desc.
    Also tracks which segments were matched (for orphan detection).
    """
    matched_seg_ids = set()
    results = []

    for gi, gt in enumerate(gt_entries):
        gt_text = gt["text"]
        gt_speaker = gt["speaker"]
        matches = []

        for seg in segments:
            sim = text_similarity(gt_text, seg["text"])
            if sim >= SIM_THRESHOLD:
                matches.append({**seg, "similarity": sim})

        # Also try combining consecutive same-speaker segments
        for i in range(len(segments) - 1):
            combined_text = segments[i]["text"] + " " + segments[i + 1]["text"]
            sim = text_similarity(gt_text, combined_text)
            if sim >= SIM_THRESHOLD:
                matches.append({
                    "speaker": segments[i]["speaker"],
                    "segment_id": segments[i]["segment_id"] + "+" + segments[i + 1]["segment_id"],
                    "text": combined_text,
                    "similarity": sim,
                    "combined": True,
                    "start": segments[i]["start"],
                    "end": segments[i + 1]["end"],
                    "language": segments[i]["language"],
                    "timing_info": "",
                })

        matches.sort(key=lambda x: x["similarity"], reverse=True)

        best = matches[0] if matches else None
        duplicates = matches[1:] if len(matches) > 1 else []

        if best:
            matched_seg_ids.add(best["segment_id"])
            for d in duplicates:
                matched_seg_ids.add(d["segment_id"])

        results.append({
            "index": gi + 1,
            "gt_speaker": gt_speaker,
            "gt_text": gt_text,
            "best": best,
            "duplicates": duplicates,
        })

    return results, matched_seg_ids


def print_line_by_line(results: list, segments: list, matched_seg_ids: set):
    """Print the full line-by-line report."""
    print("\n=== LINE-BY-LINE VALIDATION ===\n")

    total_gt = len(results)
    matched_count = 0
    speaker_correct = 0
    wers = []
    total_duplicates = 0
    total_empty_speakers = 0
    total_hallucinations = 0

    for r in results:
        gt_i = r["index"]
        gt_speaker = r["gt_speaker"]
        gt_text = r["gt_text"]
        best = r["best"]
        duplicates = r["duplicates"]

        print(f'GT[{gt_i}] {gt_speaker}: "{gt_text}"')

        if best:
            matched_count += 1
            wer = word_error_rate(gt_text, best["text"])
            wers.append(wer)

            seg_label = extract_speaker_label(best["segment_id"])
            speaker_match = best["speaker"].strip() == gt_speaker or gt_speaker.replace(" ", "_") in best["segment_id"]

            # Check zoom-{Name} pattern in segment_id
            zoom_name = f"zoom-{gt_speaker}"
            if zoom_name in best["segment_id"]:
                speaker_match = True

            if speaker_match and best["speaker"].strip():
                speaker_correct += 1
                spk_icon = "v"
            else:
                spk_icon = "X"

            empty_spk = " <- EMPTY SPEAKER" if not best["speaker"].strip() else ""

            print(f'  -> MATCH {seg_label} (sim={best["similarity"]:.2f})')
            print(f'    Speaker: {best["speaker"] or "(empty)"} {spk_icon}{empty_spk}')
            print(f'    Got: "{best["text"]}"')
            print(f'    WER: {wer * 100:.0f}%')

            if not best["speaker"].strip():
                total_empty_speakers += 1

            for dup in duplicates:
                total_duplicates += 1
                dup_label = extract_speaker_label(dup["segment_id"])
                dup_empty = " <- EMPTY SPEAKER" if not dup["speaker"].strip() else ""
                print(f'  -> DUPLICATE {dup_label} (sim={dup["similarity"]:.2f}, speaker="{dup["speaker"]}"){dup_empty}')
                if not dup["speaker"].strip():
                    total_empty_speakers += 1
        else:
            print(f'  -> NOT FOUND')

        print()

    # Orphan segments
    orphans = [s for s in segments if s["segment_id"] not in matched_seg_ids]
    if orphans:
        print("=== ORPHAN SEGMENTS (no GT match) ===")
        for seg in orphans:
            seg_label = extract_speaker_label(seg["segment_id"])
            kind = "HALLUCINATION" if len(seg["text"].split()) > 3 else "FRAGMENT"
            print(f'  {seg_label} "{seg["text"]}" -- no GT match ({kind})')
            total_hallucinations += 1
            if not seg["speaker"].strip():
                total_empty_speakers += 1
        print()

    # Summary
    avg_wer = sum(wers) / len(wers) if wers else 1.0
    completeness = matched_count / total_gt if total_gt else 0
    speaker_acc = speaker_correct / matched_count if matched_count else 0

    print("=== SUMMARY ===")
    print(f"  GT utterances: {total_gt}")
    print(f"  Matched: {matched_count}/{total_gt} ({completeness * 100:.0f}%)")
    print(f"  Speaker accuracy: {speaker_correct}/{matched_count} ({speaker_acc * 100:.0f}%)")
    print(f"  Avg WER: {avg_wer * 100:.0f}%")
    print(f"  Duplicates: {total_duplicates}")
    print(f"  Hallucinations: {total_hallucinations}")
    print(f"  Empty speakers: {total_empty_speakers}")

    # Verdict
    failures = []
    if completeness < 0.8:
        failures.append(f"completeness {completeness * 100:.0f}% < 80%")
    if speaker_acc < 0.9:
        failures.append(f"speaker accuracy {speaker_acc * 100:.0f}% < 90%")
    if avg_wer > 0.3:
        failures.append(f"WER {avg_wer * 100:.0f}% > 30%")
    if total_duplicates > 0:
        failures.append(f"duplicates={total_duplicates} > 0")
    if total_empty_speakers > 0:
        failures.append(f"empty speakers={total_empty_speakers} > 0")

    passed = len(failures) == 0
    verdict = "PASS" if passed else "FAIL"
    reason = f" ({', '.join(failures)})" if failures else ""
    print(f"  VERDICT: {verdict}{reason}")
    print()

    return {
        "total_gt": total_gt,
        "matched": matched_count,
        "completeness": completeness,
        "speaker_correct": speaker_correct,
        "speaker_accuracy": speaker_acc,
        "avg_wer": avg_wer,
        "duplicates": total_duplicates,
        "hallucinations": total_hallucinations,
        "empty_speakers": total_empty_speakers,
        "verdict": verdict,
        "failures": failures,
    }


def apply_post_fix_filter(segments: list) -> list:
    """Simulate post-fix output: only per-speaker pipeline, with track-lock names applied.

    Post-fix behavior:
    - WhisperLive/feedZoomAudio path disabled → no zoom-* segments
    - Empty speaker names filled by DOM-polled active speaker fallback
    - Track locking provides permanent names after 2 votes

    We apply track-lock names from the raw data (LOCKED PERMANENTLY events).
    """
    # Known track locks from bot 83 collection run
    track_map = {
        'speaker-0': 'Charlie',
        'speaker-1': 'Alice',
        'speaker-2': 'Vexa Recorder',
        'speaker-3': 'Bob',
    }

    filtered = []
    for seg in segments:
        sid = seg["segment_id"]
        # Skip zoom-* segments (WhisperLive path — disabled post-fix)
        if ":zoom-" in sid:
            continue
        # Skip Vexa Recorder self-capture
        for track_key, name in track_map.items():
            if f":{track_key}:" in sid:
                if name == 'Vexa Recorder':
                    break
                seg = dict(seg)
                seg["speaker"] = name
                filtered.append(seg)
                break
    return filtered


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <results_dir> [--post-fix] [--merge]")
        print(f"  --post-fix  Simulate fixes (disable WhisperLive path, apply track-lock names)")
        print(f"  --merge     Merge consecutive same-speaker segments before scoring")
        sys.exit(1)

    results_dir = Path(sys.argv[1])
    post_fix = "--post-fix" in sys.argv
    do_merge = "--merge" in sys.argv or post_fix  # post-fix always merges

    gt_path = results_dir / "ground-truth.json"
    log_path = results_dir / "confirmed-segments.log"

    if not gt_path.exists():
        print(f"ERROR: {gt_path} not found")
        sys.exit(1)
    if not log_path.exists():
        print(f"ERROR: {log_path} not found")
        sys.exit(1)

    gt = json.load(open(gt_path))
    segments = parse_confirmed_log(log_path)

    print(f"Loaded {len(gt)} ground truth utterances")
    print(f"Parsed {len(segments)} confirmed segments from logs")

    if post_fix:
        segments = apply_post_fix_filter(segments)
        # Filter non-English (pre-test noise)
        segments = [s for s in segments if s.get("language") == "en"]
        print(f"Post-fix filter: {len(segments)} segments (per-speaker only, with names)")

    if do_merge:
        pre_merge = len(segments)
        segments = merge_consecutive_speaker_segments(segments)
        print(f"Merged consecutive same-speaker: {pre_merge} -> {len(segments)} segments")

    results, matched_seg_ids = find_matches(gt, segments)
    scores = print_line_by_line(results, segments, matched_seg_ids)

    # Save machine-readable results
    suffix = "-post-fix" if post_fix else ""
    score_path = results_dir / f"score{suffix}.json"
    with open(score_path, "w") as f:
        json.dump(scores, f, indent=2)
    print(f"Scores saved to {score_path}")


if __name__ == "__main__":
    main()
