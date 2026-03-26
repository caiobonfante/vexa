# Zoom REST API Research — Meeting Creation & Waiting Room Control

## Summary

The Zoom REST API can create meetings programmatically with full control over waiting room and join-before-host settings. **However, for our MVP3 use case (automated test meetings), the browser-based approach (zoom-host-auto.js) is simpler and more reliable** — it avoids OAuth app setup, scope restrictions, and account-level setting overrides.

---

## 1. Meeting Creation API

**Endpoint:** `POST https://api.zoom.us/v2/users/{userId}/meetings`

```json
{
  "topic": "Vexa Test Meeting",
  "type": 1,           // 1 = instant, 2 = scheduled
  "settings": {
    "waiting_room": false,
    "join_before_host": true,
    "jbh_time": 0,      // 0 = join anytime before host
    "host_video": false,
    "participant_video": false,
    "mute_upon_entry": false
  }
}
```

**Response includes:** `join_url`, `id` (meeting ID), `password`, `start_url` (host URL with token).

**Meeting types:**
- `type: 1` — Instant meeting (starts immediately)
- `type: 2` — Scheduled meeting (needs `start_time`)
- `type: 3` — Recurring with no fixed time
- `type: 8` — Recurring with fixed time

## 2. Authentication Options

| Method | Complexity | Best For | Status |
|--------|-----------|----------|--------|
| **Server-to-Server OAuth** | Medium | Backend automation, no user interaction | **Recommended** |
| OAuth 2.0 (user-level) | High | Apps acting on behalf of users | Overkill for testing |
| JWT | Low | Quick prototyping | **Deprecated by Zoom (June 2023)** |

### Server-to-Server OAuth Setup

1. Go to [Zoom Marketplace](https://marketplace.zoom.us/) → Build App → Server-to-Server OAuth
2. Get `Client ID`, `Client Secret`, `Account ID`
3. Add scopes: `meeting:write:admin` (or `meeting:write`)
4. Token request:
   ```bash
   curl -X POST "https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ACCOUNT_ID}" \
     -u "{CLIENT_ID}:{CLIENT_SECRET}"
   ```
5. Use returned `access_token` in `Authorization: Bearer {token}` header

**Important:** S2S OAuth apps are "internal apps" — they work immediately on your own account without Marketplace publishing. No review process needed for internal use.

### Prerequisites / Gotchas

- Account admin must enable Server-to-Server OAuth in **User Management → Roles → Role Settings → Advanced Features**
- Some free/basic accounts report `meeting:write` scopes not appearing — only `meeting:read` visible. This is an account-level restriction, not an API limitation.
- S2S OAuth apps act as the **account**, not a specific user. Use `userId: "me"` or a specific user's email.

## 3. Waiting Room & Join-Before-Host Control

### API-Level Settings

```json
"settings": {
  "waiting_room": false,
  "join_before_host": true,
  "jbh_time": 0
}
```

### Critical: Account Settings Override API Settings

**This is the #1 source of bugs.** Even if you set `waiting_room: false` in the API request, the meeting may still have a waiting room if:

1. **Account-level setting** enforces waiting room → overrides API
2. **Group-level setting** enforces waiting room → overrides API
3. **Host's personal setting** has waiting room locked → overrides API

**Recall.ai documented this extensively:** The `waiting_room: true` setting overrides `join_before_host`. To reliably disable waiting room:
1. Set `waiting_room: false` AND `join_before_host: true` AND `jbh_time: 0` in API request
2. **Also** ensure the Zoom account's settings (web portal → Settings → Security) don't lock waiting room on
3. If the account locks waiting room at account level, the API **cannot override it**

Source: [Recall.ai — Applying account-level settings to meetings created via the Zoom API](https://www.recall.ai/blog/applying-account-level-settings-to-meetings-created-via-the-zoom-api)

### Workaround for Locked Waiting Room

If the account enforces waiting room:
- Use the `start_url` (host URL) to join as host first → then admit bots
- Or: change account settings via API: `PATCH /users/{userId}/settings` with `{ "in_meeting": { "waiting_room": false } }` (requires `user:write:admin` scope)

## 4. Required Scopes

| Scope | Purpose |
|-------|---------|
| `meeting:write:admin` | Create meetings for any user on the account |
| `meeting:write` | Create meetings for the authenticated user |
| `user:read:admin` | List users (to get userId) |
| `user:write:admin` | Change user settings (disable waiting room at user level) |

**Minimum for meeting creation:** `meeting:write:admin` (or `meeting:write`)

**Known issue:** Some accounts only show read scopes when creating S2S OAuth apps. This appears to be a role/permissions issue — the admin creating the app needs sufficient privileges.

## 5. Free Tier / Developer Account

- Free Zoom accounts **can** create Server-to-Server OAuth apps
- Free accounts have a **40-minute meeting limit** (for meetings with 2+ participants)
- Meeting creation API works on free accounts
- **Rate limit:** 100 create/update/delete meeting requests per day per user
- No separate "developer account" — you use your regular Zoom account on marketplace.zoom.us

## 6. Rate Limits

| Operation | Limit | Window |
|-----------|-------|--------|
| Create meeting | 100 per user | 24 hours |
| All API calls | Varies by endpoint | Per second (see headers) |
| Token refresh | No explicit limit documented | Tokens last 1 hour |

Response headers include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

For our testing use case (a few meetings per day), rate limits are a non-issue.

## 7. Personal Meeting ID (PMI)

- PMI is a permanent, reusable meeting URL tied to a user
- Can be used for instant meetings if "Use this ID for instant meetings" is enabled in user settings
- **API quirk:** Setting `type: 1` (instant) with PMI doesn't always work via API — the API may create a different meeting ID instead
- **Recommendation for testing:** Use `type: 2` (scheduled) meetings with explicit settings, not PMI. More predictable, more control.

## 8. Zoom Marketplace App — Dev Mode vs Published

- **S2S OAuth apps are internal** — they only work on the account that created them
- **No publishing required** for internal use — activate immediately
- **Dev mode** doesn't apply to S2S OAuth — that's for user-facing OAuth apps
- S2S OAuth apps can be activated directly from the Marketplace dashboard
- For our use case (creating meetings on our own account), S2S OAuth is perfect — no review, no publishing

## 9. Comparison: API Approach vs Browser-Based (zoom-host-auto.js)

| Factor | Zoom REST API | Browser-Based (zoom-host-auto.js) |
|--------|--------------|----------------------------------|
| **Setup complexity** | Medium: create S2S OAuth app, get credentials, write token refresh | Low: reuse existing browser session infra |
| **Waiting room control** | Fragile: account settings can override API | Reliable: host is in the meeting, can admit via DOM |
| **Meeting creation speed** | Fast: ~1s API call | Slower: ~15s browser navigation |
| **Dependencies** | Zoom OAuth credentials, scopes | Browser session (already have this) |
| **Reliability** | High for creation; waiting room is the risk | Medium: DOM selectors can break |
| **Auto-admit** | Not built-in; need host to join separately | Natural: host is already in browser |
| **Consistency with GMeet/Teams** | Different pattern (API vs browser) | Same pattern as gmeet-host-auto.js |
| **Free tier** | 40-min limit, 100 meetings/day | Same 40-min limit, no API quota |

### Recommendation

**For MVP3 (automated testing): Use browser-based approach (zoom-host-auto.js)**

Reasons:
1. **Consistency:** Same pattern as GMeet and Teams — browser session creates meeting, host stays in, auto-admits bots
2. **No credential setup:** No OAuth app, no scopes, no token refresh
3. **Waiting room is solved:** Host is in the meeting, auto-admit script handles lobby
4. **Already building it:** Builder (task #1) is already creating zoom-host-auto.js

**For future production (MVP5+): Consider Zoom REST API**

Reasons:
1. Faster meeting creation for high-volume scenarios
2. No browser session needed just for hosting
3. Better for calendar-integration feature (create meetings ahead of time)
4. But: waiting room override issue must be addressed at account settings level

## 10. How Competitors Handle This

### Recall.ai
- Bots join via meeting URL — they don't create meetings
- For testing, they use the meeting URL directly
- They document waiting room as the #1 pain point for Zoom bots
- Solution: "Zoom Signed-in Bots" using ZAK tokens to skip waiting room
- ZAK (Zoom Auth Key) token pre-authorizes the bot to bypass waiting room

### Key Insight from Recall.ai
Recall.ai's approach to waiting room: use **join tokens** (ZAK) that pre-authorize the bot. This is more reliable than trying to disable waiting room via API settings, because it doesn't depend on account-level settings.

Source: [Recall.ai — How to Enable a Zoom Bot to Skip the Waiting Room](https://www.recall.ai/blog/zoom-bot-skip-waiting-room)

## Dead Ends

- **JWT auth:** Deprecated by Zoom since June 2023. Don't use.
- **PMI for instant meetings via API:** Unreliable — API may ignore PMI setting and create a new meeting ID.
- **Disabling waiting room via API alone:** Not reliable if account-level settings enforce it. Must also change account settings or use ZAK tokens.

## Action Items for Team

1. **Builder:** Continue with zoom-host-auto.js (browser-based) for MVP3
2. **Builder:** Implement zoom-auto-admit.js using same pattern as existing auto-admit.js
3. **Future:** If we need API-based meeting creation (calendar integration, high-volume), set up S2S OAuth with `meeting:write:admin` + `user:write:admin` scopes and disable waiting room at account level
4. **Future:** Investigate ZAK tokens for production bot waiting room bypass (Recall.ai pattern)
