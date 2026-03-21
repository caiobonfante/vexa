# /host-teams-meeting-auto — Meeting URL + auto-admit, no human needed

Goal: deliver a Teams meeting URL with auto-admit running so bots join without human intervention.

## Cheat sheet

### 1. Browser session

```bash
# Find existing
curl -s "http://localhost:8067/admin/users/5" -H "X-Admin-API-Key: changeme"
# → look for platform=browser_session, status=active → get session_token, ssh_port from .data

# Or create new
API_KEY=$(curl -s -X POST "http://localhost:8067/admin/users/5/tokens?scope=bot" \
  -H "X-Admin-API-Key: changeme" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -X POST "http://localhost:8066/bots" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}'
# → SESSION_TOKEN and SSH_PORT from response .data
```

### 2. Wait for CDP

```bash
CDP_URL="http://localhost:8066/b/$SESSION_TOKEN/cdp"
# Poll until 200:
curl -s -o /dev/null -w "%{http_code}" "$CDP_URL/json/version"
```

### 3. Create meeting + join

```bash
cd features/realtime-transcription/scripts && CDP_URL="$CDP_URL" node teams-host-auto.js
```

Outputs `MEETING_URL=`, `NATIVE_MEETING_ID=`, `MEETING_PASSCODE=`, `JOINED=true`.

### 4. Start auto-admit

```bash
sshpass -p "$SESSION_TOKEN" ssh -o StrictHostKeyChecking=no root@localhost -p $SSH_PORT \
  "cd /workspace && nohup node scripts/auto-admit-all.js http://localhost:9222 > /tmp/auto-admit.log 2>&1 &"
```

### 5. Update .env

Write `MEETING_URL`, `NATIVE_MEETING_ID`, `MEETING_PASSCODE` into `features/realtime-transcription/.env`.

### Done

```
MEETING_URL=https://teams.live.com/meet/{id}?p={passcode}
Auto-admit: running
```

## Verify

```bash
# Auto-admit running?
sshpass -p "$SESSION_TOKEN" ssh -o StrictHostKeyChecking=no root@localhost -p $SSH_PORT "pgrep -af auto-admit"

# Auto-admit log (look for "[✓] Clicked: [Teams] Admit (toast)")
sshpass -p "$SESSION_TOKEN" ssh -o StrictHostKeyChecking=no root@localhost -p $SSH_PORT "cat /tmp/auto-admit.log"
```

## Teardown

```bash
# Kill auto-admit
sshpass -p "$SESSION_TOKEN" ssh ... "pkill -f auto-admit"

# Leave meeting
cd services/vexa-bot && CDP_URL="$CDP_URL" node -e "
  const b = await require('playwright').chromium.connectOverCDP(process.env.CDP_URL);
  await b.contexts()[0].pages()[0].locator('[aria-label=\"Leave\"]').click();"
```

## What teams-host-auto.js does

1. Connect CDP, check if already in meeting (reuse if so)
2. Navigate to Teams, wait for OAuth redirects
3. Meet tab → Create a meeting link → Create and copy link
4. Read URL via `clipboard.readText()` (CDP permission grant — writeText intercept does NOT work)
5. Navigate directly to meeting URL (don't click Join on card — hits wrong button)
6. Click "Join now" on pre-join screen
7. Verify Leave button visible

## Tested 2026-03-21

- Meeting created + joined in ~15s
- Auto-admit admitted bot within 20s of lobby arrival
