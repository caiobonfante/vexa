#!/usr/bin/env python3
"""Replay transcript utterances as TTS bots in a live Google Meet."""

import re
import time
import subprocess
import json
import sys

MEETING_ID = "bay-npte-svc"
BASE_URL = "http://localhost:8056"
ADMIN_TOKEN = "changeme"

# Speaker -> token mapping (each speaker bot has its own user token)
SPEAKER_TOKENS = {
    "Karl Moll": "vxa_user_Fc1qbQcWlKNDNX7jlJIOJHxxseUQPiGotXxsUdu5",
    "Dmtiry Grankin": "vxa_user_1Pt4V2lV8HvP7RaX4V9b5VnaAfFyziwRqz3MOTgf",
    "Eddie Knight (Sonatype, Inc.)": "vxa_user_mFEKVIMihzJ0FQJDmYaj2B7Yl8Yl3fxjrcaseozg",
}

# Voice assignments per speaker for variety
SPEAKER_VOICES = {
    "Karl Moll": "alloy",
    "Dmtiry Grankin": "echo",
    "Eddie Knight (Sonatype, Inc.)": "fable",
}

def parse_transcript(filepath):
    with open(filepath) as f:
        content = f.read()

    pattern = r'\[(.+?)\] \d+:\d+:\d+\n(.+?)(?=\n\n|\n\[|\Z)'
    utterances = []
    for match in re.finditer(pattern, content, re.DOTALL):
        speaker = match.group(1).strip()
        text = match.group(2).strip().replace('\n', ' ')
        if text and len(text) > 5:
            utterances.append((speaker, text))
    return utterances

def speak(token, text, voice="alloy"):
    """Send speak command to the bot."""
    url = f"{BASE_URL}/bots/google_meet/{MEETING_ID}/speak"
    data = json.dumps({"text": text[:200], "voice": voice})
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", url,
         "-H", f"X-API-Key: {token}",
         "-H", "Content-Type: application/json",
         "-d", data],
        capture_output=True, text=True
    )
    return result.stdout

def main():
    utterances = parse_transcript("/home/dima/dev/meeting_saved_closed_caption.txt")

    # Filter to only speakers we have bots for
    playable = [(s, t) for s, t in utterances if s in SPEAKER_TOKENS]
    print(f"Total utterances: {len(utterances)}")
    print(f"Playable (have bots): {len(playable)}")

    # Play first 15 playable utterances
    max_utterances = 15
    count = 0

    for speaker, text in playable[:max_utterances]:
        count += 1
        token = SPEAKER_TOKENS[speaker]
        voice = SPEAKER_VOICES.get(speaker, "alloy")

        print(f"\n[{count}/{max_utterances}] [{speaker}] ({voice})")
        print(f"  Text: {text[:100]}{'...' if len(text) > 100 else ''}")

        resp = speak(token, text, voice)
        print(f"  Response: {resp}")

        # Wait between utterances - longer for longer text
        wait_time = max(6, min(12, len(text) / 20))
        print(f"  Waiting {wait_time:.0f}s...")
        time.sleep(wait_time)

    print(f"\n=== Done! Sent {count} utterances ===")
    print("Waiting 60s for transcription to catch up...")

if __name__ == "__main__":
    main()
