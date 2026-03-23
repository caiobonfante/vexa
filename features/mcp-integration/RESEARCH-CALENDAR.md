# Google Calendar Integration Research (2026-03-23)

## Why it matters

Users manually call `POST /bots` with a meeting URL every time. No auto-join, no scheduling, no awareness of upcoming meetings. Every competitor (Recall.ai, Fireflies, Otter, Meeting-BaaS) offers calendar integration as a core feature.

## How competitors do it

### Recall.ai
- Customers implement OAuth themselves, pass refresh token to Recall API
- Recall watches for calendar changes via webhooks (`calendar.sync_events`)
- "Schedule Bot" endpoint assigns bots to calendar events
- Auto-deduplication (prevents duplicate bots when multiple org users share a meeting)
- Uses Cronofy internally for calendar sync
- V2 API with per-bot configuration on calendar events

### Meeting-BaaS
- Bring-your-own OAuth app (client_id, client_secret, refresh_token)
- Calendar events auto-sync once connected
- Supports recurring events with `all_occurrences` scheduling
- Exposes calendar tools via MCP server (`createCalendar`, `listEvents`)

### Fireflies.ai
- Calendar connects at signup via Google/Outlook OAuth
- Auto-join modes: "All meetings with a link", "Only meetings I own", invite-based
- Simplest UX — nearly zero config

### Otter.ai
- Sends "OtterPilot" to auto-join any calendar event with a video link
- Hands-off approach

## Google Calendar API

### What's needed
- **Events: list** — enumerate upcoming events with `conferenceData`
- **Events: watch** — subscribe to event changes via webhook (push notifications)
- **CalendarList: list** — enumerate user's calendars

### Meeting URL extraction
- `conferenceData.entryPoints[].uri` — Google Meet join URL
- `hangoutLink` — fallback for Google Meet
- `location` / `description` — Zoom/Teams URLs added to Google Calendar events

### OAuth
- Scope: `https://www.googleapis.com/auth/calendar.readonly` (sensitive, not restricted)
- For self-hosted: each deployment uses its own Google Cloud project (avoids marketplace review)
- For hosted: needs full Google OAuth verification (weeks, privacy policy, demo video)

### Push notifications
- `events.watch()` creates a notification channel to your HTTPS webhook
- Channels expire after max 7 days — must be renewed
- Notifications say "something changed" — you re-fetch events to see what
- Requires valid SSL certificate
- Use `syncToken` for incremental sync

## Third-party alternatives

| | Direct Google API | Cronofy | Nylas |
|---|---|---|---|
| Multi-provider | Google only | Google, Outlook, iCloud, Exchange | Google, Outlook, Exchange |
| Control | Full | Delegated | Delegated |
| Data exposure | None (self-hosted) | Third party | Third party |
| Cost | Free (API quotas) | Per-feature | Per-connected-account |
| Maintenance | Token refresh, channel renewal | Handled | Handled |
| Used by | — | Recall.ai | — |

**Recommendation:** Start with direct Google Calendar API. Vexa is self-hosted — users manage their own infra, so direct API gives full control, zero third-party data exposure, and no per-account costs. Consider Cronofy only if multi-provider support becomes a priority.

## Architecture

### New service: `calendar-service`

```
User → Dashboard (OAuth consent) → Google → Dashboard (auth code)
  → calendar-service stores refresh token (encrypted)
  → calendar-service sets up watch channel
  → Google pushes change notifications
  → calendar-service fetches events, extracts meeting URLs
  → Calls POST /bots N minutes before start
```

### Database tables

```sql
-- Calendar connections
calendar_connections (
  id, user_id, provider, refresh_token_encrypted,
  calendar_ids, status, last_sync, created_at
)

-- Synced calendar events
calendar_events (
  id, connection_id, external_event_id, title,
  start_time, end_time, meeting_url, platform,
  status (pending/scheduled/joined/skipped), created_at
)

-- User preferences
calendar_preferences (
  user_id, auto_join, join_minutes_before,
  calendars_filter, meeting_filter_rules
)
```

### Integration with existing Vexa

**Reuse:**
- `POST /bots` — calendar service just calls this existing API
- `parse_meeting_link` — URL parsing and platform detection (MCP service)
- NextAuth Google provider — already has Google OAuth, needs `calendar.readonly` scope added
- Zoom OAuth flow pattern — model to follow
- Shared models — extend with calendar tables

**New:**
- calendar-service (new microservice)
- Database migrations
- Dashboard UI: calendar connection, preferences, upcoming meetings
- Webhook endpoint (publicly accessible HTTPS)

## MCP + webhooks integration

### MCP tools to add
- `list_upcoming_meetings` — calendar events with meeting URLs
- `schedule_bot_for_event` — schedule bot for specific event
- `get_calendar_status` — connection status, sync state
- `set_auto_join_preference` — enable/disable, lead time

Enables: "Record all my meetings tomorrow" via Claude.

### Webhook events
- `calendar.connected` / `calendar.disconnected`
- `calendar.event.upcoming` — event starts within configured window
- `calendar.event.bot_scheduled` / `calendar.event.bot_joined`

## Scope estimates

### MVP (2-3 weeks)
- Google Calendar OAuth (extend NextAuth with `calendar.readonly`)
- Calendar-service: poll-based sync (every 5 minutes)
- Extract Google Meet URLs from `conferenceData`
- Auto-schedule bots N minutes before start
- Dashboard: connect calendar, toggle auto-join, upcoming meetings
- Single calendar per user

### V1 (+2-3 weeks)
- Google push notifications (replace polling)
- Channel renewal cron (every 6 days)
- Zoom/Teams URLs from `location`/`description`
- Per-meeting opt-in/opt-out
- MCP tools + webhook events

### V2 (future)
- Microsoft Outlook/Office 365
- Multi-calendar per user
- Bot deduplication across org users
- Meeting filter rules (external only, 3+ participants, etc.)
- Cronofy for simplified multi-provider

## Risks

1. **OAuth verification** — sensitive scope needs Google review for hosted offering. Self-hosted uses own project.
2. **Privacy** — calendar data is sensitive. Encrypt tokens, minimize stored data, clear retention policy.
3. **Push notification reliability** — can be delayed/dropped. Need poll-based fallback.
4. **Watch channel expiry** — 7 days max. Must handle renewal failures.
5. **Rate limits** — 10 queries/second per user, one watch channel per calendar.
6. **No existing code** — zero calendar-related code in the codebase today.

## Existing codebase check

- No calendar-related code found (only Lucide Calendar icons in dashboard UI)
- No GitHub issues requesting calendar integration
- NextAuth Google provider exists but only for user auth, no calendar scopes
- Zoom OAuth flow provides good pattern to follow

## Sources

- [Recall.ai Calendar V2](https://docs.recall.ai/docs/calendar-v2-integration-guide)
- [Meeting-BaaS Calendar](https://docs.meetingbaas.com/api-v2/getting-started/calendars)
- [Fireflies Auto-Join](https://guide.fireflies.ai/articles/5074225515-learn-about-fireflies-auto-join-settings)
- [Google Calendar Push Notifications](https://developers.google.com/workspace/calendar/api/guides/push)
- [Cronofy Best Calendar APIs](https://www.cronofy.com/blog/best-calendar-apis)
- [Nylas Calendar API](https://www.nylas.com/products/calendar-api/)
