# Mission: Vexa CLI — Local Terminal Client

Focus: A local `vexa` command that replaces `claude` CLI
Problem: Users must run `claude` locally, which requires local API keys, local model config, and runs on the local machine. The ephemeral container infrastructure (agent-api, workspace persistence, session management) exists but has no terminal client — only HTTP API consumers (Telegram bot, dashboard).
Target: `vexa` command installed locally, works exactly like `claude` CLI (same output, same interactivity), but all computation happens in an ephemeral container via agent-api.
Stop-when: MVP2 complete OR hard blocker identified with diagnosis

---

## Why This Matters

Claude CLI is a local tool. It runs on your machine, reads your local files, talks to Anthropic's API with your API key. That's fine for solo dev work. But Vexa's value is the infrastructure layer — persistent workspaces, scheduled agents, per-user env vars, session management across devices. None of that works if you're running claude locally.

The gap: Vexa has a full agent runtime (agent-api → container → claude CLI → streaming output) but no way to use it from a terminal. The only clients are the Telegram bot and the web dashboard. A developer sitting at a terminal has to choose between:

1. **`claude` locally** — great UX, no Vexa features (no persistence, no scheduling, no remote workspace)
2. **curl to agent-api** — Vexa features, terrible UX (raw SSE in terminal)
3. **Telegram bot** — Vexa features, but it's Telegram (no terminal, limited formatting)

`vexa` CLI closes this gap: terminal UX of claude, infrastructure of Vexa.

---

## System Design Constraints

### 1. Thin client — all logic stays in agent-api

The `vexa` CLI is a thin client. It sends HTTP to agent-api, renders the SSE stream in the terminal. It does NOT manage containers, sessions, or workspaces. Agent-api already does all of that. If you're adding container logic to the CLI, you're in the wrong layer.

### 2. Same SSE protocol as every other client

Telegram bot, dashboard, and vexa CLI all consume the same `POST /api/chat` → SSE stream. The CLI does NOT get a special endpoint or a different stream format. If the CLI needs something, add it to the shared SSE protocol so all clients benefit.

### 3. The workspace is remote, not local

Claude CLI works on local files. Vexa CLI works on remote workspace files (persisted in S3, mounted in ephemeral containers). The user's "project" lives in the workspace, not in their local directory. This is a fundamental difference from claude — don't try to hide it. Make the workspace concept explicit.

Future: local directory mounting (sync local dir ↔ container) is a separate mission. This mission is about the terminal client.

### 4. Authentication via API key

Same `X-API-Key` header as every other agent-api client. The CLI stores config (endpoint URL, API key, default user_id) in `~/.vexa/config.json`. No new auth mechanism.

### 5. Python, pip-installable

The CLI is Python. It lives in this repo under `services/vexa-cli/`. It's pip-installable (`pip install -e services/vexa-cli`). Dependencies: `httpx` (SSE streaming), `rich` (terminal rendering), `click` or `typer` (CLI args). Minimal dependencies — this is a thin client.

---

## What Exists vs What's Missing

| Capability | Status | Location |
|-----------|--------|----------|
| Agent-api SSE chat endpoint | **Works** | `POST /api/chat` → SSE stream |
| Session management API | **Works** | `/api/sessions` CRUD |
| Workspace file API | **Works** | `/api/workspace/files`, `/api/workspace/file` |
| Container lifecycle | **Works** | agent-api → runtime-api |
| Stream parser (JSON → events) | **Works** | `stream_parser.py` |
| **Local CLI binary** | **Missing** | Nothing exists |
| **SSE → terminal renderer** | **Missing** | Telegram bot has its own renderer, need terminal one |
| **Interactive REPL** | **Missing** | Only one-shot via API |
| **CLI config management** | **Missing** | No `~/.vexa/config.json` |
| **Session resume from CLI** | **Missing** | API supports it, no CLI UX |

---

## SSE Event Types (from agent-api)

The CLI must handle all of these — this is the contract:

```
text_delta    → {"type": "text_delta", "text": "streaming chunk"}
tool_use      → {"type": "tool_use", "tool": "Read", "summary": "Reading: /workspace/file.py"}
done          → {"type": "done", "session_id": "abc123", "cost_usd": 0.015, "duration_ms": 3200}
stream_end    → {"type": "stream_end", "session_id": "abc123"}
error         → {"type": "error", "message": "something went wrong"}
session_reset → {"type": "session_reset", "reason": "Container was recreated..."}
reconnecting  → {"type": "reconnecting"}
```

---

## MVP0: One-Shot Mode — `vexa -p "hello"`

**Goal:** Run a single prompt from the terminal, see streaming output, done.

**What we build:**
- `services/vexa-cli/` — Python package with `vexa` entry point
- `vexa -p "message"` → POST /api/chat → stream text to terminal
- Config: `~/.vexa/config.json` with `{endpoint, api_key, user_id}`
- `vexa config` → interactive setup (endpoint, API key, user_id)
- Text deltas print to stdout as they arrive (streaming, not buffered)
- Tool use events shown as dim one-liners (e.g., `  Reading: /workspace/file.py`)
- Done event shows cost and duration
- Errors print to stderr and exit non-zero

### DoD — MVP0

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 0.1 | `pip install -e services/vexa-cli` succeeds, `vexa` is on PATH | 5 | 5 | `which vexa` returns path. `vexa --help` shows usage. |
| 0.2 | `vexa config` sets endpoint + API key + user_id in `~/.vexa/config.json` | 5 | 10 | File exists with correct values after running config. |
| 0.3 | `vexa -p "what files are in my workspace?"` streams response to terminal | 30 | 0 | Text appears character-by-character (streaming). Agent lists workspace files. Response matches what `curl POST /api/chat` returns. |
| 0.4 | Tool use events render as dimmed one-liners | 10 | 30 | When agent uses Read/Bash/etc, terminal shows `  Reading: /workspace/notes.md` in grey. |
| 0.5 | Done event shows session, cost, duration | 5 | 50 | After response: `Session: abc123 | $0.015 | 3.2s` |
| 0.6 | Errors print to stderr, exit code 1 | 5 | 60 | Bad API key → error message on stderr, exit 1. Unreachable endpoint → same. |
| 0.7 | `--model` flag works | 5 | 70 | `vexa -p "hello" --model sonnet` uses specified model. |
| 0.8 | Output matches claude CLI quality — markdown renders, code blocks highlighted | 15 | 15 | Side-by-side: claude output vs vexa output for same prompt. Markdown headings, code blocks, lists all render correctly. |

**Ceilings:** 0.3 fails (no streaming) → cap 0. 0.1 fails (can't install) → cap 5. 0.8 fails (output ugly) → cap 15. 0.4 fails → cap 30.

---

## MVP1: Interactive Mode — `vexa`

**Goal:** Run `vexa` with no args, get an interactive REPL. Type messages, see responses, continue conversation.

**Depends on:** MVP0

**What we build:**
- `vexa` (no args) → interactive REPL with prompt
- Multi-line input (paste-friendly)
- Session continues across turns (same session_id reused)
- `/exit` or Ctrl+D to quit
- `/reset` to start a new session
- `/session <id>` to switch sessions
- Prompt shows current session info
- History (up arrow for previous inputs)

### DoD — MVP1

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 1.1 | `vexa` opens interactive prompt | 10 | 0 | Terminal shows prompt (`vexa> ` or similar). Cursor waits for input. |
| 1.2 | Multi-turn conversation works | 25 | 10 | Send "remember the number 42". Send "what number?". Agent says 42. Same session. |
| 1.3 | `/reset` starts fresh session | 10 | 30 | After /reset, agent doesn't remember prior context. |
| 1.4 | `/exit` and Ctrl+D quit cleanly | 5 | 50 | No traceback, no hanging, clean exit. |
| 1.5 | Input history works | 5 | 60 | Up arrow recalls previous inputs. |
| 1.6 | Session survives container restart | 15 | 20 | Chat, wait for idle timeout (container dies), chat again. Context restored (workspace files still there, session resumes). |
| 1.7 | Streaming output doesn't block input | 10 | 35 | While response is streaming, Ctrl+C interrupts cleanly (doesn't kill the CLI). |

**Ceilings:** 1.1 fails → cap 0. 1.2 fails → cap 10. 1.6 fails → cap 20. 1.3 fails → cap 30.

---

## MVP2: Session Management + Workspace Access

**Goal:** Full session and workspace management from the CLI. List sessions, switch between them, browse workspace files.

**Depends on:** MVP1

**What we build:**
- `vexa sessions` — list all sessions
- `vexa sessions --new "project X"` — create named session
- `vexa --session <id>` — start REPL in specific session
- `vexa workspace ls` — list workspace files
- `vexa workspace cat <path>` — read a file
- `vexa workspace write <path>` — write stdin to file
- `vexa status` — show current user, endpoint, container status

### DoD — MVP2

| # | Check | Weight | Ceiling | Evidence |
|---|-------|--------|---------|----------|
| 2.1 | `vexa sessions` lists sessions with name, date, id | 10 | 10 | Output shows sessions matching `/api/sessions` response. |
| 2.2 | `vexa --session <id> -p "hello"` resumes specific session | 15 | 15 | Agent has context from that session. |
| 2.3 | `vexa workspace ls` shows workspace file tree | 10 | 30 | Output matches `GET /api/workspace/files`. |
| 2.4 | `vexa workspace cat notes.md` prints file content | 10 | 40 | Content matches what's in the container workspace. |
| 2.5 | `vexa status` shows user, endpoint, container status | 5 | 55 | Shows user_id, endpoint URL, whether container is running, workspace size. |
| 2.6 | `vexa workspace write notes.md < input.txt` writes file | 10 | 50 | File appears in workspace with correct content. |
| 2.7 | Full workflow: create session → chat → switch session → chat → list sessions | 20 | 0 | Two distinct sessions, each with their own context. List shows both. |

**Ceilings:** 2.7 fails (workflow broken) → cap 0. 2.1 fails → cap 10. 2.2 fails → cap 15. 2.3 fails → cap 30.

---

## Future (not this mission)

- **Local directory sync** — `vexa --mount .` syncs local directory to container workspace. Changes sync back on completion. This makes vexa truly transparent — work on local files, computation in container.
- **MCP tool integration** — vexa CLI as MCP client, forwarding tool calls to local machine.
- **Pipe mode** — `cat file.py | vexa -p "review this"` reads stdin as context.
- **Watch mode** — `vexa watch` monitors workspace for changes, auto-syncs.

---

## Implementation Notes

### Package structure

```
services/vexa-cli/
├── pyproject.toml          # [project.scripts] vexa = "vexa_cli.main:app"
├── vexa_cli/
│   ├── __init__.py
│   ├── main.py             # CLI entry point (click/typer)
│   ├── config.py           # ~/.vexa/config.json management
│   ├── client.py           # HTTP client — POST /api/chat SSE, GET /api/sessions, etc.
│   ├── renderer.py         # SSE events → terminal output (rich)
│   └── repl.py             # Interactive REPL loop
```

### Terminal rendering approach

Use `rich` library for terminal output:
- `rich.console.Console` for styled output
- `rich.markdown.Markdown` for rendering markdown responses
- `rich.live.Live` for streaming updates (text deltas accumulate, re-render markdown)
- Dim/grey style for tool use events
- Status line for cost/duration

**Key detail:** Text deltas arrive as small chunks. Don't render each chunk as separate markdown — accumulate the full text block, re-render the markdown on each delta. This is how claude CLI does it (the markdown "settles" as more text arrives).

### SSE client

`httpx` with streaming:
```python
async with httpx.AsyncClient() as client:
    async with client.stream("POST", f"{endpoint}/api/chat",
                             json=payload, headers=headers) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                event = json.loads(line[6:])
                render(event)
```

### Config file: `~/.vexa/config.json`

```json
{
  "endpoint": "http://localhost:8100",
  "api_key": "your-api-key",
  "user_id": "your-user-id",
  "default_model": null
}
```

Environment variables override config file:
- `VEXA_ENDPOINT` → endpoint
- `VEXA_API_KEY` → api_key
- `VEXA_USER_ID` → user_id

### Interrupt handling

Ctrl+C during streaming should:
1. Cancel the HTTP stream (client disconnect)
2. Agent-api detects disconnect, stream ends
3. CLI returns to prompt (REPL) or exits (one-shot)

Ctrl+C should NOT kill the agent process in the container — that's a separate `DELETE /api/chat` call, triggered by double Ctrl+C or `/stop` command.

### Risk register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Markdown rendering differs from claude | UX gap | Start with plain text streaming, add rich markdown incrementally |
| SSE parsing edge cases | Garbled output | Test with multi-line code blocks, unicode, large responses |
| REPL blocks on long responses | Bad UX | Async rendering — input not blocked while streaming |
| Config file permissions | Security | 600 permissions on ~/.vexa/config.json (contains API key) |
