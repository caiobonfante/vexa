const { chromium } = require('playwright');

const CDP_URL = process.env.CDP_URL;
if (!CDP_URL) { console.error('CDP_URL required'); process.exit(1); }

(async () => {
  const browser = await chromium.connectOverCDP(CDP_URL);
  const context = browser.contexts()[0];
  let page = context.pages()[0] || await context.newPage();

  // --- Already in a meeting? ---
  const inMeeting = await page.locator('[aria-label="Leave"]')
    .isVisible({ timeout: 2000 }).catch(() => false);
  if (inMeeting) {
    console.log('ALREADY_IN_MEETING=true');
    console.log('PAGE_URL=' + page.url());
    return;
  }

  // --- Navigate to Meet tab ---
  if (!page.url().includes('teams.live.com') && !page.url().includes('teams.microsoft.com')) {
    await page.goto('https://teams.microsoft.com', { waitUntil: 'domcontentloaded', timeout: 15000 });
  }
  // Wait for OAuth redirects to settle and Teams UI to load
  await page.waitForURL(/teams\.live\.com/, { timeout: 30000 }).catch(() => {});
  await page.locator('button[aria-label="Meet"]').waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('button[aria-label="Meet"]').click({ timeout: 5000 });
  await page.waitForTimeout(2000);

  // --- Create meeting link ---
  await page.locator('[data-tid="create-meeting-link"]').click({ timeout: 8000 });
  const createBtn = page.locator('[data-tid="meet-app-create-meeting-link-button"]');
  await createBtn.waitFor({ state: 'visible', timeout: 8000 });
  await createBtn.click();
  await page.waitForTimeout(2000);

  // --- Capture URL via clipboard.readText (grant permission via CDP) ---
  const cdpSession = await context.newCDPSession(page);
  await cdpSession.send('Browser.grantPermissions', {
    permissions: ['clipboardReadWrite', 'clipboardSanitizedWrite'],
    origin: page.url()
  });

  // "Create and copy link" already copied — but if not, click Share link
  let meetingUrl = await page.evaluate(() =>
    navigator.clipboard.readText().catch(() => '')
  );

  if (!meetingUrl || !meetingUrl.includes('teams.live.com/meet/')) {
    // Fallback: click Share link on first card
    await page.locator('button:has-text("Share link")').first().click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(1000);
    meetingUrl = await page.evaluate(() =>
      navigator.clipboard.readText().catch(() => '')
    );
  }

  if (!meetingUrl || !meetingUrl.includes('teams.live.com/meet/')) {
    // Fallback: scan page text
    meetingUrl = await page.evaluate(() => {
      const m = document.body.innerText.match(/(https:\/\/teams\.live\.com\/meet\/[^\s]+)/);
      return m ? m[1] : '';
    });
  }

  if (!meetingUrl) {
    await page.screenshot({ path: '/tmp/teams-host-auto-fail.png' });
    console.error('SCREENSHOT=/tmp/teams-host-auto-fail.png');
    console.error('ERROR=could not capture meeting URL');
    process.exit(1);
  }

  // Parse meeting ID and passcode from URL
  const urlObj = new URL(meetingUrl);
  const nativeId = urlObj.pathname.split('/').pop();
  const passcode = urlObj.searchParams.get('p') || '';

  console.log('MEETING_URL=' + meetingUrl);
  console.log('NATIVE_MEETING_ID=' + nativeId);
  console.log('MEETING_PASSCODE=' + passcode);

  // --- Join by navigating directly to the meeting URL ---
  const pagePromise = context.waitForEvent('page', { timeout: 10000 }).catch(() => null);
  await page.goto(meetingUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
  const newPage = await pagePromise;
  const meetingPage = newPage || page;
  if (newPage) await newPage.waitForLoadState('domcontentloaded', { timeout: 10000 });

  // --- Pre-join screen: click Join now ---
  const joinNow = meetingPage.locator('button:has-text("Join now")');
  await joinNow.waitFor({ state: 'visible', timeout: 10000 });
  await meetingPage.keyboard.press('Escape'); // dismiss popups
  await joinNow.click({ timeout: 5000 });

  // --- Verify joined ---
  await meetingPage.locator('[aria-label="Leave"]')
    .waitFor({ state: 'visible', timeout: 15000 });

  console.log('JOINED=true');
  await meetingPage.screenshot({ path: '/tmp/teams-host-auto.png' });
  console.log('SCREENSHOT=/tmp/teams-host-auto.png');
})().catch(e => {
  console.error('ERROR=' + e.message);
  process.exit(1);
});
