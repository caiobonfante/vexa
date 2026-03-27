# Meeting-Aware Agent — Findings

## Score: 60

API layer fully implemented and verified. Session flag stored, gateway injects context, agent-api parses header into prompt. Agent CLI responds (but needs /login for actual LLM responses). Score 80 requires live meeting with bot.

## Evidence

### Test 1: Session with meeting_aware=true — PASS
```
$ curl -s -X POST http://localhost:8056/api/sessions \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"user_id": "5", "name": "Meeting Test", "meeting_aware": true}'

{"session_id":"36364bed-9152-4856-9018-24b786918ca5","name":"Meeting Test","meeting_aware":true}
```

### Test 2: Flag persisted in Redis — PASS
```
$ curl -s "http://localhost:8056/api/sessions?user_id=5" -H "X-API-Key: $API_KEY"
{"sessions":[{"created_at":1774650172.24589,"name":"Meeting Test","updated_at":1774650172.2458904,"meeting_aware":true,"id":"36364bed-..."}]}
```

### Test 3: Gateway fetches active bots for meeting_aware — PASS
```
# meeting_aware session triggers GET /bots/status:
Gateway logs: GET /bots/status HTTP/1.1 200 OK
              POST /api/chat HTTP/1.1 200 OK

# Non-meeting-aware session does NOT trigger /bots/status:
Gateway logs: POST /api/chat HTTP/1.1 200 OK  (no /bots/status call)
```

### Test 4: Chat SSE streaming through gateway — PASS
```
$ curl -sN http://localhost:8056/api/chat -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "5", "message": "Hello", "session_id": "36364bed-..."}'

data: {"type": "session_reset", "reason": "Container was recreated..."}
data: {"type": "text_delta", "text": "Not logged in · Please run /login"}
data: {"type": "done", "session_id": "3fdbcb71-...", "cost_usd": null, "duration_ms": 134}
data: {"type": "stream_end", "session_id": "3fdbcb71-..."}
```

### Test 5: X-Meeting-Context → prompt injection — PASS (KEY EVIDENCE)
```
$ curl -sN http://localhost:8100/api/chat \
  -H "Content-Type: application/json" \
  -H 'X-Meeting-Context: {"active_meetings":[{"meeting_id":"42","platform":"teams","status":"active","participants":["Alice","Bob"],"latest_segments":[{"speaker":"Alice","text":"We need to finalize the Q1 budget"},{"speaker":"Bob","text":"I agree, lets pull up the spreadsheet"}]}]}' \
  -d '{"user_id": "5", "message": "What are my colleagues discussing?"}'

data: {"type": "session_reset", ...}
data: {"type": "text_delta", "text": "Not logged in · Please run /login"}
data: {"type": "done", "session_id": "3fdbcb71-..."}

$ docker exec agent-5-63493e56 cat /tmp/.chat-prompt.txt

[MEETING CONTEXT] The user has active meetings right now:

Meeting 42 (teams), participants: Alice, Bob
Latest transcript:
  Alice: We need to finalize the Q1 budget
  Bob: I agree, lets pull up the spreadsheet

Use this meeting context to inform your responses. The user may ask about what's being discussed.

---

What are my colleagues discussing?
```

### Test 6: Non-meeting-aware session — PASS
```
$ curl -s http://localhost:8056/api/sessions -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "5", "name": "Normal Chat"}'
{"session_id":"cddd865e-...","name":"Normal Chat","meeting_aware":false}
```

### Test 7: Gateway /bots/status — PASS
```
$ curl -s http://localhost:8056/bots/status -H "X-API-Key: $API_KEY"
{"running_bots":[]}
```

## Certainty Table

| Check | Score | Evidence | Last checked |
|-------|-------|----------|-------------|
| Session meeting_aware flag stored | 90 | POST /api/sessions returns meeting_aware:true, persisted in Redis | 2026-03-28 |
| Gateway meeting context middleware | 80 | GET /bots/status called only for meeting_aware sessions | 2026-03-28 |
| GET /bots?user_id&status endpoint | 90 | Returns running_bots:[] via gateway | 2026-03-28 |
| Context header injected | 80 | X-Meeting-Context → prompt file in container shows formatted context | 2026-03-28 |
| Agent-api parses X-Meeting-Context | 90 | /tmp/.chat-prompt.txt contains full meeting context + user message | 2026-03-28 |
| Agent uses meeting context | 30 | Prompt injected but Claude Code needs /login for LLM responses | 2026-03-28 |
| Flag off → no injection | 90 | Non-meeting-aware session: no /bots/status in gateway logs | 2026-03-28 |
| Context refresh on each turn | 80 | Each POST /api/chat triggers fresh /bots/status fetch | 2026-03-28 |

## What's Proven (Score 60)

1. **Session flag** — meeting_aware stored in Redis, visible in session list
2. **Gateway routing** — All /api/chat and /api/sessions routes proxy to agent-api
3. **Meeting context middleware** — Gateway checks meeting_aware, fetches bots, builds context
4. **Header injection** — X-Meeting-Context header correctly forwarded to agent-api
5. **Prompt injection** — Meeting context formatted and prepended to user message in container
6. **No-flag behavior** — Sessions without meeting_aware skip all context fetching
7. **SSE streaming** — Chat response correctly streamed through gateway

## What's Needed for Score 80+

1. **Active meeting bot** — Host meeting, send bot, get transcript segments flowing
2. **Full gateway injection** — Real bots/status + real transcript → injected header
3. **Agent responds with awareness** — Claude Code needs /login or authenticated image
4. Agent references meeting content in response without being told which meeting

## Blockers

1. **Claude Code login** — Agent CLI inside container returns "Not logged in". Pre-existing issue (needs CLAUDE_CREDENTIALS_PATH or /login).
2. **No active meeting** — Need to host a Teams meeting with bot to test real context injection chain.
