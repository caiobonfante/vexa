const { chromium } = require('playwright');
const CDP_URL = process.argv[2] || 'http://localhost:9222';
const PLATFORM = process.argv[3] || 'auto'; // 'google_meet', 'teams', or 'auto'
const POLL_INTERVAL = 3000;

function detectPlatform(url) {
  if (url.includes('meet.google.com')) return 'google_meet';
  if (url.includes('teams.live.com') || url.includes('teams.microsoft.com')) return 'teams';
  return null;
}

async function tryAdmitGoogleMeet(page) {
  // Use Playwright locators — Google Meet's UI elements are not accessible via
  // plain DOM queries (page.evaluate). Use getByRole/getByText which work reliably.
  try {
    // 1. "Admit all" button (visible after people panel or pill click)
    const admitAll = page.getByRole('button', { name: 'Admit all' });
    if (await admitAll.isVisible({ timeout: 500 }).catch(() => false)) {
      await admitAll.click();
      return 'admitted';
    }

    // 2. Individual "Admit <name>" button (aria-label="Admit <name>")
    const admitOne = page.getByRole('button', { name: /^Admit / });
    if (await admitOne.first().isVisible({ timeout: 500 }).catch(() => false)) {
      await admitOne.first().click();
      return 'admitted';
    }

    // 3. "Admit N guest(s)" pill in top-right — click to expand the panel
    const pill = page.locator('text=/Admit \\d+ guest/').first();
    if (await pill.isVisible({ timeout: 500 }).catch(() => false)) {
      await pill.click();
      return 'pill_clicked';
    }

    // 4. Confirmation dialog "OK" button
    const dialogOk = page.locator('button[data-mdc-dialog-action="ok"]');
    if (await dialogOk.isVisible({ timeout: 500 }).catch(() => false)) {
      await dialogOk.click();
      return 'dialog_confirmed';
    }

    return 'none';
  } catch {
    return 'error';
  }
}

async function tryAdmitTeams(page) {
  return await page.evaluate(() => {
    // Teams: "Someone is waiting in the lobby" notification -> click Admit/View lobby
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      const text = (btn.textContent || '').trim().toLowerCase();
      if ((text === 'admit' || text === 'admit all' || text === 'view lobby') && btn.offsetParent) {
        btn.click();
        return text.includes('view') ? 'lobby_opened' : 'admitted';
      }
    }

    // Teams: lobby notification banner with Admit button
    const admitBtns = document.querySelectorAll('[data-tid*="lobby"] button, [aria-label*="Admit"]');
    for (const btn of admitBtns) {
      if (btn.offsetParent) {
        btn.click();
        return 'admitted';
      }
    }

    // Teams: People panel individual admit buttons
    const allBtns = document.querySelectorAll('button[aria-label*="dmit"]');
    for (const btn of allBtns) {
      if (btn.offsetParent) {
        btn.click();
        return 'admitted';
      }
    }

    return 'none';
  }).catch(() => 'error');
}

async function main() {
  console.log('Connecting to ' + CDP_URL);
  const browser = await chromium.connectOverCDP(CDP_URL, { timeout: 15000 });
  const ctx = browser.contexts()[0];

  // Find the meeting page
  let platform = PLATFORM;
  let page = null;

  for (const p of ctx.pages()) {
    const url = p.url();
    const detected = detectPlatform(url);
    if (detected) {
      if (platform === 'auto' || platform === detected) {
        page = p;
        platform = detected;
        break;
      }
    }
  }

  if (!page) {
    console.error('No meeting page found (tried: ' + ctx.pages().map(p => p.url()).join(', ') + ')');
    process.exit(1);
  }

  const tryAdmit = platform === 'teams' ? tryAdmitTeams : tryAdmitGoogleMeet;
  const platformLabel = platform === 'teams' ? 'Teams' : 'Google Meet';

  console.log(platformLabel + ' meeting: ' + page.url());
  console.log('Auto-admit running every ' + (POLL_INTERVAL / 1000) + 's');
  let total = 0;

  process.on('SIGTERM', async () => { await browser.close(); process.exit(0); });
  process.on('SIGINT', async () => { await browser.close(); process.exit(0); });

  while (true) {
    try {
      const r = await tryAdmit(page);
      if (r === 'admitted' || r === 'dialog_confirmed') {
        total++;
        console.log(new Date().toLocaleTimeString() + ' ' + r + ' (' + total + ')');
        await new Promise(resolve => setTimeout(resolve, 1500));
        continue;
      } else if (r === 'pill_clicked' || r === 'lobby_opened') {
        await new Promise(resolve => setTimeout(resolve, 800));
        continue;
      }
    } catch (e) {
      if (e.message && (e.message.includes('destroyed') || e.message.includes('closed'))) {
        const matchFn = platform === 'teams'
          ? p => p.url().includes('teams.live.com') || p.url().includes('teams.microsoft.com')
          : p => p.url().includes('meet.google.com');
        page = ctx.pages().find(matchFn);
        if (!page) { console.log('Meeting page lost.'); break; }
      }
    }
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
  }
  await browser.close();
}

main().catch(e => { console.error(e.message); process.exit(1); });
