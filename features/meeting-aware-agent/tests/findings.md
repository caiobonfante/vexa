# Meeting-Aware Agent — Findings

## Score: 80

Full pipeline working end-to-end: live Teams meeting with bot → gateway auto-injects context → agent responds with meeting awareness citing specific participants and metrics from transcript.

## Evidence

### Test 1: Session with meeting_aware=true — PASS
```
$ curl -s -X POST http://localhost:8056/api/sessions \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"user_id": "5", "name": "Live Meeting Test", "meeting_aware": true}'

{"session_id":"a3d07436-e481-4e1d-93aa-5af69cfd675c","name":"Live Meeting Test","meeting_aware":true}
```

### Test 2: Flag persisted in Redis — PASS
```
{"created_at": 1774653150.83, "name": "Live Meeting Test", "updated_at": 1774653150.83, "meeting_aware": true}
```

### Test 3: Gateway auto-injection chain — PASS (KEY EVIDENCE)
```
Gateway logs:
  Meeting context check: user_id=5, session_id=a3d07436-...
  Session meta from Redis: {..., "meeting_aware": true}
  Meeting-aware session detected for user 5
  Fetching meeting context for internal user 5
  Meeting context injected (1230 bytes)
```
Gateway automatically:
1. Detected meeting_aware=true from Redis
2. Called GET /bots/status → found 2 active meetings (browser_session + Teams)
3. Called GET /transcripts/teams/9371161811580 → got 5 transcript segments
4. Built X-Meeting-Context header (1230 bytes)
5. Forwarded to agent-api

### Test 4: Live Teams meeting with bot — PASS
```
Meeting ID: 93 (native: 9371161811580)
Platform: teams
Status: active
Bot container: meeting-5-de6d7f78
Participants: Sarah Chen, Dmitry Grankin
Auto-admit: running (admitted bot at 23:11:06)
Transcript: 5 segments with speaker attribution
```

### Test 5: Agent responds with meeting awareness — PASS (SCORE 80 EVIDENCE)
```
$ curl -sN http://localhost:8056/api/chat \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"user_id": "5", "message": "What are the key metrics being discussed?", "session_id": "$SESSION_ID"}'

Agent response:
  Based on your Teams meeting with Sarah Chen and Dmitry Grankin:
  - Revenue up 15% YoY
  - APAC region grew 22%
  - Customer churn improved from 3.8% to 2.3%
  - 2 out of 3 planned features shipped
```

### Test 6: Prompt file with auto-injected context — PASS
```
$ docker exec agent-5-... cat /tmp/.chat-prompt.txt

[MEETING CONTEXT] The user has active meetings right now:

Meeting bs-7503111e (browser_session), participants: unknown
Meeting 9371161811580 (teams), participants: Sarah Chen, Dmitry Grankin
Latest transcript:
  Sarah Chen: The quarterly revenue is up 15 percent year over year
  Dmitry Grankin: What about the APAC region
  Sarah Chen: APAC grew 22 percent driven by the Japan expansion
  ...

---

What are the key metrics being discussed?
```

### Test 7: Non-meeting-aware session — PASS
```
{"session_id":"cddd865e-...","name":"Normal Chat","meeting_aware":false}
No context fetching in gateway logs for this session.
```

### Test 8: Normal chat without context — PASS
```
"What is 2+2?" → "4" (no meeting context leaks)
```

## Certainty Table

| Check | Score | Evidence | Last checked |
|-------|-------|----------|-------------|
| Session meeting_aware flag stored | 95 | Redis confirmed, API returns flag | 2026-03-28 |
| Gateway fetches active meetings | 90 | GET /bots/status auto-called, found 2 active bots | 2026-03-28 |
| Gateway fetches latest transcript | 90 | GET /transcripts/teams/9371161811580 returned 5 segments | 2026-03-28 |
| Context injected as header | 90 | 1230 bytes X-Meeting-Context auto-injected by gateway | 2026-03-28 |
| Agent-api parses X-Meeting-Context | 95 | Prompt file shows [MEETING CONTEXT] block | 2026-03-28 |
| Agent uses meeting context | 85 | Cited revenue 15%, APAC 22%, churn 3.8→2.3%, participants | 2026-03-28 |
| Flag off → no injection | 95 | Normal sessions skip bots/status entirely | 2026-03-28 |
| Context refresh on each turn | 85 | Each chat triggers fresh /bots/status + transcript fetch | 2026-03-28 |

## What's Proven (Score 80)

1. **Session flag** — meeting_aware stored and retrieved from Redis
2. **Gateway auto-injection** — Gateway detects flag, fetches bots, fetches transcript, injects header
3. **Live meeting** — Real Teams meeting hosted, bot joined, transcript segments flowing
4. **Agent awareness** — Claude cites specific metrics, participants, topics from live transcript
5. **No-flag behavior** — Normal sessions have zero overhead
6. **SSE streaming** — Full chat streaming through gateway works
7. **Context freshness** — Each chat turn fetches fresh context

## Score 90 Readiness (Telegram E2E)

Everything is deployed and ready for user testing:

1. **Telegram bot running** — `@Vexa_new_bot` connected and polling, container `telegram-bot-live`
2. **Meeting-aware code deployed** — /join creates meeting_aware=true session, chat routes through gateway
3. **Live Teams meeting active** — Meeting 93 (9371161811580) with bot, transcript segments flowing
4. **TELEGRAM_BOT_TOKEN** — configured in .env

### How to test (user action required)

1. Open Telegram → message `@Vexa_new_bot`
2. Send `/join https://teams.live.com/meet/9371161811580?p=MNFMzNk8DA4SY5Tag7`
3. Wait for "Bot joining meeting" confirmation
4. Send: "What's being discussed in my meeting?"
5. Agent should respond with meeting context (participants, transcript content)

### Programmatic simulation (already verified)

The full flow was simulated programmatically:
- Created meeting_aware=true session via gateway
- Chat through gateway with session_id → gateway auto-injected 1230 bytes meeting context
- Agent correctly cited: revenue 15% YoY, APAC 22%, churn 3.8→2.3%, participants Sarah Chen + Dmitry Grankin

## Known Issues

- Browser sessions show "participants: unknown" (no transcript = no speaker names)
- Bot TTS self-filters: bot's own speech excluded from transcript (by design)
- Gateway needs AGENT_API_URL env var (not in default compose)
- Container recreation resets session_id (agent-api creates new session on fresh container)
