# Speaker Voting Test — Agent Instructions

## Working setup (verified 2026-03-22)

### Browser session for Google Meet hosting

Create a browser session under user 2280905@gmail.com (user_id=5) via the bot-manager API:

```bash
# Get token for user 5
TOKEN=$(curl -s -X POST "http://localhost:8067/admin/users/5/tokens?scope=bot" \
  -H "X-Admin-API-Key: changeme" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Create browser session (syncs Chrome profile with Google login from S3)
SESSION=$(curl -s -X POST "http://localhost:8066/bots" \
  -H "X-API-Key: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "browser_session"}')
# Returns: id, session_token, ssh_port
```

The session container syncs ~364MB of browser data from `s3://vexa-recordings/users/5/browser-userdata/` which includes a Google-authenticated Chrome profile.

**CDP access:** Get container IP via `docker inspect vexa-bot-{id}-* --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`, then connect on port 9223 (socat proxy).

### Creating a Google Meet

Use Playwright to connect and create a meeting:

```bash
cd /home/dima/dev/vexa-restore/services/vexa-bot  # playwright installed here
CDP_URL="http://{CONTAINER_IP}:9223" node ../../features/realtime-transcription/scripts/gmeet-host-auto.js
```

Or create manually via Playwright `page.goto('https://meet.new')`.

After creating, start auto-admit:
```bash
node ../../features/realtime-transcription/scripts/auto-admit.js "http://{CONTAINER_IP}:9223" &
```

### Running the test

```bash
# With existing meeting (skip browser-based creation):
bash test-runner.sh --meeting {meeting-code}

# With CDP_URL (creates meeting automatically):
CDP_URL="http://{CONTAINER_IP}:9223" bash test-runner.sh
```

**Note:** The test-runner's meeting creation via CDP_URL can hang if Playwright connections aren't released cleanly. Prefer creating the meeting separately and using `--meeting`.

### Orphaned meeting cleanup

Bot creation fails with "concurrent bot limit (1)" when old meetings aren't closed. Fix:

```sql
-- Close orphaned meetings for speaker bot users (26-31) and user 1
UPDATE meetings SET status = 'stopped', end_time = NOW()
WHERE user_id IN (1, 26, 27, 28, 29, 30, 31)
AND status IN ('requested', 'active')
AND id NOT IN ({keep_session_id});
```

The `status` column (not just `end_time`) must be set to `'stopped'` — the concurrency check queries `status IN ('requested', 'active')`.

### Bot tokens

All 6 bot tokens are pre-created in the DB for users 26-31 (SpeakerA-F@replay.vexa.ai). Each user has `max_concurrent_bots=1`, so each bot needs its own user/token.

## Pipeline behavior (learned from test run)

The Google Meet pipeline does NOT use voting/locking for speaker identity. It uses **direct element→name resolution**:

```
[SpeakerIdentity] Element N → "Name" (platform: googlemeet)
```

When participant count changes, all mappings are cleared and re-resolved:

```
[SpeakerIdentity] Participant count changed: 5 → 4. Invalidating all mappings (including locks).
[SpeakerIdentity] All track mappings cleared.
```

The score.py currently looks for `LOCKED PERMANENTLY` patterns which don't exist in Google Meet logs. It needs to be updated to parse the actual `Element N → "Name"` and `SPEAKER MAPPED` patterns.

### Known bug: element index instability after invalidation

In Phase 3 of the test, Track 0 was Alice but got remapped to Eve after the participant count changed (4→6). The element-to-speaker mapping is not stable across participant count changes because Google Meet can reorder `<audio>` elements in the DOM.
