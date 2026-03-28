const { chromium } = require('playwright');

const CDP_URL = process.env.CDP_URL;
if (!CDP_URL) { console.error('CDP_URL required'); process.exit(1); }

(async () => {
  console.log('Connecting to ' + CDP_URL + '...');
  const browser = await chromium.connectOverCDP(CDP_URL);
  const context = browser.contexts()[0];
  let page = context.pages().find(p => p.url().includes('meet.google.com') || p.url().includes('meet.new'))
    || context.pages()[0]
    || await context.newPage();
  console.log('Using page: ' + page.url().substring(0, 80));

  // --- Already in a meeting? ---
  const inMeeting = await page.locator('button[aria-label*="Leave call"]')
    .isVisible({ timeout: 2000 }).catch(() => false);
  if (inMeeting) {
    const url = page.url();
    const meetingCode = url.match(/meet\.google\.com\/([a-z]+-[a-z]+-[a-z]+)/)?.[1] || '';
    console.log('ALREADY_IN_MEETING=true');
    console.log('MEETING_URL=https://meet.google.com/' + meetingCode);
    console.log('NATIVE_MEETING_ID=' + meetingCode);
    return;
  }

  // --- Create a new meeting via meet.new ---
  console.log('Navigating to meet.new...');
  await page.goto('https://meet.new', { waitUntil: 'domcontentloaded', timeout: 30000 });

  // meet.new redirects to meet.google.com/{code} — wait for the code in the URL
  await page.waitForURL(/meet\.google\.com\/[a-z]+-[a-z]+-[a-z]+/, { timeout: 30000 });
  await page.waitForTimeout(3000);

  const meetingUrl = page.url();
  const meetingCode = meetingUrl.match(/meet\.google\.com\/([a-z]+-[a-z]+-[a-z]+)/)?.[1] || '';

  if (!meetingCode) {
    await page.screenshot({ path: '/tmp/gmeet-host-auto-fail.png' });
    console.error('SCREENSHOT=/tmp/gmeet-host-auto-fail.png');
    console.error('ERROR=could not extract meeting code from URL: ' + meetingUrl);
    process.exit(1);
  }

  console.log('MEETING_URL=https://meet.google.com/' + meetingCode);
  console.log('NATIVE_MEETING_ID=' + meetingCode);

  // --- Check if auto-joined (meet.new sometimes skips pre-join) ---
  const alreadyJoined = await page.locator('button[aria-label*="Leave call"]')
    .isVisible({ timeout: 3000 }).catch(() => false);

  if (!alreadyJoined) {
    // --- Pre-join screen: dismiss popups, click Join ---
    await page.waitForTimeout(2000);

    // Dismiss "Got it" or similar dialogs
    await page.locator('button:has-text("Got it")').click({ timeout: 3000 }).catch(() => {});
    await page.locator('button:has-text("Dismiss")').click({ timeout: 2000 }).catch(() => {});

    // Click "Join now" (host gets this) or "Ask to join" (fallback)
    const joinBtn = page.locator('button:has-text("Join now"), button:has-text("Ask to join")').first();
    await joinBtn.waitFor({ state: 'visible', timeout: 10000 });
    console.log('Clicking Join...');
    await joinBtn.click({ timeout: 5000 });

    // --- Verify joined (Leave call button appears) ---
    await page.locator('button[aria-label*="Leave call"]')
      .waitFor({ state: 'visible', timeout: 15000 });
  } else {
    console.log('AUTO_JOINED=true');
  }

  console.log('JOINED=true');
  await page.screenshot({ path: '/tmp/gmeet-host-auto.png' });
  console.log('SCREENSHOT=/tmp/gmeet-host-auto.png');
})().catch(e => {
  console.error('ERROR=' + e.message);
  process.exit(1);
});
