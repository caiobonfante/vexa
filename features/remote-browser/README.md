# Remote Browser

## Why

Vexa bots are unauthenticated guests. They launch fresh `--incognito` Chromium, join as strangers, land in lobbies, get rejected from org-restricted meetings. There's no way to give a bot a persistent browser identity.

The fix: a **human-agent collaborative browser** with profile persistence. Human authenticates via VNC, agent automates via CDP/Playwright — both control the same browser simultaneously. The entire browser state (cookies, localStorage, IndexedDB, extensions, everything) persists across sessions via MinIO.

Human handles what requires judgment (OAuth, CAPTCHAs, MFA). Agent handles what's automatable (navigation, validation, meeting scripts).

---

## MVP 1 — Authenticated bot join

### Why

Bots can't join org-restricted meetings. Users need a way to give their bot an authenticated identity.

### What

You call the API, get a unique URL. Open it — you see the bot's Chromium live. Authenticate, save, close. Next time you open a browser session, everything is exactly as you left it — all accounts logged in, all localStorage, all state.

Meeting bots launched with `authenticated: true` get the same userdata — they use `launchPersistentContext` instead of fresh `--incognito`, joining as the authenticated user with full session fidelity.

### How it works

The entire Chromium userdata directory syncs to/from MinIO (S3-compatible, already in vexa infra for recordings).

```
Browser session starts:
  s3://vexa/users/{user_id}/browser-userdata/ → /tmp/userdata/
  launchPersistentContext('/tmp/userdata')
  → everything already there from last session

User authenticates, does stuff

Save (explicit or on exit):
  /tmp/userdata/ → s3://vexa/users/{user_id}/browser-userdata/

Meeting bot (authenticated: true):
  same download → launchPersistentContext('/tmp/userdata')
  → full session fidelity, joins as authenticated user
```

No cookie extraction. No cookie injection. No `addCookies()`. No domain filtering. The userdata IS the identity.

### User experience

```
1. POST /bots { mode: "browser_session" }
   → { url: "https://vexa.ai/b/x7f9k2m..." }

2. Open URL → noVNC: live Chromium
   → if returning user: all accounts already logged in
   → toolbar: [Save] [Storage Audit]

3. Log into Google, Teams, whatever → click [Save]
   → userdata synced to MinIO

4. POST /bots { platform: "google_meet", authenticated: true }
   → bot downloads same userdata from MinIO
   → launchPersistentContext → joins as authenticated user
   → transcribes normally

5. Next browser session → open URL → everything still there
```

Agent does the same via CDP:

```js
const browser = await chromium.connectOverCDP('wss://vexa.ai/b/x7f9k2m.../cdp');
const context = browser.contexts()[0]; // persistent context with all state
const page = context.pages()[0];
// full Playwright API — navigate, click, type, screenshot
await browser.close(); // disconnects, browser stays alive
```

### Deliverables

#### 1. vexa-bot: browser session mode
- New `mode: "browser_session"` in BOT_CONFIG
- `core/src/browser-session.ts` — downloads userdata from MinIO, launches persistent context, exposes VNC + CDP
- `entrypoint.sh` — conditionally starts VNC stack
- `Dockerfile` — add VNC packages (x11vnc, websockify, noVNC, socat)
- On start: `aws s3 sync s3://vexa/users/{user_id}/browser-userdata/ /tmp/userdata/`
- On save command: `aws s3 sync /tmp/userdata/ s3://vexa/users/{user_id}/browser-userdata/`

#### 2. vexa-bot: authenticated meeting mode
- When `browserCookies` field is replaced by `authenticated: true` flag
- Bot downloads userdata from MinIO before launch
- Uses `launchPersistentContext('/tmp/userdata')` instead of `browser.newContext()` with `--incognito`
- Everything else (meeting join, audio capture, transcription) stays the same

#### 3. bot-manager: browser session lifecycle
- `POST /bots { mode: "browser_session" }` — starts vexa-bot in browser session mode, returns URL
- URL contains session token (`/b/{token}`) — no separate API key needed
- Passes MinIO credentials + user_id in BOT_CONFIG
- `DELETE /bots/:id` — triggers userdata sync before stop

#### 4. bot-manager: authenticated bot launch
- `POST /bots { platform: "...", authenticated: true }` — starts vexa-bot with MinIO userdata path
- Bot downloads userdata, uses persistent context
- No cookie extraction/filtering — full userdata

#### 5. api-gateway: URL-based access
- `GET /b/{token}` — serves noVNC client page with toolbar
- `WS /b/{token}/vnc` — proxied to container's noVNC (:6080)
- `WS /b/{token}/cdp` — proxied to container's CDP (:9222)
- Token is the auth — no X-API-Key needed for browser access

#### 6. Dashboard UI
- Page at `/b/{token}` — noVNC iframe + toolbar
- **[Save]** button — triggers userdata sync to MinIO
- **[Storage Audit]** panel — cookies + localStorage table (reuse from PoC)

### Data flow

```
POST /bots { mode: "browser_session" }
      │
      ▼
bot-manager
│  generates session token
│  starts vexa-bot with mode=browser_session + MinIO path
│  returns { url: "/b/{token}" }
│
      ▼
vexa-bot (browser session mode)
│  s3 sync: MinIO → /tmp/userdata/
│  launchPersistentContext('/tmp/userdata')
│  VNC (:6080) + CDP (:9222) exposed
│  all previously authenticated accounts already logged in
│  user/agent does stuff
│  [Save] → s3 sync: /tmp/userdata/ → MinIO
│  container stays alive until stopped
│
      MinIO: s3://vexa/users/{user_id}/browser-userdata/
                        │
POST /bots { platform:  │ bot downloads same userdata
  "google_meet",        │
  authenticated: true } │
      │                 │
      ▼                 ▼
vexa-bot (meeting mode, authenticated)
│  s3 sync: MinIO → /tmp/userdata/
│  launchPersistentContext('/tmp/userdata')
│  page.goto(meetingUrl)
│  joins as authenticated user
│  transcribes → syncs userdata → exits
```

### What's stored in MinIO

```
s3://vexa/users/{user_id}/browser-userdata/
├── Default/
│   ├── Cookies           # SQLite — all browser cookies
│   ├── Local Storage/    # LevelDB — all localStorage
│   ├── IndexedDB/        # per-origin IndexedDB
│   ├── Service Worker/   # registered service workers
│   ├── Extensions/       # installed extensions
│   └── ...               # bookmarks, history, preferences
├── Local State
└── ...
```

This is Chromium's standard user data directory. Everything the browser persists lives here.

### Scope

| In | Out |
|----|-----|
| Full userdata persistence via MinIO | Per-profile management (MVP2) |
| Any platform — full browser state | Concurrent browser sessions |
| VNC (human) + CDP (Playwright) | Automated OAuth flows |
| URL-as-token access | Browser pool |
| Dashboard UI (noVNC + save + storage audit) | |

### Gate

The gate is the URL. One API call → one URL → everything works through it:

1. **Browser**: open URL in a tab → see live Chromium via noVNC, interact with it
2. **Storage**: click Save → userdata persisted to MinIO. Reopen → everything still there
3. **Agent (CDP)**: `connectOverCDP(url + '/cdp')` → full Playwright control
4. **Files**: workspace at `/tmp/userdata/` persisted to MinIO — files created there survive restarts
5. **Terminal**: `docker exec` into the container for shell access (agent or human)

### Success criteria

1. `POST /bots { mode: "browser_session" }` → get URL
2. Open URL → see live browser
3. Authenticate Google/Teams/anything
4. Click Save → userdata synced to MinIO
5. Stop browser session
6. `POST /bots { mode: "browser_session" }` again → open URL → everything still there (all accounts, all files)
7. Agent connects via CDP, navigates, interacts — same browser
8. `POST /bots { platform: "google_meet", authenticated: true }` → bot joins as authenticated user
9. Transcription works normally

### System requirements

- **MinIO storage**: ~50-200 MB per user (Chromium userdata). Already in infra.
- **Sync time**: ~2-5s for initial download, <1s for incremental syncs
- **No schema migration**: MinIO bucket already exists for recordings
- **VNC packages**: ~50 MB added to vexa-bot Docker image

---

## MVP 2 — Meeting host for bot testing

### Why

Testing bots requires a real meeting with a real host who can admit bots from the lobby. Currently manual.

### What

Third mode: `mode: "meeting_host"`. Uses stored userdata to create a meeting and auto-admit bots. Same MinIO userdata as MVP1.

### Deliverables

1. **vexa-bot: host mode** — `core/src/meeting-host.ts`, creates meeting, runs admit loop
2. **Auto-admit script** — polls People panel, clicks Admit
3. **bot-manager: launch host** — starts with `mode: "meeting_host"`, returns meeting URL

---

## Open questions

1. **Sync granularity** — sync full userdata dir or use tar.gz archive? Archive is one file (simpler), dir sync is incremental (faster for updates)
2. **Concurrent access** — what if browser session and meeting bot both access same userdata simultaneously? Need locking or copy-on-read.
3. **Userdata size** — Chromium userdata can grow large with cache. Exclude cache dirs from sync?
4. **Token TTL** — session URL token should expire when browser session stops. How long after?
