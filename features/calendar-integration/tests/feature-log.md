# Calendar Integration — Feature Log

## [EXTERNAL] Google Calendar OAuth scope: calendar.readonly is "sensitive" not "restricted"
Source: Google API docs + RESEARCH.md
Sensitive scopes need OAuth consent screen verification for public apps, but self-hosted deployments
using their own GCP project are exempt — no Google review needed.
Implication: self-hosted MVP can ship without OAuth verification. Hosted offering needs a privacy
policy, demo video, and Google's manual review (~2-4 weeks).

## [EXTERNAL] Zoom OAuth pattern in codebase is the canonical template for calendar OAuth
Source: services/dashboard/src/app/api/zoom/oauth/start|complete/route.ts
The Zoom flow uses HMAC-signed state tokens, separate dashboard API routes (not NextAuth),
and stores refresh tokens in user.data JSONB field via admin-api. Calendar OAuth should follow
this exact pattern — no new auth infrastructure needed.

## [EXTERNAL] Token storage: JSONB user.data vs new table
For MVP: store Google Calendar refresh token in user.data.google_calendar.oauth (same as Zoom
stores in user.data.zoom.oauth). Zero migration needed for token storage.
Calendar events MUST go in their own table — needs alembic migration.
Recommendation: user.data for token (MVP speed), calendar_events table via migration (tracking).

## [PRACTICE] Alembic migrations live in libs/shared-models/alembic/versions/
Naming: {hex_id}_{description}.py. Each has revision/down_revision chain.
The transcription-collector Dockerfile runs `alembic upgrade head` at startup.
Both docker-compose files mount alembic.ini + alembic dir into transcription-collector.
New migrations must update down_revision to latest: a1b2c3d4e5f6 (recordings/media_files).

## [PRACTICE] New services in docker-compose: two compose files to update
1. deploy/compose/docker-compose.yml — main stack
2. features/agentic-runtime/deploy/docker-compose.yml — agentic stack
Both use same network pattern. Add calendar-service to both with identical env vars.
Port assignment: check PORT-MAP.md to avoid collision before assigning host port.

## [PRACTICE] API Gateway proxy pattern
gateway uses forward_request() helper + BOT_MANAGER_URL env pattern.
Adding calendar: add CALENDAR_SERVICE_URL env var + new @app.{method}("/calendar/...") routes
that call forward_request(app.state.http_client, METHOD, f"{CALENDAR_SERVICE_URL}/...", request).
Require X-API-Key header (same as /bots endpoint).

## [DEAD-END] Cannot add calendar.readonly scope to NextAuth GoogleProvider for calendar OAuth
NextAuth's Google provider is for user authentication only. Its tokens are short-lived and not
stored for reuse. Adding calendar scope to NextAuth breaks the auth flow and doesn't give a
usable refresh token for background sync.
Fix: Separate OAuth flow (like Zoom) — dashboard routes /api/calendar/oauth/start + /complete,
store refresh token in user.data via admin-api.

## [EXTERNAL] Meeting URL extraction from Google Calendar events
conferenceData.entryPoints[].uri — primary source for Google Meet URLs
hangoutLink — legacy fallback for Google Meet
location field — often contains Zoom/Teams URLs when added via those apps' GCal integrations
description field — Teams/Zoom URLs often in body text; needs regex extraction
Platform detection: same parse_meeting_link logic used elsewhere in Vexa.

## [EXTERNAL] Google Calendar push notifications: 7-day channel expiry
Source: Google Calendar API docs (developers.google.com/workspace/calendar/api/guides/push)
Watch channels expire after max 7 days. Must be renewed proactively (cron every 6 days).
Push notifications only say "something changed" — must re-fetch events to see what.
Requires valid public HTTPS endpoint. For MVP: use poll-based sync instead (every 5 min).
Push notifications are V1, not MVP.

## [EXTERNAL] Google Calendar sync tokens for incremental sync
After initial full list, API returns a nextSyncToken. Store it per-user.
Subsequent polls: pass syncToken to events.list() — returns only changed events since last sync.
On 410 Gone response: sync token expired, do a full re-sync.
Reduces API quota usage significantly — important for rate limits (10 req/s per user).
