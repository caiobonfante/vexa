# Mission: API Service READMEs — Presentation Narrative

Focus: documentation, all three core API services
Problem: The main README now tells the presentation narrative (code agents work → meetings are the next domain → three APIs), but the individual service READMEs are internally-focused audit documents. A developer clicking through from the main README lands on production readiness scores and known bugs instead of understanding what the API does, why it exists in the architecture, and how to use it.
Target: Each API service README explains its role in the Vexa platform story, provides clear API examples, and connects to the other two APIs — while preserving the existing production readiness and operational detail as a later section.
Stop-when: A developer reading main README → Meeting API README → Agent API README → Runtime API README gets a coherent narrative that matches the presentation arc. Each README has: narrative intro, curl examples, endpoint table, architecture position, and production readiness (existing content preserved).
Constraint: Don't delete existing content — restructure it. Production readiness sections stay. No code changes.

---

## Context: Why This Mission Exists

The main README was restructured (2026-04-01) to follow the presentation narrative:

1. **Coding agents work** — because code is connected, concise, executable
2. **Meetings are the next domain** — same agent loop, different data
3. **Hard problems** — security (agent isolation) and scalability (one machine per agent)
4. **Three APIs** — Meeting API (data), Agent API (intelligence), Runtime API (infrastructure)

The main README links to each service README. When a developer clicks through, they should continue the story — not hit an internal audit document.

### Current State

| Service | README lines | Opens with | Problem |
|---------|-------------|-----------|---------|
| meeting-api | 131 | "Why: Every meeting platform has its own join flow..." | Jumps straight to operational detail. No connection to the bigger picture. No "here's what you can build" section. Thin API examples (just endpoint list, no curl). |
| agent-api | 244 | "Why: Running an LLM agent inside a container is the easy part..." | Good "why" but doesn't connect to meetings or knowledge extraction. Good API examples. Missing the knowledge/workspace narrative from the presentation. |
| runtime-api | 486 | "Why: You need to spawn containers on demand..." | Excellent standalone README but positions itself as a generic container manager. Missing the Vexa platform story — this is the infrastructure layer that makes Meeting API and Agent API scalable. |

### What Good Looks Like

Each README should follow this structure:

```
# {Service Name}

## {One-line positioning in the Vexa platform}

Brief paragraph connecting to the main README narrative.
Link back to the main README for the full picture.

## What You Can Build

Table or list of concrete use cases with this API alone.

## Quick Start

3-5 curl examples showing the core workflow.

## API Reference

Endpoint table (existing content).

## Architecture

Where this fits in the platform. Diagram showing its relationship
to the other two APIs.

## Environment Variables

(existing content)

## How It Works

Data flow, module map — the operational detail.
(existing content, reorganized)

## Production Readiness

(existing content, preserved as-is)
```

---

## Phase 1: Meeting API README (highest priority)

**Goal:** Meeting API README becomes the best API README in the repo. It's the first service a developer will click into from the main README. It needs to sell the platform.

### Tasks

- [ ] Add narrative intro connecting to main README: "Meeting API is the data layer of the Vexa platform. It gives AI agents real-time access to conversations."
- [ ] Add "What You Can Build" section: self-hosted Otter replacement, meeting data pipeline, meeting bot API (like Recall.ai), AI meeting assistant
- [ ] Add curl examples for the core workflow: POST /bots → GET /transcripts → POST /speak → DELETE /bots (match the examples from the main README but with more detail — request AND response bodies)
- [ ] Add platform support table: Google Meet (status), Teams (status), Zoom (status)
- [ ] Add architecture diagram showing Meeting API's position: Client → Gateway → Meeting API → Runtime API → Bot Container → Meeting Platform → Transcription
- [ ] Add "How Meeting API connects to Agent API" section: agents schedule bots, receive transcripts, extract knowledge
- [ ] Restructure existing content: move production readiness to bottom, keep all existing detail
- [ ] Add WebSocket streaming example (or link to docs)

### DoD

| # | Item | Weight | Max if FAIL | Min if PASS |
|---|------|--------|-------------|-------------|
| 1 | Narrative intro links to main README and explains platform position | 15% | 30 | 65 |
| 2 | "What You Can Build" section with 4+ use cases | 10% | 50 | 60 |
| 3 | curl examples with request AND response bodies for core workflow | 20% | 25 | 55 |
| 4 | Architecture diagram showing relationship to Runtime API and Agent API | 15% | 35 | 60 |
| 5 | Existing production readiness content preserved (not deleted) | 15% | 0 | 70 |
| 6 | Platform support table with honest status | 10% | 50 | 65 |
| 7 | Reading main README → Meeting API README feels like a coherent continuation | 15% | 20 | 60 |

---

## Phase 2: Agent API README

**Goal:** Agent API README tells the knowledge-extraction story from the presentation. It's not just "chat with an agent" — it's "agents that turn meetings into structured knowledge."

### Tasks

- [ ] Add narrative intro: "Agent API is the intelligence layer. It spawns sandboxed AI agents that process meeting data into structured knowledge."
- [ ] Add knowledge workspace section: show the file structure, explain entity extraction, wiki-links (from presentation examples)
- [ ] Add "Combining Meeting API + Agent API" section: schedule bot → receive transcript → extract entities → update knowledge graph
- [ ] Add use cases: knowledge extraction, post-meeting automation, proactive meeting agents, personal AI assistant
- [ ] Ensure curl examples cover: chat, workspace read, session management
- [ ] Add architecture diagram showing Agent API's position between user/frontend and Runtime API, with Meeting API as data source
- [ ] Restructure: narrative first, operational detail second, production readiness at bottom

### DoD

| # | Item | Weight | Max if FAIL | Min if PASS |
|---|------|--------|-------------|-------------|
| 1 | Narrative intro connects to meetings and knowledge extraction | 15% | 30 | 65 |
| 2 | Knowledge workspace section with file structure and entity examples | 20% | 25 | 55 |
| 3 | "Combining APIs" section showing Meeting + Agent workflow | 15% | 35 | 60 |
| 4 | Architecture diagram showing platform position | 15% | 35 | 60 |
| 5 | Existing production readiness preserved | 15% | 0 | 70 |
| 6 | Reading main README → Agent API README is coherent | 20% | 20 | 55 |

---

## Phase 3: Runtime API README

**Goal:** Runtime API README positions itself as the infrastructure layer that makes the other two APIs scalable. Not just "generic container manager" but "the reason Vexa scales from laptop to cluster."

### Tasks

- [ ] Add narrative intro: "Runtime API is the infrastructure layer. It's why Meeting API and Agent API can scale from a laptop to a Kubernetes cluster without code changes."
- [ ] Add "How the Other APIs Use Runtime API" section: Meeting API spawns bot containers, Agent API spawns agent/browser containers
- [ ] Add scaling story from presentation: Process (laptop) → Docker (self-hosted) → Kubernetes (enterprise)
- [ ] Keep the excellent comparison table (vs Fly Machines, K8s Jobs, etc.)
- [ ] Keep the detailed backend resource limits table (this is a differentiator)
- [ ] Restructure: platform narrative first, standalone use cases second, operational detail third
- [ ] Add 1-2 examples showing how Meeting API and Agent API call Runtime API internally

### DoD

| # | Item | Weight | Max if FAIL | Min if PASS |
|---|------|--------|-------------|-------------|
| 1 | Narrative intro connects to platform scaling story | 15% | 35 | 65 |
| 2 | "How Other APIs Use Runtime API" section | 20% | 25 | 55 |
| 3 | Scaling story: Process → Docker → K8s | 10% | 50 | 65 |
| 4 | Comparison table and resource limits table preserved | 15% | 0 | 70 |
| 5 | Existing production readiness preserved | 15% | 0 | 70 |
| 6 | Reading main README → Runtime API README is coherent | 25% | 20 | 55 |

---

## Phase 4: Cross-linking and Consistency

**Goal:** All three READMEs link to each other and back to the main README. Consistent structure, consistent terminology.

### Tasks

- [ ] Verify all three READMEs use the same terminology: "data layer" (Meeting), "intelligence layer" (Agent), "infrastructure layer" (Runtime)
- [ ] Verify all three link back to main README
- [ ] Verify all three link to each other where relevant
- [ ] Verify main README links to services/meeting-api, services/agent-api, services/runtime-api (not packages/)
- [ ] Read all four READMEs in sequence — does the narrative hold?

### DoD

| # | Item | Weight | Max if FAIL | Min if PASS |
|---|------|--------|-------------|-------------|
| 1 | Consistent terminology across all READMEs | 25% | 30 | 65 |
| 2 | Cross-links between all three + main README | 25% | 30 | 65 |
| 3 | Main README architecture table links to correct paths | 25% | 20 | 60 |
| 4 | Sequential reading (main → meeting → agent → runtime) is coherent | 25% | 20 | 55 |
