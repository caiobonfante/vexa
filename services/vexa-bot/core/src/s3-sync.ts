import { execSync } from 'child_process';
import { existsSync, unlinkSync, mkdirSync } from 'fs';
import { join } from 'path';

export const BROWSER_DATA_DIR = '/tmp/browser-data';

export const BROWSER_CACHE_EXCLUDES = [
  'Cache/*', 'Code Cache/*', 'GrShaderCache/*', 'ShaderCache/*', 'GraphiteDawnCache/*',
  'Service Worker/CacheStorage/*', 'BrowserMetrics*', '*-journal',
  'SingletonLock', 'SingletonCookie', 'SingletonSocket',
  'GPUCache/*', 'DawnGraphiteCache/*', 'DawnWebGPUCache/*',
];

export interface S3Config {
  userdataS3Path?: string;
  s3Endpoint?: string;
  s3Bucket?: string;
  s3AccessKey?: string;
  s3SecretKey?: string;
}

function getS3Env(config: S3Config): Record<string, string> {
  return {
    ...process.env as Record<string, string>,
    AWS_ACCESS_KEY_ID: config.s3AccessKey || '',
    AWS_SECRET_ACCESS_KEY: config.s3SecretKey || '',
  };
}

export function s3Sync(localDir: string, s3Path: string, config: S3Config, direction: 'up' | 'down', excludes: string[] = []): void {
  if (!config.userdataS3Path || !config.s3Endpoint || !config.s3Bucket) return;
  const s3Uri = `s3://${config.s3Bucket}/${s3Path}`;
  const excludeArgs = excludes.map(e => `--exclude "${e}"`).join(' ');
  const deleteArg = direction === 'up' ? '--delete' : '';
  const [src, dst] = direction === 'down' ? [s3Uri, `${localDir}/`] : [`${localDir}/`, s3Uri];
  console.log(`[s3-sync] S3 sync ${direction}: ${src} → ${dst}`);
  try {
    execSync(
      `aws s3 sync "${src}" "${dst}" --endpoint-url "${config.s3Endpoint}" ${deleteArg} ${excludeArgs}`,
      { env: getS3Env(config), stdio: 'inherit', timeout: 120000 }
    );
  } catch (err: any) {
    console.log(`[s3-sync] S3 sync ${direction} issue: ${err.message}`);
  }
}

export function syncBrowserDataFromS3(config: S3Config): void {
  s3Sync(BROWSER_DATA_DIR, `${config.userdataS3Path}/browser-data`, config, 'down', BROWSER_CACHE_EXCLUDES);
}

export function syncBrowserDataToS3(config: S3Config): void {
  s3Sync(BROWSER_DATA_DIR, `${config.userdataS3Path}/browser-data`, config, 'up', BROWSER_CACHE_EXCLUDES);
}

export function cleanStaleLocks(dir: string = BROWSER_DATA_DIR): void {
  const lockFiles = ['SingletonLock', 'SingletonCookie', 'SingletonSocket'];
  for (const f of lockFiles) {
    const p = join(dir, f);
    if (existsSync(p)) {
      try { unlinkSync(p); } catch {}
      console.log(`[s3-sync] Removed stale lock: ${f}`);
    }
  }
}

export function ensureBrowserDataDir(): void {
  mkdirSync(BROWSER_DATA_DIR, { recursive: true });
}
