/**
 * Speaker bot: joins a Teams meeting via a standalone browser container,
 * then uses SpeechSynthesis to "speak" text, generating real audio
 * that other participants (and their captions) will pick up.
 *
 * Usage: node speaker-bot.js <cdp-url> <meeting-url> <bot-name> <text1> [text2] ...
 */
const { chromium } = require('playwright');

const CDP_URL = process.argv[2] || 'http://localhost:9222';
const MEETING_URL = process.argv[3] || 'https://teams.live.com/meet/9378555217628?p=LZ35aK7zB44sgskqMT';
const BOT_NAME = process.argv[4] || 'SpeakerAlice';
const TEXTS = process.argv.slice(5);

if (TEXTS.length === 0) {
  TEXTS.push(
    "Hello everyone, I wanted to discuss the quarterly results. Revenue is up fifteen percent compared to last quarter.",
    "The marketing team did an excellent job with the new campaign. Customer acquisition costs went down significantly.",
    "I think we should continue investing in the digital channels. The return on investment has been very strong."
  );
}

async function main() {
  console.log(`[${BOT_NAME}] Connecting to CDP at ${CDP_URL}...`);
  const browser = await chromium.connectOverCDP(CDP_URL);
  const context = browser.contexts()[0] || await browser.newContext({
    permissions: ['microphone', 'camera'],
  });
  const page = context.pages()[0] || await context.newPage();

  // Grant mic permissions
  try {
    await context.grantPermissions(['microphone', 'camera'], { origin: 'https://teams.live.com' });
  } catch (e) {
    console.log(`[${BOT_NAME}] Could not grant permissions: ${e.message}`);
  }

  console.log(`[${BOT_NAME}] Navigating to meeting...`);
  await page.goto(MEETING_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);

  // Click "Continue on this browser"
  try {
    const continueBtn = page.locator('button:has-text("Continue on this browser")').first();
    await continueBtn.waitFor({ timeout: 10000 });
    await continueBtn.click();
    console.log(`[${BOT_NAME}] Clicked Continue on this browser`);
    await page.waitForTimeout(5000);
  } catch (e) {
    console.log(`[${BOT_NAME}] No Continue button: ${e.message}`);
  }

  // Set name
  try {
    const nameInput = page.locator('input[placeholder*="name"], input[data-tid="prejoin-display-name-input"]').first();
    await nameInput.waitFor({ timeout: 5000 });
    await nameInput.fill(BOT_NAME);
    console.log(`[${BOT_NAME}] Set display name`);
  } catch (e) {
    console.log(`[${BOT_NAME}] Could not set name: ${e.message}`);
  }

  // Click Join now
  try {
    const joinBtn = page.locator('button:has-text("Join now")').first();
    await joinBtn.waitFor({ timeout: 10000 });
    await joinBtn.click();
    console.log(`[${BOT_NAME}] Clicked Join now`);
    await page.waitForTimeout(8000);
  } catch (e) {
    console.log(`[${BOT_NAME}] Could not click Join: ${e.message}`);
  }

  // Check if in lobby
  console.log(`[${BOT_NAME}] Waiting to be admitted...`);
  await page.waitForTimeout(5000);

  // Unmute mic
  try {
    await page.keyboard.press('Control+Shift+M');
    console.log(`[${BOT_NAME}] Toggled mic`);
    await page.waitForTimeout(1000);
  } catch (e) {}

  // Use Web Speech API to speak — this goes through the real mic/audio path
  // and Teams will show the speaker's name in captions
  for (let i = 0; i < TEXTS.length; i++) {
    const text = TEXTS[i];
    console.log(`[${BOT_NAME}] Speaking (${i + 1}/${TEXTS.length}): "${text.substring(0, 60)}..."`);

    await page.evaluate(async (args) => {
      const { text, rate } = args;
      return new Promise((resolve) => {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = rate || 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        utterance.onend = () => resolve(true);
        utterance.onerror = (e) => { console.error('TTS error:', e); resolve(false); };
        speechSynthesis.speak(utterance);
      });
    }, { text, rate: 1.0 });

    console.log(`[${BOT_NAME}] Done speaking segment ${i + 1}`);
    // Pause between segments
    await page.waitForTimeout(3000);
  }

  console.log(`[${BOT_NAME}] All segments spoken. Waiting 10s for captions to settle...`);
  await page.waitForTimeout(10000);

  // Leave meeting
  try {
    const leaveBtn = page.locator('button[id="hangup-button"], button[aria-label="Leave"]').first();
    await leaveBtn.click();
    console.log(`[${BOT_NAME}] Left meeting`);
  } catch (e) {
    console.log(`[${BOT_NAME}] Could not leave cleanly: ${e.message}`);
  }

  await page.waitForTimeout(2000);
  console.log(`[${BOT_NAME}] Done.`);
  process.exit(0);
}

main().catch(err => {
  console.error(`[${BOT_NAME}] Fatal error:`, err.message);
  process.exit(1);
});
