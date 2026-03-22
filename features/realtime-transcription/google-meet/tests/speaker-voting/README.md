# Speaker Voting Test

Test the track-to-speaker voting and locking mechanism in live Google Meet meetings, including the critical leave/join cycle where all locks get invalidated and must re-resolve.

## Problem

The pipeline maps audio element indices to speaker names via voting:
1. Audio arrives on track N, Google Meet speaking indicator shows exactly one speaker
2. Vote: track N = that speaker
3. After 3 consistent votes at 70%+ ratio, lock permanently

When a participant joins or leaves, the bot detects the count change and **clears ALL locks**. Every track must re-vote and re-lock. This is the riskiest moment — element indices may have shifted, and the voting system must correctly re-discover which track belongs to which speaker.

The YouTube pipeline test found speaker attribution errors but couldn't isolate the cause (test data segmentation vs pipeline voting). This test isolates the voting mechanism by controlling exactly when each bot speaks, leaves, and joins.

## Test cycle

One continuous meeting, three phases:

```
Phase 1: JOIN 3 + SPEAK + VALIDATE
  Send Alice, Bob, Charlie + Recorder
  Each speaks via TTS (sequential, one at a time)
  Validate: 3 tracks locked to correct names

Phase 2: LEAVE 1 + SPEAK + VALIDATE
  Charlie leaves
  Alice and Bob speak (triggers lock invalidation + re-vote)
  Validate: 2 tracks re-locked correctly, Charlie gone

Phase 3: JOIN 2 + SPEAK + VALIDATE
  Dave and Eve join
  All 4 remaining + 2 new speak (triggers another invalidation + re-vote)
  Validate: 4 tracks locked to correct names
```

Each phase uses TTS (`speak` command via Redis) — no audio file playback needed.

## How it works

```
┌────────────────────────────────────────────────────────────────┐
│  test-runner.sh                                                │
│                                                                │
│  1. Create Google Meet (browser session)                       │
│  2. Start auto-admit                                           │
│  3. Send Recorder bot (transcribe_enabled: true)               │
│                                                                │
│  PHASE 1:                                                      │
│    Send Alice, Bob, Charlie (transcribe_enabled: false)        │
│    Wait for all to join                                        │
│    TTS: Alice speaks → Bob speaks → Charlie speaks             │
│    Snapshot recorder logs → validate locks                     │
│                                                                │
│  PHASE 2:                                                      │
│    Send leave command to Charlie                               │
│    Wait for participant count change                           │
│    TTS: Alice speaks → Bob speaks                              │
│    Snapshot recorder logs → validate locks                     │
│                                                                │
│  PHASE 3:                                                      │
│    Send Dave, Eve                                              │
│    Wait for all to join                                        │
│    TTS: Alice → Bob → Dave → Eve (sequential)                  │
│    Snapshot recorder logs → validate locks                     │
│                                                                │
│  Score each phase independently                                │
└────────────────────────────────────────────────────────────────┘
```

### TTS speak command

Bots receive commands via Redis channel `bot_commands:meeting:{meetingId}`:

```json
{"action": "speak", "text": "Hello, my name is Alice. I am testing speaker identification."}
```

The bot's TTS service synthesizes and plays the audio into the meeting via PulseAudio. No pre-generated audio files needed.

### Leave command

```json
{"action": "leave"}
```

The bot gracefully leaves the meeting, which changes the participant count on the recorder bot, triggering `clearSpeakerNameCache()` — all locks cleared.

## Validation at each phase

Parse recorder bot logs for:

```
[SpeakerIdentity] Track N -> "Name" LOCKED PERMANENTLY (X/Y votes, Z%)
[SpeakerIdentity] Participant count changed: N -> M. Invalidating all mappings
[SpeakerIdentity] All track mappings cleared.
```

| Check | Meaning |
|-------|---------|
| All speakers locked | Every active speaker has a locked track |
| Correct mapping | locked name matches the bot that played TTS on that track |
| No cross-votes | No track accumulated votes for the wrong speaker |
| Lock speed | Locked within 5 votes (not stuck in voting limbo) |
| Invalidation on leave | Locks cleared when participant count changed |
| Re-lock after join | All tracks re-locked correctly after new participants join |

## Files

```
speaker-voting/
  README.md              # this file
  test-runner.sh         # phased test: join/speak/leave/rejoin
  score.py               # parse recorder logs, validate each phase
  .gitignore             # excludes results/
  results/               # test run outputs
    run-YYYY-MM-DD-HHMMSS/
      phase-1/
        recorder-snapshot.log
        score.json
      phase-2/
        ...
      phase-3/
        ...
```

## Usage

```bash
# With a browser session for meeting creation + auto-admit
CDP_URL=http://localhost:8066/b/TOKEN/cdp ./test-runner.sh

# Reuse an existing meeting
./test-runner.sh --meeting abc-defg-hij

# The test prints validation results after each phase
```

## What this test covers

- Track-to-speaker voting correctness (1:1 mapping)
- Lock invalidation on participant count change
- Re-locking after leave/join cycles
- Speaking indicator correlation with audio activity
- Multiple concurrent speakers vs single speaker voting rules

## What this does NOT cover

- Transcription accuracy (Whisper) — tested in youtube-pipeline/
- Audio capture reliability (AudioContext GC)
- WS/REST delivery
- Teams speaker resolution (uses DOM traversal, not voting)
