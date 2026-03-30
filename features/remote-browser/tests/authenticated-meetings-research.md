# Authenticated Meetings — Research Findings

## Current State: Plumbing exists, execution is missing

### What EXISTS (working)

#### 1. Browser Session Mode (remote browser for manual login)
- `POST /bots { mode: "browser_session" }` creates a VNC-accessible browser container
- `browser-session.ts` launches `chromium.launchPersistentContext('/tmp/browser-data', ...)` — persistent context
- MinIO sync on startup (`syncBrowserDataFromS3`) and on save/exit (`syncBrowserDataToS3`)
- S3 path: `s3://{bucket}/users/{user_id}/browser-userdata/browser-data/`
- Cache exclusions prevent timeout: `Cache/*, Code Cache/*, GrShaderCache/*, ShaderCache/*, SingletonLock`, etc.
- Save triggered via Redis command `save_storage` or on graceful shutdown
- Container subscribes to Redis channel `browser_session:{container_name}`

#### 2. Save endpoint updates user metadata
- `POST /bots/{meeting_id}/storage/save` triggers MinIO sync
- Updates `user.data.browser_userdata` in Postgres with:
  ```json
  {
    "s3_path": "users/{user_id}/browser-userdata",
    "storage_backend": "minio",
    "last_synced_at": "2026-03-24T..."
  }
  ```

#### 3. Meeting-api passes authenticated config to bot container
- When `req.authenticated=true`, meeting-api reads `user.data.browser_userdata`
- If metadata exists, builds `authenticated_extra_config`:
  ```json
  {
    "authenticated": true,
    "userdataS3Path": "users/{user_id}/browser-userdata",
    "s3Endpoint": "http://minio:9000",
    "s3Bucket": "vexa-recordings",
    "s3AccessKey": "...",
    "s3SecretKey": "..."
  }
  ```
- This gets merged into `BOT_CONFIG` via `extra_bot_config` → `bot_config_data.update()`
- The BotConfig TypeScript type has `authenticated`, `userdataS3Path`, `s3Endpoint`, `s3Bucket`, `s3AccessKey`, `s3SecretKey`
- Zod schema in `docker.ts` validates all these fields

#### 4. S3 path alignment
- Browser session saves to: `users/{user_id}/browser-userdata/browser-data/`
- Authenticated bot config gets: `userdataS3Path: "users/{user_id}/browser-userdata"`
- These are ALIGNED — authenticated bot would download from the same path the browser session saved to

### What's MISSING (the gap)

#### GAP 1: Bot `runBot()` ignores `authenticated` flag entirely
**File**: `services/vexa-bot/core/src/index.ts` lines 1943-2066

The `runBot()` function always calls `chromium.launch()` (ephemeral browser) for both Teams and non-Teams platforms. It **never**:
- Checks `botConfig.authenticated`
- Downloads userdata from MinIO
- Uses `chromium.launchPersistentContext()` with downloaded userdata
- Cleans SingletonLock files

The config is passed through all layers but the bot simply doesn't use it.

#### GAP 2: No `aws` CLI in meeting bot container?
Browser session mode explicitly uses `aws s3 sync` for MinIO operations. Meeting bot containers may not have the AWS CLI installed. Need to verify the Dockerfile.

#### GAP 3: No `browser_userdata` metadata check on browser session save
When a user saves a browser session, the `browser_userdata` metadata is written to `user.data`. But there's no validation that the user actually logged into something. The metadata just records "a sync happened" — not "Google cookies exist" or "auth state is valid."

#### GAP 4: No feedback to user about auth state validity
When `authenticated=true` but the saved browser profile has expired cookies or the user never logged in, there's no error. The bot would just join as a guest anyway.

---

## Full Flow Diagram with Gaps

```
STEP 1: POST /bots { mode: "browser_session" }
  └─ meeting-api creates container, Redis session, returns VNC URL
  └─ browser-session.ts: syncBrowserDataFromS3() → launchPersistentContext()
  STATUS: EXISTS ✓

STEP 2: User opens VNC → navigates to accounts.google.com → logs in
  └─ Cookies/localStorage stored in /tmp/browser-data/Default/
  STATUS: EXISTS ✓ (manual via VNC)

STEP 3: User triggers save (POST /bots/{id}/storage/save)
  └─ Redis publish "save_storage" → browser-session.ts runs syncBrowserDataToS3()
  └─ Syncs /tmp/browser-data/ → s3://vexa/users/{user_id}/browser-userdata/browser-data/
  └─ Updates user.data.browser_userdata in Postgres
  STATUS: EXISTS ✓

STEP 4: POST /bots { platform: "google_meet", meeting_url: "...", authenticated: true }
  └─ meeting-api reads user.data.browser_userdata → builds authenticated_extra_config
  └─ Passes to start_bot_container() → BOT_CONFIG includes S3 creds + path
  STATUS: EXISTS ✓ (config passed)

STEP 5: Bot container starts → reads BOT_CONFIG → runBot()
  └─ ** IGNORES authenticated flag **
  └─ Calls chromium.launch() (ephemeral, no userdata)
  └─ Joins meeting as GUEST
  STATUS: *** MISSING *** — This is the critical gap
```

---

## What Code Changes Are Needed

### Change 1: `services/vexa-bot/core/src/index.ts` — Use persistent context when authenticated

In `runBot()` (around line 1943), before the platform-specific browser launch:

```
IF botConfig.authenticated && botConfig.userdataS3Path:
  1. Download userdata from MinIO: aws s3 sync s3://{bucket}/{userdataS3Path}/browser-data/ /tmp/browser-data/
     (reuse the same exclusion list from browser-session.ts)
  2. Clean SingletonLock/SingletonCookie/SingletonSocket
  3. Use chromium.launchPersistentContext('/tmp/browser-data', { headless: false, args: ... })
     instead of chromium.launch() + browserInstance.newContext()
  4. Get page from context.pages()[0] or context.newPage()
ELSE:
  existing ephemeral launch code
```

**Estimated effort**: Medium. The s3Sync logic can be extracted from `browser-session.ts` into a shared module.

### Change 2: Extract S3 sync utilities to shared module

Create `services/vexa-bot/core/src/s3-sync.ts` with:
- `s3Sync(localDir, s3Path, config, direction, excludes)`
- `getS3Env(config)`
- `cleanStaleLocks(dir)`
- `BROWSER_CACHE_EXCLUDES` constant

Both `browser-session.ts` and `index.ts` import from this shared module.

**Estimated effort**: Small refactor.

### Change 3: Verify AWS CLI availability in bot container

Check the Dockerfile for vexa-bot. If `aws` CLI isn't installed, either:
- Add it to the Dockerfile (easiest)
- Use MinIO SDK directly (cleaner but more code)
- Use `mc` (MinIO client) instead

**Estimated effort**: Small (Dockerfile change) or Medium (SDK approach).

### Change 4 (optional): Auth state validation

Add a pre-flight check after downloading userdata:
- Look for `Default/Cookies` file (SQLite database)
- Check if Google/Teams cookie domains exist
- If no relevant cookies found, warn or fail fast

**Estimated effort**: Medium. Nice to have but not required for MVP.

---

## MinIO Storage Structure

```
s3://vexa-recordings/
  └─ users/
      └─ {user_id}/
          └─ browser-userdata/
              ├─ browser-data/          ← Chromium user data directory
              │   ├─ Default/
              │   │   ├─ Cookies         ← SQLite: auth cookies for Google, Teams, etc.
              │   │   ├─ Local Storage/   ← localStorage data
              │   │   ├─ Session Storage/ ← sessionStorage data
              │   │   ├─ Preferences
              │   │   ├─ Login Data       ← saved passwords (encrypted by Chromium)
              │   │   └─ ...
              │   ├─ Local State
              │   └─ First Run
              └─ workspace/             ← optional git/S3 workspace (separate feature)
```

Excluded from sync (large, regenerated on launch):
- `Cache/*`, `Code Cache/*`, `GrShaderCache/*`, `ShaderCache/*`
- `GraphiteDawnCache/*`, `GPUCache/*`, `DawnGraphiteCache/*`, `DawnWebGPUCache/*`
- `Service Worker/CacheStorage/*`, `BrowserMetrics*`, `*-journal`
- `SingletonLock`, `SingletonCookie`, `SingletonSocket`

---

## Security Considerations

### 1. Stored Credentials Scope
- Chromium's `Login Data` (saved passwords) is encrypted with the OS keyring. In a Docker container without a keyring, Chromium uses a hardcoded key. This means **passwords in MinIO are recoverable** by anyone with S3 access.
- **Mitigation**: The current approach stores cookies/sessions, not passwords. Users should NOT save passwords in the browser. The login flow should use OAuth which stores tokens, not credentials.

### 2. MinIO Access Control
- S3 path is `users/{user_id}/browser-userdata/` — user-scoped
- But MinIO credentials (`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`) are global — any container with these creds can access any user's data
- **Mitigation**: Acceptable for self-hosted single-tenant deployments. For multi-tenant, would need per-user MinIO policies or a proxy.

### 3. Cookie/Token Expiry
- Google session cookies expire (typically 2 weeks active, shorter if idle)
- Teams tokens expire (typically 24h, refreshed by the browser)
- **Impact**: An authenticated bot that starts days after the last browser session may have expired cookies → joins as guest
- **Mitigation**: Check cookie expiry before launching authenticated bot; prompt user to refresh via browser session if stale.

### 4. Bot Detection Risk
- Using persistent context with real cookies makes the bot look like a real user
- Google/Teams may flag automated activity from a "logged-in" account
- The `--enable-automation` flag is already stripped in browser-session mode
- Meeting bots use stealth plugin for non-Teams platforms
- **Mitigation**: Low risk for meeting attendance (passive). Higher risk if bot performs non-meeting actions.

---

## Implementation Plan

### Phase 1: Extract S3 sync (prerequisite)
1. Create `services/vexa-bot/core/src/s3-sync.ts` — shared S3 sync + lock cleanup
2. Refactor `browser-session.ts` to import from shared module
3. Verify: browser session mode still works after refactor

### Phase 2: Authenticated bot launch
1. In `runBot()`, detect `authenticated=true` + valid S3 config
2. Download userdata from MinIO (using shared s3-sync)
3. Clean stale locks
4. Switch to `launchPersistentContext()` instead of `launch()` + `newContext()`
5. Verify: bot joins Google Meet as authenticated user (no lobby, shows user's name)

### Phase 3: Verify Dockerfile
1. Check if `aws` CLI is available in meeting bot container
2. If not, add to Dockerfile or switch to MinIO SDK

### Phase 4: Integration test
1. Start browser session → login to Google via VNC → save
2. Start authenticated bot for a Google Meet → verify joins as user (not guest)
3. Verify transcription still works with persistent context

### Estimated total effort
- Phase 1: ~1 hour (refactor)
- Phase 2: ~2 hours (core change + testing)
- Phase 3: ~30 min (Dockerfile check)
- Phase 4: ~1 hour (manual E2E)
