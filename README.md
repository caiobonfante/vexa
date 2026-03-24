<p align="center" style="margin-bottom: 0.75em;">
  <img src="assets/logodark.svg" alt="Vexa Logo" width="56"/>
</p>

<h1 align="center" style="margin-top: 0.25em; margin-bottom: 0.5em; font-size: 2.5em; font-weight: 700; letter-spacing: -0.02em;">Vexa</h1>

<p align="center" style="font-size: 1.75em; margin-top: 0.5em; margin-bottom: 0.75em; font-weight: 700; line-height: 1.3; letter-spacing: -0.01em;">
  <strong>Open-source meeting transcription API & agent runtime</strong>
</p>

<p align="center" style="font-size: 1em; color: #a0a0a0; margin-top: 0.5em; margin-bottom: 1.5em; letter-spacing: 0.01em;">
  meeting bots • real-time transcription • interactive agents • MCP server • self-hosted
</p>

<p align="center" style="margin: 1.5em 0; font-size: 1em;">
  <img height="24" src="assets/google-meet.svg" alt="Google Meet" style="vertical-align: middle; margin-right: 10px;"/> <strong style="font-size: 1em; font-weight: 600;">Google Meet</strong>
  &nbsp;&nbsp;&nbsp;&nbsp;•&nbsp;&nbsp;&nbsp;&nbsp;
  <img height="24" src="assets/microsoft-teams.svg" alt="Microsoft Teams" style="vertical-align: middle; margin-right: 10px;"/> <strong style="font-size: 1em; font-weight: 600;">Microsoft Teams</strong>
  &nbsp;&nbsp;&nbsp;&nbsp;•&nbsp;&nbsp;&nbsp;&nbsp;
  <img height="24" src="assets/icons8-zoom.svg" alt="Zoom" style="vertical-align: middle; margin-right: 10px;"/> <strong style="font-size: 1em; font-weight: 600;">Zoom</strong>
</p>

<p align="center" style="margin: 1.75em 0 1.25em 0;">
  <a href="https://github.com/Vexa-ai/vexa/stargazers"><img src="https://img.shields.io/github/stars/Vexa-ai/vexa?style=flat-square&color=yellow" alt="Stars"/></a>
  &nbsp;&nbsp;&nbsp;
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square" alt="License"/></a>
  &nbsp;&nbsp;&nbsp;
  <a href="https://discord.gg/Ga9duGkVz9"><img src="https://img.shields.io/badge/Discord-join-5865F2?style=flat-square&logo=discord&logoColor=white" alt="Discord"/></a>
</p>

<p align="center">
  <a href="#whats-new">What’s new</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="#agent-runtime">Agent Runtime</a> •
  <a href="#2-get-transcripts">API</a> •
  <a href="https://docs.vexa.ai">Docs</a> •
  <a href="#roadmap">Roadmap</a> •
  <a href="https://discord.gg/Ga9duGkVz9">Discord</a>
</p>

---

## What is Vexa?

**Vexa** is an open-source, self-hostable API for real-time meeting transcription — with an agent runtime built in. It automatically joins Google Meet, Microsoft Teams, and Zoom meetings, captures audio, provides real-time transcriptions, and lets AI agents actively participate in and act on meetings.

### At a glance

| Capability | What it means |
|---|---|
| **Meeting bots** | Automatically joins Google Meet, Microsoft Teams, and Zoom meetings |
| **Real-time transcription** | Sub-second transcript delivery during the call |
| **Interactive bots** | Make bots speak, send/read chat, share screen content, and set avatar in live meetings |
| **Agent runtime** | Ephemeral containers for AI agents — browser, agent, worker profiles. Zero cost when idle |
| **Post-meeting automation** | Meetings trigger action: summarize, create tickets, push to Slack/CRM — no human needed |
| **Proactive agents** | Scheduler + calendar integration: agents join meetings on schedule, act without being asked |
| **MCP server** | 17 tools for Claude/Cursor/Windsurf — join calls, read transcripts, speak in meetings |
| **Multilingual** | 100+ languages via Whisper (transcription + translation) |
| **Multi-tenant** | Users, scoped API tokens, isolated containers — deploy once, serve your team |
| **Self-hostable** | Run on your infra for complete data sovereignty |
| **Accessible anywhere** | Same agent via web dashboard, Telegram, meeting chat, or any chat client |

### Who it's for

| You are... | You want... |
|---|---|
| **Enterprises** | Self-hosted transcription with strict privacy — replace $17-20/seat SaaS |
| **AI product builders** | Give your agents meeting superpowers via MCP or API |
| **SaaS developers** | Multi-tenant meeting API to embed in your product |
| **Platform teams** | Deploy one service for your org — isolated agents, scoped tokens, no per-user infra |
| **Automation builders** | Post-meeting pipelines: meeting ends → agent summarizes → Slack/CRM/Linear |

---

## Build on Top. In Hours, Not Months

**Build powerful meeting assistants (like Otter.ai, Fireflies.ai, Fathom) for your startup, internal use, or custom integrations.** Or go further — build AI agents that don't just transcribe, but actively participate in and act on meetings.

The Vexa API provides powerful abstractions and a clear separation of concerns, enabling you to build sophisticated applications on top with a safe and enjoyable coding experience.

## 🛡️ Built for Data Sovereignty

Vexa is open-source and self-hostable — ideal for regulated industries and teams that cannot compromise on privacy. 

Modular architecture scales from edge devices to millions of users. You choose what to self-host and what to use as a service.

**You control everything:**

**1. Hosted service**
At [vexa.ai](https://vexa.ai) — get an API key and start sending bots. No infrastructure needed.
*<small style="color: #999;">Ready to integrate</small>*

<hr style="margin: 1.25em 0; border: none; border-top: 1px solid #333;">

**2. Self-host with Vexa transcription**
Run Vexa yourself, use vexa.ai for transcription — ready to go, no GPU needed.
*<small style="color: #999;">Control with minimal DevOps</small>*

<hr style="margin: 1.25em 0; border: none; border-top: 1px solid #333;">

**3. Fully self-host**
Run everything including your own GPU transcription service.
*<small style="color: #999;">Full data sovereignty for regulated industries</small>*


<a id="whats-new"></a>

## What's new

**Agent Runtime (preview)**
- **Ephemeral agent containers** — browser, agent, worker profiles with zero idle cost
- **Agent API** — agent sessions, Claude CLI streaming, workspace sync, scheduling
- **Scheduler** — cron, relative delays, `on_success`/`on_failure` container chaining
- **Remote browser** — VNC + CDP, persistent auth across sessions
- **Telegram bot** — interact with your agent from mobile
- **Dashboard agent chat** — talk to your agent from the web UI

**v0.9 (pre-release)**
- **Zoom:** initial Zoom Meeting SDK support (requires Zoom app setup/approval; see docs)
- **Recordings:** persist recording artifacts to S3-compatible storage (or local)
- **Post-meeting playback:** stream recordings via `/recordings/.../raw` with `Range` seeking (`206`) + `Content-Disposition: inline`
- **Delete semantics:** deleting a meeting also purges recording objects/artifacts (best-effort) before anonymizing the meeting
- **Interactive Bots API:** live controls for speak/chat/screen/avatar during active meetings
- **MCP server:** 17 tools for AI agents — join, transcribe, speak, chat, share screen

---

> See full release notes: https://github.com/Vexa-ai/vexa/releases

---

## Quickstart

### Option 1: Hosted (no deployment needed)

Get your API key at [vexa.ai/dashboard/api-keys](https://vexa.ai/dashboard/api-keys) and start sending bots immediately. No infrastructure needed.

### Option 2: Vexa Lite (recommended for self-hosting)

**Single Docker container. Easiest way to self-host Vexa.**

- **Self-hosted multiuser service** - Multiple users, API tokens, and team management
- **Single container** - Easy to deploy on any platform
- **No GPU required** - Transcription runs externally
- **Choose your frontend** - Pick from open-source user interfaces like [Vexa Dashboard](./services/dashboard)
- **Production-ready** - Stateless, scalable, serverless-friendly

Needs external Postgres + transcription service. Use Vexa transcription (sign up at [vexa.ai](https://vexa.ai) for a transcription API key — ready to go, no GPU needed), or self-host your own GPU transcription for full data sovereignty.

**Quick start:**
```bash
docker run -d \
  --name vexa \
  -p 8056:8056 \
  -e DATABASE_URL="postgresql://user:pass@host/vexa" \
  -e ADMIN_API_TOKEN="your-admin-token" \
  -e TRANSCRIBER_URL="https://transcription.service" \
  -e TRANSCRIBER_API_KEY="transcriber-token" \
  vexaai/vexa-lite:latest
```

**Deployment options:**
- **One-click platform deployments**: [vexa-lite-deploy repository](https://github.com/Vexa-ai/vexa-lite-deploy) (Fly.io ready, more platforms coming)
- **Complete setup guide**: [Vexa Lite Deployment Guide](https://docs.vexa.ai/vexa-lite-deployment)
- **Frontend options**: [Vexa Dashboard](./services/dashboard)

### Option 3: Docker Compose (development)

**Full stack deployment with all services. Perfect for development and testing.**

```bash
git clone https://github.com/Vexa-ai/vexa.git
cd vexa
make all
```

**What `make all` does:**
- Builds all Docker images
- Spins up all containers (API, bots, transcription services, database)
- Runs database migrations
- Starts a simple test to verify everything works

Full guide: [Deployment Guide](https://docs.vexa.ai/deployment)

### Option 4: Helm (production K8s)

For Kubernetes production deployments. See [deploy/helm/README.md](deploy/helm/README.md).

### Recording storage (local and cloud)

Recording supports local filesystem, MinIO, and cloud S3-compatible backends.
See [Recording Storage](https://docs.vexa.ai/recording-storage) for configuration details.

<a id="agent-runtime"></a>

## Agent Runtime

Vexa isn't just a meeting API — it's a runtime where AI agents natively understand meetings. No gluing together E2B sandboxes with Recall.ai webhooks. Meetings are a built-in primitive.

### What agents can do

| Capability | How |
|-----------|-----|
| **Join meetings** | `vexa meeting join --platform teams --url {url}` |
| **Transcribe live** | `vexa meeting transcript {id}` — streams segments in real-time |
| **Speak in meetings** | `vexa meeting speak --text "Here's the summary"` — TTS to meeting audio |
| **Read/write chat** | `vexa meeting chat --text "Action items..."` — interact via meeting chat |
| **Share screen** | `vexa meeting screen --type url --url {url}` — display content to participants |
| **Control browsers** | `vexa container spawn --profile browser` + CDP/Playwright automation |
| **Schedule pipelines** | `vexa schedule --cron "0 9 * * 1-5" chat "join standup, send notes"` |
| **Persist memory** | `vexa workspace save` — workspace survives across sessions |

### Specialist containers, not fat stacks

| Profile | RAM | Purpose | Idle cost |
|---------|-----|---------|-----------|
| **browser** | ~1.5GB | Meeting attendance, authenticated sessions, VNC + CDP | Zero — killed on timeout |
| **agent** | ~200MB | Claude CLI, summarization, automation, chat | Zero — killed on completion |
| **worker** | ~50MB | Webhook delivery, file processing, notifications | Zero — fire and forget |

The browser doesn't carry an agent. The agent doesn't carry Chromium. They connect via CDP over the network when needed, then die independently.

### Agents that act without being asked

```
Every weekday at 9am:
  → Browser container spawns, joins standup
  → Transcribes the meeting live
  → Meeting ends → agent container wakes up
  → Summarizes, creates Linear tickets, posts to #engineering
  → All containers die. Zero cost until tomorrow.
```

No human triggered anything. Calendar → scheduler → containers → business action.

### Multi-tenant by design

Unlike single-user agent tools (OpenClaw: "not a hostile multi-tenant security boundary," one VPS per user), Vexa runs as a multi-user service:

- **Isolated containers** per user, per session
- **Scoped API tokens** — `bot`, `tx`, `admin` enforced at gateway
- **User/team management** via Admin API
- **Deploy once**, serve your whole team — or your customer base

### MCP server — 17 meeting tools for AI agents

Connect Claude, Cursor, Windsurf, or any MCP client. Your agent gains meeting superpowers:

```
Tools: join_meeting, list_meetings, get_transcript, search_meetings,
       bot_speak, send_chat, read_chat, share_screen, set_avatar,
       start_recording, stop_recording, get_recording, list_bots,
       create_bot, stop_bot, get_bot_status, schedule_meeting
```

Other meeting MCP servers (Otter, Fireflies, Read.ai) are read-only. Vexa's is read + write + control — and self-hosted.

### Your agent, wherever you are

Same agent, same memory, every surface:

| Surface | Status |
|---------|--------|
| **Web dashboard** | Working — chat with your agent, see meetings, play recordings |
| **Telegram** | Working — message your agent from your phone |
| **Meeting chat** | Working — agent reads/responds in live meeting chat |
| **Slack/Discord** | Planned — same Agent API backbone |

---

## 1. Send bot to meeting:

Set `API_BASE` to your deployment:

- Hosted: `https://api.cloud.vexa.ai`
- Self-hosted Lite: `http://localhost:8056`
- Self-hosted full stack (default): `http://localhost:8056`

```bash
export API_BASE="http://localhost:8056"
```

### Request a bot for Microsoft Teams

```bash
curl -X POST "$API_BASE/bots" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_KEY>" \
  -d '{
    "platform": "teams",
    "native_meeting_id": "<NUMERIC_MEETING_ID>",
    "passcode": "<MEETING_PASSCODE>"
  }'
```

### Or request a bot for Google Meet

```bash
curl -X POST "$API_BASE/bots" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_KEY>" \
  -d '{
    "platform": "google_meet",
    "native_meeting_id": "abc-defg-hij"
  }'
```

### Or request a bot for Zoom

```bash
# Caveat: Zoom Meeting SDK apps typically require Marketplace approval to join other users' meetings.
# Before approval, expect you can reliably join only meetings created by you (the authorizing account).
#
# From URL: https://us05web.zoom.us/j/YOUR_MEETING_ID?pwd=YOUR_PWD
# Extract meeting ID and optional passcode separately.
curl -X POST "$API_BASE/bots" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_KEY>" \
  -d '{
    "platform": "zoom",
    "native_meeting_id": "YOUR_MEETING_ID",
    "passcode": "YOUR_PWD",
    "recording_enabled": true,
    "transcribe_enabled": true,
    "transcription_tier": "realtime"
  }'
```

## 2. Get transcripts:

### Get transcripts over REST

```bash
curl -H "X-API-Key: <API_KEY>" \
  "$API_BASE/transcripts/<platform>/<native_meeting_id>"
```

For real-time streaming (sub‑second), see the [WebSocket guide](https://docs.vexa.ai/websocket).
For full REST details, see the [User API Guide](https://docs.vexa.ai/user_api_guide).

Note: Meeting IDs are user-provided (Google Meet code like `xxx-xxxx-xxx` or Teams numeric ID and passcode). Vexa does not generate meeting IDs.

---

## Who Vexa is for

* **Enterprises (self-host):** Replace $17-20/seat meeting SaaS — data sovereignty, no per-seat fees
* **AI product builders:** Give your agents meeting superpowers via MCP — join calls, speak, act on transcripts
* **SaaS developers:** Multi-tenant meeting API to embed in your product — scoped tokens, isolated containers
* **Platform/DevOps teams:** Deploy once for your org — proactive agents, scheduled meetings, zero babysitting
* **Automation builders:** Post-meeting pipelines with n8n, webhooks, and agent containers
  - Tutorial: https://vexa.ai/blog/google-meet-transcription-n8n-workflow

---

## Roadmap

For the up-to-date roadmap and priorities, see GitHub Issues and Milestones. Issues are grouped by milestones to show what's coming next, in what order, and what's currently highest priority.

- Issues: https://github.com/Vexa-ai/vexa/issues
- Milestones: https://github.com/Vexa-ai/vexa/milestones

> For discussion/support, join our [Discord](https://discord.gg/Ga9duGkVz9).

## Architecture

**Core API services** (always running):

| Service | Purpose |
|---------|---------|
| [api-gateway](./services/api-gateway) | Reverse proxy — routes REST, WebSocket, VNC, CDP to backends |
| [admin-api](./services/admin-api) | User/org CRUD, scoped API tokens, team management |
| [bot-manager](./services/bot-manager) | Bot lifecycle, meeting CRUD, recordings, interactive bot controls |
| [agent-api](./services/agent-api) | Agent sessions, Claude CLI streaming, workspace sync, scheduling |
| [runtime-api](./services/runtime-api) | Container CRUD — spawn/stop/exec, port mapping, idle timeout |
| [transcription-collector](./services/transcription-collector) | Persists segments from Redis to Postgres, serves transcript API |

**Meeting & AI services:**

| Service | Purpose |
|---------|---------|
| [vexa-bot](./services/vexa-bot) | Joins meetings, captures per-speaker audio, transcribes, interactive controls |
| [transcription-service](./services/transcription-service) | GPU inference — OpenAI-compatible Whisper API |
| [tts-service](./services/tts-service) | Text-to-speech for bot voice |
| [mcp](./services/mcp) | 17-tool MCP server for AI agents (Claude, Cursor, etc.) |

**Frontends & clients:**

| Service | Purpose |
|---------|---------|
| [dashboard](./services/dashboard) | Open-source Next.js web UI — meetings, transcripts, agent chat, browser sessions |
| [telegram-bot](./services/telegram-bot) | Telegram client for agent interaction on mobile |

**Ephemeral containers** (spawned on demand, auto-reclaimed):

| Profile | RAM | Use case |
|---------|-----|----------|
| **browser** | ~1.5GB | Meeting attendance, authenticated browser sessions (VNC + CDP) |
| **agent** | ~200MB | Claude CLI, post-meeting processing, automation |
| **worker** | ~50MB | Webhook delivery, file processing |

- [Database models](./libs/shared-models/shared_models/models.py): Shared ORM models, schemas, migrations

> 💫 If you're building with Vexa, we'd love your support! [Star our repo](https://github.com/Vexa-ai/vexa/stargazers) to help us reach 2000 stars.

### Features

**Meeting transcription:**
- **Real-time multilingual transcription** supporting **100 languages** with **Whisper** — replace $17-20/seat SaaS
- **Post-meeting transcription** — record during meeting, transcribe on demand with full-audio context
- **Per-speaker audio** — no diarization needed, speaker labels from the platform itself
- **WebSocket streaming** — sub-second transcript delivery via WebSocket
- **Google Meet, Microsoft Teams, Zoom** — one API, all platforms, auto-detected from URL

**Interactive bots:**
- **Speaking bot** — TTS voice in meetings (like Recall.ai's Output Media API, but open-source)
- **Chat** — read/write meeting chat for AI-powered in-meeting interaction
- **Screen sharing** — display content to meeting participants programmatically
- **Avatar** — set bot avatar/display name per meeting

**Agent runtime:**
- **Ephemeral containers** — browser/agent/worker profiles, zero idle cost, ~5s spin-up
- **System layer fluency** — agents wake up knowing Vexa (CLI + instructions baked into image)
- **Persistent workspaces** — files, memory, scripts survive across sessions (MinIO/Git)
- **Container chaining** — `on_success`/`on_failure` callbacks orchestrate multi-step pipelines
- **Scheduler** — cron + relative delays + event-triggered jobs, backed by Redis sorted sets
- **Remote browser** — VNC for human control + CDP for agent automation, persistent auth

**Platform:**
- **Multi-tenant** — users, orgs, scoped API tokens, container isolation
- **MCP server** — 17 tools for Claude, Cursor, Windsurf — read + write + control meetings
- **Webhooks** — push events for post-meeting automation pipelines
- **REST API** — complete API for bots, users, transcripts, recordings, agents
- **Self-hostable** — full data sovereignty, Apache-2.0 licensed
- **Open-source frontends** — [Vexa Dashboard](./services/dashboard), Telegram bot

**Deployment & Management Guides:**
- [Vexa Lite Deployment Guide](https://docs.vexa.ai/vexa-lite-deployment) - Single container deployment
- [Docker Compose Deployment](https://docs.vexa.ai/deployment) - Full stack for development
- [Self-Hosted Management Guide](https://docs.vexa.ai/self-hosted-management) - Managing users and API tokens
- [Recording Storage](https://docs.vexa.ai/recording-storage) - S3, MinIO, and local storage configuration

## Features Directory

Each feature has its own README with business context, competitive positioning, architecture, and validation status:

| Feature | What it does | Status |
|---------|-------------|--------|
| [realtime-transcription](./features/realtime-transcription/) | Live speaker-attributed transcription via WebSocket | Production |
| [multi-platform](./features/multi-platform/) | One API for Google Meet, Teams, Zoom | GMeet/Teams working, Zoom WIP |
| [agentic-runtime](./features/agentic-runtime/) | Ephemeral containers, agent chat, workspace persistence | MVP3 complete |
| [mcp-integration](./features/mcp-integration/) | 17-tool MCP server for AI agents | Validated (10/10 tests) |
| [speaking-bot](./features/speaking-bot/) | TTS voice in meetings | Code complete |
| [chat](./features/chat/) | Read/write meeting chat via API | Code complete |
| [post-meeting-transcription](./features/post-meeting-transcription/) | Record → transcribe on demand with speaker mapping | Working |
| [webhooks](./features/webhooks/) | Push events for post-meeting automation | P0 complete |
| [scheduler](./features/scheduler/) | Cron + event-driven job execution with container chaining | Core library done (16/16 tests) |
| [remote-browser](./features/remote-browser/) | VNC + CDP browser with persistent auth | PoC proven |
| [calendar-integration](./features/calendar-integration/) | Auto-join meetings from Google Calendar | Research complete |
| [token-scoping](./features/token-scoping/) | Per-token permission scopes for multi-tenant security | Validated (14/14 tests) |

## Related Projects

Vexa is part of an ecosystem of open-source tools:

### [Vexa Dashboard](./services/dashboard)
100% open-source web interface for Vexa, included in this monorepo at `services/dashboard/`. Join meetings, view transcripts, chat with agents, manage browser sessions, and more. Self-host everything with no cloud dependencies.

## Contributing

We use **GitHub Issues** as our main feedback channel. New issues are triaged within **72 hours** (you'll get a label + short response). Not every feature will be implemented, but every issue will be acknowledged. Look for **`good-first-issue`** if you want to contribute.

Contributors are welcome! Join our community and help shape Vexa's future. Here's how to get involved:

1. **Understand Our Direction**:
2. **Engage on Discord** ([Discord Community](https://discord.gg/Ga9duGkVz9)):

   * **Introduce Yourself**: Start by saying hello in the introductions channel.
   * **Stay Informed**: Check the Discord channel for known issues, feature requests, and ongoing discussions. Issues actively being discussed often have dedicated channels.
   * **Discuss Ideas**: Share your feature requests, report bugs, and participate in conversations about a specific issue you're interested in delivering.
   * **Get Assigned**: If you feel ready to contribute, discuss the issue you'd like to work on and ask to get assigned on Discord.
3. **Development Process**:

   * Browse available **tasks** (often linked from Discord discussions or the roadmap).
   * Request task assignment through Discord if not already assigned.
   * Submit **pull requests** for review.

- **Critical Tasks & Bounties**:
  - Selected **high-priority tasks** may be marked with **bounties**.
  - Bounties are sponsored by the **Vexa core team**.
  - Check task descriptions (often on the roadmap or Discord) for bounty details and requirements.

We look forward to your contributions!

Licensed under **Apache-2.0** — see [LICENSE](LICENSE).

## Project Links

- 🌐 [Vexa Website](https://vexa.ai)
- 💼 [LinkedIn](https://www.linkedin.com/company/vexa-ai/)
- 🐦 [X (@grankin_d)](https://x.com/grankin_d)
- 💬 [Discord Community](https://discord.gg/Ga9duGkVz9)

## Repository Structure

This is the main Vexa repository containing the core API and services. For related projects:

- **[vexa-lite-deploy](https://github.com/Vexa-ai/vexa-lite-deploy)** - Deployment configurations for Vexa Lite
- **[Vexa Dashboard](./services/dashboard)** - Web UI for managing Vexa instances (included in this monorepo)

[![Meet Founder](https://img.shields.io/badge/LinkedIn-Dmitry_Grankin-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/dmitry-grankin/)

[![Join Discord](https://img.shields.io/badge/Discord-Community-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.gg/Ga9duGkVz9)

The Vexa name and logo are trademarks of **Vexa.ai Inc**.
