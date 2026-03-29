# /setup-nginx-gateway — Configure nginx to proxy gateway.dev.vexa.ai to the agentic gateway

Goal: make the agentic gateway accessible at `https://gateway.dev.vexa.ai` with full WebSocket support for VNC, CDP, and real-time meeting events. This is required for the dashboard to work with browser sessions when accessed through SSH tunnels.

## What it does

Adds/updates nginx server blocks so `gateway.dev.vexa.ai` on port 443 proxies to the agentic gateway on `:8066` with:
- HTTP proxy for all API routes
- WebSocket upgrade for `/ws` (real-time events)
- WebSocket upgrade for `/b/*/vnc/websockify` (noVNC)
- WebSocket upgrade for `/b/*/cdp` (Chrome DevTools Protocol)

## Check current state

```bash
# Which port does gateway.dev.vexa.ai proxy to?
sudo nginx -T 2>/dev/null | grep -A5 "server_name gateway.dev.vexa.ai" | grep proxy_pass

# Does it work?
curl -sk -o /dev/null -w "%{http_code}" "https://gateway.dev.vexa.ai/"
# 200 or 404 = working, 502 = upstream down, no response = nginx block missing
```

## Fix if needed

The gateway.dev.vexa.ai block in `/etc/nginx/sites-enabled/vexa.ai` must:
1. Listen on port 443 (for browser access) — not just 8443
2. Proxy to `http://0.0.0.0:8066` (agentic gateway)
3. Have WebSocket locations for `/ws`, `/b/*/vnc/websockify`, `/b/*/cdp`

```bash
# Check if port 443 block exists for gateway
sudo nginx -T 2>/dev/null | grep -B2 "server_name gateway.dev.vexa.ai" | grep "listen"
# Should show: listen 443 ssl; AND listen 127.0.0.1:8443 ssl;

# If missing the 443 block, add it (see /tmp/nginx-gateway-443.conf pattern)
```

## Dashboard env

The dashboard must use `gateway.dev.vexa.ai` as its public API URL:

```bash
# In services/dashboard/.env:
NEXT_PUBLIC_VEXA_API_URL=https://gateway.dev.vexa.ai
NEXT_PUBLIC_VEXA_WS_URL=wss://gateway.dev.vexa.ai/ws
```

## Verify

```bash
# API through nginx
curl -sk -o /dev/null -w "%{http_code}" "https://gateway.dev.vexa.ai/bots/status" -H "X-API-Key: <token>"
# → 200

# VNC HTML through nginx (needs active browser session token)
curl -sk -o /dev/null -w "%{http_code}" "https://gateway.dev.vexa.ai/b/<session_token>/vnc/vnc.html"
# → 200

# CDP through nginx
curl -sk -o /dev/null -w "%{http_code}" "https://gateway.dev.vexa.ai/b/<session_token>/cdp/json/version"
# → 200

# Dashboard config returns correct publicApiUrl
curl -s "http://localhost:3001/api/config" | python3 -c "import sys,json; print(json.load(sys.stdin)['publicApiUrl'])"
# → https://gateway.dev.vexa.ai
```
