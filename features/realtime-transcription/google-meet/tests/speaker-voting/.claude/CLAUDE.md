# Speaker Voting Test — Agent Instructions

## Working setup (verified 2026-03-22)

### Prerequisites

1. Compose stack running (`make all` from `deploy/compose/`)
2. Browser session with Google account for meeting hosting
3. No orphaned meetings blocking bot creation (see cleanup below)

### Step-by-step: run a test

```bash
# 1. Create browser session under 2280905@gmail.com (user_id=5)
TOKEN=$(curl -s -X POST "http://localhost:8067/admin/users/5/tokens?scope=bot" \
  -H "X-Admin-API-Key: changeme" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

SESSION=$(curl -s -X POST "http://localhost:8066/bots" \
  -H "X-API-Key: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}')
# Wait ~30s for S3 sync (~364MB Chrome profile with Google login)

# 2. Get container IP
CONTAINER_IP=$(docker inspect $(docker ps --format '{{.Names}}' | grep vexa-bot-$(echo $SESSION | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")-) --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')

# 3. Create meeting via Playwright
cd /home/dima/dev/vexa-restore/services/vexa-bot
node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.connectOverCDP('http://${CONTAINER_IP}:9223');
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto('https://meet.new', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForURL(/meet\.google\.com\/[a-z]+-[a-z]+-[a-z]+/, { timeout: 30000 });
  await page.waitForTimeout(3000);
  const code = page.url().match(/meet\.google\.com\/([a-z]+-[a-z]+-[a-z]+)/)?.[1];
  console.log('MEETING=' + code);
  const joinBtn = page.locator('button:has-text(\"Join now\")');
  if (await joinBtn.isVisible({ timeout: 5000 }).catch(() => false)) await joinBtn.click();
  await page.waitForTimeout(5000);
  await browser.close();
})();
"

# 4. Start auto-admit (keeps running in background)
node ../../features/realtime-transcription/scripts/auto-admit.js "http://${CONTAINER_IP}:9223" &

# 5. Run tests
cd /home/dima/dev/vexa-restore/features/realtime-transcription/google-meet/tests/speaker-voting
bash test-runner.sh --meeting {MEETING_CODE}
bash test-edge-cases.sh --meeting {MEETING_CODE}
```

### Orphaned meeting cleanup

Bot creation fails with "concurrent bot limit (1)" when old meetings aren't stopped. Fix:

```sql
UPDATE meetings SET status = 'stopped', end_time = NOW()
WHERE user_id IN (1, 26, 27, 28, 29, 30, 31)
AND status IN ('requested', 'active')
AND id NOT IN ({browser_session_id});
```

The `status` column must be `'stopped'` — the concurrency check uses `status IN ('requested', 'active')`.

### Bot tokens

Users 26-31 (SpeakerA-F@replay.vexa.ai) have pre-created tokens in the DB. Each has `max_concurrent_bots=1`. Token values are hardcoded in test-runner.sh and test-edge-cases.sh.

### Key gotchas

- **CDP connection:** Use container IP:9223 (socat proxy), not the gateway `/b/{token}/cdp` (returns 307)
- **Meeting creation via script hangs:** `gmeet-host-auto.js` hangs when called from subshell. Create meeting separately via Playwright, then pass `--meeting`.
- **Playwright location:** Only installed in `/home/dima/dev/vexa-restore/services/vexa-bot/node_modules`. Run Playwright scripts from that directory or with NODE_PATH.
- **Redis module:** The test scripts find the Redis client module via `find` in `services/`. This path is resolved at runtime.

## Pipeline behavior (verified 2026-03-22)

### Speaker identity in Google Meet

The pipeline has two layers:

1. **Resolution:** `resolveSpeakerName()` queries the speaking indicator and returns a candidate name. Logs: `[SpeakerIdentity] Element N → "Name"`
2. **Dedup:** `isDuplicateSpeakerName()` rejects the name if already assigned to another track. Only accepted names produce `[SPEAKER MAPPED]` events.

The voting/locking path (`LOCKED PERMANENTLY`) exists but **never fires with TTS bots** because Google Meet's speaking indicator doesn't reliably detect PulseAudio playback. The dedup layer is the actual protection against misattribution.

### Log patterns to parse

| Pattern | Meaning | Reliable? |
|---------|---------|-----------|
| `[SpeakerIdentity] Element N → "Name"` | Raw resolution (may be rejected by dedup) | Shows attempts, not state |
| `[SPEAKER MAPPED] Track N: "old" → "new"` | Accepted state change | Ground truth for mapping |
| `[SPEAKER ACTIVE] Track N → "Name"` | Initial track assignment | Ground truth |
| `[SpeakerIdentity] Participant count changed` | Invalidation trigger | Always reliable |
| `[CONFIRMED] Speaker \| lang \| ...` | Final transcription segment | Ground truth for attribution |

### Scoring

`score.py` uses `SPEAKER MAPPED` + `SPEAKER ACTIVE` events (accepted state) for mapping checks, and `CONFIRMED` segments for attribution checks. Raw `Element → Name` logs are NOT used for scoring because they include rejected resolutions during simultaneous speech.
