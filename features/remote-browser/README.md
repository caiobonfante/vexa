# Remote Browser

## Why

Browserbase raised $40M at a $300M valuation selling headless browsers for AI agents. Their use case: web scraping, form filling, testing. Vexa's browser container does something they can't — **attend meetings with a persistent authenticated identity**.

**How this differs from Browserbase/Browserless:**

| Capability | Browserbase | Browserless | Vexa Browser |
|-----------|-------------|-------------|--------------|
| Headless browser for agents | Yes | Yes | Yes |
| CDP/Playwright control | Yes | Yes | Yes |
| VNC (human sees what agent sees) | No | No | **Yes** |
| Human + agent control simultaneously | No | No | **Yes** |
| Persistent auth across sessions | No (ephemeral) | No | **Yes** (MinIO sync) |
| Meeting attendance | No | No | **Yes** |
| Audio capture + transcription | No | No | **Yes** |
| Self-hosted | No | Partial | **Yes** |
| Cost | $0.10-0.12/hr | $0.05-0.10/hr | **Your infra** |

The unique capability: **human authenticates once via VNC (OAuth, MFA, CAPTCHAs), agent takes over via CDP for all future sessions**. Browser state (cookies, localStorage, IndexedDB) persists to MinIO and restores on next spawn. No re-authentication.

This solves the hardest problem in meeting bots: org-restricted meetings that reject unauthenticated guests. Human logs into Teams/Google once → agent joins all future meetings as an authenticated user.

---

Vexa bots are unauthenticated guests. They launch fresh `--incognito` Chromium, join as strangers, land in lobbies, get rejected from org-restricted meetings. There's no way to give a bot a persistent browser identity.

The fix: a **human-agent collaborative browser** with profile persistence. Human authenticates via VNC, agent automates via CDP/Playwright — both control the same browser simultaneously. Browser state and user workspace persist across sessions.

Human handles what requires judgment (OAuth, CAPTCHAs, MFA). Agent handles what's automatable (navigation, validation, meeting scripts).

---

## What

Browser sessions are first-class meetings — created from the Meetings page, managed like any meeting, counted against `max_concurrent_bots`.

- **VNC** — see and interact with Chromium live, embedded in the meeting detail page
- **CDP/Playwright** — `connectOverCDP(cdpUrl)` for full programmatic control
- **SSH** — shell access into the container (port mapped automatically)
- **Persistent workspace** — scripts, files, data survive container restarts (git or MinIO)
- **Persistent browser state** — cookies, localStorage, IndexedDB survive restarts (MinIO)
- **Connect Agent** — one-click copy of instructions to paste into Claude or any AI agent

## How

Two persistent layers, separated:

```
/workspace/              ← user files (scripts, data) — synced via git or MinIO
/tmp/browser-data/       ← Chromium profile (cookies, localStorage) — synced via MinIO
```

On start: download both. On save: upload both. On next start: everything is there.

### Storage options for workspace

**Option A: MinIO (default)** — workspace syncs to `s3://vexa-recordings/users/{id}/browser-userdata/workspace/`. No external setup needed.

**Option B: GitHub (recommended for teams)** — workspace clones from a private GitHub repo. On save: commit + push. Full git history, PRs, collaboration. Configured via dashboard (stored in localStorage).

Browser data always uses MinIO (Chromium profile is binary, not git-friendly).

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | Browser profile (cookies, localStorage, IndexedDB) + workspace files | Human interaction via VNC | MinIO/GitHub persistence |
| **rendered** | Persisted state in MinIO/GitHub, accessible on next session start | Save operation | Next browser session |

Data lives externally (MinIO: `s3://vexa-recordings/users/{id}/browser-userdata/`, GitHub: workspace repo). No local `data/` directory — persistence is the feature.

---

## Quick start (Dashboard)

### 1. Start a browser session

Go to the Meetings page → click **Browser** button in the header.

The session appears in your meetings list with a Monitor icon. Click it to open the VNC view.

### 2. Connect an agent

In the meeting detail view, click **Connect Agent** → sidebar opens with copy-pastable instructions:

```js
const { chromium } = require('playwright');
const browser = await chromium.connectOverCDP('CDP_URL_FROM_DASHBOARD');
const page = browser.contexts()[0].pages()[0];

await page.goto('https://accounts.google.com');
await page.screenshot({ path: 'screenshot.png' });
await browser.close(); // disconnects only — browser stays alive
```

### 3. SSH into the container

The Connect Agent sidebar also shows SSH access:

```bash
ssh root@localhost -p PORT_FROM_DASHBOARD
# Password: the session_token (shown in Connect Agent sidebar)
# Workspace: /workspace
```

### 4. Save storage

Click **Save** in the toolbar. Saves workspace (git push or S3) + browser profile (S3).

### 5. Stop

Click **Stop** in the toolbar, or it stops like any other meeting.

---

## Quick start (API)

### 1. Create a browser session

```bash
curl -X POST http://localhost:8056/bots \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}'
```

Response:
```json
{
  "id": 42,
  "status": "active",
  "data": {
    "mode": "browser_session",
    "session_token": "HxpBmQsJOsHtG8myegDHuS-wMhBJaPDv",
    "ssh_port": 32789
  }
}
```

### 2. Access the browser

Dashboard (noVNC + toolbar):
```
http://localhost:8056/b/HxpBmQsJOsHtG8myegDHuS-wMhBJaPDv
```

Playwright CDP:
```js
const browser = await chromium.connectOverCDP(
  'http://localhost:8056/b/HxpBmQsJOsHtG8myegDHuS-wMhBJaPDv/cdp'
);
```

SSH:
```bash
ssh root@localhost -p 32789
# Password: the session_token (shown in Connect Agent sidebar)
```

### 3. Save and stop

```bash
# Save
curl -X POST http://localhost:8056/b/HxpBmQsJOsHtG8myegDHuS-wMhBJaPDv/save

# Stop
curl -X DELETE http://localhost:8056/bots/browser_session/bs-abc123 \
  -H "X-API-Key: YOUR_API_KEY"

# Start again — everything restored
curl -X POST http://localhost:8056/bots \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}'
```

---

## GitHub workspace setup

Use a private GitHub repo to persist your workspace files (scripts, configs, data).

### 1. Create a private repo

Create a new private repo on GitHub (e.g., `my-bot-workspace`). Can be empty.

### 2. Create a fine-grained personal access token

Go to: https://github.com/settings/personal-access-tokens/new

Settings:
- **Token name**: `vexa-bot-workspace`
- **Expiration**: 90 days
- **Repository access**: "Only select repositories" → select your workspace repo
- **Permissions**:
  - **Contents**: Read and write
  - **Metadata**: Read-only (auto-selected)
- Everything else: No access

### 3. Configure in dashboard

Go to Meetings page → click **Browser** → configure Git Workspace settings (repo URL, PAT, branch). Settings are saved in localStorage and passed automatically when creating sessions.

### 4. Configure via API

Pass git config when creating the session:

```bash
curl -X POST http://localhost:8056/bots \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "browser_session",
    "workspaceGitRepo": "https://github.com/YOUR_USER/my-bot-workspace.git",
    "workspaceGitToken": "github_pat_...",
    "workspaceGitBranch": "main"
  }'
```

---

## Architecture

```
Meetings Page
│  [Browser] button → POST /bots { mode: "browser_session" }
│  → creates meeting record (platform=browser_session)
│  → counts against max_concurrent_bots
│  → starts container with VNC + CDP + SSH
│
Meeting Detail (/meetings/{id})
│  detects mode=browser_session → shows VNC view
│  toolbar: Save, Connect Agent, Fullscreen, Stop
│  Connect Agent sidebar: CDP URL, SSH, MCP
│
Container (vexa-bot, browser_session mode)
│  downloads browser data from MinIO
│  clones/pulls workspace from GitHub (or MinIO)
│  launchPersistentContext('/tmp/browser-data')
│  VNC (:6080) + CDP (:9223 via socat) + SSH (:22)
│
│  Human: VNC iframe in dashboard
│  Agent: connectOverCDP('/b/{token}/cdp')
│  Shell: ssh root@host -p PORT
│
│  [Save] → git commit + push workspace (or S3 sync)
│         → S3 sync browser data (excludes cache)
│  container stays alive until stopped
```

### Container layout

```
/workspace/              ← user files, git-tracked (GitHub or MinIO)
├── scripts/
│   └── auto-admit.js
├── .git/
└── ...

/tmp/browser-data/       ← Chromium profile (MinIO, excludes cache)
├── Default/
│   ├── Cookies
│   ├── Local Storage/
│   ├── IndexedDB/
│   └── ...
└── Local State
```

---

## API reference

### Browser session lifecycle

```
POST   /bots { mode: "browser_session" }
  → creates browser session, returns { id, data.session_token, data.ssh_port }

DELETE /bots/browser_session/{platform_specific_id}
  → stops browser session
```

### Browser access (token-authenticated, no API key needed)

```
GET  /b/{token}              → dashboard page (noVNC + toolbar)
WS   /b/{token}/vnc/websockify  → VNC WebSocket proxy
GET  /b/{token}/vnc/{path}   → noVNC static files proxy
WS   /b/{token}/cdp          → CDP WebSocket proxy
GET  /b/{token}/cdp/{path}   → CDP HTTP proxy (e.g. /json/version)
POST /b/{token}/save         → trigger storage save
```

### Storage save (internal)

```
POST /bots/{id}/storage/save
  → trigger save (authenticated, for direct API use)

POST /internal/browser-sessions/{token}/save
  → trigger save (internal, used by gateway proxy)
```

---

## System requirements

| Resource | Per session |
|----------|------------|
| RAM | ~1-1.5 GB (Chromium + Xvfb + VNC) |
| CPU | 0.5 core idle, 1 core active |
| SHM | 2 GB |
| Disk | ~50 MB workspace + ~20 MB browser data (excludes cache) |
| Image size | +50 MB over base vexa-bot (VNC + awscli + git + socat + sshd) |
| MinIO | ~20-50 MB per user |
