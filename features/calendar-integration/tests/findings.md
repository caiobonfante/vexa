# Calendar Integration Test Findings

## Gate verdict: DEPLOYED — pending OAuth test

## Score: 65 (deployed, endpoints responding, migration applied)

## Implementation status (2026-03-25)

Full MVP built by calendar-executor, verified by independent verifier (5/6 confirmed, 1 blocking auth bug found and fixed).

### What was built

| Component | Status | Verified |
|-----------|--------|----------|
| Alembic migration (`calendar_events` table) | Done | CONFIRMED — schema correct, revision chain valid |
| SQLAlchemy model (`CalendarEvent`) | Done | CONFIRMED — matches migration |
| Dashboard OAuth start route | Done | CONFIRMED — `calendar.readonly` scope, state signed |
| Dashboard OAuth complete route | Done | CONFIRMED — token exchange + storage in user.data |
| Dashboard OAuth callback page | Done | CONFIRMED — redirect handling correct |
| calendar-service (FastAPI, 6 endpoints) | Done | CONFIRMED |
| Google Calendar sync (refresh token, events.list, syncToken) | Done | CONFIRMED |
| Meeting URL extraction (conferenceData, hangoutLink, location, description) | Done | CONFIRMED |
| Bot scheduling (POST /bots with X-API-Key) | Done | CONFIRMED (auth bug found + fixed) |
| API Gateway proxy routes | Done | CONFIRMED — 501 when unconfigured |
| Docker Compose integration (port 8050) | Done | CONFIRMED |

### Bug found and fixed during verification

**Auth bug in sync.py**: Originally used `X-User-Id` header for POST /bots — bot-manager requires `X-API-Key` token auth. Would silently fail with 401/403 on every scheduling attempt. Fixed: now uses `BOT_API_TOKEN` env var with `X-API-Key` header.

### Deployment (2026-03-25)

Deployed by calendar-executor:
- Container built and running on port 8050
- Migration applied (calendar_events table with 12 columns, 5 indexes, 2 FKs)
- Health: `{"status":"ok","service":"calendar-service"}`
- Gateway proxy: `GET /calendar/status?user_id=1` → `{"connected":false,"event_count":0}`
- Gateway proxy: `GET /calendar/status?user_id=999` → `{"detail":"User not found"}`
- Gateway proxy: `GET /calendar/events?user_id=1` → `[]`
- BOT_API_TOKEN configured: `vxa_user_efBmQuJGVpA6lwNNxVkC7vE0hXWm9yjPJA1ecJmm`
- email-validator dependency added to requirements.txt

### What remains for full functionality

1. **Google Console setup** — add `calendar.readonly` scope to OAuth consent screen, add redirect URI
2. **Test OAuth flow** — connect a Google Calendar, verify events sync
3. **Test auto-join** — verify bot is sent to upcoming meeting within lead_time

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Google OAuth flow | 60 | Dashboard routes built (copy of Zoom pattern), independently verified | 2026-03-25 | Deploy + test with real Google account |
| Event sync | 60 | google_calendar.py: events.list with syncToken, 410 handling | 2026-03-25 | Deploy + verify events appear in DB |
| Meeting URL extraction | 70 | Covers conferenceData, hangoutLink, location, description regex | 2026-03-25 | Test with diverse calendar events |
| Auto-schedule | 60 | POST /bots with X-API-Key auth (bug fixed) | 2026-03-25 | Deploy + test with upcoming meeting |
| Dashboard UI | 0 | Settings/calendar page not built yet | 2026-03-25 | Build connection + upcoming views |
| Push notifications | 0 | Not in MVP scope | — | Google watch channel + webhook (V1) |
| API Gateway routes | 80 | 5 proxy routes, optional 501 degradation | 2026-03-25 | Deploy + test |

## Risks

- Google OAuth consent screen may be in "Testing" mode (max 100 users)
- Zoom URL regex may miss base64 password chars (+, /)
- sync_token DB column unused (stored in user.data JSONB instead) — dead column
- No immediate sync on OAuth connect — first events appear after 5min polling interval
