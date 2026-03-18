import { chromium } from 'playwright-extra';
import { createClient, RedisClientType } from 'redis';
import { execSync } from 'child_process';
import { mkdirSync, existsSync, unlinkSync } from 'fs';
import { join } from 'path';
import { getBrowserSessionArgs } from './constans';
import { BrowserSessionConfig } from './types';

const USERDATA_DIR = '/tmp/userdata';

// --- S3 sync helpers using aws CLI ---

function getS3Env(config: BrowserSessionConfig): Record<string, string> {
  return {
    ...process.env as Record<string, string>,
    AWS_ACCESS_KEY_ID: config.s3AccessKey || '',
    AWS_SECRET_ACCESS_KEY: config.s3SecretKey || '',
  };
}

export function syncFromS3(config: BrowserSessionConfig): void {
  if (!config.userdataS3Path || !config.s3Endpoint || !config.s3Bucket) {
    console.log('[browser-session] No S3 path configured, starting with empty userdata');
    return;
  }
  const s3Uri = `s3://${config.s3Bucket}/${config.userdataS3Path}`;
  console.log(`[browser-session] Syncing userdata from ${s3Uri} ...`);
  try {
    execSync(
      `aws s3 sync "${s3Uri}" "${USERDATA_DIR}/" --endpoint-url "${config.s3Endpoint}"`,
      { env: getS3Env(config), stdio: 'inherit', timeout: 120000 }
    );
    console.log('[browser-session] S3 download complete');
  } catch (err: any) {
    // If the path doesn't exist yet (first time), aws s3 sync just does nothing
    console.log(`[browser-session] S3 sync from failed (may be first-time): ${err.message}`);
  }
}

export function syncToS3(config: BrowserSessionConfig): void {
  if (!config.userdataS3Path || !config.s3Endpoint || !config.s3Bucket) {
    console.log('[browser-session] No S3 path configured, skipping upload');
    return;
  }
  const s3Uri = `s3://${config.s3Bucket}/${config.userdataS3Path}`;
  console.log(`[browser-session] Syncing userdata to ${s3Uri} ...`);
  try {
    execSync(
      `aws s3 sync "${USERDATA_DIR}/" "${s3Uri}" --endpoint-url "${config.s3Endpoint}" --delete`,
      { env: getS3Env(config), stdio: 'inherit', timeout: 120000 }
    );
    console.log('[browser-session] S3 upload complete');
  } catch (err: any) {
    console.error(`[browser-session] S3 sync to failed: ${err.message}`);
  }
}

// --- Clean stale Chromium lock files that prevent launch after unclean shutdown ---

function cleanStaleLocks(): void {
  const lockFiles = ['SingletonLock', 'SingletonCookie', 'SingletonSocket'];
  for (const f of lockFiles) {
    const p = join(USERDATA_DIR, f);
    if (existsSync(p)) {
      try { unlinkSync(p); } catch {}
      console.log(`[browser-session] Removed stale lock: ${f}`);
    }
  }
}

// --- Main entry point ---

export async function runBrowserSession(config: BrowserSessionConfig): Promise<void> {
  // Ensure userdata dir exists
  mkdirSync(USERDATA_DIR, { recursive: true });

  // Download existing userdata from S3
  syncFromS3(config);

  // Clean stale locks from previous unclean shutdowns
  cleanStaleLocks();

  // Launch persistent browser context
  const context = await chromium.launchPersistentContext(USERDATA_DIR, {
    headless: false,
    ignoreDefaultArgs: ['--enable-automation'],
    args: getBrowserSessionArgs(),
    viewport: null,
  });

  // Get or create a page
  const pages = context.pages();
  const page = pages.length > 0 ? pages[0] : await context.newPage();
  await page.goto('about:blank');

  console.log('[browser-session] Browser session ready. VNC :6080, CDP :9222');

  // Set up Redis subscriber for commands
  const channelName = `browser_session:${config.container_name || 'default'}`;

  if (config.redisUrl) {
    const subscriber: RedisClientType = createClient({ url: config.redisUrl }) as RedisClientType;
    const publisher: RedisClientType = createClient({ url: config.redisUrl }) as RedisClientType;
    await subscriber.connect();
    await publisher.connect();

    await subscriber.subscribe(channelName, async (message: string) => {
      console.log(`[browser-session] Redis command: ${message}`);

      if (message === 'save_storage') {
        syncToS3(config);
        await publisher.publish(channelName, 'save_storage:done');
      } else if (message === 'stop') {
        console.log('[browser-session] Stop command received, saving and exiting...');
        syncToS3(config);
        await context.close();
        process.exit(0);
      }
    });

    console.log(`[browser-session] Listening for commands on Redis channel: ${channelName}`);
  }

  // Graceful shutdown
  const shutdown = async () => {
    console.log('[browser-session] Shutting down, saving userdata...');
    syncToS3(config);
    await context.close();
    process.exit(0);
  };

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);

  // Keep alive
  await new Promise(() => {});
}
