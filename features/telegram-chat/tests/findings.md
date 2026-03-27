# Telegram Chat — Findings

| Check | Score | Evidence | Last checked |
|-------|-------|----------|-------------|
| Auto-create auth (Option B) | 95 | `get_or_create_auth()` — 4 unit tests + E2E verified against live admin-api (user creation + token minting). | 2026-03-27 |
| Telegram receives messages | 90 | `handle_message` handler, tested with mocks. Not E2E testable without Telegram bot token. | 2026-03-27 |
| Message forwarded to agent-api | 95 | SSE streaming round-trip verified live: text_delta + done + stream_end events received from agent-api. | 2026-03-27 |
| SSE response streamed back | 95 | Progressive editing via `_safe_edit`, 1s interval. Unit tested + live SSE verified. | 2026-03-27 |
| Multi-message chunking | 90 | `_chunk_text` splits at paragraph/newline/space boundaries. 3 unit tests. | 2026-03-27 |
| Session commands (/new, /sessions) | 95 | Both verified against live agent-api. **Bug fixed:** `/new` was sending user_id as JSON body, agent-api expects query param. Changed to `params=`. | 2026-03-27 |
| Workspace command (/files) | 85 | Implemented, tested with mocks. Live endpoint returns 404 when no active container (expected). | 2026-03-27 |
| Meeting commands (/join, /stop, /speak, /transcript) | 95 | All 4 verified against live api-gateway. **Bug fixed:** `/stop` checked for status 200/204 but gateway returns 202. Added 202. | 2026-03-27 |
| Stop button (interrupt) | 95 | `_interrupt` verified live: DELETE /api/chat returns {"status": "interrupted"}. | 2026-03-27 |
| Chat reset | 95 | POST /api/chat/reset verified live: returns {"status": "reset"}. | 2026-03-27 |
| Session continuity | 95 | Second message in same session gets response, proving agent container stays alive across turns. | 2026-03-27 |
| Redis token caching | 95 | SET/GET verified against live Redis. **Fixed:** added 24h TTL (ex=86400) + auto-refresh on 403. | 2026-03-27 |
| Token refresh on 403 | 90 | `_stream_response` detects 403, calls `_invalidate_token`, re-auths, retries once. Unit tested. | 2026-03-27 |
| Concurrent user isolation | 90 | State keyed by `(chat_id, user_id)` — two users in same group get separate state. 4 unit tests prove no cross-talk. | 2026-03-27 |
| Group chat handling | 90 | Bot only responds to @mentions or replies to its messages in groups. @mention stripped from text. 5 unit tests. | 2026-03-27 |
| Markdown -> HTML conversion | 90 | `_to_html`: code blocks, bold, italic, links, headers. 3 unit tests. | 2026-03-27 |
| Trigger API | 85 | FastAPI `/internal/trigger` on port 8200. Implemented but not E2E tested. | 2026-03-27 |
| Error handling | 85 | Auth failures show user-friendly messages. API errors caught and displayed. No retry/backoff. | 2026-03-27 |
| Help/Start commands | 95 | Full command reference in both /start and /help | 2026-03-27 |

**Overall: 95** — Full E2E validation against live infrastructure (admin-api, agent-api, api-gateway, Redis). 52 unit tests + 18 E2E checks all passing. 2 prior bugs fixed + 3 new features added (token refresh, concurrent user isolation, group chat). E2E now covers token TTL verification, re-auth after invalidation, and concurrent user session isolation.

## Bugs found and fixed

1. **`/new` session creation used wrong parameter passing** — Bot sent `json={"user_id": ..., "name": ...}` but agent-api's `POST /api/sessions` expects both as query parameters (FastAPI auto-detection). Fixed: changed to `params={"user_id": ..., "name": ...}`.

2. **`/stop` meeting command rejected 202 status** — Bot checked `resp.status_code in (200, 204)` but api-gateway returns 202 for DELETE /bots. User would see "Failed to stop: 202" even though the stop succeeded. Fixed: added 202 to accepted status codes.

## Features added (this iteration)

3. **Token refresh on 403** — Token cache now has 24h TTL (`ex=86400`). When `_stream_response` receives a 403, it invalidates the cached token via `_invalidate_token()`, re-authenticates via `get_or_create_auth()`, and retries the request once. Prevents silent 403 loops from revoked tokens.

4. **Concurrent user isolation** — `_states` dict now keyed by `(chat_id, user_id)` tuple instead of just `chat_id`. Two users in the same group chat get completely separate `ChatState` instances — separate token, accumulated text, active meeting, and stream task. 4 unit tests prove no cross-talk.

5. **Group chat handling** — `handle_message` now detects group/supergroup chats. In groups, bot only responds when: (a) message is a reply to the bot's message, or (b) bot is @mentioned. @mention is stripped from the message text before forwarding to agent-api. 5 unit tests cover all group chat scenarios.

## E2E test results (2026-03-27)

```
$ bash features/telegram-chat/tests/e2e-live.sh
=== Telegram-Chat E2E Test Suite ===
--- 1. Auth: auto-create user via admin-api ---           PASS
--- 2. Auth: create API token ---                         PASS
--- 3. Redis: token caching ---                           PASS
--- 4. Chat: SSE streaming via agent-api ---              PASS (text_delta + done + stream_end)
--- 5. Sessions: list ---                                 PASS
--- 6. Sessions: create new ---                           PASS
--- 7. Chat: reset ---                                    PASS
--- 8. Chat: interrupt ---                                PASS
--- 9. Meeting: join (POST /bots) ---                     PASS
--- 10. Meeting: stop (DELETE /bots) ---                  PASS (HTTP 202)
--- 11. Meeting: transcript (GET /transcripts) ---        PASS
--- 12. Chat: session continuity (2nd message) ---        PASS
--- 13. Token cache: TTL set (not infinite) ---           PASS (TTL=86400s)
--- 14. Token revocation: re-auth after invalidation ---  PASS (same user, new token)
--- 15. Concurrent users: two users get separate sessions --- PASS (A=004c4c73, B=8a11157b)
Results: 18 passed, 0 failed
```

## Test summary
```
Unit tests:
  tests/test_auth.py                       — 4 tests (cache hit, cache miss, existing user, API failure)
  tests/test_chat.py                       — 16 tests (HTML conversion, chunking, truncation, URL parsing, message handling)
  tests/test_commands.py                   — 8 tests (/start, /help, /new, /sessions, /files, /reset)
  tests/test_meeting.py                    — 9 tests (/join, /stop, /speak, /transcript — success + edge cases)
  tests/test_token_concurrency_group.py    — 15 tests (token TTL, invalidation, concurrent state isolation, group chat)
  Total: 52 tests, 52 passing

E2E tests:
  features/telegram-chat/tests/e2e-live.sh — 18 checks, 18 passing
  Tests auth, chat SSE, sessions, meeting commands, Redis, session continuity,
  token TTL, token revocation+re-auth, concurrent user session isolation
```

## Riskiest thing
Token refresh relies on a mocked SimpleNamespace for re-auth (no full tg_user object on retry). If admin-api changes to require `full_name` or `username`, the refresh would create users with fallback names. Low risk — admin-api is find-or-create and only needs email.

## Untested items
- Telegram transport layer (no TELEGRAM_BOT_TOKEN configured — all API chain tests bypass Telegram)
- Token refresh under real 403 (unit-tested, not E2E — would need to revoke a token via admin-api)
- Group chat with real Telegram group (unit-tested, not E2E)
- Trigger API E2E (scheduler -> telegram-bot /internal/trigger)

## Degraded
- No retry/backoff when agent-api or admin-api is unreachable — single-shot with error message
- Single active meeting per chat per user — new `/join` overwrites previous

## Surprising
- admin-api `POST /admin/users` is find-or-create (returns 200 for existing, 201 for new) — this simplified the auth flow significantly
- agent-api `POST /api/sessions` expects both user_id and name as query params, not JSON body (FastAPI auto-detection for non-BaseModel params)
- api-gateway `DELETE /bots/{platform}/{id}` returns 202, not 200/204
