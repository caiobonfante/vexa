# Shared Tools

Validation tools used by product features. Each tool is a mini-feature with a confidence score. **A product feature can only validate at a level where all required tools have confidence ≥ 80.**

## Tool Confidence

| Tool | Confidence | Blocker | Unlocks |
|------|-----------|---------|---------|
| [unit-tests](unit-tests/) | 90 | — | Level 1 (cap 50) |
| [wav-pipeline](wav-pipeline/) | 80 | validated post-confirmation-fix 2026-03-24 | Level 2 (cap 60) |
| [replay-pipeline](replay-pipeline/) | 70 | data/raw/ empty in repo | Level 3 (cap 70) |
| [generate-test-audio](generate-test-audio/) | 80 | gTTS alternative validated 2026-03-24 | Level 4 (cap 75) |
| [send-tts-bots](send-tts-bots/) | 80 | validated 2026-03-24, TTS spoke in live meeting | Level 5 (cap 80) |
| [host-gmeet-meeting](host-gmeet-meeting/) | 30 | not validated recently | Level 5 (cap 80) |
| [host-teams-meeting](host-teams-meeting/) | 80 | validated 2026-03-24, meeting created + joined | Level 5 (cap 80) |
| [score-output](score-output/) | 90 | — | All levels |

## Highest Reachable Level

**Level 5 (cap 80) via Teams** — all required tools at ≥ 80: host-teams-meeting (80), send-tts-bots (80), score-output (90). Validated 2026-03-24.

Level 3 still blocked by replay-pipeline (70 < 80) — but Level 5 is reachable by skipping to live meeting validation.

To unlock Level 3: validate replay-pipeline (70 → 80) + test data now exists in data/raw/synthetic/.

GMeet path to Level 5 still blocked: host-gmeet-meeting (30 < 80).

## For Agents

Read this table first. Don't attempt a validation level if a required tool is below 80. Instead: improve the tool, then retry.

Improving a tool follows the same loop as improving a feature: read the tool's README → find the blocker → fix it → verify with execution → update confidence.
