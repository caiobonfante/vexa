# /host-teams-meeting — Create and host a Teams meeting with auto-admission

Create a Teams meeting from a remote browser session, join as host, run auto-admit, and output the meeting URL for downstream skills.

## Inputs

- `API_GATEWAY_URL` — from feature `.env` or default `http://localhost:8066`
- `USER_EMAIL` — defaults to `2280905@gmail.com`
- `ADMIN_API_KEY` — defaults to `changeme`

## Execution

Run these steps sequentially. Stop on failure and report the error.

### Step 1: Find or create a browser session

Check for an active browser session for the user. If none exists, create one.

```bash
# Get user list to find user ID
USERS=$(curl -s "$API_GATEWAY_URL/../admin/users" -H "X-Admin-API-Key: $ADMIN_API_KEY" 2>/dev/null || \
        curl -s "http://localhost:8067/admin/users" -H "X-Admin-API-Key: $ADMIN_API_KEY")
# Parse USER_ID for USER_EMAIL from the JSON

# Check for active browser_session meetings
MEETINGS=$(curl -s "http://localhost:8067/admin/users/$USER_ID" -H "X-Admin-API-Key: $ADMIN_API_KEY")
# Look for meetings with platform=browser_session and status=active

# If an active session exists, get its session_token and ssh_port from meeting.data
# If no active session, create an API token and start one:
TOKEN_RESP=$(curl -s -X POST "http://localhost:8067/admin/users/$USER_ID/tokens?scope=bot" \
  -H "X-Admin-API-Key: $ADMIN_API_KEY")
API_KEY=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

SESSION_RESP=$(curl -s -X POST "$API_GATEWAY_URL/bots" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}')
# Extract session_token, ssh_port from response
```

Wait for the container to be ready (up to 30s):
```bash
# Poll the CDP endpoint until it responds
CDP_URL="$API_GATEWAY_URL/b/$SESSION_TOKEN/cdp"
# curl -s "$CDP_URL/../json/version" until it returns HTTP 200
```

**Output from Step 1:** `SESSION_TOKEN`, `SSH_PORT`, `CDP_URL`, `API_KEY`

### Step 2: Connect via CDP and create a meeting

Write a Playwright script in the vexa-bot directory (where playwright is installed) and run it.

**IMPORTANT:** Use `chromium.connectOverCDP(CDP_URL)` where CDP_URL goes through the API gateway proxy: `http://localhost:8066/b/{SESSION_TOKEN}/cdp`. Do NOT use the container's internal IP directly.

```javascript
// teams-host.js — run from /home/dima/dev/vexa-restore/services/vexa-bot/
const { chromium } = require('playwright');
const CDP_URL = process.env.CDP_URL;

(async () => {
  const browser = await chromium.connectOverCDP(CDP_URL);
  const context = browser.contexts()[0];
  const page = context.pages()[0] || await context.newPage();

  // Check if already in a meeting (Leave button visible)
  const inMeeting = await page.locator('button:has-text("Leave"), [aria-label="Leave"]')
    .isVisible({ timeout: 2000 }).catch(() => false);

  if (inMeeting) {
    // Already in a meeting — extract URL from page
    const url = page.url();
    console.log('ALREADY_IN_MEETING=true');
    console.log('MEETING_PAGE_URL=' + url);
  } else {
    // Navigate to Teams Meet tab
    await page.goto('https://teams.microsoft.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);

    // Click Meet in sidebar
    await page.locator('button[aria-label="Meet"]').click({ timeout: 10000 });
    await page.waitForTimeout(3000);

    // Intercept clipboard BEFORE clicking create
    await page.evaluate(() => {
      window.__lastCopied = '';
      const orig = navigator.clipboard.writeText.bind(navigator.clipboard);
      navigator.clipboard.writeText = async (text) => {
        window.__lastCopied = text;
        return orig(text);
      };
    });

    // Click "Create a meeting link"
    await page.locator('[data-tid="create-meeting-link"]').click({ timeout: 10000 });
    await page.waitForTimeout(2000);

    // Click "Create and copy link" (appears in the panel)
    await page.locator('[data-tid="meet-app-create-meeting-link-button"]').click({ timeout: 10000 });
    await page.waitForTimeout(3000);

    // Get meeting URL from clipboard intercept
    const meetingUrl = await page.evaluate(() => window.__lastCopied);
    console.log('MEETING_URL=' + meetingUrl);

    // Now join the meeting — click Join on the first (newest) meeting card
    await page.locator('button:has-text("Join")').first().click({ timeout: 5000 });
    await page.waitForTimeout(5000);

    // Pre-join screen — dismiss any popups and click Join now
    await page.keyboard.press('Escape');
    await page.waitForTimeout(1000);
    await page.locator('button:has-text("Join now")').click({ timeout: 10000 });
    await page.waitForTimeout(5000);

    console.log('JOINED=true');
  }

  // Take confirmation screenshot
  await page.screenshot({ path: '/tmp/teams-host-result.png' });
  console.log('SCREENSHOT=/tmp/teams-host-result.png');
})().catch(e => { console.error('ERROR=' + e.message); process.exit(1); });
```

Run this script:
```bash
cd /home/dima/dev/vexa-restore/services/vexa-bot && CDP_URL="$CDP_URL" node teams-host.js
```

Parse `MEETING_URL` from stdout. The format is: `https://teams.live.com/meet/{ID}?p={PASSCODE}`

**If the create panel doesn't appear** (the button click doesn't show "Create and copy link"), take a screenshot, diagnose, and retry. The Meet tab must be fully loaded first.

### Step 3: Verify host is in the meeting

Read the screenshot at `/tmp/teams-host-result.png`. You should see:
- "Waiting for others to join..." or the meeting UI with toolbar
- Timer running in the top area

If NOT in the meeting, check for:
- Pre-join screen still showing → click "Join now" again
- Error dialog → screenshot and report

### Step 4: Start auto-admit

SSH into the browser container and run auto-admit in the background:

```bash
sshpass -p "$SESSION_TOKEN" ssh -o StrictHostKeyChecking=no root@localhost -p $SSH_PORT \
  "cd /workspace && nohup node scripts/auto-admit-all.js http://localhost:9222 > /tmp/auto-admit.log 2>&1 &"
```

Verify it started:
```bash
sshpass -p "$SESSION_TOKEN" ssh -o StrictHostKeyChecking=no root@localhost -p $SSH_PORT \
  "pgrep -f auto-admit-all && echo 'AUTO_ADMIT=running' || echo 'AUTO_ADMIT=failed'"
```

### Step 5: Output

Log the final result:

```
MEETING READY
  URL: https://teams.live.com/meet/{ID}?p={PASSCODE}
  Host: Speaker D (2280905@gmail.com)
  Auto-admit: running
  Session token: {SESSION_TOKEN}
  SSH: ssh root@localhost -p {SSH_PORT}
```

The meeting URL can be used by downstream skills to send bots:
```bash
curl -s -X POST "$API_GATEWAY_URL/bots" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"platform\":\"teams\",\"native_meeting_id\":\"{ID}\",\"meeting_url\":\"$MEETING_URL\"}"
```

## Error handling

- **CDP connection timeout:** Container may still be starting. Wait 10s and retry (max 3 attempts).
- **Teams not logged in:** If page shows login form instead of Teams UI, report error — user must VNC in and log in manually.
- **"Create and copy link" not visible:** The create panel may not open on first click. Screenshot, close panel (`[data-tid="meet-app-close-create-meeting-link-panel"]`), and retry.
- **Pre-join screen stuck:** Try clicking "Join now" multiple times with 2s waits. Check for mic/camera permission dialogs.
- **Auto-admit not starting:** Check if `/workspace/scripts/auto-admit-all.js` exists. If not, the workspace git sync may have failed.

## Cleanup

When testing is done, leave the meeting:
```javascript
await page.locator('button:has-text("Leave")').click();
```

The browser session stays alive for reuse. Stop it via:
```bash
curl -s -X POST "$API_GATEWAY_URL/bots/{MEETING_ID}/stop" -H "X-API-Key: $API_KEY"
```
