# Calendar Integration Test Findings

## Gate verdict: NOT STARTED

## Implementation status (2026-03-23)

No implementation exists. Research complete — see `RESEARCH.md`.

### What exists
- Research report with architecture, competitor analysis, API overview
- Feature scaffold (README, CLAUDE.md, .env.example, tests/)

### What's needed
- calendar-service (new Python/FastAPI microservice)
- Database migrations (calendar_connections, calendar_events)
- Dashboard OAuth flow (extend NextAuth with calendar.readonly scope)
- Dashboard calendar management UI
- Scheduler (background task to send bots before meetings)

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Google OAuth flow | 0 | NextAuth Google provider exists, needs calendar scope | 2026-03-23 (audit) | Implement OAuth + store refresh token |
| Event sync | 0 | No calendar-service exists | 2026-03-23 (audit) | Build calendar-service with sync |
| Meeting URL extraction | 0 | parse_meeting_link exists in MCP service | 2026-03-23 (audit) | Extract from conferenceData + location |
| Auto-schedule | 0 | POST /bots endpoint exists | 2026-03-23 (audit) | Build scheduler |
| Dashboard UI | 0 | No calendar UI exists | 2026-03-23 (audit) | Build connection + upcoming views |
| Push notifications | 0 | Not implemented | — | Google watch channel + webhook |
