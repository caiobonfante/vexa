# Shared Tools

Validation tools used by product features. Each tool is a mini-feature with a confidence score. **A product feature can only validate at a level where all required tools have confidence ≥ 80.**

## Tool Confidence

| Tool | Confidence | Blocker | Unlocks |
|------|-----------|---------|---------|
| [unit-tests](unit-tests/) | 90 | — | Level 1 (cap 50) |
| [wav-pipeline](wav-pipeline/) | 70 | not tested since confirmation fix | Level 2 (cap 60) |
| [replay-pipeline](replay-pipeline/) | 70 | data/raw/ empty in repo | Level 3 (cap 70) |
| [generate-test-audio](generate-test-audio/) | 40 | TTS service not port-mapped | Level 4 (cap 75) |
| [send-tts-bots](send-tts-bots/) | 70 | needs live meeting | Level 5 (cap 80) |
| [host-gmeet-meeting](host-gmeet-meeting/) | 30 | not validated recently | Level 5 (cap 80) |
| [host-teams-meeting](host-teams-meeting/) | 60 | needs browser session | Level 5 (cap 80) |
| [score-output](score-output/) | 90 | — | All levels |

## Highest Reachable Level

**Level 1 (cap 50)** — all tools at ≥ 80 up to this point.

To unlock Level 2: validate wav-pipeline (70 → 80). Run it once with the confirmation fix, confirm it works.

To unlock Level 3: validate replay-pipeline (70 → 80) + generate or commit test data to data/raw/.

To unlock Level 4: fix generate-test-audio (40 → 80). Either port-map TTS service or switch to gTTS.

To unlock Level 5: fix host-gmeet-meeting (30 → 80). Run gmeet-host-auto.js, verify it creates a meeting.

## For Agents

Read this table first. Don't attempt a validation level if a required tool is below 80. Instead: improve the tool, then retry.

Improving a tool follows the same loop as improving a feature: read the tool's README → find the blocker → fix it → verify with execution → update confidence.
