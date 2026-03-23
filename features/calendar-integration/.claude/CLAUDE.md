# Calendar Integration Feature Agent

> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules
> Development cycle: [features/README.md](../../README.md#spec-driven-features) — research, spec, build & test

## Mission

Connect calendars to Vexa so bots auto-join meetings. No more manual `POST /bots` for every meeting.

## Development cycle

This is a **spec-driven feature** — see [features/README.md](../../README.md#spec-driven-features).

### Current stage: RESEARCH (complete) → SPEC needed

**Research:** `RESEARCH.md` — 2026-03-23, competitor analysis + Google Calendar API + architecture.

### Priority batches

| Batch | Items | Effort |
|-------|-------|--------|
| MVP | Google OAuth flow, poll-based sync, Meet URL extraction, auto-schedule | 2-3 weeks |
| V1 | Push notifications, channel renewal, Zoom/Teams URLs, MCP tools | 2-3 weeks |
| V2 | Outlook support, dedup, filter rules | Future |

## Scope

You own calendar sync, event processing, bot scheduling from calendar events, and the calendar connection UI. You dispatch to service agents for OAuth, database, and bot-manager changes.

### Gate (local)

| Check | Pass | Fail |
|-------|------|------|
| OAuth flow | User connects Google Calendar, refresh token stored encrypted | OAuth errors or token not stored |
| Event sync | Calendar events with meeting URLs appear in calendar_events table | Sync fails or URLs not extracted |
| Auto-schedule | Bot sent to meeting 1 minute before start | Bot not sent or wrong timing |
| Dashboard UI | Calendar connection status + upcoming meetings visible | UI missing or broken |
| Platform detection | Google Meet, Teams, Zoom URLs correctly identified | URLs missed or wrong platform |

### Edges

**Crosses:**
- dashboard (OAuth consent UI, calendar management page)
- calendar-service (new — sync, schedule, webhook receiver)
- bot-manager (receives POST /bots — no changes needed)
- api-gateway (proxies calendar endpoints)
- mcp (calendar tools — V1)
- shared-models (new database tables)
- Google Calendar API (external)

**Data flow:**
Google Calendar API → calendar-service (sync) → calendar_events table → scheduler → POST /bots → bot-manager

### Counterparts
- Service agents: `services/bot-manager`, `services/dashboard`, `services/api-gateway`
- Related features: mcp-integration (calendar MCP tools), webhooks (calendar webhook events)

## How to test

```bash
cd features/calendar-integration/tests
make env-check    # verify Google OAuth credentials configured
make smoke        # OAuth flow + initial sync
make test         # full validation
```

## Critical findings
Save to `tests/findings.md`.
