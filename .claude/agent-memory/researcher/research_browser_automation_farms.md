---
name: Browser Automation Farm Research
description: Comparative analysis of 7 browser automation farm projects (Browserless, Selenium Grid 4, Moon, Selenoid, Browserbase, Steel Browser, Playwright MCP) for CaaS API design reference
type: project
---

# Browser Automation Farm Research (2026-03-26)

Comprehensive comparison of projects that spawn/manage ephemeral browser containers on demand via API. Evaluated for relevance to a generic Container-as-a-Service (CaaS) API.

## 1. Browserless (browserless/browserless)

| Field | Value |
|-------|-------|
| GitHub | https://github.com/browserless/browserless |
| Stars | ~12.8k |
| Last release | v2.40.0 (Feb 2026); npm v2.22.0 (Mar 2026) |
| Maintenance | Actively maintained, regular releases |
| License | **SSPL-1.0 OR Browserless Commercial License** |
| Language | Node.js/TypeScript |

### Docker + K8s
- **Docker:** First-class. `docker run ghcr.io/browserless/chromium`. Multi-browser images (chromium, firefox, multi).
- **K8s:** No native K8s orchestration. Runs as a Docker container; user manages K8s deployment themselves.

### REST API
Rich REST API for stateless operations:
- `/content`, `/scrape`, `/screenshot`, `/pdf`, `/function`, `/download`, `/export`, `/unblock`, `/performance`, `/smart-scrape`, `/search`, `/map`
- WebSocket connections for Puppeteer/Playwright sessions
- BaaS sessions API for persistent sessions (Enterprise/Cloud)
- API Playground for interactive testing

### Profile/Template System
- No browser version templates per se; ships specific browser images (chromium, firefox)
- Enterprise: persistent sessions with cookies/cache/localStorage (up to 90 days retention)
- Launch parameters configurable per request

### Idle/Timeout Management
- `TIMEOUT` env var (default 30s, -1 for disabled)
- `MAX_RECONNECT_TIME` for session reconnection window
- `CONCURRENT` / `MAX_CONCURRENT_SESSIONS` (default 10 Enterprise, 5 OSS)
- `QUEUED` / `QUEUE_LENGTH` (default 10)
- `HEALTH` pre-request health check with CPU/memory thresholds

### Webhooks/Callbacks
**Enterprise only, 5 webhook types:**
- `QUEUE_ALERT_URL` - when queuing begins
- `REJECT_ALERT_URL` - when requests rejected
- `TIMEOUT_ALERT_URL` - when timeouts occur
- `ERROR_ALERT_URL` - on limiter errors (includes error message)
- `FAILED_HEALTH_URL` - when CPU/memory > 99%
- All fire GET requests; no response monitoring

### Library vs Infrastructure
**Infrastructure.** Standalone service you deploy. Clients connect via WebSocket or REST.

### CaaS Relevance
**HIGH.** Closest to a CaaS for browsers: session management, queue, health checks, webhooks, REST API. However SSPL license is restrictive for commercial use. The webhook pattern and queue/concurrency model are excellent reference designs.

---

## 2. Selenium Grid 4 (SeleniumHQ/docker-selenium)

| Field | Value |
|-------|-------|
| GitHub | https://github.com/SeleniumHQ/docker-selenium |
| Stars | ~8.6k |
| Last release | v4.41.0 (Feb 22, 2026) |
| Maintenance | Very actively maintained by Selenium project |
| License | **Apache-2.0** |
| Language | Java (Grid), Shell (Docker images) |

### Docker + K8s
- **Docker:** Full support. Standalone, Hub+Node, and Distributed modes. Dynamic Grid spawns Docker containers per session.
- **K8s:** **Native K8s Dynamic Grid** (new in 4.41.0). Provisions one browser Pod per session request, deletes on close. Helm chart included. InheritedPodSpec auto-propagates tolerations, affinity, node selectors, resource limits.
- TOML config via ConfigMaps for browser stereotypes

### REST API
- `GET /status` - Grid state (nodes, sessions, slots)
- `DELETE /session/<session-id>` - Terminate session
- `DELETE /se/grid/distributor/node/<node-id>` - Remove node
- `POST /se/grid/distributor/node/<node-id>/drain` - Graceful drain
- `GET /se/grid/node/owner/<session-id>` - Check session owner
- `DELETE /se/grid/newsessionqueue/queue` - Clear queue
- `GET /se/grid/newsessionqueue/queue` - List pending requests
- **GraphQL endpoint** at `/graphql` for flexible querying (sessions, nodes, slots, capabilities)

### Profile/Template System
- Browser "stereotypes" in TOML config: pairs browser image with capability JSON
- Dynamic Node matches incoming session capabilities to configured images
- Multi-version support (Chrome, Firefox, Edge, each with multiple versions)

### Idle/Timeout Management
- `SE_NODE_SESSION_TIMEOUT` (default 300s) - idle session auto-kill
- `SE_SESSION_REQUEST_TIMEOUT` - queue timeout
- `SE_SESSION_RETRY_INTERVAL` - retry interval
- `SE_NODE_MAX_SESSIONS` - max sessions per container
- `--session-timeout` CLI flag

### Webhooks/Callbacks
- **No webhooks.** Has internal Event Bus (ZeroMQ pub/sub) for inter-component communication.
- Event Bus carries session start/stop/status events; external services CAN subscribe (video container does this for recording lifecycle)
- But no HTTP webhook callbacks

### Library vs Infrastructure
**Infrastructure.** Full distributed system with Router, Queue, Distributor, EventBus, SessionMap, Node components.

### CaaS Relevance
**HIGH.** The Dynamic Grid K8s model is the gold standard for on-demand container spawning per session request. GraphQL API is sophisticated. Apache-2.0 license. The stereotype/config pattern is a good reference for container profiles. Missing: HTTP webhooks for external integrations.

---

## 3. Moon (aerokube/moon)

| Field | Value |
|-------|-------|
| GitHub | https://github.com/aerokube/moon |
| Stars | ~269 |
| Last release | v2.8.0 (Mar 3, 2026) |
| Maintenance | Actively maintained |
| License | **Apache-2.0** (repo) but **commercially licensed** (closed-source binary) |
| Language | Go (closed-source) |

### Docker + K8s
- **Docker:** No standalone Docker mode. Moon IS Kubernetes-native.
- **K8s:** First-class. One browser pod per session, auto-created and destroyed. Multi-namespace support. Resource limits, affinity, tolerations. Stateless Moon replicas behind LB.

### REST API
- Standard Selenium WebDriver at `/wd/hub`
- Clipboard API: `/wd/hub/session/{sessionId}/aerokube/clipboard`
- `/download` for browser-downloaded files
- Moon API provides session/browser information

### Profile/Template System
- **BrowserSet** Kubernetes CRD: defines browser images, versions, defaults per browser type
- Custom labels, host aliases, env vars per browser set
- Mobile device emulation with deviceName + orientation
- `moon:options` capability for per-session customization (screen resolution, video, audio, DNS, fonts, etc.)

### Idle/Timeout Management
- Per-session `sessionTimeout` capability (Go duration format)
- Global timeout configuration via Moon config

### Webhooks/Callbacks
- **No webhooks documented.** Callback URL in Helm chart for ALB/ingress routing (not event callbacks).

### Library vs Infrastructure
**Infrastructure.** K8s-native, closed-source binary. Helm chart deployment.

### CaaS Relevance
**MEDIUM.** Excellent K8s-native architecture and BrowserSet CRD is a great pattern for profiles/templates. But closed-source, commercially licensed (free tier: 4 parallel pods only), and tightly coupled to Selenium protocol. Not directly reusable.

---

## 4. Selenoid (aerokube/selenoid)

| Field | Value |
|-------|-------|
| GitHub | https://github.com/aerokube/selenoid |
| Stars | ~2.7k |
| Last release | v1.11.3 (May 2025) |
| Maintenance | **ARCHIVED / UNMAINTAINED** (Dec 17, 2024). Moon recommended instead. |
| License | **Apache-2.0** |
| Language | Go (98.2%) |

### Docker + K8s
- **Docker:** Core design. Launches browser containers via Docker API. 6MB Go binary.
- **K8s:** Not natively supported. Docker-only.

### REST API
- `POST /wd/hub` - WebDriver (create sessions)
- `GET /status` - Usage stats (total, used, queued, pending by browser/version)
- `GET /ping` - Health check (uptime, reload time, request count)
- `GET/DELETE /video/<filename>.mp4` - Video management
- `GET/DELETE /logs/<filename>.log` - Log management
- `GET/DELETE /download/<session-id>/<filename>` - Downloaded files
- `GET/POST /clipboard/<session-id>` - Clipboard
- `ws://localhost:4444/devtools/<session-id>/page` - CDP WebSocket
- `http://localhost:4444/vnc/<session-id>` - VNC proxy

### Profile/Template System
**browsers.json is the standout pattern:**
```json
{
  "chrome": {
    "default": "128.0",
    "versions": {
      "128.0": {
        "image": "selenoid/vnc:chrome_128.0",
        "port": "4444",
        "tmpfs": {"/tmp": "size=512m"},
        "env": ["VAR=value"],
        "shmSize": 268435456,
        "cpu": "1.0",
        "mem": "512m"
      }
    }
  }
}
```
- Per-version: image, port, path, tmpfs, volumes, env, hosts, labels, shmSize, cpu, mem
- Hot-reload via SIGHUP

### Idle/Timeout Management
- `-timeout` flag (default 60s) - idle time between HTTP requests
- `-max-timeout` - upper bound for per-session overrides
- `-service-startup-timeout` - container startup timeout
- `-session-attempt-timeout` - new session creation timeout
- `-session-delete-timeout` - container removal timeout
- Per-session: `sessionTimeout` capability (Go duration)
- `-limit` flag for max concurrent sessions

### Webhooks/Callbacks
**None.** Poll-based or log-based external integration only.

### Library vs Infrastructure
**Infrastructure.** Single Go binary + Docker. Lightweight and simple.

### CaaS Relevance
**HIGH (as design reference).** Despite being unmaintained, Selenoid's `browsers.json` is the best example of a simple profile/template system for container spawning. The timeout flag taxonomy (-timeout, -max-timeout, -service-startup-timeout, -session-attempt-timeout, -session-delete-timeout) is exactly what a CaaS needs. Apache-2.0. The status API with total/used/queued/pending is a clean operational model.

---

## 5. Browserbase

| Field | Value |
|-------|-------|
| GitHub | https://github.com/browserbase (org, 64 repos) |
| Open-source components | Stagehand (MIT), Open Operator (MIT), MCP Server (Apache-2.0) |
| Core platform | **Closed-source SaaS** |
| Maintenance | Actively maintained |
| License | Proprietary (platform); MIT/Apache (SDKs) |

### Docker + K8s
- **Not applicable.** Managed cloud service. No self-hosted option for core platform.
- Docker available for MCP Server component only

### REST API
- Sessions API: create, navigate, act, extract, end sessions
- CDP connection via WebSocket for remote browser control
- SDKs: Python, Node.js
- Stagehand API: higher-level AI-driven browser automation

### Profile/Template System
- Project-level defaults for timeout
- Per-session timeout overrides
- Browser configuration at session creation time

### Idle/Timeout Management
- CDP connections close after 10 minutes without commands
- Project-level default timeouts
- Per-session timeout overrides
- Heartbeat pattern recommended (CDP ping every 5 min)
- Sessions up to 24 hours (paid plans)

### Webhooks/Callbacks
**Not documented.** Session Inspector for replay/debugging. No event-driven callbacks found.

### Library vs Infrastructure
**Cloud SaaS.** SDKs are libraries, but the core is managed infrastructure.

### Pricing
- Free: 1 concurrent browser, 1 browser hour, 15 min max session
- Developer: $20/mo, 100 hours, then $0.12/hr
- Startup: $99/mo, 500 hours, then $0.10/hr
- Scale: Custom

### CaaS Relevance
**LOW for self-hosted CaaS.** Proprietary. But Stagehand's session lifecycle model (create -> live -> released/failed) and the CDP heartbeat pattern are good references. Open-source components (Stagehand, MCP) are useful but are SDK/client-side, not infrastructure.

---

## 6. Steel Browser (steel-dev/steel-browser)

| Field | Value |
|-------|-------|
| GitHub | https://github.com/steel-dev/steel-browser |
| Stars | ~6.7k |
| Last release | Active development (recent commits) |
| Maintenance | Public beta, actively maintained |
| License | **Apache-2.0** |
| Language | Node.js/TypeScript |

### Docker + K8s
- **Docker:** First-class. `docker run ghcr.io/steel-dev/steel-browser`. Docker Compose for API/UI separation.
- **K8s:** **Not used.** Steel chose Fly.io Machines API over K8s for scaling (founders found K8s too complex). No native K8s support.
- 1-click deploy to Railway, Render

### REST API
- `POST /v1/sessions` - Create session with config
- `GET /v1/sessions` - List sessions
- `DELETE /v1/sessions/{id}` - Release session
- `/scrape`, `/screenshot`, `/pdf` - Quick actions
- Swagger UI at `/documentation`
- CDP endpoint for Puppeteer/Playwright/Selenium connection

### Profile/Template System
- Session creation with custom config (proxy, extensions, stealth settings)
- No multi-browser-version template system
- Chrome-only (no Firefox/WebKit templates)

### Idle/Timeout Management
- Default 5-minute session timeout
- Configurable via `timeout` parameter (milliseconds) at session creation
- Max 24 hours (plan-dependent)
- Explicit `release()` and `releaseAll()` for cleanup
- Cannot modify timeout on live sessions
- Three states: Live, Released, Failed (auto-cleanup on crash)

### Webhooks/Callbacks
**None documented.** Lifecycle hooks into CDP launch/shutdown exist internally but no external webhook API.

### Library vs Infrastructure
**Infrastructure.** Standalone service with REST API. Python and Node SDKs available.

### CaaS Relevance
**HIGH.** Apache-2.0, clean REST API with Swagger, session lifecycle model (Live/Released/Failed), explicit cleanup. The `/v1/sessions` pattern is the most "CaaS-like" API of all projects reviewed. Missing: multi-container-type templates, K8s support, webhooks. The session timeout model (default + per-session override + explicit release) is a good pattern.

---

## 7. Playwright MCP Server (microsoft/playwright-mcp)

| Field | Value |
|-------|-------|
| GitHub | https://github.com/microsoft/playwright-mcp |
| Status | Official Microsoft project |
| License | Apache-2.0 |

### Summary
- MCP (Model Context Protocol) server for LLM-driven browser automation
- Can run as ephemeral Docker container or long-lived service (port 8931)
- Playwright Server in Docker exposes WebSocket at `ws://localhost:53333/playwright`
- Not a container management platform; single-browser-instance tool
- No session management, no multi-container orchestration, no REST API for spawning

### CaaS Relevance
**LOW.** This is a single-instance browser tool, not a farm/fleet management system. Only relevant as a client-side library pattern.

---

## Comparative Matrix

| Feature | Browserless | Selenium Grid 4 | Moon | Selenoid | Browserbase | Steel Browser |
|---------|-------------|-----------------|------|----------|-------------|---------------|
| Stars | 12.8k | 8.6k | 269 | 2.7k | N/A (SaaS) | 6.7k |
| License | SSPL-1.0 | Apache-2.0 | Commercial | Apache-2.0 | Proprietary | Apache-2.0 |
| Maintained | Yes | Yes | Yes | **No (archived)** | Yes | Yes (beta) |
| Docker | Yes | Yes | No (K8s only) | Yes | N/A | Yes |
| K8s native | No | **Yes (Dynamic Grid)** | **Yes** | No | N/A | No |
| REST API | Rich | Rich + GraphQL | WebDriver + extras | Rich | SDK-based | Clean REST |
| Profiles/Templates | Launch params | TOML stereotypes | BrowserSet CRD | **browsers.json** | Project defaults | Session config |
| Idle timeout | Configurable | Configurable | Configurable | **5 timeout types** | CDP 10min idle | 5min default |
| Webhooks | **5 types (Enterprise)** | No (Event Bus internal) | No | No | No | No |
| Session lifecycle | Stateless REST + BaaS sessions | WebDriver sessions | K8s pod lifecycle | Container lifecycle | Create/Live/Released/Failed | Live/Released/Failed |
| Spawn-per-request | Queue-based | **Pod-per-session (K8s)** | **Pod-per-session** | Container-per-session | Cloud-managed | Session-per-request |
| Open source | SSPL (restrictive) | **Full OSS** | Closed binary | **Full OSS** | SDKs only | **Full OSS** |

## Key Patterns for CaaS API Design

### Best-in-class patterns to adopt:

1. **Container profiles** (from Selenoid `browsers.json`): JSON config mapping profile names to container images + resource limits + env vars. Hot-reloadable.

2. **Session lifecycle states** (from Steel Browser): Live -> Released/Failed. Explicit create/release API. Timeout with per-session override.

3. **Timeout taxonomy** (from Selenoid): Separate timeouts for idle, startup, creation-attempt, and deletion. Per-session override with global max.

4. **Webhooks** (from Browserless): Queue alerts, rejection alerts, timeout alerts, error alerts, health failure alerts. Simple GET callbacks.

5. **Queue + concurrency model** (from Browserless): CONCURRENT + QUEUED limits. Health-gated admission. 429 on overflow.

6. **GraphQL for introspection** (from Selenium Grid 4): Rich querying of sessions, nodes, slots, capabilities.

7. **K8s Dynamic Grid** (from Selenium Grid 4): Pod-per-session with InheritedPodSpec. ConfigMap for stereotypes. Auto-cleanup.

8. **Status API** (from Selenoid): total/used/queued/pending breakdown by container type and version.

### Patterns to avoid:

1. **SSPL licensing** (Browserless): Too restrictive for a platform service.
2. **K8s-only** (Moon): Limits deployment flexibility; Docker should be first-class.
3. **No webhooks** (most projects): External systems need event-driven integration.
4. **Selenium-only protocol** (Selenoid, Moon): Ties to WebDriver; a CaaS should be protocol-agnostic.

**Why:** These patterns were extracted from production-proven projects with combined ~30k GitHub stars. The CaaS API should cherry-pick the best patterns while staying protocol-agnostic and supporting both Docker and K8s backends.

**How to apply:** Use these patterns as design references when defining the Runtime API's container profile system, session lifecycle, timeout model, and webhook API.
