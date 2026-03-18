const { chromium } = require('playwright');
const CDP_URL = process.argv[2] || 'http://localhost:9222';
const POLL_INTERVAL = 3000;

async function main() {
  console.log('Connecting to ' + CDP_URL);
  const browser = await chromium.connectOverCDP(CDP_URL, { timeout: 15000 });
  const ctx = browser.contexts()[0];
  let page = ctx.pages().find(p => p.url().includes('meet.google.com'));
  if (!page) { console.error('No Meet page'); process.exit(1); }
  console.log('Meeting: ' + page.url());
  console.log('Auto-admit running every ' + (POLL_INTERVAL / 1000) + 's');
  let total = 0;

  process.on('SIGTERM', async () => { await browser.close(); process.exit(0); });
  process.on('SIGINT', async () => { await browser.close(); process.exit(0); });

  while (true) {
    try {
      // Check for green pill "Admit N guest(s)" in toolbar
      const hasGuests = await page.evaluate(() => {
        const els = document.querySelectorAll('div[role="button"]');
        for (const el of els) {
          if (/Admit \d+ guest/.test(el.textContent || '') && el.offsetParent) return true;
        }
        return false;
      }).catch(() => false);

      if (hasGuests) {
        // Click the green pill
        await page.locator('div[role="button"]').filter({ hasText: /Admit \d+ guest/ }).first().click();
        // Wait for confirmation dialog
        await page.waitForTimeout(800);
        // Click "Admit all" button in dialog
        const confirmBtn = page.getByRole('button', { name: 'Admit all', exact: true });
        if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await confirmBtn.click({ force: true });
          total++;
          console.log(new Date().toLocaleTimeString() + ' Admitted (' + total + ')');
          await page.waitForTimeout(1500);
          continue;
        }
      }
    } catch (e) {
      if (e.message && (e.message.includes('destroyed') || e.message.includes('closed'))) {
        page = ctx.pages().find(p => p.url().includes('meet.google.com'));
        if (!page) { console.log('Meeting page lost.'); break; }
      }
    }
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
  }
  await browser.close();
}

main().catch(e => { console.error(e.message); process.exit(1); });
