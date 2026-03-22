#!/usr/bin/env python3
"""End-to-end scoring: compare pipeline output against ground truth.

Compares at two levels:
1. Bot-level: confirmed segments from recorder bot logs
2. DB-level: persisted segments from Postgres (after immutability)

For each ground truth utterance, finds the best matching output segment
and scores: speaker correctness, text similarity, completeness.

Usage:
  python3 score-e2e.py <results_dir>
"""

import csv
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def normalize_speaker(name: str) -> str:
    """Normalize speaker name: strip '(Guest)', 'Vexa Bot', etc."""
    name = re.sub(r'\s*\(Guest\)\s*$', '', name)
    name = re.sub(r'\s*\(Organizer\)\s*$', '', name)
    return name.strip()


def text_similarity(a: str, b: str) -> float:
    """Compute text similarity (0-1) using SequenceMatcher on normalized text."""
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na.split(), nb.split()).ratio()


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Compute WER between reference and hypothesis (normalized)."""
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    # Levenshtein on word level
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j
    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            cost = 0 if ref_words[i-1] == hyp_words[j-1] else 1
            d[i][j] = min(d[i-1][j] + 1, d[i][j-1] + 1, d[i-1][j-1] + cost)

    return d[len(ref_words)][len(hyp_words)] / len(ref_words)


def match_gt_to_segments(gt_entries: list, segments: list) -> list:
    """Match each ground truth entry to the best output segment(s).

    A GT entry may be split across multiple segments, or merged with adjacent entries.
    We find the best match by concatenating consecutive same-speaker segments
    and comparing against each GT entry.
    """
    matches = []

    for gt in gt_entries:
        gt_speaker = gt["speaker"]
        gt_text = gt["text"]
        gt_norm = normalize_text(gt_text)

        best_match = None
        best_similarity = 0.0

        # Try individual segments
        for seg in segments:
            sim = text_similarity(gt_text, seg["text"])
            if sim > best_similarity:
                best_similarity = sim
                best_match = {
                    "segments": [seg],
                    "combined_text": seg["text"],
                    "speaker": seg["speaker"],
                    "similarity": sim,
                }

        # Try consecutive same-speaker segment pairs
        for i in range(len(segments) - 1):
            if segments[i]["speaker"] == segments[i+1]["speaker"]:
                combined = segments[i]["text"] + " " + segments[i+1]["text"]
                sim = text_similarity(gt_text, combined)
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = {
                        "segments": [segments[i], segments[i+1]],
                        "combined_text": combined,
                        "speaker": segments[i]["speaker"],
                        "similarity": sim,
                    }

        # Try triples
        for i in range(len(segments) - 2):
            if segments[i]["speaker"] == segments[i+1]["speaker"] == segments[i+2]["speaker"]:
                combined = segments[i]["text"] + " " + segments[i+1]["text"] + " " + segments[i+2]["text"]
                sim = text_similarity(gt_text, combined)
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = {
                        "segments": [segments[i], segments[i+1], segments[i+2]],
                        "combined_text": combined,
                        "speaker": segments[i]["speaker"],
                        "similarity": sim,
                    }

        matches.append({
            "gt_speaker": gt_speaker,
            "gt_text": gt_text,
            "match": best_match,
        })

    return matches


def score_matches(matches: list) -> dict:
    """Score the matched results."""
    total = len(matches)
    speaker_correct = 0
    speaker_wrong = 0
    not_found = 0
    similarities = []
    wers = []

    for m in matches:
        match = m["match"]
        if not match or match["similarity"] < 0.3:
            not_found += 1
            continue

        similarities.append(match["similarity"])

        if normalize_speaker(match["speaker"]) == m["gt_speaker"]:
            speaker_correct += 1
        else:
            speaker_wrong += 1

        wer = word_error_rate(m["gt_text"], match["combined_text"])
        wers.append(wer)

    found = total - not_found
    avg_similarity = sum(similarities) / len(similarities) if similarities else 0
    avg_wer = sum(wers) / len(wers) if wers else 1.0

    return {
        "total_gt": total,
        "found": found,
        "not_found": not_found,
        "speaker_correct": speaker_correct,
        "speaker_wrong": speaker_wrong,
        "speaker_accuracy": speaker_correct / found if found else 0,
        "avg_text_similarity": avg_similarity,
        "avg_wer": avg_wer,
        "completeness": found / total if total else 0,
    }


def load_bot_segments(results_dir: Path) -> list:
    """Load confirmed segments from bot logs."""
    path = results_dir / "bot-segments.json"
    if not path.exists():
        return []
    return json.load(open(path))


def load_db_segments(results_dir: Path) -> list:
    """Load segments from DB CSV export."""
    path = results_dir / "db-segments.csv"
    if not path.exists():
        return []
    segments = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            segments.append({
                "speaker": row["speaker"],
                "text": row["text"],
                "start_time": float(row["start_time"]) if row.get("start_time") else 0,
                "end_time": float(row["end_time"]) if row.get("end_time") else 0,
                "segment_id": row.get("segment_id", ""),
            })
    return segments


def print_report(title: str, matches: list, scores: dict):
    """Print a human-readable report."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(f"  Utterances: {scores['total_gt']} ground truth, {scores['found']} found, {scores['not_found']} missing")
    print(f"  Speaker accuracy: {scores['speaker_correct']}/{scores['found']} ({scores['speaker_accuracy']*100:.0f}%)")
    print(f"  Avg text similarity: {scores['avg_text_similarity']*100:.0f}%")
    print(f"  Avg WER: {scores['avg_wer']*100:.0f}%")
    print(f"  Completeness: {scores['completeness']*100:.0f}%")
    print()

    for i, m in enumerate(matches):
        match = m["match"]
        gt_short = m["gt_text"][:60]
        if match and match["similarity"] >= 0.3:
            speaker_ok = "OK" if normalize_speaker(match["speaker"]) == m["gt_speaker"] else f"WRONG ({match['speaker']})"
            out_short = match["combined_text"][:60]
            print(f"  {i+1}. [{m['gt_speaker']:8s}] \"{gt_short}...\"")
            print(f"     -> [{speaker_ok:8s}] \"{out_short}...\" (sim={match['similarity']:.0%}, wer={word_error_rate(m['gt_text'], match['combined_text']):.0%})")
        else:
            print(f"  {i+1}. [{m['gt_speaker']:8s}] \"{gt_short}...\"")
            print(f"     -> NOT FOUND")
        print()

    # Overall verdict
    passed = (
        scores["speaker_accuracy"] >= 0.9 and
        scores["completeness"] >= 0.8 and
        scores["avg_wer"] <= 0.3
    )
    verdict = "PASS" if passed else "FAIL"
    print(f"  Verdict: {verdict}")
    print(f"    Speaker >= 90%: {'YES' if scores['speaker_accuracy'] >= 0.9 else 'NO'} ({scores['speaker_accuracy']*100:.0f}%)")
    print(f"    Completeness >= 80%: {'YES' if scores['completeness'] >= 0.8 else 'NO'} ({scores['completeness']*100:.0f}%)")
    print(f"    WER <= 30%: {'YES' if scores['avg_wer'] <= 0.3 else 'NO'} ({scores['avg_wer']*100:.0f}%)")
    print()
    return verdict


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <results_dir>")
        sys.exit(1)

    results_dir = Path(sys.argv[1])
    gt_path = results_dir / "ground-truth.json"
    if not gt_path.exists():
        print(f"ERROR: {gt_path} not found")
        sys.exit(1)

    gt = json.load(open(gt_path))

    # Score bot-level output
    bot_segments = load_bot_segments(results_dir)
    bot_matches = match_gt_to_segments(gt, bot_segments)
    bot_scores = score_matches(bot_matches)

    # Score DB-level output
    db_segments = load_db_segments(results_dir)
    db_matches = match_gt_to_segments(gt, db_segments)
    db_scores = score_matches(db_matches)

    # Print reports
    bot_verdict = print_report("BOT-LEVEL (confirmed segments from recorder logs)", bot_matches, bot_scores)
    db_verdict = print_report("DB-LEVEL (persisted segments from Postgres)", db_matches, db_scores)

    # Save JSON
    result = {
        "ground_truth_count": len(gt),
        "bot": {"segments": len(bot_segments), "scores": bot_scores, "verdict": bot_verdict},
        "db": {"segments": len(db_segments), "scores": db_scores, "verdict": db_verdict},
        "overall": "PASS" if bot_verdict == "PASS" or db_verdict == "PASS" else "FAIL",
    }
    with open(results_dir / "score.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"Overall: {result['overall']}")


if __name__ == "__main__":
    main()
