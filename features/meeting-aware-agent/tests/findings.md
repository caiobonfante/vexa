# Meeting-Aware Agent — Findings

## Score: 60

Full API chain implemented and verified. Agent responds with meeting awareness when X-Meeting-Context header is present. Gateway middleware works but needs an active running bot to trigger automatic injection.

## Evidence

### Test 1: Session with meeting_aware=true — PASS
```
$ curl -s -X POST http://localhost:8056/api/sessions \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"user_id": "5", "name": "Meeting Test", "meeting_aware": true}'

{"session_id":"36364bed-...","name":"Meeting Test","meeting_aware":true}
```

### Test 2: Flag persisted in Redis — PASS
```
$ curl -s "http://localhost:8056/api/sessions?user_id=5" -H "X-API-Key: $API_KEY"
{"sessions":[{..."meeting_aware":true,"id":"36364bed-..."}]}
```

### Test 3: Gateway middleware detects meeting_aware — PASS
```
Gateway logs when meeting_aware=true:
  Meeting context check: user_id=5, session_id=36364bed-...
  Session meta from Redis: {..., "meeting_aware": true}
  Meeting-aware session detected for user 5
  Fetching meeting context for internal user 5

Gateway logs when meeting_aware=false:
  Meeting context check: user_id=5, session_id=cddd865e-...
  Session meta from Redis: {..., "meeting_aware": false}
  (no further context fetching)
```

### Test 4: SSE streaming through gateway — PASS
```
$ curl -sN http://localhost:8056/api/chat -H "X-API-Key: $API_KEY" ...
data: {"type": "session_reset", ...}
data: {"type": "text_delta", "text": "..."}
data: {"type": "done", "session_id": "..."}
data: {"type": "stream_end", ...}
```

### Test 5: Agent responds with meeting awareness — PASS (KEY EVIDENCE)
```
$ curl -sN http://localhost:8100/api/chat \
  -H "Content-Type: application/json" \
  -H 'X-Meeting-Context: {"active_meetings":[{"meeting_id":"bay-npte-svc","platform":"google_meet","status":"active","participants":["Dmitriy Grankin","Alice"],"latest_segments":[{"speaker":"Dmitriy Grankin","text":"We need to finalize the Q1 budget by Friday"},{"speaker":"Alice","text":"I agree, lets pull up the spreadsheet with the latest numbers"},{"speaker":"Dmitriy Grankin","text":"The marketing spend was higher than expected but revenue targets are on track"}]}]}' \
  -d '{"user_id": "5", "message": "What is being discussed in my meeting right now?"}'

data: {"type": "text_delta", "text": "\n\nYour meeting **bay-npte-svc** (Google Meet) with **Dmitriy Grankin** and **Alice** is discussing:\n\n- **Finalizing the Q1 budget** — deadline is Friday\n- **Marketing spend** came in higher than expected\n- **Revenue targets** are on track despite the overspend\n- They're pulling up a spreadsheet with the latest numbers to review"}
data: {"type": "done", "session_id": "ba16ac07-...", "duration_ms": 3578}
```

### Test 6: Prompt file verified in agent container — PASS
```
$ docker exec agent-5-306ee30f cat /tmp/.chat-prompt.txt

[MEETING CONTEXT] The user has active meetings right now:

Meeting bay-npte-svc (google_meet), participants: Dmitriy Grankin, Alice
Latest transcript:
  Dmitriy Grankin: We need to finalize the Q1 budget by Friday
  Alice: I agree, lets pull up the spreadsheet with the latest numbers
  Dmitriy Grankin: The marketing spend was higher than expected but revenue targets are on track

Use this meeting context to inform your responses. The user may ask about what's being discussed.

---

What is being discussed in my meeting right now?
```

### Test 7: Non-meeting-aware session — PASS
```
$ curl -s http://localhost:8056/api/sessions -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" -d '{"user_id": "5", "name": "Normal Chat"}'
{"session_id":"cddd865e-...","name":"Normal Chat","meeting_aware":false}
```

## Certainty Table

| Check | Score | Evidence | Last checked |
|-------|-------|----------|-------------|
| Session meeting_aware flag stored | 90 | POST /api/sessions returns meeting_aware:true, persisted in Redis | 2026-03-28 |
| Gateway meeting context middleware | 80 | Middleware runs, checks Redis, calls bots/status. Dual-strategy fetch. | 2026-03-28 |
| GET /bots?user_id&status endpoint | 90 | Returns running_bots via gateway | 2026-03-28 |
| Context header injected | 80 | Manual header test → prompt file confirmed. Auto-inject needs active bot. | 2026-03-28 |
| Agent-api parses X-Meeting-Context | 95 | Prompt file + agent response reference meeting content | 2026-03-28 |
| Agent uses meeting context | 90 | Agent cited participants, topics, details from transcript (Test 5) | 2026-03-28 |
| Flag off → no injection | 90 | Non-meeting-aware: no context fetching in logs | 2026-03-28 |
| Context refresh on each turn | 80 | Each POST /api/chat triggers fresh context fetch | 2026-03-28 |

## What's Proven (Score 60)

1. **Session flag** — meeting_aware stored in Redis, returned on creation
2. **Gateway middleware** — detects meeting_aware, fetches bots, resolves user_id
3. **Context formatting** — JSON → human-readable prompt with participants and transcript
4. **Prompt injection** — Context prepended to user message in agent container
5. **Agent awareness** — Claude references meeting participants, topics, and details (Test 5)
6. **No-flag behavior** — Sessions without meeting_aware skip context fetching
7. **SSE streaming** — Chat response correctly streamed through gateway (300s timeout)

## What's Needed for Score 80

1. **Active meeting bot** — need a real meeting (Teams/GMeet) with bot staying active
2. **Auto injection** — gateway must fetch context automatically (not manual header)
3. Run: `/host-teams-meeting-auto` → send bot → wait for transcript → chat via gateway

## What's Needed for Score 90

1. Telegram bot sending meeting-aware chat
2. Real meeting running with bot
3. User sends message via Telegram → agent responds with meeting awareness

## Blockers

1. **No Teams/Google credentials** — can't host a meeting programmatically
2. **Bot container naming** — runtime API container names don't encode DB meeting ID correctly, requiring fallback to /meetings endpoint
