# /host-teams-meeting — Create and host a Teams meeting with auto-admission

Host a Teams meeting from the remote browser session. Creates a meeting (or reuses an existing one), joins as organizer, and runs auto-admit to let bots through the lobby.

## Prerequisites

- Remote browser session running with Teams signed in (Speaker D account)
- CDP URL available at `http://localhost:8066/b/{token}/cdp`

## Remote workspace

The browser container has scripts at `/workspace/scripts/`:
- `auto-admit-all.js` — Polls for lobby participants and admits them (Teams + Google Meet)
- `auto-admit.js` — Google Meet specific auto-admit

Playwright is installed at `/workspace/node_modules/playwright`.

## Step 1: Connect to remote browser via CDP

```javascript
const { chromium } = require('playwright');
const CDP_URL = 'http://localhost:8066/b/{token}/cdp';
const browser = await chromium.connectOverCDP(CDP_URL);
const page = browser.contexts()[0].pages()[0];
```

## Step 2: Check if already in a meeting

Before creating a new meeting, check if the browser is already in one:

```javascript
const url = page.url();
// If URL contains teams.live.com and we see meeting UI (timer, Leave button), reuse it
const inMeeting = await page.locator('button:has-text("Leave"), [aria-label="Leave"]').isVisible({ timeout: 2000 }).catch(() => false);
```

If already in a meeting, skip to Step 5 (auto-admit).

## Step 3: Navigate to Meet and create a meeting link

```javascript
// Go to Teams
await page.goto('https://teams.microsoft.com', { waitUntil: 'load', timeout: 30000 });
await page.waitForTimeout(5000);

// Click Meet sidebar
await page.locator('[data-tid="app-bar-Meet"]').click({ timeout: 10000 });
await page.waitForTimeout(3000);

// Click "Create a meeting link"
await page.locator('button:has-text("Create a meeting link")').click({ timeout: 10000 });
await page.waitForTimeout(2000);

// Name the meeting
const nameInput = page.locator('input').first();
await nameInput.fill('Speaker Attribution Test');

// Intercept clipboard to capture the URL
await page.evaluate(() => {
  window.__lastCopied = '';
  const orig = navigator.clipboard.writeText.bind(navigator.clipboard);
  navigator.clipboard.writeText = async (text) => { window.__lastCopied = text; return orig(text); };
});

// Click "Create and copy link"
await page.locator('button:has-text("Create and copy link")').click({ timeout: 5000 });
await page.waitForTimeout(2000);

// Get the meeting URL from clipboard intercept
const meetingUrl = await page.evaluate(() => window.__lastCopied);
// Format: https://teams.live.com/meet/NNNN?p=XXXX
```

If "Share link" was used instead of create, re-intercept clipboard and click "Share link" on the meeting card.

## Step 4: Join as host

```javascript
// Click Join on the meeting card
await page.locator('text="Join"').first().click({ timeout: 5000 });
await page.waitForTimeout(5000);

// Pre-join screen appears — dismiss mic popup and click Join now
await page.keyboard.press('Escape'); // dismiss any popup
await page.locator('button:has-text("Join now")').click({ timeout: 5000 });
await page.waitForTimeout(5000);
// Now in meeting: "Waiting for others to join..."
```

## Step 5: Run auto-admit (on remote container)

SSH into the remote container and run the auto-admit script:

```bash
sshpass -p '{token}' ssh -o StrictHostKeyChecking=no root@localhost -p {ssh_port} \
  "cd /workspace && node scripts/auto-admit-all.js http://localhost:9222"
```

Or via CDP from local:

```javascript
// The auto-admit-all.js script on the remote container handles both Teams and Google Meet.
// It polls every 2 seconds for lobby participants and clicks:
//   Teams: button[aria-label="Admit participant in lobby"], "Admit all", "Allow", "Let in"
//   Meet: "Admit", "Admit all", "View all" -> "Admit all"
```

**Key Teams selectors for admission:**
- Lobby participants: `[data-tid^="participantsInLobby-"]`
- Admit individual: `button[aria-label="Admit participant in lobby"]`
- Admit all: `button:has-text("Admit all")`
- View lobby toast: `button:has-text("View lobby")`

## Step 6: Get meeting URL for bots

The meeting URL from Step 3 is what bots use to join:

```bash
curl -X POST http://localhost:8066/bots \
  -H "X-API-Key: {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "teams",
    "native_meeting_id": "{meeting_id}",
    "meeting_url": "https://teams.live.com/meet/{meeting_id}?p={passcode}"
  }'
```

## Important: PiP mode

When clicking sidebar items (Chat, People, etc.) while in a meeting, Teams enters PiP mode — the meeting shrinks to a small window in the top-left. The meeting continues running. To expand back to full meeting view, click the expand icon in the PiP window.

The People panel in the meeting toolbar (top bar: Chat, People, Raise, React, View, More) is DIFFERENT from the People sidebar. Use the toolbar buttons for in-meeting controls.

## Learned (2026-03-19)

- `Create a meeting link` → dialog with title input + "Create and copy link" → copies URL to clipboard
- URL format: `https://teams.live.com/meet/{numeric_id}?p={passcode}`
- `Share link` button on meeting cards also copies URL to clipboard (no visible UI)
- The `...` menu on meeting cards only has "Hide" — no URL display
- Pre-join screen: Camera preview, audio options (Computer/Phone/Don't use), Cancel + Join now
- In-meeting toolbar: Chat, People, Raise, React, View, More, Camera, Mic, Share, Leave
- Meeting shows "Waiting for others to join..." when host is alone
- Auto-admit script on remote uses internal CDP `http://localhost:9222` (inside container)
- Clipboard intercept works: override `navigator.clipboard.writeText` BEFORE the click
- **Lobby toast**: Shows "Waiting in the lobby" / "Listener (Guest)" with Deny + Admit buttons
- **Auto-admit issue**: `[data-tid^="participantsInLobby-"]` selector doesn't match — the toast has plain `button:has-text("Admit")`
- **Meeting toolbar More button**: `id="callingButtons-showMoreBtn"`, `aria-label="More"`
- **Guest vs Host More menu is DIFFERENT**:
  - Host: Start recording, Meeting info, Timer, Video effects, Audio settings, **Language and speech** → Show live captions
  - Guest: Listener, Speaker D, Meeting info, Devices, Video effects, **Captions**, Don't show chat bubbles, Accessibility
- **Captions for guest**: Direct "Captions" menu item (no submenu), role="menuitem"
- **Audio tracks**: Teams delivers tracks with `muted=true` initially — this is normal WebRTC behavior, tracks unmute when remote sends audio
