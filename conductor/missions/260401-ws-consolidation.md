# Mission: Consolidate WebSocket through dashboard proxy

Focus: dashboard networking, api-gateway, WebSocket reliability
Problem: The dashboard has a split-brain networking design. HTTP goes through the Next.js proxy (`localhost:3001/api/vexa/...` → `api-gateway:8000`), but WebSocket bypasses it entirely — the browser connects directly to `localhost:8056/ws`. This creates two independent URLs, two auth mechanisms, two failure modes, and zero automated WS testing. Result: WS silently breaks on any infrastructure change and nobody notices until a user reports it.
Target: Single entry point for both HTTP and WS. If HTTP works, WS works. Automated WS smoke test catches regressions.
Stop-when: Dashboard's live transcript page connects via WS through the proxy. WS smoke test runs and passes.
Constraint: No changes to the api-gateway WS endpoint. The proxy handles routing, not protocol changes.

---

## Context: Why This Mission Exists

Discovered 2026-04-01 during packages-restructure. The restructure passed D1-D3 (build, stack, cross-imports) at confidence 80, but WS was never tested because no mission includes WS verification.

### Current architecture (split-brain)

```
HTTP:   Browser → localhost:3001 → Next.js proxy (/api/vexa/[...path]) → api-gateway:8000
WS:     Browser → localhost:8056 → api-gateway:8000/ws (BYPASSES dashboard entirely)
VNC:    Browser → localhost:3001/b/* → Next.js rewrite → api-gateway:8000/b/* (proxied correctly)
```

Problems:
1. **Two URLs to configure**: `VEXA_API_URL` (internal HTTP), `NEXT_PUBLIC_VEXA_WS_URL` (public WS). If either is wrong, one path works and the other doesn't.
2. **Two auth flows**: HTTP proxy injects auth from cookie/env. WS gets auth token from `/api/config` and passes it as query param. Different code paths, different failure modes.
3. **Browser must reach api-gateway directly**: Port 8056 must be exposed and reachable. In hosted deployments behind a reverse proxy, this requires separate WS routing rules.
4. **Zero automated testing**: No mission DoD has ever included WS verification. The confidence framework is blind to WS regressions.

### The VNC precedent

VNC/CDP browser access (`/b/*` routes) is ALREADY proxied through Next.js rewrites in `next.config.ts` (line 46-53), including WebSocket upgrade. This proves the pattern works. WS should use the same approach.

### Key files

| File | Role |
|------|------|
| `services/dashboard/next.config.ts` | Rewrites config — already proxies `/b/*` with WS upgrade |
| `services/dashboard/src/app/api/config/route.ts` | Returns `wsUrl` to browser — currently points to api-gateway directly |
| `services/dashboard/src/hooks/use-vexa-websocket.ts` | Browser WS client — connects to `wsUrl` from config, sends subscribe |
| `services/api-gateway/main.py:1864` | `@app.websocket("/ws")` — accepts WS, authenticates, subscribes to Redis |

---

## Target Architecture

```
HTTP:   Browser → localhost:3001 → Next.js proxy (/api/vexa/[...path]) → api-gateway:8000
WS:     Browser → localhost:3001/ws → Next.js rewrite → api-gateway:8000/ws
VNC:    Browser → localhost:3001/b/* → Next.js rewrite → api-gateway:8000/b/*
```

Single entry point: `localhost:3001`. No direct api-gateway access needed from browser.

---

## Phase 1: Proxy WS through dashboard

**Goal:** Add `/ws` rewrite to Next.js so the browser connects to `localhost:3001/ws` and it proxies to `api-gateway:8000/ws`.

### Tasks

- [ ] Add `/ws` rewrite to `next.config.ts` alongside the existing `/b/:path*` rewrite:
  ```ts
  { source: "/ws", destination: `${VEXA_API_URL}/ws` }
  ```
  Next.js rewrites support WebSocket upgrade — the `/b/*` rewrite already uses this.
- [ ] Update `/api/config/route.ts` — derive `wsUrl` relative to the dashboard origin, not from a separate env var:
  ```ts
  // WS goes through the same origin via rewrite
  const wsUrl = `ws://${request.headers.get('host')}/ws`;
  ```
  Or simpler: return a relative path and let the client build the URL from `window.location`.
- [ ] Update `use-vexa-websocket.ts` fallback URL — currently falls back to `ws://localhost:8066/ws`, should fall back to `ws://${window.location.host}/ws`.
- [ ] Remove `NEXT_PUBLIC_VEXA_WS_URL` from docker-compose env — no longer needed, WS URL is derived from the dashboard's own origin.

### Verify

- Open dashboard at `localhost:3001`, navigate to a meeting's live view
- Browser DevTools Network tab shows WS connection to `ws://localhost:3001/ws` (not `:8056`)
- WS connects, subscribes, receives `{"type": "subscribed"}`

---

## Phase 2: WS smoke test

**Goal:** Automated test that verifies the WS path works end-to-end.

### Tasks

- [ ] Create `tests/smoke/ws-health.py` (or .sh):
  ```python
  # 1. Connect to ws://localhost:3001/ws?api_key=<token>
  # 2. Send {"action": "subscribe", "meetings": [{"platform": "google_meet", "native_id": "smoke-test"}]}
  # 3. Expect {"type": "subscribed", "meetings": [...]}
  # 4. Send {"action": "ping"}
  # 5. Expect {"type": "pong"}
  # 6. Exit 0 if both pass, exit 1 if not
  ```
- [ ] Add WS smoke test to the standard DoD template — every mission that touches api-gateway, meeting-api, or dashboard must run it.
- [ ] Document in mission DoD pattern: "D_ws: WS smoke test passes" with weight and ceiling.

---

## Phase 3: Cleanup

**Goal:** Remove the split-brain artifacts.

### Tasks

- [ ] Remove `NEXT_PUBLIC_VEXA_WS_URL` from docker-compose, env templates, and any documentation
- [ ] Remove the env var fallback chain in `/api/config/route.ts` for WS URL derivation
- [ ] Verify no code references `NEXT_PUBLIC_VEXA_WS_URL` or hardcodes `localhost:8056/ws`

---

## DoD

| DoD | Weight | Max if FAIL | Min if PASS | Verify |
|-----|--------|-------------|-------------|--------|
| **D1. `docker compose build` passes** | **20** | **0** | 20 | `docker compose build` — zero errors |
| **D2. Dashboard loads** | **15** | **20** | 35 | `curl -s localhost:3001` → HTTP 200 with HTML |
| **D3. WS connects through proxy** | **25** | **35** | 60 | Browser DevTools: WS connects to `ws://localhost:3001/ws`, NOT `:8056`. Or: `ws-health.py` against port 3001 passes. |
| **D4. WS subscribe works** | **15** | **50** | 75 | Send subscribe message, receive `{"type": "subscribed"}` response through the proxied path |
| **D5. HTTP proxy still works** | **10** | **60** | 85 | `curl -s localhost:3001/api/vexa/bots` returns valid JSON (not 502) |
| D6. No stale NEXT_PUBLIC_VEXA_WS_URL refs | 5 | 90 | 90 | `grep -rn "NEXT_PUBLIC_VEXA_WS_URL" .` → zero hits outside git history |
| D7. WS smoke test script exists and passes | 5 | 90 | 95 | `python3 tests/smoke/ws-health.py` exits 0 |
| D8. VNC proxy still works | 5 | 90 | 100 | `/b/` routes still rewrite correctly (existing functionality preserved) |
| | **= 100** | | | |

**Critical path:** D1→D2→D3→D4 are sequential gates. Can't exceed 50 without WS actually connecting through the proxy (D3). Can't exceed 75 without subscribe working (D4).

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| Next.js rewrite doesn't upgrade to WS | The `/b/*` rewrite already supports WS upgrade — use same pattern. If it fails, use custom server middleware as fallback. |
| Auth breaks after removing direct api-gateway access | Auth token still passed as query param by the client. The rewrite is transparent — api-gateway sees the same request. |
| Hosted deployments break | Hosted deployments already route through nginx/ingress. Consolidating to one origin simplifies routing, doesn't complicate it. |
| Performance overhead of proxying WS through Next.js | Negligible — Next.js rewrites are handled by the HTTP server, not the JS runtime. The `/b/*` VNC proxy already works this way. |
