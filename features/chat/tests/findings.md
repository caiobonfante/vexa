# Chat Test Findings

## Gate verdict: UNTESTED

## Implementation status (audit 2026-03-23)

Implementation is **code-complete across the full stack** but never validated end-to-end:
- `services/vexa-bot/core/src/services/chat.ts` (~700 lines) — MeetingChatService with DOM observation (MutationObserver), message injection, Redis pub/sub relay
- `services/bot-manager/app/main.py` (lines 2968-3030) — chat endpoints, Redis list persistence
- `services/api-gateway/main.py` — POST/GET proxy routes (route existence verified in tests)
- `services/dashboard/src/components/meetings/chat-panel.tsx` — renders messages with auto-scroll
- `libs/shared-models` — ChatSendRequest, ChatMessage, ChatMessagesResponse schemas

Notable: chat-to-transcript injection code exists but is **disabled** (`if (false)` at line 212 of chat.ts). Dashboard uses a dedicated chat panel instead.

Platform selectors may be stale — Google Meet (~150 lines of DOM selectors), Teams (minimal coverage). Zoom chat is **not implemented**.

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Send message via API | 0 | Code exists, route test passes, no E2E | 2026-03-23 (audit) | POST /bots/{id}/chat in live meeting, verify 200 + DOM |
| Message appears in meeting | 0 | DOM injection code exists for GMeet/Teams | 2026-03-23 (audit) | Verify selectors still match current platform DOM |
| Read messages from participants | 0 | MutationObserver + Redis relay code exists | 2026-03-23 (audit) | GET /bots/{id}/chat returns messages from other participants |
| Bidirectional flow | 0 | Full data flow implemented | 2026-03-23 (audit) | Send + receive in same session, verify both directions |
| Message relay via Redis | 0 | pub/sub channel `va:meeting:{id}:chat` + list storage | 2026-03-23 (audit) | Check Redis for chat message events during test |

## Risks
- Platform DOM selectors (especially Google Meet) may have drifted since implementation
- Silent failure on send — client gets 202 even if DOM injection fails
- No retry logic for failed sends
- Zoom chat not implemented
