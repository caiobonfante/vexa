# /test-dashboard-auth — Run Playwright E2E tests for dashboard token management via remote browser

Goal: verify dashboard profile page shows scopes, name, last_used, expires for tokens; create/revoke flows work.

## Prerequisites

- Agentic stack running (gateway on :8066, admin-api, bot-manager)
- Dashboard accessible from the remote browser (see step 1)
- Playwright installed in `services/dashboard/`

## Setup

### 1. Determine dashboard URL for the remote browser

The remote browser runs inside Docker on the `vexa-agentic_vexa_agentic` network. The dashboard must be reachable from inside that network.

**Option A: Dashboard running on host (dev server)**
```bash
# Start dashboard dev server if not running
cd services/dashboard && npm run dev &

# Get the Docker gateway IP (host IP from container perspective)
DOCKER_GATEWAY=$(docker network inspect vexa-agentic_vexa_agentic --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}')
DASHBOARD_URL="http://${DOCKER_GATEWAY}:3001"
echo "Dashboard URL for remote browser: $DASHBOARD_URL"
```

**Option B: Dashboard container on agentic network**
```bash
DASHBOARD_URL="http://dashboard:3000"
```

### 2. Get/create browser session

```bash
ADMIN_KEY="vexa-admin-token"
GATEWAY="http://localhost:8066"

# Create a bot-scoped API key for user 5
API_KEY=$(curl -s -X POST "$GATEWAY/admin/users/5/tokens?scope=bot" \
  -H "X-Admin-API-Key: $ADMIN_KEY" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Create browser session
SESSION_DATA=$(curl -s -X POST "$GATEWAY/bots" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}')

SESSION_TOKEN=$(echo "$SESSION_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['session_token'])")
echo "Session token: $SESSION_TOKEN"
echo "VNC view: $GATEWAY/b/$SESSION_TOKEN"
```

### 3. Wait for CDP to be ready

```bash
CDP_URL="$GATEWAY/b/$SESSION_TOKEN/cdp"
for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$CDP_URL/json/version")
  if [ "$STATUS" = "200" ]; then
    echo "CDP ready at $CDP_URL"
    break
  fi
  echo "Waiting for CDP... ($i/30)"
  sleep 2
done
```

## Run Playwright tests

```bash
cd services/dashboard

# Run the dashboard auth Playwright tests via CDP
# Uses tsx to run TypeScript directly; playwright is imported as a library (not @playwright/test runner)
DASHBOARD_URL="$DASHBOARD_URL" \
CDP_URL="$CDP_URL" \
ADMIN_KEY="$ADMIN_KEY" \
GATEWAY="$GATEWAY" \
  npx tsx ../../features/auth-and-limits/tests/dashboard.spec.ts
```

The test file connects via `playwright.chromium.connectOverCDP(cdpUrl)` — it does NOT launch a local browser. It's a standalone script, not a Playwright Test runner config.

## Verify

After tests run, check output for:
- All tests passed (key list loads, scope badges visible, create flow, revoke flow)
- No timeouts (if timeout, check VNC view for visual debugging)

```bash
# Visual debugging — open VNC to see what the browser shows
echo "VNC: $GATEWAY/b/$SESSION_TOKEN"
```

## Teardown

```bash
# Stop browser session
curl -s -X POST "$GATEWAY/bots/stop" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d "{\"session_token\": \"$SESSION_TOKEN\"}"
```

## Troubleshooting

- **Dashboard not reachable from browser**: Check gateway IP with `docker network inspect vexa-agentic_vexa_agentic`. Try `http://<gateway-ip>:3001`.
- **CDP connection refused**: Session may not be started yet. Check `curl $CDP_URL/json/version`.
- **Login required**: Dashboard may need auth. The test should handle login or use a pre-authenticated session.
- **Playwright not found**: Run `cd services/dashboard && npm install` to install deps.
- **Tests timeout**: Check VNC view at `$GATEWAY/b/$SESSION_TOKEN` to see browser state.
