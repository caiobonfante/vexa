# Bot Browser View

> **Confidence: 30** — Unified bot/browser architecture implemented. Every bot has VNC. Gateway routes by meeting ID. Dashboard shows browser view for any active meeting.
> **Tested:** VNC in meeting mode, meeting-ID gateway routing, dashboard tab toggle, full-screen layout.
> **Not tested:** MinIO persistence for meeting bots, authenticated bot flow, CDP proxy for meeting bots.
> **Contributions welcome:** Authenticated meeting joins, MinIO sync for browser profiles, CDP proxy through gateway ([#122](https://github.com/Vexa-ai/vexa/issues/122)).

## Why

Every bot runs a real browser (Playwright on Xvfb). Users should be able to see what the bot sees — whether it's in a meeting or running as a standalone browser session. This helps with:

- **Monitoring** — watch the bot join, navigate, and interact in real time
- **Debugging** — see exactly what went wrong when a bot fails
- **Human intervention** — take over via VNC when the bot hits a CAPTCHA or auth wall
- **Authenticated joins** — log into Google/Teams once via VNC, cookies persist for future bots

A browser session is just a bot without a meeting. Same image, same VNC, same container — just different config.

---

## Design

### Every bot has VNC

The vexa-bot container runs Xvfb on display `:99` and Playwright in non-headless mode for ALL modes. The entrypoint starts the VNC stack (fluxbox, x11vnc, websockify) regardless of whether the bot is joining a meeting or running as a standalone browser session.

```
entrypoint.sh (all modes):
  Xvfb :99                    ← virtual display (always)
  fluxbox                     ← window manager, maximizes all windows
  x11vnc :99 → port 5900      ← VNC server
  websockify 5900 → port 6080 ← VNC-over-WebSocket for noVNC
  node dist/docker.js          ← bot process
```

### Gateway routes by meeting ID

When a bot is created, the meeting-api registers the container in Redis:

```
Redis key:   browser_session:{meeting_id}
Redis value: {"container_name": "meeting-5-abc123", "meeting_id": 42, "user_id": 5}
```

The gateway resolves `/b/{meeting_id}/vnc/...` by looking up this key — same resolver used for browser sessions. No separate session_token needed for meeting bots.

Browser sessions additionally store by their `session_token` for backward compatibility.

### Dashboard browser view

The meeting detail page (`/meetings/{id}`) shows a **Transcript | Browser** tab toggle for any active meeting. The Browser tab renders a full-screen noVNC iframe.

```
/meetings/{id}  →  status is active?  →  show Transcript | Browser tabs
                                          Browser tab: full-screen VNC via /b/{id}/vnc/...
                                          Transcript tab: normal transcript view
```

For `mode=browser_session`, the dedicated `BrowserSessionView` component renders instead (with Save, Connect Agent, SSH controls).

---

## What

### For any meeting bot (Google Meet, Teams, Zoom)

- **VNC** — see the bot's browser live on the dashboard via Browser tab
- **Full-screen layout** — toolbar with Transcript/Browser toggle, meeting name, Fullscreen button
- **Interactive** — click, type, scroll in the VNC view (useful for debugging or manual intervention)

### For browser sessions (standalone browser, no meeting)

All of the above, plus:

- **CDP/Playwright** — `connectOverCDP(cdpUrl)` for full programmatic control
- **SSH** — shell access into the container
- **Persistent workspace** — scripts, files, data survive container restarts (git or MinIO)
- **Persistent browser state** — cookies, localStorage, IndexedDB survive restarts (MinIO)
- **Connect Agent** — one-click copy of instructions for Claude or any AI agent
- **Save** — persist workspace + browser profile to storage

## How

### Architecture

```
POST /bots { meeting_url }           POST /bots { mode: "browser_session" }
         │                                       │
         ▼                                       ▼
    meeting-api                             meeting-api
    ├─ create meeting record                ├─ create meeting record (platform=browser_session)
    ├─ spawn container (vexa-bot)           ├─ spawn container (vexa-bot)
    ├─ Redis: browser_session:{id}          ├─ Redis: browser_session:{id}
    │         → container_name              │         → container_name
    │                                       ├─ Redis: browser_session:{session_token}
    │                                       │         → container_name (backward compat)
    ▼                                       ▼
  Container (same image)               Container (same image)
  ├─ fluxbox + x11vnc + websockify     ├─ fluxbox + x11vnc + websockify
  ├─ Playwright joins meeting           ├─ Playwright opens blank browser
  ├─ VNC on :6080 (view/interact)       ├─ VNC on :6080 + CDP on :9223 + SSH on :22
  └─ no persistence                     └─ workspace + browser data persistence

Dashboard /meetings/{id}
  ├─ Meeting bot: Transcript | Browser tabs
  └─ Browser session: full BrowserSessionView (Save, Connect Agent, etc.)

Gateway /b/{id}/vnc/websockify
  └─ Redis lookup browser_session:{id} → proxy to container:6080
```

### Container layout (browser session mode)

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

## Quick start (Dashboard)

### View any meeting bot's browser

1. Go to the Meetings page → join a meeting (Google Meet, Teams, or Zoom)
2. Open the meeting detail page
3. Click **Browser** in the toolbar → see the bot's live browser view
4. Click **Transcript** to switch back

### Start a browser session

1. Go to the Meetings page → click **Browser** button in the header
2. The session appears in your meetings list with a Monitor icon
3. Click it → full VNC view with Save, Connect Agent, Fullscreen, Stop

---

## Quick start (API)

### Join a meeting (with browser view)

```bash
curl -X POST http://localhost:8056/bots \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"meeting_url": "https://meet.google.com/abc-defg-hij"}'
```

Browser view available at: `http://localhost:8056/b/{meeting_id}/vnc/vnc.html?autoconnect=true&resize=scale`

### Create a browser session

```bash
curl -X POST http://localhost:8056/bots \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}'
```

Response includes `id` for VNC access and `data.session_token` for CDP/SSH.

---

## API reference

### Bot browser view (any meeting)

```
GET  /b/{meeting_id}/vnc/vnc.html     → noVNC web client
WS   /b/{meeting_id}/vnc/websockify   → VNC WebSocket proxy
GET  /b/{meeting_id}/vnc/{path}       → noVNC static files
```

### Browser session extras (standalone browser only)

```
WS   /b/{token}/cdp                   → CDP WebSocket proxy
GET  /b/{token}/cdp/{path}            → CDP HTTP proxy (e.g. /json/version)
POST /b/{token}/save                  → trigger storage save
```

### Lifecycle

```
POST   /bots { meeting_url }          → join meeting, browser view at /b/{id}/vnc/...
POST   /bots { mode: "browser_session" } → standalone browser
DELETE /bots/{platform}/{native_id}   → stop bot
```

---

## System requirements

| Resource | Per bot |
|----------|---------|
| RAM | ~1-1.5 GB (Chromium + Xvfb + VNC) |
| CPU | 0.5 core idle, 1 core active |
| SHM | 2 GB |
| Image size | vexa-bot includes VNC + fluxbox + websockify |

## Development Notes

### Key constraints

- **Persistent context**: Always `chromium.launchPersistentContext('/tmp/userdata', ...)` -- never `launch()` or `--incognito`
- **No `--enable-automation`**: Strip via `ignoreDefaultArgs`
- **MinIO sync**: `aws s3 sync` before launch (download) and on save/exit (upload)
- **SingletonLock cleanup**: Always `rm -f SingletonLock SingletonCookie SingletonSocket` before Chromium start
- **URL is auth**: `/b/{token}` routes need no API key -- the token IS the auth

### Infrastructure

- **vexa-bot** container in `browser_session` mode
- **MinIO** at `s3://vexa/users/{user_id}/browser-userdata/`
- **Ports**: noVNC :6080, CDP :9222 (proxied through api-gateway)
