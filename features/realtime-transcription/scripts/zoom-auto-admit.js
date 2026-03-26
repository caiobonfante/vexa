const { chromium } = require('playwright');

const CDP_URL = process.env.CDP_URL || process.argv[2] || 'http://localhost:9222';
const POLL_INTERVAL = 5000;

async function tryAdmitZoom(page) {
  return await page.evaluate(() => {
    // Zoom Web: "Admit All" button in participants panel
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      const text = (btn.textContent || '').trim().toLowerCase();
      if (text === 'admit all' && btn.offsetParent) {
        btn.click();
        return 'admit_all';
      }
    }

    // Zoom Web: Individual "Admit" buttons in waiting room list
    for (const btn of buttons) {
      const text = (btn.textContent || '').trim().toLowerCase();
      if (text === 'admit' && btn.offsetParent) {
        btn.click();
        return 'admitted';
      }
    }

    // Zoom Web: aria-label based admit buttons
    const ariaAdmit = document.querySelectorAll('button[aria-label*="dmit"]');
    for (const btn of ariaAdmit) {
      if (btn.offsetParent) {
        btn.click();
        return 'admitted';
      }
    }

    // Zoom Web: "Someone is in the waiting room" notification banner
    const notifications = document.querySelectorAll('[class*="notification"]');
    for (const notif of notifications) {
      const text = (notif.textContent || '').toLowerCase();
      if (text.includes('waiting room') || text.includes('waiting to join')) {
        const admitBtn = notif.querySelector('button');
        if (admitBtn && admitBtn.offsetParent) {
          admitBtn.click();
          return 'notification_admit';
        }
      }
    }

    return 'none';
  }).catch(() => 'error');
}

async function ensureParticipantsPanelOpen(page) {
  // Try to open the participants panel so we can see waiting room entries
  try {
    const panelOpen = await page.evaluate(() => {
      // Check if participants panel is already open (look for panel content)
      const panel = document.querySelector('[class*="participants-section"], [class*="waiting-room"]');
      return !!panel;
    });
    if (panelOpen) return;

    // Click participants button to open panel
    const participantsBtn = page.locator('button[aria-label*="participants list"], button[aria-label*="Participants"]').first();
    const visible = await participantsBtn.isVisible({ timeout: 1000 });
    if (visible) {
      await participantsBtn.click();
      console.log('Opened participants panel');
    }
  } catch { /* panel may already be open or button not found */ }
}

async function main() {
  console.log('Connecting to ' + CDP_URL);
  const browser = await chromium.connectOverCDP(CDP_URL, { timeout: 15000 });
  const ctx = browser.contexts()[0];

  // Find the Zoom meeting page
  let page = null;
  for (const p of ctx.pages()) {
    const url = p.url();
    if (url.includes('zoom.us') || url.includes('zoom.com')) {
      page = p;
      break;
    }
  }

  if (!page) {
    console.error('No Zoom meeting page found (tried: ' + ctx.pages().map(p => p.url()).join(', ') + ')');
    process.exit(1);
  }

  console.log('Zoom meeting page: ' + page.url());
  console.log('Auto-admit running every ' + (POLL_INTERVAL / 1000) + 's');

  // Try to open participants panel once at start
  await ensureParticipantsPanelOpen(page);

  let total = 0;

  process.on('SIGTERM', async () => { await browser.close(); process.exit(0); });
  process.on('SIGINT', async () => { await browser.close(); process.exit(0); });

  while (true) {
    try {
      const r = await tryAdmitZoom(page);
      if (r === 'admit_all' || r === 'admitted' || r === 'notification_admit') {
        total++;
        console.log(new Date().toLocaleTimeString() + ' ' + r + ' (' + total + ')');
        // Brief pause then check again immediately (more people may be waiting)
        await new Promise(resolve => setTimeout(resolve, 1500));
        continue;
      }
    } catch (e) {
      if (e.message && (e.message.includes('destroyed') || e.message.includes('closed'))) {
        // Page navigated away — try to re-find Zoom page
        page = ctx.pages().find(p => p.url().includes('zoom.us') || p.url().includes('zoom.com'));
        if (!page) { console.log('Zoom meeting page lost.'); break; }
      }
    }
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
  }
  await browser.close();
}

main().catch(e => { console.error(e.message); process.exit(1); });
