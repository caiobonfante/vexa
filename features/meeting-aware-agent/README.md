# Meeting-Aware Agent

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
packages/agent-api                → session config (meeting_aware flag), context parsing
packages/meeting-api              → GET /bots?user_id=&status= endpoint (may exist)
services/transcription-collector  → GET /transcripts with limit (exists)
```

## Quality Bar

```
Session created with meeting_aware=true     flag persisted in Redis          FAIL
Gateway fetches active meetings             GET /bots returns active bots    FAIL
Gateway fetches latest transcript           GET /transcripts returns segs    FAIL
Context injected as header                  X-Meeting-Context present        FAIL
Agent-api parses context into prompt        system prompt has meeting data   FAIL
Agent responds with meeting knowledge       references meeting content       FAIL
No meeting_aware → no context injection     header absent, normal chat       FAIL
Context refresh on each turn                fresh data, not stale cache      FAIL
```

## Gate

**90 test**: Real meeting running with bot (Teams or GMeet) → open Telegram → send message → agent responds with awareness of the meeting (who's in it, what's been said). No manual meeting ID or /transcript command needed — the agent just knows.

**PASS**: Agent references meeting content without being told which meeting.

**FAIL**: Agent asks "which meeting?" or has no meeting knowledge.

## Certainty

```
Session meeting_aware flag stored    0   not implemented    —
Gateway meeting context middleware   0   not implemented    —
GET /bots?user_id&status endpoint    0   may exist, unchecked    —
Context header injected              0   not implemented    —
Agent-api parses X-Meeting-Context   0   not implemented    —
Agent uses meeting context           0   not implemented    —
Flag off → no injection              0   not implemented    —
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

## Known Issues

- None yet (not implemented)

## Design Decisions

- **Only active meetings** — no history, no calendar. If no bot is active, no context injected.
- Multiple active meetings: include all (gateway doesn't filter)
- 50 segments per meeting max — prevents context explosion
- Write-back (agent sends to meeting chat) is a separate feature, not in scope
