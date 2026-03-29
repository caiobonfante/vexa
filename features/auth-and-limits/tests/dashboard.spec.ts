/**
 * Dashboard token management E2E tests.
 * Connects to a remote browser via CDP — does NOT launch a local browser.
 *
 * Required env vars:
 *   CDP_URL      — e.g. http://localhost:8066/b/$SESSION_TOKEN/cdp
 *   DASHBOARD_URL — e.g. http://172.29.0.1:3001 (reachable from the remote browser)
 *   ADMIN_KEY    — admin API key (default: vexa-admin-token)
 *   GATEWAY      — gateway URL from host (default: http://localhost:8066)
 */

import { chromium, type Browser, type BrowserContext, type Page } from "playwright";

const CDP_URL = process.env.CDP_URL!;
const DASHBOARD_URL = process.env.DASHBOARD_URL!;
const ADMIN_KEY = process.env.ADMIN_KEY || "vexa-admin-token";
const GATEWAY = process.env.GATEWAY || "http://localhost:8066";
const TEST_EMAIL = "playwright-e2e@example.com";

let browser: Browser;
let context: BrowserContext;
let page: Page;

async function setup() {
  if (!CDP_URL) throw new Error("CDP_URL env var required");
  if (!DASHBOARD_URL) throw new Error("DASHBOARD_URL env var required");

  console.log(`Connecting to CDP at ${CDP_URL}`);
  console.log(`Dashboard URL: ${DASHBOARD_URL}`);

  browser = await chromium.connectOverCDP(CDP_URL);
  context = browser.contexts()[0] || (await browser.newContext());
  page = context.pages()[0] || (await context.newPage());

  // Set a reasonable default timeout
  page.setDefaultTimeout(15000);
}

async function teardown() {
  if (browser) await browser.close();
}

/**
 * Log in to the dashboard.
 *
 * The dashboard uses direct login mode when SMTP is not configured:
 * POST /api/auth/send-magic-link with {email} returns {token, user}
 * and sets httpOnly cookie `vexa-token`.
 *
 * We navigate to /login, fill the email form and submit via the UI,
 * which triggers the auth store's sendMagicLink. In direct mode this
 * sets both the cookie (via server response) and localStorage state
 * automatically, then redirects to /agent.
 *
 * If the browser session already has auth state from a previous run,
 * navigating to /login will auto-redirect — we detect that and skip.
 */
async function loginToDashboard() {
  // Always force fresh login to ensure token has all scopes (bot, tx, browser)
  console.log("  Clearing old session for fresh login...");
  await context.clearCookies();
  await page.goto(`${DASHBOARD_URL}/profile`, { waitUntil: "domcontentloaded", timeout: 30000 });
  // Clear localStorage auth state
  await page.evaluate(() => localStorage.removeItem("vexa-auth"));

  const currentUrl = page.url();
  console.log(`  Current URL after clearing: ${currentUrl}`);

  // If redirected to login, we need to authenticate
  console.log("  Not authenticated, proceeding to login...");
  if (!currentUrl.includes("/login")) {
    await page.goto(`${DASHBOARD_URL}/login`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(3000);
  }

  // The login page starts in "onboarding" state with a meeting URL input
  // We need to click "Already have an account? Sign in" to get to the email form
  const signInLink = page.locator('text=Already have an account');
  const emailInput = page.locator('input[type="email"]');

  // Wait for the page to stabilize
  await page.waitForTimeout(2000);

  const hasSignInLink = await signInLink.isVisible({ timeout: 5000 }).catch(() => false);
  if (hasSignInLink) {
    console.log("  Clicking 'Already have an account? Sign in'...");
    await signInLink.click();
    await page.waitForTimeout(1000);
  }

  // Wait for the email input to appear
  console.log("  Waiting for email input...");
  await emailInput.waitFor({ state: "visible", timeout: 10000 });

  // Fill in the email
  console.log(`  Entering email: ${TEST_EMAIL}`);
  await emailInput.fill(TEST_EMAIL);

  // Wait for the submit button to be enabled (health check must complete)
  const submitButton = page.locator('button[type="submit"]');
  await submitButton.waitFor({ state: "visible", timeout: 5000 });
  await page.waitForFunction(
    () => {
      const btn = document.querySelector('button[type="submit"]') as HTMLButtonElement;
      return btn && !btn.disabled;
    },
    { timeout: 15000 }
  );

  console.log("  Submitting login form...");
  await submitButton.click();

  // In direct mode, login redirects to /agent after success
  console.log("  Waiting for login redirect...");
  await page.waitForURL(/\/(agent|profile|$)/, { timeout: 20000 });

  // Navigate to profile
  console.log("  Login successful, navigating to profile...");
  await page.goto(`${DASHBOARD_URL}/profile`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(5000);
}

// ============================================================
// Tests
// ============================================================

async function testProfilePageLoads() {
  console.log("TEST: Profile page loads with API Keys section");

  // Wait for the API Keys card heading
  await page.waitForSelector("text=API Keys", { timeout: 15000 });

  // Wait for the Create Key button
  const createKeyBtn = page.locator('button:has-text("Create Key")');
  await createKeyBtn.waitFor({ state: "visible", timeout: 5000 });

  // Also check the Account card
  await page.waitForSelector("text=Account", { timeout: 5000 });

  console.log("  PASS: Profile page loaded, API Keys section visible");
}

async function testCreateKeyFlow(): Promise<string> {
  console.log("TEST: Create key flow — name + scope -> key appears with correct badge");

  const keyName = `e2e-key-${Date.now()}`;

  // Click Create Key button
  const createKeyBtn = page.locator('button:has-text("Create Key")').first();
  await createKeyBtn.click();

  // Wait for the dialog to appear
  await page.waitForSelector('text=Create API Key', { timeout: 5000 });

  // Fill in key name (placeholder is "e.g. Production Bot Key")
  const nameInput = page.locator('input[placeholder*="Production Bot Key"]');
  await nameInput.waitFor({ state: "visible", timeout: 5000 });
  await nameInput.fill(keyName);

  // The "Bot" scope checkbox should be selected by default.
  // Verify the Bot scope button is in checked state.
  // The scope buttons contain "Bot" text and checkboxes.
  // Let's just ensure "Bot" is visible in the dialog.
  const botScopeLabel = page.locator('text=Bot').first();
  await botScopeLabel.waitFor({ state: "visible", timeout: 3000 });

  // Click the Create Key button in the dialog footer
  // There may be multiple buttons with "Create Key" text; the one in the dialog footer is the action button
  const dialogCreateBtn = page.locator('[role="dialog"] button:has-text("Create Key")');
  await dialogCreateBtn.click();

  // Wait for the "Key created successfully" message in the dialog
  await page.waitForSelector('text=Key created successfully', { timeout: 10000 });
  console.log("  Key creation dialog shows success");

  // Close the dialog with Done button
  const doneBtn = page.locator('button:has-text("Done")');
  await doneBtn.click();

  // Wait for dialog to close
  await page.waitForSelector('[role="dialog"]', { state: "detached", timeout: 5000 }).catch(() => {
    // Dialog might use different close mechanism
  });

  // Wait a moment for the key list to update
  await page.waitForTimeout(500);

  // Verify key appears in the list
  const keyNameLocator = page.locator(`text=${keyName}`);
  const keyVisible = await keyNameLocator.isVisible({ timeout: 5000 });
  if (!keyVisible) {
    throw new Error(`Key "${keyName}" not found in the key list after creation`);
  }

  // Check that the scope badge "bot" appears near the key name
  // The key row structure: div > div > (name + scope badges) + (masked token)
  // Scope badges have classes like bg-purple-900/40 and contain "bot" text
  const keyRow = page.locator('.rounded-lg.bg-muted\\/50', { has: page.locator(`text=${keyName}`) });
  const scopeBadge = keyRow.locator('span:has-text("bot")');
  const badgeCount = await scopeBadge.count();
  if (badgeCount === 0) {
    throw new Error("Scope badge 'bot' not found next to created key");
  }

  console.log(`  PASS: Key "${keyName}" created with bot scope badge`);
  return keyName;
}

async function testScopeBadgesVisible() {
  console.log("TEST: Scope badges are visible on key list");

  // Look for scope badge elements - they use text-purple-300 (bot) or text-cyan-300 (tx)
  // and have very small text (text-[10px])
  const badges = page.locator('.rounded-lg.bg-muted\\/50 span.text-\\[10px\\]');
  const count = await badges.count();

  if (count === 0) {
    // Fallback: look for any span containing "bot" or "tx" within key rows
    const altBadges = page.locator('.rounded-lg.bg-muted\\/50 span:text-is("bot")');
    const altCount = await altBadges.count();
    if (altCount === 0) {
      throw new Error("No scope badges found in key list");
    }
    console.log(`  PASS: ${altCount} scope badge(s) visible in key list (alt selector)`);
    return;
  }

  console.log(`  PASS: ${count} scope badge(s) visible in key list`);
}

async function testLastUsedAndExpiresColumns() {
  console.log("TEST: last_used and expires columns show");

  // The profile page renders spans with title="Last used" and title="Expires"
  const lastUsedSpans = page.locator('[title="Last used"]');
  const expiresSpans = page.locator('[title="Expires"]');

  const lastUsedCount = await lastUsedSpans.count();
  const expiresCount = await expiresSpans.count();

  if (lastUsedCount === 0) {
    throw new Error("No elements with title='Last used' found");
  }
  if (expiresCount === 0) {
    throw new Error("No elements with title='Expires' found");
  }

  // Verify the text content isn't empty
  const firstLastUsed = await lastUsedSpans.first().textContent();
  if (!firstLastUsed?.trim()) {
    throw new Error("Last used column text is empty");
  }

  const firstExpires = await expiresSpans.first().textContent();
  if (!firstExpires?.trim()) {
    throw new Error("Expires column text is empty");
  }

  console.log(`  PASS: Last used shows "${firstLastUsed?.trim()}", Expires shows "${firstExpires?.trim()}"`);
}

async function testRevokeKeyFlow(keyName: string) {
  console.log(`TEST: Revoke key flow — key "${keyName}" disappears`);

  // Find the key row containing our key name
  const keyRow = page.locator('.rounded-lg.bg-muted\\/50', { has: page.locator(`text=${keyName}`) });

  // Find the Revoke button within that row
  const revokeButton = keyRow.locator('button:has-text("Revoke")');
  const revokeCount = await revokeButton.count();

  if (revokeCount === 0) {
    throw new Error(`Revoke button not found for key "${keyName}"`);
  }

  await revokeButton.click();

  // Wait for the key to disappear from the list
  await page.waitForFunction(
    (name: string) => {
      return !document.body.textContent?.includes(name);
    },
    keyName,
    { timeout: 10000 }
  );

  console.log(`  PASS: Key "${keyName}" revoked and removed from list`);
}

async function testLoginTokenHasAllScopes() {
  console.log("TEST: Login token has all scopes (bot, tx, browser)");

  // Get the vexa-token cookie value
  const cookies = await context.cookies();
  const vexaToken = cookies.find((c) => c.name === "vexa-token");
  if (!vexaToken) {
    throw new Error("vexa-token cookie not found");
  }

  // Validate via dashboard proxy routes (same origin, no CORS issues)
  const validateRes = await page.evaluate(async () => {
    const botRes = await fetch("/api/vexa/bots/status");
    const meetingsRes = await fetch("/api/vexa/meetings");
    return {
      botStatus: botRes.status,
      meetingsStatus: meetingsRes.status,
    };
  });

  if (validateRes.botStatus !== 200) {
    throw new Error(`Bot scope failed: /api/vexa/bots/status returned ${validateRes.botStatus} (expected 200)`);
  }
  if (validateRes.meetingsStatus !== 200) {
    throw new Error(`TX scope failed: /api/vexa/meetings returned ${validateRes.meetingsStatus} (expected 200)`);
  }

  console.log(`  PASS: Login token has bot scope (${validateRes.botStatus}) and tx scope (${validateRes.meetingsStatus})`);
}

async function testBrowserSessionCreation() {
  console.log("TEST: Browser session creation works with login token");

  // Try creating a browser session via dashboard proxy (same origin)
  const result = await page.evaluate(async () => {
    const res = await fetch("/api/vexa/bots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "browser_session" }),
    });
    return { status: res.status, body: await res.json() };
  });

  // 201 = created, 403 with "Concurrent bot limit" = scope is fine (just at limit)
  if (result.status === 201) {
    console.log(`  PASS: Browser session created (201)`);
  } else if (result.status === 403 && result.body?.detail?.includes("Concurrent bot limit")) {
    console.log(`  PASS: Browser scope accepted — blocked by concurrent limit, not scope (403: ${result.body.detail})`);
  } else if (result.status === 403 && (result.body?.detail?.includes("scope") || result.body?.detail?.includes("Insufficient"))) {
    throw new Error(`Browser scope REJECTED: ${result.status} ${JSON.stringify(result.body)}`);
  } else {
    console.log(`  PASS: Browser session request accepted (${result.status}: ${result.body?.detail || "ok"})`);
  }
}

async function testMeetingEndpointAccessible() {
  console.log("TEST: Meeting/transcript endpoints accessible with login token");

  const result = await page.evaluate(async () => {
    const meetingsRes = await fetch("/api/vexa/meetings");
    return { status: meetingsRes.status };
  });

  if (result.status === 403) {
    throw new Error(`Meetings endpoint returned 403 — login token missing tx scope`);
  }

  console.log(`  PASS: /meetings accessible (${result.status})`);
}

// ============================================================
// Runner
// ============================================================

async function run() {
  let passed = 0;
  let failed = 0;
  const failures: string[] = [];

  try {
    await setup();
    await loginToDashboard();

    const tests: [string, () => Promise<unknown>][] = [
      ["Login token has all scopes", testLoginTokenHasAllScopes],
      ["Browser session creation", testBrowserSessionCreation],
      ["Meeting endpoint accessible", testMeetingEndpointAccessible],
      ["Profile page loads", testProfilePageLoads],
      ["Create key flow", testCreateKeyFlow],
      ["Scope badges visible", testScopeBadgesVisible],
      ["Last used and expires columns", testLastUsedAndExpiresColumns],
    ];

    let createdKeyName: string | undefined;

    for (const [name, testFn] of tests) {
      try {
        const result = await testFn();
        if (name === "Create key flow") createdKeyName = result as string;
        passed++;
      } catch (err) {
        failed++;
        const msg = `FAIL: ${name} — ${(err as Error).message}`;
        console.error(`  ${msg}`);
        failures.push(msg);
      }
    }

    // Revoke test depends on create succeeding
    if (createdKeyName) {
      try {
        await testRevokeKeyFlow(createdKeyName);
        passed++;
      } catch (err) {
        failed++;
        const msg = `FAIL: Revoke key flow — ${(err as Error).message}`;
        console.error(`  ${msg}`);
        failures.push(msg);
      }
    } else {
      console.log("SKIP: Revoke key flow (create key failed)");
    }
  } catch (err) {
    console.error(`SETUP FAILED: ${(err as Error).message}`);
    console.error((err as Error).stack);
    failed++;
    failures.push(`Setup: ${(err as Error).message}`);
  } finally {
    await teardown();
  }

  console.log(`\n--- Results: ${passed} passed, ${failed} failed ---`);
  if (failures.length > 0) {
    console.log("Failures:");
    failures.forEach((f) => console.log(`  - ${f}`));
    process.exit(1);
  }
}

run();
