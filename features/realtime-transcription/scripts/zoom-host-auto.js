const { chromium } = require('playwright');

const CDP_URL = process.env.CDP_URL;
if (!CDP_URL) { console.error('CDP_URL required'); process.exit(1); }

(async () => {
  console.log('Connecting to ' + CDP_URL + '...');
  const browser = await chromium.connectOverCDP(CDP_URL);
  const context = browser.contexts()[0];
  let page = context.pages().find(p => p.url().includes('zoom.us'))
    || context.pages()[0]
    || await context.newPage();
  console.log('Using page: ' + page.url().substring(0, 80));

  // --- Already in a Zoom meeting? ---
  const inMeeting = await page.locator('button[aria-label="Leave"]')
    .isVisible({ timeout: 2000 }).catch(() => false);
  if (inMeeting) {
    const url = page.url();
    const meetingId = url.match(/\/wc\/(\d+)\//)?.[1] || '';
    console.log('ALREADY_IN_MEETING=true');
    console.log('MEETING_URL=' + url);
    console.log('NATIVE_MEETING_ID=' + meetingId);
    return;
  }

  // --- Create instant meeting via zoom.us/start ---
  console.log('Navigating to zoom.us/start/videomeeting...');
  await page.goto('https://zoom.us/start/videomeeting', { waitUntil: 'domcontentloaded', timeout: 30000 });

  // Zoom may redirect through auth pages; wait for either web client or launch page
  // zoom.us/start redirects to: app.zoom.us/wc/{id}/start or a "launch meeting" page
  await page.waitForTimeout(5000);

  let currentUrl = page.url();
  console.log('After redirect: ' + currentUrl);

  // If we landed on a "launch meeting" page, look for "Join from Your Browser" link
  if (!currentUrl.includes('/wc/')) {
    const browserLink = page.locator('a:has-text("Join from Your Browser"), a:has-text("join from your browser"), a:has-text("Start from your browser")').first();
    const linkVisible = await browserLink.isVisible({ timeout: 5000 }).catch(() => false);
    if (linkVisible) {
      await browserLink.click();
      console.log('Clicked "Join from Your Browser"');
      await page.waitForTimeout(3000);
      currentUrl = page.url();
    }
  }

  // Wait for web client URL pattern
  try {
    await page.waitForURL(/zoom\.us\/wc\/\d+/, { timeout: 20000 });
  } catch {
    // May already be there or on a different Zoom domain
    currentUrl = page.url();
    if (!currentUrl.includes('/wc/')) {
      await page.screenshot({ path: '/tmp/zoom-host-auto-fail.png' });
      console.error('SCREENSHOT=/tmp/zoom-host-auto-fail.png');
      console.error('ERROR=could not reach Zoom web client. URL: ' + currentUrl);
      process.exit(1);
    }
  }

  currentUrl = page.url();
  const meetingId = currentUrl.match(/\/wc\/(\d+)\//)?.[1] || '';
  const pwd = new URL(currentUrl).searchParams.get('pwd') || '';

  if (!meetingId) {
    await page.screenshot({ path: '/tmp/zoom-host-auto-fail.png' });
    console.error('SCREENSHOT=/tmp/zoom-host-auto-fail.png');
    console.error('ERROR=could not extract meeting ID from URL: ' + currentUrl);
    process.exit(1);
  }

  // Build the join URL that bots will use
  let joinUrl = 'https://app.zoom.us/wc/' + meetingId + '/join';
  if (pwd) joinUrl += '?pwd=' + pwd;

  // Also build a standard invite URL for bot-manager
  let inviteUrl = 'https://zoom.us/j/' + meetingId;
  if (pwd) inviteUrl += '?pwd=' + pwd;

  console.log('MEETING_URL=' + inviteUrl);
  console.log('NATIVE_MEETING_ID=' + meetingId);
  if (pwd) console.log('MEETING_PASSWORD=' + pwd);

  // --- Handle pre-join: permission dialogs, name, join ---
  // Dismiss permission dialogs (Allow or Continue without)
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const allowBtn = page.locator('button:has-text("Allow")').first();
      if (await allowBtn.isVisible({ timeout: 2000 })) {
        await allowBtn.click();
        console.log('Granted permission (attempt ' + (attempt + 1) + ')');
        await page.waitForTimeout(600);
        continue;
      }
      const dismissBtn = page.locator('button:has-text("Continue without")').first();
      if (await dismissBtn.isVisible({ timeout: 1000 })) {
        await dismissBtn.click();
        await page.waitForTimeout(600);
      } else {
        break;
      }
    } catch { break; }
  }

  // Wait for name input (pre-join page)
  const nameInput = page.locator('#input-for-name');
  const nameVisible = await nameInput.isVisible({ timeout: 5000 }).catch(() => false);
  if (nameVisible) {
    // As host, name may be pre-filled; leave it
    console.log('Pre-join page detected');
  }

  // Click Join/Start button
  const joinBtn = page.locator('button.preview-join-button, button:has-text("Join"), button:has-text("Start Meeting")').first();
  await joinBtn.waitFor({ state: 'visible', timeout: 10000 });
  console.log('Clicking Join/Start...');
  await joinBtn.click({ timeout: 5000 });

  // --- Verify joined (Leave button appears) ---
  await page.locator('button[aria-label="Leave"]')
    .waitFor({ state: 'visible', timeout: 20000 });

  // Join audio as host
  try {
    const computerAudioBtn = page.locator([
      'button:has-text("Join with Computer Audio")',
      'button:has-text("Join Audio by Computer")',
      'button:has-text("Computer Audio")',
    ].join(', ')).first();
    if (await computerAudioBtn.isVisible({ timeout: 3000 })) {
      await computerAudioBtn.click();
      console.log('Joined computer audio');
    }
  } catch { /* may auto-join audio */ }

  console.log('JOINED=true');
  await page.screenshot({ path: '/tmp/zoom-host-auto.png' });
  console.log('SCREENSHOT=/tmp/zoom-host-auto.png');
})().catch(e => {
  console.error('ERROR=' + e.message);
  process.exit(1);
});
