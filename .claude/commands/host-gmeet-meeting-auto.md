# /host-gmeet-meeting-auto — Google Meet URL + auto-admit, no human needed

Goal: deliver a Google Meet URL with auto-admit running so bots join without human intervention.

## Cheat sheet

### 1. Browser session

```bash
# Find existing browser sessions
curl -s "http://localhost:8056/meetings" \
  -H "X-API-Key: $(curl -s "http://localhost:8056/admin/users/5" -H "X-Admin-API-Key: changeme" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_tokens'][0]['token'])")" \
  | python3 -c "
import sys,json
d = json.load(sys.stdin)
for m in d.get('meetings', d if isinstance(d,list) else []):
    if m.get('platform') == 'browser_session' and m.get('status') == 'active':
        print(f'SESSION_TOKEN={m[\"data\"][\"session_token\"]}')
        print(f'MEETING_ID={m[\"id\"]}')
        break
"

# Or create new
API_KEY=$(curl -s -X POST "http://localhost:8056/admin/users/5/tokens?scope=bot" \
  -H "X-Admin-API-Key: changeme" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -X POST "http://localhost:8056/bots" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}'
# → SESSION_TOKEN from response .data.session_token
```

### 2. Wait for CDP

```bash
CDP_URL="http://localhost:8056/b/$SESSION_TOKEN/cdp"
# Poll until 200:
curl -s -o /dev/null -w "%{http_code}" "$CDP_URL/json/version"
```

### 3. Create meeting + join

```bash
cd features/realtime-transcription/scripts && CDP_URL="$CDP_URL" node gmeet-host-auto.js
```

Outputs `MEETING_URL=`, `NATIVE_MEETING_ID=`, `JOINED=true`.

### 4. Start auto-admit

Run locally (no SSH needed — auto-admit connects via CDP):

```bash
cd features/realtime-transcription/scripts && nohup node auto-admit.js "$CDP_URL" google_meet > /tmp/auto-admit.log 2>&1 &
```

### 5. Update .env

Write `MEETING_URL` and `NATIVE_MEETING_ID` into `features/realtime-transcription/.env`.

### Done

```
MEETING_URL=https://meet.google.com/{code}
Auto-admit: running
```

## Verify

```bash
# Auto-admit running?
pgrep -af "auto-admit.js"

# Auto-admit log (look for "admitted" or "pill_clicked")
cat /tmp/auto-admit.log
```

## Teardown

```bash
# Kill auto-admit
pkill -f "auto-admit.js"

# Leave meeting
cd features/realtime-transcription/scripts && CDP_URL="$CDP_URL" node -e "
  const b = await require('playwright').chromium.connectOverCDP(process.env.CDP_URL);
  await b.contexts()[0].pages()[0].locator('button[aria-label*=\"Leave call\"]').click();"
```

## What gmeet-host-auto.js does

1. Connect CDP, check if already in meeting (reuse if so)
2. Navigate to `meet.new` which redirects to `meet.google.com/{code}`
3. Wait for URL pattern match, extract meeting code
4. Dismiss "Got it" / "Dismiss" dialogs
5. Click "Join now" (host) or "Ask to join" (fallback)
6. Verify "Leave call" button visible

## What auto-admit.js does for Google Meet

1. Connect CDP, find page with `meet.google.com` in URL
2. Poll every 3s for admit UI:
   - Confirmation dialog → click OK button
   - "Admit" / "Admit all" buttons → click
   - "Admit N guest(s)" pill → click smallest matching element
3. Tracks total admitted count, handles page navigation

## Troubleshooting

- **meet.new doesn't redirect**: Google OAuth may have expired. Check screenshot at `/tmp/gmeet-host-auto-fail.png`. Re-login via VNC at `http://localhost:8056/b/$SESSION_TOKEN`.
- **"Ask to join" instead of "Join now"**: Account doesn't own the meeting org. Should still work — you'll be in meeting after host admits.
- **Auto-admit not clicking**: Check `/tmp/auto-admit.log`. If "No meeting page found", the page may have navigated away. Restart auto-admit.
- **Bot stuck in lobby**: Auto-admit poll is 3s. If pill text doesn't match `Admit`, check Google Meet locale — script expects English UI.
- **CDP proxy 404**: Session token may be expired. Create a new browser session via POST /bots.
