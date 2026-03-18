import { Page } from "playwright";
import { log } from "../../utils";

/**
 * Enable Teams live captions for the bot's browser session.
 *
 * Captions are per-user — the bot can always enable them for itself
 * regardless of meeting settings. Once enabled, the caption DOM elements
 * (data-tid="author" + data-tid="closed-caption-text") appear in the page
 * and are observed by the caption MutationObserver in recording.ts.
 *
 * Flow: More → Language and speech → Show live captions
 */
export async function enableTeamsLiveCaptions(page: Page): Promise<void> {
  log("[Captions] Attempting to enable Teams live captions...");

  // Wait a few seconds for the meeting UI to stabilize
  await page.waitForTimeout(3000);

  // Check if captions are already enabled
  const alreadyEnabled = await page.evaluate(() => {
    return !!document.querySelector('[data-tid="closed-caption-renderer-wrapper"]');
  });

  if (alreadyEnabled) {
    log("[Captions] Live captions already enabled");
    return;
  }

  try {
    // Click "More" button in the meeting toolbar
    const moreButton = page.locator('button[aria-label="More"]');
    await moreButton.click({ timeout: 5000 });
    await page.waitForTimeout(800);

    // Click "Language and speech" to expand submenu
    const langItem = page.locator('[role="menuitem"]').filter({ hasText: 'Language and speech' });
    await langItem.click({ timeout: 5000 });
    await page.waitForTimeout(800);

    // Click "Show live captions"
    const captionsItem = page.locator('[role="menuitem"], [role="menuitemcheckbox"]').filter({ hasText: 'Show live captions' });
    await captionsItem.click({ timeout: 5000 });
    await page.waitForTimeout(1000);

    // Verify captions are now enabled
    const captionsEnabled = await page.evaluate(() => {
      return !!document.querySelector('[data-tid="closed-caption-renderer-wrapper"]');
    });

    if (captionsEnabled) {
      log("[Captions] ✅ Live captions enabled successfully");
    } else {
      log("[Captions] ⚠️ Captions menu clicked but wrapper not found yet — caption observer will detect when it appears");
    }
  } catch (err: any) {
    // Close any open menu before re-throwing
    try {
      await page.keyboard.press('Escape');
    } catch {}
    throw err;
  }
}
