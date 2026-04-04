# Mission: CALM Knowledge Workspace

Focus: public repo (`Vexa-ai/calm-traderx-knowledge`) + CLAUDE.md + Telegram bot
Problem: The FINOS CALM community has rich public data (GitHub, docs, talks) but no structured knowledge layer. Nobody captures project activity in a queryable form.
Target: A public repo that IS a Vexa workspace — auto-updated daily by a regular Vexa agent, serving as the upstream for end users who clone it and interact via a dedicated Telegram bot.
Stop-when: MVP5 complete OR hard blocker identified with diagnosis

---

## Relationship to Vexa

**Vexa is infrastructure. This project is an application. Vexa knows nothing about CALM or FINOS.**

To Vexa, this project is just a user_id (`calm-traderx`) with a workspace, some scheduled jobs, and per-user env vars. No different from any other user. Everything CALM-specific lives in this repo's CLAUDE.md.

**Three layers, but only one matters to Vexa:**

```
1. Vexa platform (infra)
   Generic: containers, workspaces, scheduler, per-user env vars, git clone init.
   See: conductor/missions/260401-workspace-lifecycle.md
   Knows nothing about CALM.

2. FINOS-CALM project (this mission) — user_id: "calm-traderx"
   A regular Vexa user. Its CLAUDE.md teaches the agent about CALM/TraderX.
   Scheduler jobs fire [scheduled:github-sync] etc → agent does the work.
   Agent pushes to GitHub (GITHUB_TOKEN in per-user env vars).
   The public repo is the workspace committed to git.

3. FINOS-CALM end users — regular Vexa users
   Same as any Vexa user. Their workspace is cloned from this project's public repo
   (Vexa's generic git clone init feature). The CLAUDE.md in the cloned repo teaches
   their agent to git pull upstream for updates. The "rebase" is an agentic workflow —
   the agent follows CLAUDE.md instructions, Vexa doesn't know about it.
   
   Entry point: a CALM-specific Telegram bot (not Vexa's generic bot) that routes
   users to Vexa with the right workspace config.
```

**To Vexa, layers 2 and 3 are identical — regular users with workspaces.**

### What this project provides (not Vexa's business)

- `.claude/CLAUDE.md` — CALM knowledge, entity formats, sync handlers, git push/pull instructions, upstream rebase logic
- `GITHUB_TOKEN` — write access to the public repo (stored as per-user env var for `calm-traderx`)
- Scheduler job registrations — curl commands to register cron jobs
- CALM-specific Telegram bot — entry point for end users, configures their workspace to clone from this repo

### What this project depends on from Vexa (generic platform features)

- `POST /internal/chat` — scheduler triggers agent
- Workspace persistence — sync_down on container start, sync_up on save
- Git clone init — end users get workspace from this repo on first use
- Per-user env vars — GITHUB_TOKEN injected into calm-traderx container
- Per-user workspace config — git_repo_url set for end users

---

## System Design Constraints

1. **This project is a regular Vexa user.** No platform modifications for CALM. If you're editing files under `services/agent-api/` or `services/runtime-api/` for this mission, you're in the wrong repo. All CALM-specific logic lives in the workspace CLAUDE.md and the Telegram bot.
2. **CLAUDE.md is the only brain.** Every application behavior — GitHub sync, CALM generation, entity extraction, upstream pull, git push — is instructed by CLAUDE.md. The agent follows instructions. No application-specific code in the platform.
3. **The agent is self-configuring.** Bootstrap message triggers the agent to register its own scheduler jobs, crawl sources, and populate the workspace. No operator scripts to register jobs.
4. **Public data only.** No FINOS meeting transcripts without explicit permission. If a data source requires authentication or permission, don't use it.
5. **Upstream pull is agentic, not platform.** End users' agents do `git pull` from the public repo, instructed by CLAUDE.md. Vexa doesn't know about "base workspaces" or "rebasing."
6. **The Telegram bot is the only custom code.** ~50 lines. It sets workspace config and routes to Vexa. It does NOT contain CALM knowledge.

---

## Decisions Made

1. **Public repo under `Vexa-ai/`.** `Vexa-ai/calm-traderx-knowledge`. Propose FINOS adoption later.
2. **Agent does the work.** No manual content. The agent crawls sources and populates the workspace. We write the CLAUDE.md, register scheduler jobs, and let it run.
3. **Public data only.** No meeting transcripts without FINOS permission. GitHub API, RSS, public docs, YouTube transcripts only.
4. **CALM 1.2 spec.** Generated artifacts target `$schema: https://calm.finos.org/release/1.2/meta/calm.json`.
5. **GITHUB_TOKEN is this project's credential.** Stored as per-user env var for `calm-traderx`. CLAUDE.md tells agent to `git push` using `$GITHUB_TOKEN`. Vexa doesn't know what it is.
6. **Dedicated Telegram bot for end users.** Not Vexa's generic Telegram bot. A CALM-specific bot that sets workspace config (git_repo_url → this repo) for each new user, then routes to Vexa's agent API. Separate project at `/home/dima/dev/calm-telegram-bot/`, NOT inside Vexa. This is the only custom code beyond the workspace CLAUDE.md.
7. **Upstream pull is agentic.** End users' CLAUDE.md says "git pull origin main on each session." The agent handles merge logic. Vexa provides git clone init, agent handles everything after.

---

## Data Sources (public only)

| Source | Cadence | Method |
|--------|---------|--------|
| `finos/architecture-as-code` commits/PRs/issues/releases | Daily | GitHub API (5000/hr with token) |
| `finos/traderX` commits/PRs/issues | Daily | GitHub API |
| FINOS blog RSS | Daily | `curl https://www.finos.org/blog/rss.xml` |
| calm.finos.org docs | Weekly | curl public pages |
| CALM YouTube talks (6 public) | One-time + new | YouTube transcript API |
| TraderX source code | Weekly | Clone + analyze (public repo) |

**Future (with permission):** FINOS office hours transcripts via Vexa bot attendance.

---

## MVP0: Repo + CLAUDE.md + Agent Bootstraps Content

**Goal:** Create the public repo. Write the CLAUDE.md. Agent bootstraps content via API — no manual authoring.

**What we build:**
- Public repo `Vexa-ai/calm-traderx-knowledge`
- `.claude/CLAUDE.md` — CALM ecosystem knowledge, entity formats, `[scheduled:*]` handlers, CALM JSON generation, upstream pull instructions for end users
- Bootstrap via `POST /internal/chat {user_id: "calm-traderx", message: "[bootstrap]"}` — agent crawls TraderX and architecture-as-code repos, populates knowledge/, generates CALM JSON

### DoD — MVP0

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 0.1 | Public repo exists with workspace structure and CLAUDE.md | 10 | 10 | `gh repo view Vexa-ai/calm-traderx-knowledge` succeeds. CLAUDE.md has sections for scheduled tasks, entity formats, CALM generation, upstream pull instructions. |
| 0.2 | Agent bootstraps knowledge via API — not manually authored | 25 | 10 | `POST /internal/chat` with bootstrap message. Files appear in `knowledge/entities/`. Git log shows agent commit, not human. |
| 0.3 | TraderX services extracted (at least 5) | 15 | 40 | Files in `knowledge/entities/services/` match actual TraderX code. |
| 0.4 | Contributors and projects extracted from GitHub data | 10 | 70 | Entity files in `contacts/` and `projects/`. Sourced from API, not hardcoded. |
| 0.5 | `calm/traderx-architecture.json` — valid CALM 1.2 | 30 | 30 | `$schema` set. Nodes have required fields. Relationships reference existing nodes. At least 1 flow. |
| 0.6 | README explains concept, setup, how end users connect | 10 | 85 | README exists with architecture, setup instructions, Telegram bot info. |

**Ceilings:** 0.1/0.2 fail → cap 10. 0.5 fails → cap 30. 0.4 fails → cap 70.

---

## MVP1: Scheduler — Daily Auto-Updates

**Goal:** Scheduler fires daily. Agent crawls sources, updates knowledge, pushes to GitHub. Workspace persists across container restarts.

**Depends on:** MVP0 + workspace-lifecycle mission (sync_down, /internal/chat)

**What we build:**
- Register cron jobs via `POST /scheduler/jobs` targeting `/internal/chat`
- CLAUDE.md `[scheduled:github-sync]` and `[scheduled:rss-sync]` handlers
- Agent pushes to GitHub at end of each sync (`git push` from bash, per CLAUDE.md)

### DoD — MVP1

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 1.1 | Scheduler jobs registered | 5 | 5 | `GET /scheduler/jobs?source=calm-traderx` returns jobs. |
| 1.2 | GitHub sync fires → agent updates workspace with real data | 25 | 15 | Set `execute_at` now+30s. After: new files in knowledge/ with real GitHub commit messages and issue titles. |
| 1.3 | RSS sync fires → streams/ updated | 10 | 80 | `streams/` has file with actual FINOS blog items. |
| 1.4 | Incremental sync — no duplicates on second run | 15 | 45 | Two syncs. Second adds only new activity. `.state.json` advances. |
| 1.5 | Workspace survives container restart | 30 | 0 | Kill container. Next sync fires. Workspace restored. Prior content still there. |
| 1.6 | Agent pushes to GitHub after sync | 15 | 20 | `git log` on `Vexa-ai/calm-traderx-knowledge` shows agent commit matching sync. |

**Ceilings:** 1.5 fails → cap 0. 1.1 fails → cap 5. 1.2 fails → cap 15. 1.6 fails → cap 20.

---

## MVP2: CALM Generation + Living Public Repo

**Goal:** Weekly CALM artifact regeneration. Public repo shows knowledge evolving over days. This is the deliverable — a repo with daily agent commits showing structured knowledge accumulating.

**Depends on:** MVP1

### DoD — MVP2

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 2.1 | CALM regeneration updates calm/ from knowledge/ | 25 | 20 | After calm-generate job: nodes match current `knowledge/entities/services/`. |
| 2.2 | CALM JSON valid against 1.2 spec | 25 | 25 | Required fields present. Node refs valid. Relationship-types correct. |
| 2.3 | Public repo shows 3+ days of agent commits | 25 | 15 | `git log` shows commits on 3+ distinct days with real content diffs. |
| 2.4 | New entities from sync appear in CALM output | 15 | 40 | Add service entity via sync. Run calm-generate. New node in CALM JSON. |
| 2.5 | Workspace audit identifies stale content | 10 | 80 | Audit job fires. Agent writes findings to workspace. |

**Ceilings:** 2.3 fails → cap 15 (repo IS the deliverable). 2.1 fails → cap 20. 2.2 fails → cap 25.

---

## MVP3: End User Access via Telegram Bot

**Goal:** FINOS community members interact with the knowledge via a dedicated CALM Telegram bot. Each user gets a workspace cloned from the public repo. Their agent pulls upstream updates and answers from the knowledge base.

**Depends on:** MVP2 + workspace-lifecycle mission (git clone init, per-user env vars)

**What we build:**
- **CALM Telegram bot** — a thin bot (separate from Vexa's generic Telegram bot) that:
  - On first message from a user: sets `workspace:config:{user_id}` with `git_repo_url` pointing to `Vexa-ai/calm-traderx-knowledge`, then routes to Vexa's `POST /api/chat`
  - On subsequent messages: routes directly to `POST /api/chat`
  - This is the ONLY custom code beyond CLAUDE.md
- CLAUDE.md includes upstream pull instructions: "on each session, `git pull origin main` to get latest base knowledge. Preserve your soul.md and notes.md."

### DoD — MVP3

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 3.1 | New Telegram user gets workspace from public repo | 20 | 0 | First message → workspace cloned from repo. Agent has CLAUDE.md and knowledge/. |
| 3.2 | Agent answers from knowledge — not hallucinated | 30 | 0 | "What services does TraderX have?" → answer matches knowledge/entities/services/. |
| 3.3 | User context persists across sessions | 15 | 35 | User says interest. Container dies. Next session: agent remembers (reads soul.md). |
| 3.4 | Upstream updates reach user | 15 | 25 | Base gets new entity from sync. User asks about it. Agent has it (git pull ran). |
| 3.5 | Two users isolated | 10 | 50 | User A and B have different soul.md. Both share base knowledge/. |
| 3.6 | CALM Telegram bot routes correctly | 10 | 10 | Bot sets workspace config and routes to agent API. Errors if Vexa is unreachable. |

**Ceilings:** 3.1/3.2 fail → cap 0. 3.6 fails → cap 10. 3.4 fails → cap 25.

**G11 applies:** 3.2 is the critical path.

---

## MVP4: Production — Week of Unattended Operation

**Goal:** System runs unattended for a week. Public repo shows daily commits. Telegram bot serves users. End-to-end data flow works.

**Depends on:** MVP0-MVP3

### DoD — MVP4

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 4.1 | Public repo shows 7+ days of daily commits | 25 | 10 | `git log` shows 7+ distinct days of agent commits with real content. |
| 4.2 | CALM artifacts reflect current state | 15 | 40 | CALM JSON includes entities from the past week's syncs. |
| 4.3 | Failed sync recovers | 15 | 50 | Simulate failure. Next run succeeds. Workspace not corrupted. |
| 4.4 | 3+ Telegram users served with grounded answers | 20 | 25 | 3 accounts interact. Knowledge-grounded answers. Personal context isolated. |
| 4.5 | End-to-end: new commit on finos repo → user sees it via Telegram | 25 | 15 | Real commit lands on finos/architecture-as-code. Next sync picks it up. User asks → agent knows. Under 24 hours. |

**Ceilings:** 4.1 fails → cap 10. 4.5 fails → cap 15. 4.4 fails → cap 25.

---

## Implementation Notes

### Repo structure: `Vexa-ai/calm-traderx-knowledge`

```
calm-traderx-knowledge/
├── .claude/CLAUDE.md              # Agent brain — everything CALM-specific
├── knowledge/
│   ├── entities/
│   │   ├── contacts/              # People — from GitHub API
│   │   ├── projects/              # CALM, TraderX, CalmHub, etc.
│   │   └── services/              # TraderX microservices
│   ├── meetings/                  # Future (with permission)
│   └── action-items/              # From GitHub issues
├── calm/
│   ├── traderx-architecture.json  # Valid CALM 1.2
│   └── reports/
│       └── architecture-summary.md
├── streams/                       # Active topics
├── timeline.md
├── notes.md
├── soul.md                        # "You serve the FINOS CALM community"
├── .state.json                    # Sync timestamps
├── .gitignore
└── README.md
```

### Scheduler jobs (agent registers itself)

The agent registers its own jobs during `[bootstrap]` via the `vexa schedule` CLI (already in PATH inside agent containers). No operator curl commands needed.

CLAUDE.md instructs the agent:
```markdown
## On [bootstrap]
Register your scheduled jobs:
  vexa schedule --cron "0 8 * * *" chat "[scheduled:github-sync]"
  vexa schedule --cron "0 9 * * *" chat "[scheduled:rss-sync]"
  vexa schedule --cron "0 10 * * 5" chat "[scheduled:calm-generate]"
  vexa schedule --cron "0 8 */3 * *" chat "[scheduled:audit]"
```

The `vexa schedule` CLI wraps `POST /scheduler/jobs` on the runtime API. The agent is self-configuring.

### CALM Telegram bot (the only custom code)

A thin bot that routes FINOS users to Vexa. On first message:

```python
# Pseudocode — the CALM Telegram bot
async def on_message(telegram_user_id, text):
    vexa_user_id = f"calm-tg-{telegram_user_id}"
    
    # First time? Configure workspace to clone from CALM repo
    if not await workspace_config_exists(vexa_user_id):
        await set_workspace_config(vexa_user_id, {
            "git_repo_url": "https://github.com/Vexa-ai/calm-traderx-knowledge.git",
            "git_branch": "main"
        })
    
    # Route to Vexa agent API
    response = await post("http://agent-api:8100/api/chat", {
        "user_id": vexa_user_id,
        "message": text
    })
    return response
```

This is ~50 lines of code. It does NOT contain CALM knowledge — that's in the workspace CLAUDE.md.

### How end users get upstream updates

The CLAUDE.md in the public repo teaches the agent:

```markdown
## On each session start
If this workspace was cloned from a repo (check: `git remote -v` shows origin):
1. git fetch origin main
2. git merge origin/main --no-edit  
3. If conflicts: keep YOUR soul.md, notes.md, user.json. Accept upstream for knowledge/ and calm/.
4. vexa workspace save
```

The agent follows these instructions. Vexa doesn't know about upstream repos or rebasing.

### Setup (one-time, at deploy)

How the operator configures this application on Vexa is a Vexa platform concern — this mission doesn't prescribe it. Vexa provides some mechanism (admin API, config file, env vars) to set per-user env vars and workspace config. This project needs:

1. **Create the repo** — `gh repo create Vexa-ai/calm-traderx-knowledge --public`. Repo exists first, empty.
2. **Per-user env var** for `calm-traderx`: `GITHUB_TOKEN=ghp_...`
3. **Workspace config** for `calm-traderx`: `git_repo_url=https://github.com/Vexa-ai/calm-traderx-knowledge.git`, `git_branch=main`
4. **Bootstrap the agent** — one `POST /internal/chat {user_id: "calm-traderx", message: "[bootstrap]"}`. Agent registers its own scheduler jobs, crawls sources, populates workspace, pushes to repo. After this, end users can clone.
5. **CALM Telegram bot** deployed as separate project (`/home/dima/dev/calm-telegram-bot/`), connects to Vexa over the network

### Risk register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Agent doesn't have git credentials for push | Blocks MVP1 | GITHUB_TOKEN set as per-user env var for calm-traderx |
| Agent doesn't follow [scheduled:*] reliably | Blocks MVP1 | Test with one simple task first. Very explicit CLAUDE.md instructions. |
| CALM JSON hallucination | Blocks MVP2 | Full CALM 1.2 examples in CLAUDE.md. Agent validates after generation. |
| git pull conflicts in user workspaces | Affects MVP3 | CLAUDE.md merge rules: upstream wins for knowledge/, user wins for soul.md. |
| OSFF Toronto April 14 (13 days) | Time pressure | MVP0-MVP1 is minimum demo. |

### CALM 1.2 quick reference

- `$schema`: `https://calm.finos.org/release/1.2/meta/calm.json`
- `nodes[]`: `unique-id`, `node-type`, `name`, `description`
- `relationships[]`: `unique-id`, `relationship-type` (one of: connects/interacts/composed-of/deployed-in)
- `flows[]`: `unique-id`, `name`, `description`, `transitions[]`
- TraderX benchmark (Jim Thompson PR #333): 12 nodes, 17 relationships, 7 flows

### Data permission status

| Source | Permission |
|--------|-----------|
| GitHub API (public repos) | **Yes** |
| FINOS blog RSS | **Yes** |
| calm.finos.org docs | **Yes** |
| YouTube transcripts | **Yes** |
| FINOS office hours transcripts | **Needs permission** |
| FINOS Slack | **Needs access** |
