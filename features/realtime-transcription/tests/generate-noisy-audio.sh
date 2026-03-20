#!/usr/bin/env bash
# Generate noisy test audio files for transcription pipeline testing.
# Uses only Python standard library + numpy (no scipy, no external packages).
# All output is 16kHz mono WAV.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/_generate_noisy_audio.py" "$@"
