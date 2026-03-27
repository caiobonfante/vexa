# Telegram Chat Feature Agent

> **System design: [README.md](../README.md)** — why, data flow, ownership, quality bar, constraints. Read it. Follow it.
> Shared protocol: [agents.md](../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
You test and extend the Telegram-to-agent-api chat integration. The service code lives in `services/telegram-bot/bot.py`. You dispatch service agents — you don't write code directly unless extending bot.py.

### Gate (local)
Send Telegram message -> agent-api streams SSE response -> bot progressively edits Telegram message with response text. PASS: full round-trip works, response renders correctly. FAIL: message not forwarded, stream broken, or response not displayed.

### Docs
- Feature README: `features/telegram-chat/README.md`
- Service README: `services/telegram-bot/README.md`
- Agent API: `packages/agent-api/README.md`

### Edges
**Crosses:**
- telegram-bot service (message handling, SSE streaming)
- agent-api (chat, sessions, workspace endpoints)
- runtime-api (container orchestration, via agent-api)
- Redis (session state, via agent-api)

**Data flow:**
Telegram user -> telegram-bot -> agent-api `/api/chat` (SSE) -> telegram-bot -> Telegram message edit

### Counterparts
- Service: `services/telegram-bot`
- Packages: `packages/agent-api`, `packages/runtime-api`
- Related features: scheduler (triggers via telegram-bot), chat (in-meeting chat — different surface, same agent-api)

## Resources

| Level | Cap | Tool | Tool Confidence | Command | Data needed |
|-------|-----|------|----------------|---------|-------------|
| 1 | 30 | (built-in) | — | `python -c "import bot"` | TELEGRAM_BOT_TOKEN |
| 2 | 50 | agent-api | 70 | Send message via Telegram, check response | agent-api + runtime-api running |
| 3 | 70 | agent-api + sessions | 60 | Test /new, /sessions, /workspace commands | agent-api with session endpoints |
| 4 | 85 | multi-message | — | Send long prompt, verify chunked response | agent container with verbose output |
| 5 | 95 | full-stack | 50 | Automated E2E: message -> response -> verify content | Full stack + test Telegram account |

## How to test
1. Ensure agent-api and runtime-api are running
2. Set TELEGRAM_BOT_TOKEN and CHAT_API_URL
3. Run `python services/telegram-bot/bot.py`
4. Send a test message via Telegram
5. Verify progressive response editing
6. Test /reset, stop button
7. Check logs for errors

## Critical findings
Report: riskiest thing, untested items, degraded behavior, surprising findings.
Save to `tests/findings.md`.
