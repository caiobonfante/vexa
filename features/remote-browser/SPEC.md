# Bot Browser View — Unified Architecture (IMPLEMENTED)

## WHY

Previously, browser sessions were a separate concept from meeting bots — different code paths, different UI, different token system. But they use the same image (vexa-bot), same Xvfb, same Playwright. A browser session is just a bot without a meeting.

The unified architecture:
1. **Every bot has VNC** — entrypoint starts fluxbox + x11vnc + websockify in all modes
2. **Gateway routes by meeting ID** — no separate session_token needed for meeting bots
3. **Dashboard shows browser view for any active meeting** — Transcript/Browser tab toggle
4. **Browser sessions are still first-class** — same creation flow, with extra features (CDP, SSH, persistence)

## WHAT

### Meeting bots (Google Meet, Teams, Zoom)

- VNC stack starts automatically in the container (fluxbox + x11vnc + websockify)
- Container registered in Redis as `browser_session:{meeting_id}` after spawn
- Dashboard meeting detail page shows **Transcript | Browser** tab toggle
- Browser tab renders full-screen noVNC iframe via `/b/{meeting_id}/vnc/...`
- Gateway resolves meeting ID from Redis, proxies to container:6080

### Browser sessions (standalone)

- Same VNC stack, plus CDP proxy (socat on :9223) and SSH server
- Registered in Redis by both `session_token` (backward compat) and `meeting_id`
- Dashboard renders `BrowserSessionView` with Save, Connect Agent, SSH, Fullscreen, Stop
- Persistent workspace (git/MinIO) and browser profile (MinIO)

### Escalation (needs_human_help)

- When a meeting bot gets stuck (CAPTCHA, auth wall, waiting room timeout)
- VNC is already running — no lazy-start needed
- Container already registered in Redis by meeting ID
- Dashboard shows escalation banner with VNC link: `/b/{meeting_id}`

## HOW

### 1. Entrypoint (all modes)

```bash
# entrypoint.sh — runs for both meeting and browser_session mode
Xvfb :99 -screen 0 1920x1080x24 &
fluxbox &                    # maximizes all windows
x11vnc -display :99 -forever -nopw -shared -rfbport 5900 &
websockify --web /usr/share/novnc 6080 localhost:5900 &
node dist/docker.js
```

Browser session mode additionally starts: socat (CDP proxy), SSH server.

### 2. Meeting API — container registration

After spawning a container for any bot:

```python
# meetings.py — after container spawn
await redis_client.set(
    f"browser_session:{meeting_id}",
    json.dumps({"container_name": container_name, "meeting_id": meeting_id, "user_id": user_id}),
    ex=86400,
)
```

Browser sessions additionally store by `session_token` for backward compat.

### 3. Gateway — unchanged

The gateway's `resolve_browser_session(token)` does `redis.get(f"browser_session:{token}")`. The "token" can be a meeting ID (integer) or a session_token (random string) — both resolve to the same container info. Zero gateway changes needed.

### 4. Dashboard — meeting detail page

```tsx
// page.tsx
const hasBrowserView = ['requested', 'joining', 'awaiting_admission', 'active'].includes(status);

// Full-screen layout when browser tab is active
if (browserViewIframe) {
  return (
    <div className="flex flex-col h-[calc(100vh-64px)] -m-4 md:-m-6">
      <toolbar>  Transcript | Browser | Fullscreen  </toolbar>
      <iframe src="/b/{meeting_id}/vnc/vnc.html?autoconnect=true&resize=scale" />
    </div>
  );
}

// Otherwise: normal transcript view with tab toggle in header
```

Browser session mode: early return to `<BrowserSessionView />` (unchanged).

## Architecture

```
Meetings Page (list)
  ├── Regular meetings → click → /meetings/[id] → Transcript | Browser tabs
  └── Browser sessions → click → /meetings/[id] → BrowserSessionView

Container lifecycle (unified):
  POST /bots { meeting_url | mode: "browser_session" }
    → check max_concurrent_bots
    → INSERT meetings
    → start container (vexa-bot image, same for both)
    → Redis: browser_session:{meeting_id} → container_name
    → VNC available at /b/{meeting_id}/vnc/...

Gateway VNC proxy:
  /b/{id}/vnc/websockify
    → resolve_browser_session(id)
    → Redis GET browser_session:{id}
    → proxy WebSocket to container:6080
```
