# Meeting-Aware Agent

<!-- DESIGN: what we want. Can be ahead of code. Updated before implementation. -->

## Why

The agent (via Telegram, dashboard, or MCP) has no knowledge of the user's meetings. Users have to manually ask "what meetings do I have?" or paste meeting IDs. When meeting_aware is enabled on a bot session, the agent automatically knows about the user's active meetings — who's in them, what's been said, what the status is. This makes the agent useful as a real-time meeting companion, not just a chatbot.

## Data Flow

```
Client creates session with meeting awareness:
    POST /api/sessions { meeting_aware: true }
        |
        v
    api-gateway :8056 → agent-api :8100
        |
        v
    agent-api stores session config in Redis
        session:{id} = { ..., meeting_aware: true }

Every chat turn in a meeting-aware session:
    POST /api/chat { session_id: "abc" }
        |
        v
    api-gateway :8056
        |
        v
    look up session config (Redis or agent-api)
        meeting_aware = true?
            |
            no  → forward to agent-api as-is (normal chat)
            yes → fetch meeting context:
                    |
                    v
                GET /bots?user_id={X-User-ID}&status=active
                    → meeting-api :8080
                    → returns: active bots with meeting IDs
                    |
                    v
                for each active meeting:
                    GET /transcripts/{meeting_id}?limit=50
                    → transcription-collector
                    → returns: latest 50 segments with speakers
                    |
                    v
                build context JSON:
                    {
                      "active_meetings": [
                        {
                          "meeting_id": 123,
                          "platform": "teams",
                          "participants": ["Alice", "Bob"],
                          "status": "active",
                          "latest_segments": [
                            { "speaker": "Alice", "text": "...", "timestamp": "..." }
                          ]
                        }
                      ]
                    }
                    |
                    v
                inject as X-Meeting-Context header
        |
        v
    agent-api :8100
        |
        v
    X-Meeting-Context header present?
        no  → normal chat (no meeting knowledge)
        yes → parse JSON, prepend to Claude system prompt:
              "The user has these active meetings: [...]
               Latest transcript from meeting 123:
               Alice: ... Bob: ... Alice: ..."
        |
        v
    Claude agent responds with meeting awareness
        "Based on your meeting with Alice and Bob,
         they discussed quarterly results..."
```

## Code Ownership

```
services/api-gateway              → meeting context injection logic (new middleware)
services/agent-api                → session config (meeting_aware flag), context parsing
services/meeting-api              → GET /bots?user_id=&status= endpoint (may exist)
services/transcription-collector  → GET /transcripts with limit (exists)
```

---

<!-- STATE: what we have. Only updated with execution evidence. Never optimistic. -->

## Quality Bar

```
Session created with meeting_aware=true     flag persisted in Redis          PASS
Gateway fetches active meetings             GET /bots returns active bots    PASS (live: found 2 active bots)
Gateway fetches latest transcript           GET /transcripts returns segs    PASS (live: 5 segments from Teams meeting)
Context injected as header                  X-Meeting-Context present        PASS (1230 bytes auto-injected by gateway)
Agent-api parses context into prompt        system prompt has meeting data   PASS (prompt file shows [MEETING CONTEXT])
Agent responds with meeting knowledge       references meeting content       PASS (cited revenue 15%, APAC 22%, participants)
No meeting_aware → no context injection     header absent, normal chat       PASS
Context refresh on each turn                fresh data, not stale cache      PASS (each chat triggers fresh /bots/status)
```

## Gate

**Score 60 (API layer)**: Create meeting-aware session → send chat via curl → gateway fetches active bots + transcript → response references meeting content. Testable without Telegram or live meeting (use existing meeting data in DB).

**Score 80 (live meeting)**: Host a meeting with `/host-teams-meeting-auto`, send TTS bots, wait for transcript segments → send chat via API → agent references what was said in the meeting.

**Score 90 (Telegram E2E)**: Real meeting running with bot → open Telegram → send message → agent responds with meeting awareness. Requires TELEGRAM_BOT_TOKEN.

**PASS**: Agent references meeting content without being told which meeting.

**FAIL**: Agent asks "which meeting?" or has no meeting knowledge.

## Certainty

```
Session meeting_aware flag stored    95  Redis confirmed, API returns flag    2026-03-28
Gateway meeting context middleware   90  Auto-detects flag, fetches bots, fetches transcript    2026-03-28
GET /bots?user_id&status endpoint    90  Found 2 active bots in live test    2026-03-28
Context header injected              90  1230 bytes auto-injected by gateway    2026-03-28
Agent-api parses X-Meeting-Context   95  Prompt file shows full [MEETING CONTEXT] block    2026-03-28
Agent uses meeting context           85  Cited revenue 15%, APAC 22%, churn 3.8→2.3%    2026-03-28
Flag off → no injection              95  Normal sessions skip bots/status entirely    2026-03-28
```

## Constraints

- Gateway owns the context injection — agent-api never calls meeting-api directly
- agent-api receives meeting context as a header, does not know where it came from
- meeting-api is not modified — gateway uses existing endpoints to fetch data
- Context is fetched fresh on every chat turn — no caching (meetings change in real time)
- meeting_aware is per-session, not per-user — different sessions can have different settings
- X-Meeting-Context header is JSON — agent-api parses it, not the gateway
- When meeting_aware=false or unset, gateway does NOT fetch meetings (zero overhead)
- Transcript limit: latest 50 segments max — prevents context explosion
- No new database tables — uses existing bots, meetings, transcriptions tables via API

## Deployment

```
Code changes:
    services/api-gateway/       → new middleware for meeting context injection
    services/agent-api/         → parse X-Meeting-Context, inject into system prompt
    deploy/compose/             → env vars if needed (none expected)

Containers to rebuild:
    vexa-restore-api-gateway-1       → docker compose build api-gateway
    vexa-restore-agent-api-1         → docker compose build agent-api

Restart required:
    docker compose up -d api-gateway agent-api

Verification after deploy:
    curl -sf http://localhost:8056/health          → gateway healthy
    curl -sf http://localhost:8100/health          → agent-api healthy
    POST /api/chat with meeting_aware session      → X-Meeting-Context injected

No migration needed — no database changes.
No new env vars expected — gateway already has access to meeting-api routes.

Env source of truth: deploy/env/env-example
    Running env: docker exec vexa-restore-api-gateway-1 env | sort
    If worktree needs different env, create conductor/env-overrides in the worktree.
```

## Testing Prerequisites

```
For score 60 (API layer):
    - compose stack running (make up)
    - at least one meeting with transcription in DB (from prior test runs)
    - curl to test API directly

For score 80 (live meeting):
    - /host-teams-meeting-auto to create meeting + auto-admit
    - send TTS bots to generate transcript
    - curl to test API with active meeting

For score 90 (Telegram E2E):
    - TELEGRAM_BOT_TOKEN set in .env (available)
    - telegram-bot service running
    - active meeting with bot
    - send message from real Telegram client
```

## Known Issues

- Browser sessions show "participants: unknown" when no transcript segments exist
- Bot TTS self-filters: bot's own speech excluded from transcript (by design, prevents loops)
- X-Meeting-Context header has HTTP header size limits (~8KB) — 50 segments should fit but may need monitoring
- Gateway needs AGENT_API_URL env var set manually (not in default compose, uses bridge gateway IP)

## Design Decisions

- **Only active meetings** — no history, no calendar. If no bot is active, no context injected.
- Multiple active meetings: include all (gateway doesn't filter)
- 50 segments per meeting max — prevents context explosion
- Write-back (agent sends to meeting chat) is a separate feature, not in scope
