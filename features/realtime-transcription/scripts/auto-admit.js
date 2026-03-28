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
  return await page.evaluate(() => {
    // Google Meet: confirmation dialog
    const dialogOk = document.querySelector('button[data-mdc-dialog-action="ok"]');
    if (dialogOk && dialogOk.offsetParent) {
      dialogOk.click();
      return 'dialog_confirmed';
    }

    // Google Meet: individual Admit / Admit all buttons (check deepest matches first)
    const buttons = document.querySelectorAll('button, div[role="button"], span[role="button"]');
    for (const btn of buttons) {
      const text = (btn.textContent || '').trim();
      if (btn.offsetParent && (text === 'Admit' || text === 'Admit all' || /^Admit \d+ guest/.test(text))) {
        btn.click();
        return text === 'Admit' ? 'admitted' : 'pill_clicked';
      }
    }

    // Google Meet: "Admit N guest(s)" pill — search all divs, pick smallest matching element
    let bestPill = null;
    let bestLen = Infinity;
    const divs = document.querySelectorAll('div, span');
    for (const el of divs) {
      const text = (el.textContent || '').trim();
      if (/^Admit \d+ guest/.test(text) && el.offsetParent && text.length < bestLen) {
        bestPill = el;
        bestLen = text.length;
      }
    }
    if (bestPill) {
      bestPill.click();
      return 'pill_clicked';
    }

    return 'none';
  }).catch(() => 'error');
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
