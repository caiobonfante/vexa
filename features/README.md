# Features

Features are **self-describing, self-improving manifests.** Each feature has a purpose you can explain, a gate you can validate, and transparent confidence scores so you know exactly what works and what doesn't. Seven concepts make this work.

## Core Concepts

### 1. Confidence Gate

A table of checks, each scored 0-95 with **mandatory evidence.** No evidence = 0.

```
 0  untested — no evidence exists
30  indirect — "logs suggest it works"
60  validated once — code may have changed since
80  validated recently — minor caveats
90  real conditions — tested against live infrastructure
95  production — real users, verified by human
```

**Rules:**
- Gate passes when **ALL** checks ≥ 80. One zero blocks the feature.
- Evidence is specific: "HTTP 200, 7 segments, meeting_id=8791, checked 2026-03-16" — not "it works."
- Scores decay when code changes. A 90 from last week becomes 60 if that code path was touched.
- Mock caps at 90. Only real-world validation reaches 95.

**File:** `tests/findings.md`

### 2. Autonomous Loop

Two cycles depending on feature type:

**Validation cycle** — for features with data flowing through a pipeline:
```
COLLECT → ITERATE → EXPAND → COLLECT
```
- **COLLECT:** Get real-world data with known ground truth (you control the input, so you know what "correct" looks like). Expensive — minutes, real infrastructure.
- **ITERATE:** Replay data through pipeline, score against truth, fix, repeat. Cheap — seconds per cycle, no live infrastructure.
- **EXPAND:** Scoring plateaued (same score 3+ runs)? Data doesn't cover the failing scenario. Design new collection with hypothesis. Back to COLLECT.

Requires: ground truth, replay mechanism, scoring function.

**Spec cycle** — for features with API contracts:
```
RESEARCH → SPEC → BUILD & TEST
```
- **RESEARCH:** Understand domain, competitors, gaps. Produce RESEARCH.md.
- **SPEC:** Write testable assertions that fail first. The spec IS the test.
- **BUILD & TEST:** Implement until assertions pass.

Requires: clear contract, test assertions.

**File:** `.claude/CLAUDE.md` (defines which cycle and transition rules)

### 3. Dead-End Record

Append-only log of what was tried and failed:
```
[DEAD-END] minAudioDuration=0.5s — introduced garbage segments. Reverted.
[DEAD-END] Full-text match for confirmation — never confirms mid-stream.
[RESULT]   Per-segment stability tracking: works. Fixes confirmation.
```

Without this, the next agent retries the same failed approach. The ms-teams findings show 5 debug runs — each building on the last. Run 4's aggressive caption flush (lost 8/18 utterances) prevents future agents from trying the same thing.

**File:** `tests/feature-log.md`

### 4. Edge Contracts

Declaration of where data crosses between features or services:

```
| Edge | From | To | Data format | Failure mode |
| Audio | Browser ScriptProcessor | Node.js handler | (index, number[]) | GC collects AudioContext |
| Transcription | TranscriptionClient | transcription-service | HTTP POST WAV | 502 timeout |
```

When something breaks, check edges first. If audio reaches the transcription service but segments don't appear in Redis, the bug is between those two edges.

**File:** `.claude/CLAUDE.md` (edges section)

### 5. Agent Manifest

The set of files that lets an agent (human or AI) pick up a feature with zero handoff:

| File | Read order | What it tells you |
|------|-----------|-------------------|
| `.claude/CLAUDE.md` | First (2 min) | Mission, scope, gate criteria, edges, which cycle |
| `tests/findings.md` | Second (2 min) | Every check with score + evidence. Lowest score = the blocker. |
| `tests/feature-log.md` | Third (5 min) | What was tried, what failed, dead ends to avoid |
| `README.md` | As needed | Architecture, data flow, components, config |

After 10 minutes of reading, the agent knows the mission, knows what's broken, knows what not to retry, and knows the architecture.

### 6. Stage Determination

On entry, the agent determines its stage from artifacts — no human tells it what to do:

**Validation cycle:**
```
1. .env exists and infra verified?           NO → ENV SETUP
2. Collected data with ground truth exists?   NO → COLLECT
3. Scoring improving?                        YES → ITERATE
4. Scoring stuck (plateau)?                  YES → EXPAND
```

**Spec cycle:**
```
1. RESEARCH.md exists?                       NO → RESEARCH
2. Test assertions exist and fail?           NO → SPEC
3. Some tests pass, some fail?              YES → BUILD & TEST
4. All tests pass?                          YES → next batch or GATE
```

The artifacts tell the agent where it is. Findings show the scores. Feature log shows the trajectory. The agent acts accordingly.

### 7. Cost Ladder

Improve confidence with **minimum cost.** Never go to a higher level until you've exhausted lower levels. **Every level requires actual execution — code review alone is Level 0.**

| Level | Cost | Score cap | What it proves | What it requires |
|-------|------|-----------|---------------|-----------------|
| 0 Read code | Free, seconds | 30 | Logic appears correct | Human or agent reads code |
| 1 Unit test **executed** | Free, seconds | 50 | Function produces right output for known input | `npm test` / `pytest` actually runs and passes |
| 2 Integration test **executed** | Free, minutes | 60 | Multiple components work together | Services running, test hits real APIs |
| 3 Replay existing data | Cheap, minutes | 70 | Pipeline works on known audio end-to-end | Stack running, replay data exists, scoring runs |
| 4 Replay with edge cases | Cheap, minutes | 75 | Pipeline handles stress: overlaps, long monologues, silence | Modified/synthetic datasets targeting known weaknesses |
| 5 Live meeting + TTS bots | Cheap, minutes | 80 | Works on real platform with real WebRTC, real DOM, controlled audio | Browser session, TTS bots, auto-admit, ground truth script |
| 6 Live meeting + TTS bots + extensive edge cases | Medium, hours | 85 | Handles all known edge cases on real platform | Multiple collection runs covering all designed scenarios |
| 7 Live meeting + human participants | Expensive, hours | 90 | Works with real human speech patterns, overlaps, mumbling | Real people in a real meeting |
| 8 Beta / other developers test | Expensive, days | 90 | Works for people other than the author | Independent testers, fresh eyes, different environments |
| 9 Production with real users | Ongoing, weeks | 95 | Stable in production over time, validated by user behavior | Real users, real meetings, monitored, no regressions over N meetings |

**Target: 80 without a human.** Levels 0-5 are fully automatable. An agent team can research, implement, test through unit → integration → replay → live TTS meeting — all without human involvement. Level 5 (score 80) is the autonomous ceiling.

**Score caps are hard.** Evidence must include **execution output** — test runner stdout, segment counts from replay, meeting IDs from live tests. "Code looks correct" is Level 0 (cap 30). "9/9 tests pass" with actual test runner output is Level 1 (cap 50). An agent claiming Level 1 evidence must show the command it ran and the output it got.

**The rule:** Never claim a score above what your evidence level supports. If you ran unit tests, your score caps at 50 — doesn't matter how confident you are in the code.

**The improvement cycle:**

```
1. READ FINDINGS → lowest score, what level of testing does it need?
2. READ DEAD ENDS → what was tried, what failed?
3. RESEARCH (if root cause unknown) → cheapest method first
4. FIX → minimal change to root cause
5. VALIDATE — EXECUTE at cheapest sufficient level
     Run unit test → Level 1 (cap 50)
     Run integration test → Level 2 (cap 60)
     Run replay with scoring → Level 3-4 (cap 70-75)
     Run live TTS meeting → Level 5 (cap 80)
     MUST SHOW: command run + actual output
6. UPDATE SCORE → findings.md with execution evidence + feature-log.md
7. DECIDE → score ≥ 80? done. Didn't improve? log dead end, back to 3.
```

Each step requires the previous to pass. If the unit test fails, don't run replay — the logic is wrong. **No skipping levels.**

---

## Feature Completeness

Every feature should implement all 7 concepts:

| Concept | File | Required |
|---------|------|----------|
| Confidence Gate | `tests/findings.md` | Yes — certainty table with scores, evidence, last-checked |
| Autonomous Loop | `.claude/CLAUDE.md` | Yes — defines cycle type and transition rules |
| Dead-End Record | `tests/feature-log.md` | Yes — append-only, [DEAD-END] and [RESULT] entries |
| Edge Contracts | `.claude/CLAUDE.md` | Yes — edges section with from/to/format/failure |
| Agent Manifest | All 4 files above + `README.md` | Yes — complete set for zero-handoff onboarding |
| Stage Determination | `.claude/CLAUDE.md` | Yes — "on entry" section with stage checks |
| Cost Ladder | `tests/findings.md` | Yes — score caps enforced, cheapest validation level used |

## Status (2026-03-24)

| Feature | Status | Certainty | Key Gap |
|---------|--------|-----------|---------|
| [realtime-transcription](realtime-transcription/) | Active iteration | Teams 90, GMeet 90, Zoom 0 | Zoom not implemented; GMeet/Teams both E2E PASS |
| [multi-platform](multi-platform/) | Partial | GMeet 75, Teams 65, Zoom 0 (weighted 50) | Zoom requires browser-based impl; Teams audio needs retest |
| [remote-browser](remote-browser/) | PoC proven | 30 | Working PoC not integrated into feature; persistence untested |
| [chat](chat/) | Code complete, untested | 0 | Full stack impl exists (~700 LOC); needs E2E validation |
| [webhooks](webhooks/) | P0 complete | 85 | Envelope standardized; E2E delivery needs public URL test |
| [speaking-bot](speaking-bot/) | Code complete, untested | 0 | TTS service + PulseAudio pipeline exist; needs E2E test |
| [token-scoping](token-scoping/) | Validated | 90 | 14/14 tests pass; all 4 scopes enforced |
| [mcp-integration](mcp-integration/) | Validated | 90 | 10/10 tests pass; 17 tools discoverable; P0 bugs fixed |
| [post-meeting-transcription](post-meeting-transcription/) | Partial | 85 | Pipeline works, 100% speaker accuracy (2sp); dashboard playback untested |
| [scheduler](scheduler/) | Core library done | 90 (unit) | 16/16 unit tests pass; executor not wired; REST API not built |
| [calendar-integration](calendar-integration/) | Research complete | 0 | New feature — Google Calendar auto-join; calendar-service not built |
| [agentic-runtime](agentic-runtime/) | MVP3+ Hardening | 85 | MVP0-3 done; BOT_API_TOKEN wiring, post-meeting webhook |
| [knowledge-workspace](knowledge-workspace/) | Template done, pipeline missing | 60 | Template + persistence working; entity extraction, git backing not built |

**Blockers affecting all features:** 7 open bot join/leave bugs (#171, #166, #189, #190, #115, #123, #124) block live testing. Bot resource waste (#167, #168, #170) adds 81% unnecessary CPU load.

### Open issues by feature (2026-03-23)

| Feature | Issues | Highlights |
|---------|--------|------------|
| realtime-transcription | #191, #192, #193, #194, #157, #155, #156, #148 | Caption-driven speaker detection (#192), VAD segmentation (#191), fuzzy text matching (#194), Whisper alternatives (#148, #156) |
| multi-platform | #171, #166, #189, #190, #115, #150, #128 | Teams admission bug (#171), GMeet join/leave bugs (#189, #190), Zoom SDK broken (#150, #128) |
| remote-browser | #122 | Expose CDP WebSocket for remote debugging |
| chat | #133 | Teams chat 'typing' but never delivers (#133) |
| webhooks | — | Recently closed: durable delivery (#183), status tracking (#184) |
| speaking-bot | #130, #131, #151 | Local TTS (#130), Ultravox voice assistant (#131), disable avatar (#151) |
| token-scoping | #158, #160 | Per-meeting RBAC (#158), analytics token (#160) |
| mcp-integration | #127, #139 | Interactive bot MCP tools (#127), LLM decision listener (#139) |
| post-meeting-transcription | — | No open issues |
| infrastructure | #173, #182, #142, #143, #144 | Reconciliation kills bots (#173), base migration (#182), image bloat (#142, #143) |
| not feature-scoped | #121, #136, #137, #138, #141, #145, #146, #147, #159, #161 | Meeting metadata (#121), hybrid diarization (#136), data retention (#159), raw URL support (#161) |

### Missing documentation pages

| Feature | Missing page | Status |
|---------|-------------|--------|
| post-meeting-transcription | `docs/deferred-transcription.mdx`, `docs/per-speaker-audio.mdx` | Not created |
| token-scoping | `docs/token-scoping.mdx` | Created |
| remote-browser | No docs page | Not created |
| transcript-rendering | `docs/transcript-rendering.mdx` | Not created (#174, #175) |

## Glossary

These terms are used consistently across all feature docs. Use them by name.

| Term | Definition |
|------|-----------|
| **Feature** | A job to be done. Has purpose, can be explained, developed, validated. Uses the codebase, doesn't own it. |
| **Ground truth** | What should have happened — the script TTS bots speak from. Speaker, text, timestamp. The input IS the truth. |
| **Script** | The utterances, speakers, timing, and scenario design fed to TTS bots during a collection run. Doubles as ground truth. |
| **Scenario** | A specific pattern designed into a script: normal turns, rapid exchanges, overlaps, silence gaps, single-word utterances. Each targets a known weakness. |
| **Collection run** | A live meeting session where bots speak from a script and we capture everything. The expensive outer loop. |
| **Data stage** | A named step in the feature's data pipeline: **raw** (collected from real world), **core** (pipeline output), **rendered** (delivery output). Each stage has its own folder under `data/`. One stage's output is the next stage's input. |
| **Dataset** | A tagged, self-describing bundle of data at a specific stage. Has a manifest, an ID, scenario tags. Lives under `data/{stage}/{dataset-id}/`. Datasets are the unit of reuse — same ID flows across stages (raw → core → rendered). |
| **Collected data** | Everything captured during a collection run: audio, caption events, speaker changes — all timestamped. Lives in `data/raw/{dataset-id}/`. |
| **Sandbox** | Offline replay environment. Feeds collected data through the pipeline without meetings, bots, or API costs. The cheap inner loop. |
| **Replay** | A single execution of collected data through the pipeline in sandbox. `make play-replay`. |
| **Scoring** | Comparing pipeline output to ground truth. Word-level attribution accuracy, content diff, utterance capture rate. |
| **Plateau** | When sandbox iteration stops improving — remaining errors are in scenarios not covered by current collected data. Triggers a new collection run. |
| **Inner loop** | Sandbox iteration: change code, replay, score. Seconds per cycle. Free. |
| **Outer loop** | Collection run → sandbox iteration → plateau → new collection run. Days per cycle. Expensive. |
| **Gate** | Binary pass/fail validation. A feature passes when all certainty checks >= 80. |
| **Certainty score** | 0-95 confidence in a gate check, tied to specific evidence. No evidence = 0. Mock caps at 90. Real-world = 95. |
| **Edge** | Boundary where data crosses between features or services. Each side owns its contract. |
| **Caption boundary** | The timestamp where platform captions switch speakers. The raw signal speaker-mapper works from. |
| **Infra snapshot** | Frozen record of the infrastructure state used during a collection run: service versions, model config, pipeline params, network topology. Saved alongside collected data so the sandbox can reproduce the same conditions. |
| **Collection manifest** | Pre-flight document produced during EXPAND. Specifies what to collect, why, and how — script, scenarios, data capture plan, scoring criteria, infra snapshot requirements, replay readiness. Required before a collection run. |
| **Env setup** | Stage where infrastructure is configured and verified before a collection run. Ensures services are running, configs match the collection manifest, and capture pipelines are functional. |
| **Feature log** | Append-only activity log for a feature. Records everything the agent does and why: observations, hypotheses, decisions, actions, results, dead ends. Lives at `tests/feature-log.md`. |
| **Findings** | What broke, why, what to do next. Tracked in `findings.md` with certainty scores. |

## Features vs services

**Services** (`services/`) are infrastructure — a transcription service, an API gateway, a bot manager. They exist to be composed. A service doesn't know why it's being called.

**Features** (`features/`) are the reason services exist. A feature like `realtime-transcription` orchestrates speaker-streams, transcription-client, segment-publisher, speaker-mapper, transcription-collector, and api-gateway into a pipeline that does something a user cares about: live speaker-attributed transcription.

```
features/                          services/
  realtime-transcription/    USES    vexa-bot/
    google-meet/             USES    transcription-service/
    ms-teams/                USES    transcription-collector/
    zoom/                    USES    api-gateway/
  speaking-bot/              USES    tts-service/, vexa-bot/, bot-manager/
  browser-control/           USES    vexa-bot/ (CDP, PulseAudio)
  ...
```

A feature can be explained to someone who doesn't read code. A service can't — it's a building block.

## What a feature contains

```
features/{name}/
  README.md              # Why / What / How — the feature spec
  .claude/CLAUDE.md      # Scope, gate, edges, certainty table
  .env.example           # Committed template — all vars with defaults/placeholders
  .env                   # Gitignored — actual values for this environment
  data/                  # Feature's data, organized by pipeline stage
    raw/                 # Collected from real world — audio, events, platform behavior
    core/                # Pipeline output — confirmed segments, transcriptions
    rendered/            # Delivery output — REST responses, WS captures, DB snapshots
  tests/
    README.md            # Test strategy, scoring, results
    findings.md          # Certainty table, gate verdict, action items
    feature-log.md       # Append-only activity log — observations, decisions, results
    Makefile             # Stage-aware test commands (reads from ../.env)
  {platform}/            # Platform-specific implementations (if multi-platform)
```

### .env.example / .env — Infrastructure config

Each **feature** has its own `.env.example` (committed) and `.env` (gitignored). This separates feature-level infra config from the global stack config.

**Why per-feature:** Different **features** in development may need different infra — one feature testing with `large-v3-turbo` while another tests with `base` for speed, one pointing at GPU transcription while another uses CPU. The feature `.env` is the single source of truth for what infra that feature is using right now.

**`.env.example`** — committed, documents every variable the feature needs:
```bash
# Transcription service
TRANSCRIPTION_URL=http://localhost:8085/v1/audio/transcriptions
TRANSCRIPTION_TOKEN=
MODEL_SIZE=large-v3-turbo
COMPUTE_TYPE=int8

# Pipeline params
SUBMIT_INTERVAL=3
CONFIRM_THRESHOLD=3
MIN_AUDIO_DURATION=3
MAX_BUFFER_DURATION=120
IDLE_TIMEOUT_SEC=15

# Platform
PLATFORM=ms-teams

# Stack
API_GATEWAY_URL=http://localhost:8066
REDIS_URL=redis://localhost:6379
POSTGRES_URL=postgresql://postgres:postgres@localhost:5448/vexa_restore
```

**`.env`** — gitignored, actual values for this machine/environment. Created during **env setup** by copying `.env.example` and filling in real values.

The feature's `Makefile` and test scripts read from `.env`. The **infra snapshot** records the `.env` values at the time of a **collection run**.

### data/ — Feature data organized by pipeline stage

A feature knows its data. The `data/` directory organizes all datasets by the pipeline stage they represent. One stage's output is the next stage's input.

#### Stages

| Stage | What it contains | Example |
|-------|-----------------|---------|
| **raw** | Collected from the real world during a **collection run**. Audio, platform events, caption data, speaker changes. Unprocessed. | WAV files, caption-events.json, speaker-changes.txt |
| **core** | Output of the feature's pipeline. Confirmed segments, transcriptions, scored results. | segments.json, scoring.md |
| **rendered** | Delivery output. What clients see — REST responses, WebSocket captures, DB snapshots. | rest-output.json, ws-capture.json |

Not every feature uses all three stages. A feature declares which stages it has:

```markdown
### Data stages
| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| raw   | audio + caption events | collection run (live meeting) | transcription pipeline |
| core  | confirmed segments | SpeakerStreamManager | delivery pipeline |
```

#### Directory structure

```
data/
  raw/
    {dataset-id}/              # One directory per collection run
      manifest.md              # What, why, when, hypothesis, scenarios, infra
      ground-truth.txt         # [GT] timestamp speaker "text"
      infra-snapshot.md        # Frozen .env + service state at collection time
      audio/                   # WAV files (per-utterance + combined)
      events/                  # Platform events (caption, speaker change, DOM)
  core/
    {dataset-id}/              # Derived from a raw dataset (same ID)
      segments.json            # Confirmed segments from pipeline
      scoring.md               # Accuracy vs ground truth
  rendered/
    {dataset-id}/              # Derived from a core dataset (same ID)
      rest-output.json         # GET /transcripts response
      ws-capture.json          # WebSocket messages captured
```

A **dataset ID** flows across stages. `teams-3sp-diverse-20260320` appears in `data/raw/` after collection, in `data/core/` after replay, in `data/rendered/` after delivery testing. This makes lineage explicit — you can always trace rendered output back to the raw data that produced it.

#### Dataset ID format

`{platform}-{speakers}sp-{scenario-tag}-{YYYYMMDD}`

Examples:
- `teams-3sp-diverse-20260320` — 3 speakers, diverse scenarios, Teams, March 20
- `gmeet-5sp-overlap-20260405` — 5 speakers, overlap focus, Google Meet, April 5

#### Cross-feature data flow

When one feature's output is another feature's input, the consuming feature references the producing feature's data stage:

```
realtime-transcription/data/core/     ← produced by transcription pipeline
              |
              v
delivery/data/raw/                    ← delivery's "raw" IS transcription's "core"
```

A sub-feature's `data/raw/` may be a symlink or explicit reference to its parent's `data/core/`. The README documents this relationship.

#### Rules

- **Datasets are immutable.** Once collected/produced, never modify. If you need different processing, produce a new dataset in the next stage.
- **Every dataset has a manifest.** No anonymous data files floating around.
- **Stage folders that don't apply are omitted.** Don't create empty `data/rendered/` if the feature has no rendered stage.
- **Ground truth lives in raw.** It's collected alongside the raw data, not derived.
- **Infra snapshot lives in raw.** It records the conditions under which raw data was captured.
- **Scoring lives in core/rendered.** It compares pipeline output to ground truth.

### tests/Makefile — Stage-aware commands

The `Makefile` is the instrument for executing each stage. It reads config from the feature's `.env` so infra is configured in one place, not duplicated across scripts.

Every feature Makefile should expose targets mapped to stages:

| Stage | Targets | What they do |
|-------|---------|-------------|
| **Env setup** | `make env-check` | Verify `.env` exists, show config |
| | `make smoke` | One utterance end-to-end — proves infra works |
| **Collection run** | `make audio` | Generate WAVs from **scripts** via TTS |
| **Sandbox iteration** | `make unit` | Unit tests (mocked, instant) |
| | `make play-*` | **Replay** specific WAV through pipeline |
| | `make play-replay` | **Replay** real **collected data** |
| | `make test` | Full **scoring** run (unit + all replays) |

The Makefile loads `.env` via `-include ../. env` and exports all vars. Fallback defaults allow CI/quick runs without a `.env`, but the feature `.env` is the source of truth for local development.

### README.md — Why / What / How

Every feature README follows this structure:
- **Why** — the problem this feature solves, from the user's perspective
- **What** — what it does, its architecture, key behaviors, components used
- **How** — how to run, verify, and develop it

The README is the feature spec. If the README says it does something, the code must do it. If the code does something, the README must say it.

### CLAUDE.md — Scope, gate, edges

Defines what the feature owns and what it dispatches:
- **Scope** — what you test, what you don't
- **Gate** — binary pass/fail criteria with certainty scores
- **Edges** — data contracts with other features and services
- **Counterparts** — related features and services

### tests/ — Validation

Where the feature proves it works. See [validation cycle](#validation-cycle) below.

## Validation cycle

Features that interact with real-world systems (meetings, speech, platforms) follow a **collect-once, iterate-many** cycle. The real world is expensive. The sandbox is free.

### The cycle

```
1. COLLECT                        2. ITERATE                     3. EXPAND
   Real world                        Sandbox                        Back to real world
   ──────────                        ───────                        ─────────────────
   Run the feature in prod-like      Replay collected data          Design new scenarios
   conditions (live meeting,         offline through the pipeline   that cover gaps found
   real platform, real users)        Score against ground truth     in step 2
                                     Change code, re-score
   Collect everything:               in seconds — no meetings,     Collect new dataset
   - inputs (audio, events)          no bots, no API costs         Feed into sandbox
   - platform behavior (captions,                                  Repeat
     DOM events, timing)             Hit accuracy ceiling?
   - pipeline output (segments,      Need new scenarios? ──────►
     drafts, confirmations)
   - ground truth (scripts = truth)
```

### Why this way

The real-world environment is not controllable and expensive to run against repeatedly. A live meeting involves browser automation, TTS API calls, network latency, platform-specific behavior — all slow, flaky, and costly. You can't iterate by running 50 live meetings a day.

But you **need** real platform behavior — caption delays, DOM quirks, overlap truncation — because synthetic data won't surface those issues.

So: collect reality once, iterate against it many times. Only go back to real world when the current dataset can't teach you anything new.

### Artifacts

Each **feature** that uses this cycle maintains:

| Artifact | Location | Purpose | Example |
|----------|----------|---------|---------|
| **Datasets** | `data/{stage}/{id}/` | Tagged bundles at each **data stage** | `data/raw/teams-3sp-diverse-20260320/` |
| **Replay** test | `tests/Makefile` | Feeds **datasets** through pipeline offline | `make play-replay` |
| **Scoring** | `data/core/{id}/scoring.md` | Compares pipeline output to **ground truth** | Word-level attribution accuracy, content diff |
| **Findings** | `tests/findings.md` | What broke, why, what to collect next | **Certainty scores**, action items |

### Datasets

A **dataset** is the unit of reuse. Each **collection run** produces a raw **dataset**. Running the pipeline produces a core **dataset** from that raw. Same ID flows across **data stages** — lineage is always traceable.

Datasets are tagged, self-describing, and independent — you can replay one dataset, combine several, or retire old ones.

#### Directory structure

```
data/
  raw/
    {dataset-id}/
      manifest.md          # What, why, when, hypothesis, scenarios, infra
      ground-truth.txt     # Script send times: [GT] timestamp speaker "text"
      infra-snapshot.md    # Frozen .env + service state at collection time
      audio/               # WAV files (per-utterance + combined)
      events/              # Platform events (caption, speaker change, DOM)
  core/
    {dataset-id}/            # Same ID as the raw dataset it was derived from
      segments.json          # Confirmed segments from pipeline
      scoring.md             # Accuracy vs ground truth
      pipeline-logs/         # Drafts, confirmations, debug output
  rendered/
    {dataset-id}/            # Same ID as the core dataset it was derived from
      rest-output.json       # GET /transcripts response
      ws-capture.json        # WebSocket messages captured
```

Dataset ID format and examples are defined in the [data/ section](#data--feature-data-organized-by-pipeline-stage) above.

#### Dataset manifest (manifest.md)

Every **dataset** has a manifest that describes what it contains and why it was collected. This is the dataset's self-description — without it, the data is unlabeled and can't be reused.

```markdown
# Dataset: {id}

## Collection run
- **Date:** {YYYY-MM-DD}
- **Platform:** {ms-teams | google-meet | zoom}
- **Speakers:** {N} ({names})
- **Duration:** {seconds}
- **Triggered by:** {what plateau/gap led to this collection}

## Hypothesis
{What this dataset was designed to test. What will scoring prove or disprove?}

## Scenarios
| Tag | Description | Utterances | Expected scoring |
|-----|------------|-----------|-----------------|
| normal-turns | >2s gaps, clean transitions | 4 | ~100% attribution |
| rapid-exchange | <1s gaps | 6 | ~80-85% (caption delay) |
| short-phrase | sub-1s single-word utterances | 5 | unknown — this is what we're testing |
| control | repeat of known-good scenario | 2 | must match previous scoring |

## Files
| File | Type | Records | Scenarios covered |
|------|------|---------|------------------|
| ground-truth.txt | ground truth | 17 utterances | all |
| audio/alice-01.wav | audio | 1 utterance | normal-turns |
| events/caption-events.json | collected data | 293 events | all |
| pipeline/bot-logs.txt | collected data | 157 lines | all |

## Infra
See infra-snapshot.md. Key values:
- MODEL_SIZE={value}
- COMPUTE_TYPE={value}
- MIN_AUDIO_DURATION={value}

## Baseline scoring
{Filled after first replay — the initial score before any iteration}

## Status
{active | superseded by {id} | retired — reason}
```

#### Why tagging matters

Without tags, datasets are opaque blobs:
- You don't know which **scenarios** a dataset covers → you can't pick the right one for iteration
- You don't know why it was collected → you can't tell if it's still relevant
- You don't know what infra was used → you can't reproduce conditions in **sandbox**
- You can't combine datasets → each **collection run** is isolated

With tags:
- **Scenario tags** let you select datasets by what they test: "give me all datasets with short-phrase scenario"
- **Hypothesis** lets you know if a dataset is still useful or superseded
- **Status** lets you retire datasets when they're no longer needed
- **Infra snapshot** lets you verify sandbox matches collection conditions
- Multiple datasets can be replayed together if their infra snapshots are compatible

#### Dataset lifecycle

1. **Created** during a **collection run** — all files saved, manifest filled
2. **Active** — used in **sandbox iteration**, replayed, scored against
3. **Superseded** — a newer dataset covers the same scenarios with better data. Keep for reference but don't iterate against.
4. **Retired** — no longer useful. Keep the manifest, delete large files (audio) if needed.

#### Combining datasets

When iterating, you may need to **replay** multiple **datasets** together — e.g., the normal-turns dataset for control + the new short-phrase dataset for the target scenario. This works if:
- **Infra snapshots** are compatible (same model, same pipeline params)
- **Scenarios** don't conflict (no overlapping time ranges)
- The **replay** test knows how to load multiple datasets

If infra snapshots differ, you can't combine — the scoring would mix results from different configs.

## Feature log

The **feature log** (`tests/feature-log.md`) is an append-only record of everything the agent does on a feature and why. It's a lab notebook — the agent writes as it works, not just at milestones.

### Why

Without a log:
- Each session starts blind — the agent reads `findings.md` (current state) but not how it got there
- Dead ends get retried — nothing records "tried X, it made things worse, reverted"
- Reasoning is lost — you see code changes in git but not WHY that approach was chosen
- Trajectory is invisible — is scoring going up? oscillating? stuck?

With a log:
- Agent reads history on startup, continues where it left off
- Dead ends are recorded and avoided
- Humans can review the agent's reasoning
- Trajectory table shows at a glance whether things are improving

### Structure

```markdown
# Feature Log: {name}

## Trajectory
| # | Date | Datasets | Scoring | Delta | Fix | Status |
|---|------|----------|---------|-------|-----|--------|
| 1 | 03-20 | teams-3sp-diverse | 71% | baseline | — | iterating |
| 2 | 03-20 | teams-3sp-diverse | 81% | +10% | mapper boundary shift | iterating |
| 3 | 03-21 | teams-3sp-diverse | 81% | +0% | minAudio=0.5s | dead-end, reverted |

## Log

### 2026-03-20 14:30 [STAGE]
Entering sandbox iteration. Datasets: teams-3sp-diverse (target), teams-2sp-normal (control).
Current scoring: 71% diverse, 100% normal.

### 2026-03-20 14:32 [OBSERVE]
Checked caption events for 5 lost utterances in diverse dataset.
- "Agreed." (Alice 33.1s) — NO caption event. Teams didn't generate one.
- "OK." (Bob 37.1s) — NO caption event.
- "Thanks." (Alice 33.1s) — caption exists but inside Charlie boundary (29.5-44.4s).
2/5 have no caption at all. 3/5 have caption but wrong speaker.

### 2026-03-20 14:35 [DECIDE]
Two categories of loss:
1. Caption exists, wrong speaker (3/5) — fixable in speaker-mapper
2. No caption at all (2/5) — unfixable with captions, needs audio-energy approach
Focusing on category 1. Category 2 is a new scenario for /expand.

### 2026-03-20 14:40 [HYPOTHESIS]
Caption boundaries lag real speech by ~1.5s. Words in first 1.5s of new speaker
get attributed to previous speaker. Shifting boundaries backward should recover.

### 2026-03-20 14:42 [ACTION]
speaker-mapper.ts:mapWordsToSpeakers L47 — subtract 1.5s from caption boundary
start times before overlap matching.

### 2026-03-20 14:44 [RESULT] Iteration 1
| Dataset | Scenario | Before | After | Delta |
|---------|----------|--------|-------|-------|
| diverse | normal-turns | 100% | 100% | 0% |
| diverse | short-phrase | 40% | 60% | +20% |
| diverse | overall | 71% | 81% | +10% |
| normal | control | 100% | 100% | 0% |

### 2026-03-20 14:45 [DECIDE]
+10%, no regression on control. Keep boundary shift.
2 phrases still lost — no caption events exist. Can't fix with mapper.
Next: try lowering minAudioDuration to catch at audio level.

### 2026-03-20 14:50 [DEAD-END]
Tried minAudioDuration=0.5s. Diverse: 81% → 78%. Introduced 3 garbage segments
from silence. Reverted. Short phrases without captions need a different approach.
```

### Entry types

| Type | When to write | What to include |
|------|--------------|----------------|
| `STAGE` | Entering or exiting a stage | Which stage, which datasets, current scoring |
| `OBSERVE` | Found something in data, code, or output | What you found, where, what it implies |
| `HYPOTHESIS` | Theory about a root cause | The theory, what evidence supports it, how to test it |
| `DECIDE` | Making a choice | What you chose, what alternatives existed, WHY this one |
| `ACTION` | Changing code or config | File:line, what changed, what it's supposed to fix |
| `RESULT` | Scoring output from a replay | Per-dataset per-scenario table, delta from previous |
| `DEAD-END` | Tried something, didn't work | What was tried, what happened, why it failed, reverted? |
| `QUESTION` | Something unknown | What you don't know, where to find the answer |

### Rules

- **Append only.** Never edit or delete previous entries. The log is a timeline.
- **Write as you go.** Don't batch entries at the end. Write when you observe, decide, or act.
- **Include WHY.** Every `DECIDE` and `ACTION` entry must explain reasoning. "Changed X" is not enough — "Changed X because Y, expecting Z" is.
- **Update the trajectory table** after every `RESULT` entry. The table is the summary; the log is the detail.
- **Mark dead ends explicitly.** A `DEAD-END` entry prevents the same approach from being retried in future sessions.
- **Read the log on startup.** Before starting work, read the full log to understand history, current state, and dead ends.
- **Committed, not gitignored.** The log is part of the feature's history. Commit after each session.

### Feature log vs other files

| File | Purpose | Mutability |
|------|---------|-----------|
| `feature-log.md` | Stream of what happened, why, and how — full history | Append only |
| `findings.md` | Current state: certainty scores, gate verdict, action items | Overwritten to reflect current state |
| Dataset `manifest.md` | What a dataset contains and why it was collected | Immutable after collection |
| `README.md` | Feature spec and test approach | Updated when approach changes |

## Stages

The validation cycle has four stages. Know which stage you are in. Each stage has a purpose, allowed actions, constraints, and exit criteria. Do not mix stages.

### How to determine your stage

```
Is the infra running and verified for this feature?
  NO  → you are in ENV SETUP
  YES → Do you have collected data + ground truth + replay test?
          NO  → you are in COLLECTION RUN
          YES → run replay, check scoring
                Is scoring improving between iterations?
                  YES → you are in SANDBOX ITERATION
                  NO  → you are in EXPAND
```

---

### Stage 0: ENV SETUP

**Purpose:** Configure and verify the infrastructure so you have a working environment to test against. Different **features** may need different infra configurations — Whisper model, compute type, pipeline params, service versions. You must set this up and prove it works before spending time on a **collection run**.

**Entry conditions:**
- Starting work on a **feature** for the first time
- **Collection manifest** specifies infra requirements that don't match current setup
- Infra changed since last run (service upgrade, config drift, different machine)

**What you do:**
1. **Read the collection manifest** (or feature CLAUDE.md if first time) — what infra does this feature need?
2. **Create `.env` from `.env.example`** — copy `features/{name}/.env.example` to `features/{name}/.env`, fill in actual values for this machine/environment. If `.env` already exists, verify it matches the manifest requirements.
3. **Start services** — `make up` or equivalent, using the config from `.env`
4. **Verify each service** — health checks, version checks, config checks. Every service in the `.env` must be reachable and returning expected versions.
5. **Run a smoke test** — send one utterance through the full pipeline, verify output arrives. This proves the feature's full path works end-to-end with this infra.
6. **Record the infra snapshot** — save `tests/infra-snapshot.md` with the `.env` values and verification results

#### Infra snapshot

An **infra snapshot** is a frozen record of the infrastructure configuration. It's saved as `tests/infra-snapshot.md` (committed) alongside your **collected data** so the **sandbox** can reproduce identical conditions.

The **infra snapshot** has two parts:

**1. The `.env` values** — copy of the feature's `.env` at the time of the **collection run**. This is the primary record — it contains the actual config used.

**2. Verified service state** — proof that services were running and healthy with those configs:

```markdown
## Infra snapshot: {date}

### Environment
Source: `features/{name}/.env`
```
TRANSCRIPTION_URL=http://localhost:8085/v1/audio/transcriptions
TRANSCRIPTION_TOKEN=your-token-here
MODEL_SIZE=large-v3-turbo
COMPUTE_TYPE=int8
SUBMIT_INTERVAL=3
CONFIRM_THRESHOLD=3
MIN_AUDIO_DURATION=3
...
```

### Service verification
| Service | Image/Version | Health check | Result |
|---------|--------------|-------------|--------|
| transcription-service | faster-whisper, large-v3-turbo, int8 | GET /health | 200 OK |
| redis | 7.0-alpine | PING | PONG |
| postgres | 17-alpine | SELECT 1 | ok |
| tts-service | piper, en_US-lessac-medium | GET /health | 200 OK |
| bot-manager | vexa-bot-restore:dev | GET /health | 200 OK |

### Smoke test
Sent: "Hello world" via TTS → pipeline → confirmed segment
Result: "Hello world." received in {X}ms
```

**Why the snapshot matters:** If you change `MODEL_SIZE` from `large-v3-turbo` to `base` between **collection run** and **sandbox iteration**, your **scoring** is comparing apples to oranges. The snapshot lets you verify the **sandbox** is running the same infra as the **collection run**.

**Constraints:**
- Do NOT start a **collection run** until every service in the snapshot is verified healthy
- Do NOT assume previous infra is still valid — always re-verify after any gap in time
- Do NOT mix infra from different stacks (e.g., transcription-service on port 8085 from main stack with bot on restore stack port 8066)
- Record the **infra snapshot** even if "nothing changed" — the snapshot is evidence, not a guess

**Exit criteria:**
- All required services are running and healthy
- **Infra snapshot** is recorded
- A smoke test passes: send one utterance through the full pipeline, verify output
- If entering COLLECTION RUN: infra matches **collection manifest** requirements
- If entering SANDBOX ITERATION: infra matches the **infra snapshot** from the **collection run** that produced the **collected data**

**Log:** `STAGE: env-setup started — feature: {name}, platform: {platform}`
**Log:** `STAGE: env-setup complete — {N} services verified, infra snapshot saved`

---

### Stage 1: COLLECTION RUN

**Purpose:** Capture real-world behavior that the **sandbox** can replay. You are gathering data, not improving the pipeline. **Collection runs are expensive** — you need to get everything in one shot.

**Entry conditions:**
- **Env setup** complete — all services healthy, **infra snapshot** recorded
- No **collected data** exists for this **feature** or platform, OR
- **Plateau** reached in **sandbox** — need new **scenarios**, OR
- Platform behavior changed — existing **collected data** may be stale
- A **collection manifest** exists (see below)

#### Collection manifest (required before running)

Before you run anything, produce a **collection manifest** — a document that specifies exactly what you're collecting and why. This is the contract between EXPAND and COLLECTION RUN. If you can't fill this out, you're not ready to collect.

```markdown
## Collection manifest: {name}

### Why this collection run
{What plateau/gap triggered this? Link to findings.}

### Hypothesis
{What do you believe is the root cause of the remaining errors? What will this data prove or disprove?}

### Script
| # | Speaker | Utterance | Timing | Scenario |
|---|---------|-----------|--------|----------|
| 1 | Alice   | "..."     | T+0s   | normal-turns |
| 2 | Bob     | "..."     | T+12s  | normal-turns |
| ...

### Scenarios covered
| Scenario | What it tests | Expected behavior | How to score |
|----------|--------------|-------------------|--------------|
| normal-turns | >2s gaps between speakers | Clean attribution | Word-level accuracy |
| rapid-exchange | <1s gaps | Caption boundary delay | Boundary word accuracy |
| ...

### Infra requirements
What .env config does this collection run need? What must differ from default?

| Variable | Required value | Why |
|----------|---------------|-----|
| MODEL_SIZE | large-v3-turbo | Production model — scoring must reflect real accuracy |
| COMPUTE_TYPE | int8 | Matches production |
| MIN_AUDIO_DURATION | 3 | Current default — baseline before tuning |
| PLATFORM | ms-teams | Testing Teams caption boundaries |
| ... | | |

### Data to capture
| Data | Source | Format | Why needed |
|------|--------|--------|------------|
| Audio | TTS WAV output | WAV, per-utterance + combined | Replay through Whisper |
| Caption events | DOM MutationObserver | JSON, timestamped | Replay caption boundaries |
| Speaker changes | DOM author switches | JSON, timestamped | Speaker-mapper input |
| Pipeline output | Bot logs | JSON, timestamped | Baseline to beat |
| Ground truth | Script send times | TXT, Unix timestamps | Scoring reference |
| Infra snapshot | .env + health checks | Markdown | Reproduce conditions in sandbox |

### Capture checklist
For each data type, specify: where it comes from, how it's logged, and how you'll verify it was captured.

### Replay readiness
How will this data be fed into the sandbox? What replay test will consume it?
What .env values must the sandbox match? (Reference the infra snapshot.)
```

**Why the manifest matters:** A **collection run** costs real time and money. If you forget to capture **caption boundary** events, or your timestamps aren't synced, or you didn't include a control **scenario**, the entire run is wasted. The manifest forces you to think through what you need before you spend the budget.

#### What you do

1. **Write the collection manifest** — fill out every section above
2. **Review the manifest** — does every **scenario** have scoring criteria? Is every data type accounted for? Will the **replay** test be able to consume this data?
3. **Create the dataset directory** — `data/raw/{id}/` using the [dataset ID format](#data--feature-data-organized-by-pipeline-stage). Copy the collection manifest into it as `manifest.md`.
4. Set up the meeting environment (live meeting, TTS bots, platform)
5. **Verify capture is working** before running the full **script** — send one test utterance, check that all data types are being logged with timestamps
6. Run the bots — they speak from the **script**
7. Capture **everything** with timestamps. Refer to the manifest's data table — every row must be captured.
8. Save all files into the **dataset** directory structure: `ground-truth.txt`, `audio/`, `events/`, `pipeline/`, `infra-snapshot.md`
9. **Tag every file** — each file in the dataset must be traceable to a **scenario** in the manifest. The manifest's files table must list every file with its scenario coverage.
10. **Verify completeness against the manifest** — for each data type, confirm the file exists in the dataset, has the expected format, and covers all **scenarios**
11. Run a smoke **replay** — feed the dataset through the pipeline once to verify it's consumable
12. **Record baseline scoring** in the dataset manifest under "Baseline scoring"
13. **Write the dataset README** — human summary of what's in the dataset, why it was collected, how to replay it

#### Constraints

- Do NOT start without a **collection manifest** — if you can't articulate what you need, you'll miss it
- Do NOT change pipeline code during a **collection run** — you're capturing a baseline, not iterating
- Do NOT discard partial or "bad" data — it may reveal real platform behavior
- Do NOT run multiple **scripts** in one session unless the **scenarios** are independent (different time windows)
- Do NOT assume capture is working — verify each data source is logging before running the full **script**
- Do NOT save data outside the **dataset** directory — all files for one collection run go in one dataset

#### Exit criteria

- A **dataset** directory exists at `data/raw/{id}/` with the correct structure
- **Dataset manifest** (`manifest.md`) is complete: hypothesis, scenarios, files table, infra, baseline scoring
- **Ground truth** file exists with all utterances, speakers, timestamps
- **Collected data** files exist in the dataset: every row in the manifest's files table has a corresponding file
- Every file is tagged with which **scenarios** it covers
- **Infra snapshot** is saved in the dataset
- A **replay** test can load this dataset and feed it through the pipeline offline
- **Scoring** produces a baseline number (recorded in manifest)
- **Dataset status** is set to `active`

**Log:** `STAGE: collection-run started — manifest: {name}, platform: {platform}, scenarios: {list}`
**Log:** `STAGE: collection-run complete — {N} utterances, {M} events, {K} data files, baseline scoring: {X}%`

---

### Stage 2: SANDBOX ITERATION (inner loop)

**Purpose:** Improve the pipeline by replaying **datasets** and measuring improvement via **scoring**. This is where development happens.

**Entry conditions:**
- At least one **active** **dataset** exists in `data/raw/`
- **Scoring** is not at **plateau**

#### Select your datasets

Before iterating, decide which **datasets** to replay against. Read the manifests in `data/raw/*/manifest.md`:

- Which **datasets** are `active`? Ignore `superseded` or `retired`.
- Which **scenarios** does each dataset cover? Match to the errors you're fixing.
- Are the **infra snapshots** compatible with your current `.env`? If not → `/env-setup` first.
- Do you need to combine datasets? Only if infra snapshots match.

If you're targeting a specific problem (e.g., short phrase loss), you may iterate against just the dataset that covers that **scenario**. But always include a control **dataset** to catch regressions — a dataset with known-good scenarios that should keep scoring the same.

Log: `SANDBOX: iterating against datasets: {id1} (scenarios: X, Y), {id2} (control: Z)`

**What you do:**
1. **Replay** — run `make play-replay DATASET={id}` (or equivalent) to feed a **dataset** through the pipeline
2. **Score** — compare output to **ground truth** in the dataset, get accuracy numbers per **scenario**
3. **Diagnose** — find the root cause of errors (not symptoms). Trace through pipeline: buffer thresholds? **caption boundary** delay? confidence filter? speaker-mapper logic?
4. **Fix** — make the minimal code change to address the root cause
5. **Replay** again — re-score against the same **dataset(s)**, verify improvement
6. **Check controls** — did scoring regress on control **scenarios** or control **datasets**? If yes, the fix broke something.
7. **Log** the delta — what changed, what improved, what regressed, which **dataset(s)** were used

Repeat steps 1-7. Each iteration should take seconds to minutes, not hours.

**Constraints:**
- Do NOT run live meetings — you are in the **sandbox**, work only with **datasets**
- Do NOT modify **datasets** — they are immutable records of what happened
- Do NOT add **scenarios** that aren't in any **dataset** — if you need new scenarios, exit to EXPAND
- Do NOT skip **scoring** after a fix — every change must be measured
- Do NOT iterate without a control — always replay at least one known-good **dataset** to catch regressions
- Follow the [diagnose → fix → verify → audit](../.claude/agents.md#phases) phase discipline within each iteration

**Exit criteria (to EXPAND):**
- **Scoring** has stopped improving across 3+ iterations
- Remaining errors are in **scenarios** not covered by any active **dataset**
- You can articulate exactly which **scenarios** you need — this becomes the input to EXPAND

**Exit criteria (to GATE):**
- **Scoring** meets target accuracy for all **scenarios** across all active **datasets**
- Control **datasets** show no regression
- All **certainty scores** in **findings** are >= 80

**Log:** `SANDBOX: iteration {N} — dataset: {id} — scoring: {X}% → {Y}% (delta: {+/-Z}%) — fix: {description}`
**Log:** `SANDBOX: plateau reached — scoring stuck at {X}% for {N} iterations — need scenarios: {list} — active datasets don't cover them`

---

### Stage 3: EXPAND

**Purpose:** Design new **scenarios** and **scripts** that target known weaknesses, then produce a **collection manifest** for the next **collection run**. This is where you decide what data you need and why — before spending the budget.

**Entry conditions:**
- **Plateau** in **sandbox** — remaining errors traced to missing **scenarios**
- You can name the specific **scenarios** needed

**What you do:**
1. Review **findings** — what errors remain? What **scenarios** cause them? Be specific: "5/17 utterances lost, all single-word, all followed by speaker change within 1s"
2. Formulate a hypothesis: "Short phrases are lost because `minAudioDuration=3s` prevents submission. We need a **scenario** with many sub-1s utterances to measure the true loss rate and test alternative flush thresholds."
3. Design new **scenarios** that target those errors specifically:
   - Each **scenario** should isolate one variable (e.g., "single-word utterances followed by speaker change")
   - Reuse working **scenarios** from previous **scripts** as controls — you need to verify you didn't regress
   - Define how each **scenario** will be **scored** — what's the expected output, what counts as correct?
4. Write the **collection manifest** (see [Stage 1](#stage-1-collection-run) for template):
   - **Script** with speakers, utterances, timing, **scenario** labels
   - **Data to capture** — every data type you need, where it comes from, how it's logged
   - **Replay readiness** — how the **sandbox** will consume this data
5. Review: does the manifest cover the hypothesis? Will you have enough data to confirm or disprove it?

**Constraints:**
- Do NOT guess what data you need — base **scenario** design on specific errors from **findings**
- Do NOT design **scenarios** you can't **score** — every **scenario** needs a clear expected output
- Do NOT combine too many new **scenarios** in one **script** — isolate variables so **scoring** is unambiguous
- Do NOT skip the hypothesis — if you don't know why you're collecting, the data is wasted
- Do NOT skip control **scenarios** — include **scenarios** that already work to catch regressions

**Exit criteria:**
- **Collection manifest** is complete (every section filled, every **scenario** has **scoring** criteria)
- Hypothesis is documented and testable
- **Script** covers both new **scenarios** and control **scenarios**
- Ready for Stage 1 (COLLECTION RUN)

**Log:** `EXPAND: plateau at {X}% — {N} errors in scenarios: {list}`
**Log:** `EXPAND: manifest ready — scenarios: {list} — hypothesis: {description}`

---

### Stage transitions

```
                    ┌─────────────────────────┐
                    │                         │
                    v                         │
             COLLECTION RUN                   │
                    │                         │
                    │ data collected           │
                    v                         │
            SANDBOX ITERATION ──plateau──► EXPAND
                    │
                    │ target met
                    v
                   GATE
```

**Rules:**
- You must be in exactly one stage at a time
- Log every stage transition with the reason
- Never skip SANDBOX ITERATION — even if you think the code is right, **replay** and **score** to prove it
- EXPAND always leads back to COLLECTION RUN — you don't iterate in sandbox on scenarios you haven't collected data for

## Feature lifecycle

1. **Define** — Write the README (Why / What / How) and CLAUDE.md (scope, **gate**, **edges**)
2. **Collection run** — Run the **feature** against real-world conditions, capture **collected data** and **ground truth**
3. **Sandbox iteration** — **Replay**, **score**, diagnose, fix, repeat (**inner loop**)
4. **Expand** — Hit **plateau**, design new **scenarios**, new **script**, new **collection run** (**outer loop**)
5. **Gate** — All **certainty scores** >= 80, docs gate passes

## Spec-driven features

Not every feature interacts with the real world. Features like **webhooks**, **MCP integration**, and **token-scoping** are **deterministic, spec-driven** — the ground truth is the API contract, not a recording. These features don't need collection runs, TTS bots, or audio replay. They need specs, contract tests, and fast iteration.

### Why a different cycle

| | Real-world features | Spec-driven features |
|---|---|---|
| **Ground truth** | Script TTS bots speak from | API spec (expected request/response) |
| **Expensive step** | Collection run (live meeting) | Nothing — iteration is always cheap |
| **Inner loop** | Replay audio → score → fix | Run test script → check assertions → fix |
| **Outer loop** | New scenarios → new collection | Research → new spec items → new tests |
| **Plateau** | Errors in uncovered scenarios | Gaps found by research or competitor analysis |
| **Data** | Audio, caption events, segments | Request/response pairs, payload captures |

### Spec-driven cycle

```
1. RESEARCH                      2. SPEC                         3. BUILD & TEST
   External                         Contract                        Inner loop
   ──────────                        ────────                        ──────────
   What do competitors do?           Define the contract:            Implement the spec
   What does the protocol            - Event catalog / tool list     Run make test
   support that we don't?            - Payload schemas               Check assertions
   What do users need?               - Error cases                   Fix, re-run
                                     - Edge cases                    Seconds per cycle
   What broke in production?
   What did users report?         Write as test assertions
                                  BEFORE writing code               All tests pass?
   Produce: RESEARCH.md                                             Update findings.md
                                  Produce: SPEC.md                  Update certainty scores
                                          test scripts
                                                                    Done? → GATE
                         ◄── plateau / gap found ──────────────────┘
```

### Stage 0: ENV SETUP (same as real-world features)

Verify infra, create `.env`, run `make smoke`. Same process, simpler services.

### Stage 1: RESEARCH

**Purpose:** Understand what "great" looks like before writing code. Produce `RESEARCH.md`.

**What you do:**
1. **Audit current implementation** — read the code, map what exists
2. **Competitive analysis** — what do Recall.ai, Fireflies, Stripe, etc. do?
3. **Protocol/standard analysis** — what does MCP/webhook best practice say?
4. **User/issue analysis** — what are users asking for? What broke?
5. **Gap identification** — what's missing, what's broken, what's inconsistent?
6. **Priority ranking** — P0 (fix now), P1 (quick wins), P2 (medium), P3 (big bets)

**Exit criteria:**
- `RESEARCH.md` exists with prioritized gaps and recommendations
- Clear understanding of what "done" looks like for each priority level

**Constraints:**
- Do NOT write code during research — understand first
- Do NOT skip competitive analysis — you can't know what's missing without context
- Do NOT limit research to reading docs — test the actual running system

### Stage 2: SPEC

**Purpose:** Turn research into a testable contract. Write test assertions BEFORE implementation.

**What you do:**
1. **Pick a priority batch** — start with P0, then P1. Don't boil the ocean.
2. **Write the spec** — for each item in the batch:
   - What is the expected behavior? (request → response, event → payload)
   - What are the edge cases? (missing fields, invalid input, auth failures)
   - What is the payload schema? (required fields, types, format)
3. **Write test assertions** — add test cases to the feature's test script that assert the spec. These tests SHOULD FAIL initially (the feature doesn't do this yet).
4. **Update CLAUDE.md certainty table** — add checks for each spec item at score 0.

**Artifacts:**
- `tests/spec-{batch}.md` — the spec for this batch (what to build, expected behavior)
- Updated test scripts with new assertions
- Updated `findings.md` with new certainty checks

**Exit criteria:**
- Spec is written and reviewable
- Test assertions exist that will validate the spec
- Running `make test` shows the new tests failing (expected — not implemented yet)

**Constraints:**
- Do NOT implement during spec — define the contract first
- Each spec item must have at least one test assertion
- Spec items must be small enough to implement and test independently

### Stage 3: BUILD & TEST (inner loop)

**Purpose:** Implement the spec, one item at a time, validating with tests after each change.

**What you do:**
1. **Pick one spec item** — smallest, most foundational first
2. **Implement** — make the minimal code change in the service(s)
3. **Run `make test`** — check if the assertion passes
4. **If fail** — diagnose, fix, re-run. Seconds per cycle.
5. **If pass** — update `findings.md` certainty score, move to next item
6. **Capture evidence** — save request/response pairs to `data/rendered/` for regression

**Repeat** until all spec items in the batch pass.

**Exit to RESEARCH:**
- During implementation, you discover the spec is wrong or incomplete
- You find a new gap not covered by research
- A user reports a new issue
- Back to Stage 1 with specific questions

**Exit to GATE:**
- All spec items pass
- All certainty scores >= 80
- Docs updated

**Constraints:**
- Do NOT skip tests — every change must be validated
- Do NOT implement items not in the spec — if you want to add something, update the spec first
- Do NOT batch multiple changes before testing — one item at a time
- Capture request/response pairs for each passing test (regression data)

### Makefile targets for spec-driven features

| Stage | Targets | What they do |
|-------|---------|-------------|
| **Env setup** | `make env-check` | Verify `.env` exists, show config |
| | `make smoke` | One request end-to-end — proves infra works |
| **Spec validation** | `make test` | Run all test assertions against live services |
| | `make test-{category}` | Run one category of tests |
| **Evidence** | `make capture` | Save request/response pairs to `data/rendered/` |

### Data stages for spec-driven features

| Stage | Contents | Example |
|-------|----------|---------|
| **raw** | Not used (no collection run) | — |
| **core** | Not used (no pipeline) | — |
| **rendered** | Captured request/response pairs, webhook payloads | `data/rendered/webhook-payloads.jsonl`, `data/rendered/mcp-tool-responses/` |

### Spec-driven feature lifecycle

1. **Define** — README, CLAUDE.md (already done for webhooks, MCP, token-scoping)
2. **Research** — Audit, competitive analysis, gap identification → `RESEARCH.md`
3. **Spec** — Turn gaps into testable contracts → `tests/spec-{batch}.md`, test assertions
4. **Build & Test** — Implement spec items, validate with tests → update `findings.md`
5. **Gate** — All certainty scores >= 80, docs updated
