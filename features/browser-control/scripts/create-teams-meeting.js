#!/usr/bin/env node
// Create an MS Teams meeting via CDP on an authenticated browser.
// Usage: node create-teams-meeting.js [--cdp http://localhost:9222] [--name "Test Meeting"]
//
// Outputs: MEETING:https://teams.live.com/meet/xxx?p=yyy
// Exits 0 on success, 1 on failure.

const { chromium } = require('/home/dima/dev/playwright-vnc-poc/node_modules/playwright');
const fs = require('fs');

const LOG_FILE = '/home/dima/dev/vexa/test.log';
const AGENT = 'browser-control/create-teams-meeting';

function log(level, msg) {
  const line = `[${new Date().toISOString()}] [${AGENT}] ${level}: ${msg}`;
  console.error(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

function parseArgs() {
  const args = process.argv.slice(2);
  let cdp = process.env.CDP_URL || 'http://localhost:9222';
  let name = 'Vexa Test Meeting';
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--cdp' && args[i + 1]) cdp = args[++i];
    if (args[i] === '--name' && args[i + 1]) name = args[++i];
  }
  return { cdp, name };
}

async function main() {
  const { cdp, name } = parseArgs();
  let browser;

  try {
    log('PASS', `Connecting to CDP at ${cdp}`);
    browser = await chromium.connectOverCDP(cdp, { timeout: 15000 });
  } catch (err) {
    log('FAIL', `Cannot connect to CDP at ${cdp}: ${err.message}`);
    process.exit(1);
  }

  try {
    const contexts = browser.contexts();
    if (contexts.length === 0) {
      log('FAIL', 'No browser contexts found. Is Chromium running?');
      process.exit(1);
    }
    const context = contexts[0];
    const page = context.pages()[0] || await context.newPage();

    // Navigate to Teams
    log('PASS', 'Navigating to Teams');
    await page.goto('https://teams.microsoft.com', { waitUntil: 'load', timeout: 30000 });
    await page.waitForTimeout(5000);

    // Check if sign-in is required
    const url = page.url();
    if (url.includes('login.microsoftonline.com') || url.includes('login.live.com')) {
      log('FAIL', `Microsoft sign-in required. Current URL: ${url}. Sign in via VNC first.`);
      console.log('FAIL:AUTH_REQUIRED');
      process.exit(1);
    }

    // Click Meet in sidebar
    log('PASS', 'Looking for Meet sidebar button');
    try {
      const meetBtn = page.locator('[data-tid="app-bar-Meet"], button:has-text("Meet"), [data-tid="meet-app-bar-button"]').first();
      await meetBtn.click({ timeout: 10000 });
      log('PASS', 'Clicked Meet sidebar button');
    } catch (err) {
      log('FAIL', `Could not find Meet sidebar button: ${err.message}`);
      process.exit(1);
    }

    await page.waitForTimeout(3000);

    // Click "Create a meeting link"
    log('PASS', 'Looking for "Create a meeting link" button');
    try {
      const createBtn = page.locator('button:has-text("Create a meeting link"), button:has-text("Create a meeting")').first();
      await createBtn.click({ timeout: 10000 });
      log('PASS', 'Clicked "Create a meeting link"');
    } catch (err) {
      log('FAIL', `Could not find "Create a meeting link" button: ${err.message}`);
      process.exit(1);
    }

    await page.waitForTimeout(2000);

    // Name the meeting
    try {
      const nameInput = page.locator('input[placeholder*="meeting"], input[placeholder*="Meeting"], input[aria-label*="meeting name" i]').first();
      if (await nameInput.isVisible({ timeout: 3000 }).catch(() => false)) {
        await nameInput.fill(name);
        log('PASS', `Set meeting name: ${name}`);
      }
    } catch {}

    // Click "Create and copy link" or similar
    try {
      const copyBtn = page.locator('button:has-text("Create and copy"), button:has-text("Create")').first();
      await copyBtn.click({ timeout: 5000 });
      log('PASS', 'Clicked create button');
    } catch (err) {
      log('FAIL', `Could not click create button: ${err.message}`);
      process.exit(1);
    }

    await page.waitForTimeout(3000);

    // Try to extract meeting link from the page
    let meetingUrl = null;

    // Method 1: Look for the link displayed on page
    try {
      const linkEl = page.locator('a[href*="teams.live.com/meet"], a[href*="teams.microsoft.com/meet"], [data-tid*="meeting-link"], input[value*="teams"]').first();
      if (await linkEl.isVisible({ timeout: 3000 }).catch(() => false)) {
        const tag = await linkEl.evaluate(el => el.tagName.toLowerCase());
        if (tag === 'input') {
          meetingUrl = await linkEl.inputValue();
        } else {
          meetingUrl = await linkEl.getAttribute('href') || await linkEl.textContent();
        }
      }
    } catch {}

    // Method 2: Try clipboard (from "Copy link" action)
    if (!meetingUrl) {
      try {
        meetingUrl = await page.evaluate(() => navigator.clipboard.readText());
      } catch {}
    }

    // Method 3: Scan page text for URL pattern
    if (!meetingUrl) {
      try {
        const text = await page.evaluate(() => document.body.innerText);
        const match = text.match(/(https:\/\/teams\.live\.com\/meet\/\S+)/);
        if (match) meetingUrl = match[1];
      } catch {}
    }

    // Method 4: Look for any visible text with teams meeting URL
    if (!meetingUrl) {
      try {
        const allLinks = await page.evaluate(() => {
          return Array.from(document.querySelectorAll('a')).map(a => a.href).filter(h => h.includes('teams') && h.includes('meet'));
        });
        if (allLinks.length > 0) meetingUrl = allLinks[0];
      } catch {}
    }

    if (!meetingUrl) {
      log('FAIL', 'Could not extract meeting URL from page');
      // Take screenshot for debugging
      try { await page.screenshot({ path: '/tmp/teams-create-fail.png' }); } catch {}
      process.exit(1);
    }

    // Clean up URL
    meetingUrl = meetingUrl.trim();

    log('PASS', `Meeting link obtained: ${meetingUrl}`);

    // Join as organizer
    log('PASS', 'Attempting to start/join as organizer');
    try {
      const startBtn = page.locator('button:has-text("Start meeting"), button:has-text("Join meeting"), button:has-text("Join now")').first();
      if (await startBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await startBtn.click();
        log('PASS', 'Clicked start/join meeting button');
        await page.waitForTimeout(5000);

        // Handle "Join now" on pre-join screen
        try {
          const joinNow = page.locator('button:has-text("Join now"), button[data-tid*="prejoin-join-button"]').first();
          if (await joinNow.isVisible({ timeout: 5000 }).catch(() => false)) {
            await joinNow.click();
            log('PASS', 'Clicked "Join now" on pre-join screen');
          }
        } catch {}
      }
    } catch (err) {
      log('DEGRADED', `Could not auto-join as organizer: ${err.message}`);
    }

    console.log(`MEETING:${meetingUrl}`);

  } catch (err) {
    log('FAIL', `Error creating Teams meeting: ${err.message}`);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main().catch(err => {
  log('FAIL', `Unhandled error: ${err.message}`);
  process.exit(1);
});
