# Calendar Integration

> **Confidence: 0** — Research complete. **Not built.** This is a new feature — calendar-service doesn't exist yet. Architecture designed, competitor analysis done, Google Calendar API researched.
> **Tested:** Nothing — no code exists.
> **Not tested:** Everything — OAuth flow, event sync, URL extraction, auto-schedule, dashboard UI.
> **Contributions welcome:** This is a **greenfield 2-3 week project.** Google OAuth flow, calendar-service (Python/FastAPI), dashboard calendar connection UI. See the architecture below.

## Why

Auto-join meetings from Google Calendar (Outlook later). Without this, someone has to call `POST /bots` for every meeting. With it, bots are scheduled automatically based on calendar events with video conferencing links.

Table stakes — every competitor (Recall.ai, Fireflies, Otter, Meeting-BaaS) offers this. Pipeline: calendar event → scheduler → `POST /bots` 1 min before start → transcription → post-meeting automation.

## What

Connect Google Calendar (and later Outlook) to Vexa. The system watches for meetings with video conferencing links and auto-sends bots. Users configure which calendars, which meetings, and how far in advance bots join.

### Components

- **calendar-service** (new) — syncs calendar events, schedules bots, manages OAuth tokens
- **dashboard** — OAuth consent flow, calendar connection UI, preferences panel, upcoming meetings view
- **api-gateway** — proxies calendar API endpoints
- **bot-manager** — receives `POST /bots` from calendar-service (existing API, no changes)
- **mcp** — exposes calendar tools for AI agents

### Data flow

```
[Setup — one time]
  User → Dashboard OAuth consent → Google → auth code
  → calendar-service stores encrypted refresh token
  → calendar-service creates watch channel on user's calendars

[Ongoing — automatic]
  Google pushes event change notification → calendar-service webhook
  → calendar-service fetches updated events (incremental sync)
  → extracts meeting URLs from conferenceData / location / description
  → stores in calendar_events table

[Before each meeting]
  Scheduler checks calendar_events where start_time - now < join_minutes_before
  → calls POST /bots with extracted meeting URL
  → updates calendar_event status: pending → scheduled → joined

[Dashboard]
  Shows upcoming meetings with bot status
  Toggle auto-join per meeting
  Calendar connection status
```

### Key behaviors

- Auto-join: bots join N minutes before meeting start (configurable, default 1 minute)
- Platform detection: extracts Google Meet, Teams, Zoom URLs from calendar events
- Deduplication: one bot per meeting even if multiple org users share the event
- Incremental sync: only fetches changed events (Google syncToken)
- Watch channel renewal: auto-renews every 6 days (7-day expiry)
- Fallback polling: if push notifications fail, poll every 5 minutes
- Encrypted token storage: refresh tokens encrypted at rest

### Supported meeting URL sources

| Calendar field | Platform | Example |
|---|---|---|
| `conferenceData.entryPoints[].uri` | Google Meet | `https://meet.google.com/abc-defg-hij` |
| `hangoutLink` | Google Meet | `https://meet.google.com/abc-defg-hij` |
| `location` | Zoom, Teams | `https://zoom.us/j/123456`, `https://teams.microsoft.com/meet/...` |
| `description` (URL extraction) | Any | URLs parsed from event description |

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | Calendar events from Google API | calendar-service sync | Event processor |
| **core** | Extracted meeting URLs + scheduling decisions | Event processor | Bot scheduler |
| **rendered** | Bot status per calendar event | Bot scheduler + bot-manager callbacks | Dashboard, webhooks |

### Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `GOOGLE_CLIENT_ID` | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | — | Google OAuth client secret |
| `CALENDAR_SYNC_INTERVAL` | `300` | Polling interval in seconds (fallback) |
| `JOIN_MINUTES_BEFORE` | `1` | Minutes before meeting start to send bot |
| `CALENDAR_WEBHOOK_URL` | — | Public HTTPS URL for Google push notifications |
| `TOKEN_ENCRYPTION_KEY` | — | Key for encrypting stored refresh tokens |

## How

### Prerequisites

1. Google Cloud project with Calendar API enabled
2. OAuth consent screen configured (calendar.readonly scope)
3. OAuth credentials (web application type)
4. Public HTTPS endpoint for Google push notifications (production only; polling for dev)

### Setup

```bash
# 1. Create .env
cp .env.example .env
# Fill in Google OAuth credentials

# 2. Start services
cd deploy/compose && docker compose up -d calendar-service

# 3. Connect calendar via dashboard
# Navigate to Settings → Calendar → Connect Google Calendar
```

### Verify

```bash
cd features/calendar-integration/tests
make env-check    # verify config
make smoke        # OAuth flow + initial sync
make test         # full validation
```

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Dashboard   │────▶│  calendar-service │────▶│  bot-manager │
│  (OAuth UI)  │     │  (sync + schedule)│     │  (POST /bots)│
└─────────────┘     └──────────────────┘     └──────────────┘
                           │    ▲
                           │    │ push notifications
                           ▼    │
                    ┌──────────────┐
                    │ Google       │
                    │ Calendar API │
                    └──────────────┘
```

### Database tables

```sql
calendar_connections (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  provider VARCHAR(20) DEFAULT 'google',    -- google, microsoft (future)
  refresh_token_encrypted TEXT NOT NULL,
  calendar_ids JSONB DEFAULT '[]',          -- selected calendar IDs
  sync_token TEXT,                          -- Google incremental sync token
  channel_id TEXT,                          -- Google watch channel ID
  channel_expiry TIMESTAMPTZ,              -- watch channel expiry
  status VARCHAR(20) DEFAULT 'active',     -- active, expired, revoked
  last_sync TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

calendar_events (
  id SERIAL PRIMARY KEY,
  connection_id INTEGER REFERENCES calendar_connections(id),
  external_event_id TEXT NOT NULL,          -- Google event ID
  title TEXT,
  start_time TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ,
  meeting_url TEXT,                         -- extracted video conference URL
  platform VARCHAR(20),                    -- google_meet, teams, zoom
  recurrence_id TEXT,                      -- for recurring events
  bot_status VARCHAR(20) DEFAULT 'pending', -- pending, scheduled, joining, joined, skipped, failed
  meeting_id INTEGER,                      -- FK to meetings table once bot is sent
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(connection_id, external_event_id)
);
```

## Scheduler

Calendar integration uses the **generic scheduler** (`libs/shared-models/shared_models/scheduler.py`) to fire API calls at the right time.

### How it works

```
Calendar sync finds meeting at 10:00
  → schedule_job(redis, {
      execute_at: 09:59 (1 min before),
      request: POST /bots with meeting URL,
      idempotency_key: "cal_evt123_bot"
    })
  → Redis sorted set: ZADD scheduler:jobs 1774220340 <job_json>

Executor loop (every 5s):
  → ZRANGEBYSCORE scheduler:jobs -inf <now>  → finds due jobs
  → ZREM (atomic pop, prevents duplicate execution)
  → Fires POST /bots
  → On success: notify callback, store in history
  → On failure: retry with backoff (30s, 2min, 5min)
```

### Reliability

| Scenario | Handling |
|----------|----------|
| Service restart | Orphaned executing jobs re-queued on startup |
| Duplicate scheduling | `idempotency_key` prevents two bots for same event |
| API failure | 3 retries with exponential backoff |
| API timeout | 30s default, counts as failure |
| Redis restart | Jobs persisted via RDB/AOF |

### Scheduler

The scheduler is a **core feature** — see [features/scheduler/](../scheduler/) for full design, tests, and roadmap. Calendar integration is one consumer; webhooks, deferred transcription, and recording cleanup also use it.

### Other use cases

The scheduler is generic — not tied to calendar:

| Use case | When | What |
|----------|------|------|
| Calendar auto-join | 1min before meeting | `POST /bots` |
| Deferred transcription | Meeting end + 30s | `POST /meetings/{id}/transcribe` |
| Recording cleanup | 90 days after | `DELETE /recordings/{id}` |
| Meeting reminder | 5min before | Webhook to user endpoint |

## Roadmap

### MVP (P0)
- Google Calendar OAuth flow via dashboard
- Poll-based sync (every 5 minutes)
- Extract Google Meet URLs from conferenceData
- Auto-schedule bots 1 minute before start
- Dashboard: connect/disconnect, upcoming meetings list

### V1 (P1)
- Google push notifications (replace polling)
- Watch channel auto-renewal
- Zoom/Teams URL extraction from location/description
- Per-meeting opt-in/opt-out in dashboard
- MCP tools: `list_upcoming_meetings`, `schedule_bot_for_event`
- Webhook events: `calendar.event.upcoming`, `calendar.event.bot_scheduled`

### V2 (P2)
- Microsoft Outlook/Office 365 support
- Multi-calendar per user
- Bot deduplication across org users
- Meeting filter rules (external only, 3+ participants, etc.)
- Calendar-specific bot configuration
