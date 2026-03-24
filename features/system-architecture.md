# Self-Improvement System Architecture

## The Big Picture

```
                         ┌─────────────────────────────────┐
                         │           INPUTS                 │
                         │                                  │
                         │  Market ─── competitors          │
                         │            technologies          │
                         │            narratives            │
                         │                                  │
                         │  Best Practice ── agent patterns │
                         │                  testing methods │
                         │                  industry std    │
                         │                                  │
                         │  Users ──── GitHub issues        │
                         │             Discord              │
                         │             usage patterns       │
                         └──────────────┬──────────────────┘
                                        │
                                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│                     FEATURES ORCHESTRATOR                             │
│                                                                       │
│  Reads all 13 features' findings.md                                   │
│  Watches market, competitors, user feedback                           │
│  Decides highest-impact work                                          │
│  Spawns feature teams on self-improvement branches                    │
│  Cross-pollinates findings between features                           │
│  Researches how to improve the system itself                          │
│                                                                       │
└───────────┬──────────────┬──────────────┬─────────────────────────────┘
            │              │              │
            ▼              ▼              ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ Feature Team │ │ Feature Team │ │ Feature Team │    (spawned on demand)
   │              │ │              │ │              │
   │ researcher   │ │ researcher   │ │ researcher   │
   │ implementer  │ │ implementer  │ │ implementer  │
   │ tester       │ │ tester       │ │ tester       │
   │              │ │              │ │              │
   │ works on:    │ │ works on:    │ │ works on:    │
   │ feature/     │ │ feature/     │ │ feature/     │
   │ self-improv- │ │ self-improv- │ │ self-improv- │
   │ ement-*      │ │ ement-*      │ │ ement-*      │
   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │                │                │
          │  confidence    │  confidence    │  confidence
          │  gate ≥ 80     │  gate ≥ 80     │  gate ≥ 80
          │                │                │
          ▼                ▼                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│               feature/agentic-runtime  (working branch)               │
│                                                                       │
│  features/          ← self-improving manifests                        │
│  services/          ← actual code                                     │
│  blog/              ← narratives, competitive research                │
│  .claude/agents/    ← orchestrator, researcher definitions            │
│                                                                       │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
                                │  quality gates:
                                │  - audit (all changes reviewed)
                                │  - security (no secrets, no injection)
                                │  - docs (README ↔ code consistency)
                                │  - confidence (all features ≥ 80)
                                │  - blog stripped / cleaned
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│                        main  (production)                             │
│                                                                       │
│  features/          ← engineering docs, transparent status            │
│  services/          ← production code                                 │
│  docs/              ← user-facing documentation                       │
│  NO blog/           ← stripped by pre-merge gate                      │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

## The Three Loops

```
Loop 1: Market → Features                              (days/weeks)
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║  competitors ──→ orchestrator ──→ new feature         ──→ repo  ║
║  technologies    reads market     or reprioritize                ║
║  user feedback   decides impact   updates README                 ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝


Loop 2: Features → Stack                               (hours/days)
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║  findings.md ──→ feature team ──→ code change    ──→ services/  ║
║  (lowest score)  researcher       in services/       deploy/    ║
║                  implementer      deploy/ docs/      docs/      ║
║                  tester                                          ║
║                                                                  ║
║  Each cycle:                                                     ║
║  1. researcher forms hypothesis (reads dead ends first)          ║
║  2. competing hypotheses debate                                  ║
║  3. implementer fixes (minimal change)                           ║
║  4. tester validates (independent context)                       ║
║  5. findings.md updated with new scores                          ║
║  6. if score improved → PR. if not → back to 1.                 ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝


Loop 3: Quality Gates                                  (minutes, automated)
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║  pre-commit:   audit changes, security scan                      ║
║  pre-PR:       confidence ≥ 80, docs gate, no regressions       ║
║  pre-release:  all shipping features have evidence               ║
║                blog stripped, marketing cleaned                   ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

## Feature Team Workflow (Detail)

```
                    Lead (orchestrator)
                    reads findings.md across all features
                    picks: "gmeet speaker locking, score 40"
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Researcher    Researcher-2   Tester
         (hypothesis A) (hypothesis B) (waits)
              │            │
              │  debate via messages
              │  "I think buffer growth shifts
              │   Whisper boundaries"
              │            │
              │  "No, I think it's submitInterval
              │   timing — here's evidence..."
              │            │
              └─────┬──────┘
                    │ winner
                    ▼
              Implementer
              (reads dead ends first)
              (makes minimal fix)
              (describes change to tester)
                    │
                    ▼
               Tester
               (fresh context — no implementation bias)
               (runs E2E test)
               (updates findings.md)
                    │
              ┌─────┴─────┐
              ▼            ▼
         Score improved   Score didn't improve
         → PR to          → back to researchers
           agentic-runtime   (wrong hypothesis)
```

## What Runs Where

```
┌─────────────────────────────────────────────────────────────┐
│                    Vexa Infrastructure                        │
│                    (we are the first customer)                │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  Agent Container  │  │  Agent Container  │               │
│  │  (orchestrator)   │  │  (researcher)     │               │
│  │                   │  │                   │               │
│  │  workspace:       │  │  workspace:       │               │
│  │  orchestrator-    │  │  competitive-     │               │
│  │  log.md           │  │  intelligence/    │               │
│  │  priority-map     │  │  user-feedback/   │               │
│  │                   │  │  tech-landscape/  │               │
│  └──────────────────┘  └──────────────────┘                │
│                                                              │
│  ┌──────────────────┐                                       │
│  │  Scheduler        │                                      │
│  │                   │                                      │
│  │  weekly: market   │                                      │
│  │    research scan  │                                      │
│  │  daily: user      │                                      │
│  │    feedback check │                                      │
│  │  on-demand:       │                                      │
│  │    feature teams  │                                      │
│  └──────────────────┘                                       │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │  Claude Code Agent Teams                  │              │
│  │  (feature improvement sessions)           │              │
│  │                                           │              │
│  │  Each on feature/self-improvement-* branch│              │
│  │  Each with isolation: worktree            │              │
│  │  researcher + implementer + tester        │              │
│  └──────────────────────────────────────────┘               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## The Artifact Flow

```
findings.md          feature-log.md          orchestrator-log.md
(what's true now)    (what was tried)        (system-level decisions)
     │                    │                        │
     │  agent reads       │  agent reads           │  orchestrator reads
     │  before acting     │  to avoid dead ends    │  before spawning teams
     │                    │                        │
     ▼                    ▼                        ▼
┌─────────┐        ┌──────────┐             ┌──────────┐
│ Agent   │        │ Agent    │             │ Orch.    │
│ decides │        │ avoids   │             │ picks    │
│ what to │        │ repeating│             │ highest  │
│ fix     │        │ failures │             │ impact   │
└────┬────┘        └────┬─────┘             └────┬─────┘
     │                  │                        │
     │  after acting    │  after acting          │  after team finishes
     │                  │                        │
     ▼                  ▼                        ▼
findings.md          feature-log.md          orchestrator-log.md
(updated scores)     (new entries)           (what happened, what's next)

     THE LOOP CLOSES — next agent reads updated artifacts
```
