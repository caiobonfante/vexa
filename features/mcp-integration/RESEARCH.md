# MCP Integration Research (2026-03-23)

Research from ecosystem analysis, competitive landscape, and live testing against the running server.

## Current State

16 tools, 4 prompts. Stateless FastAPI proxy using `fastapi-mcp`. Only uses **Tools + Prompts** from the MCP protocol.

### Tool Usefulness (live tested)

| Tool | Agent Rating | Notes |
|------|-------------|-------|
| `parse_meeting_link` | 5/5 | Excellent edge-case handling (Teams variants, Zoom events) |
| `request_meeting_bot` | 5/5 | Smart URL parsing built in, handles 409 gracefully |
| `get_meeting_bundle` | 5/5 | Best single-call tool — combines status + notes + recordings + share link |
| `get_meeting_transcript` | 4/5 | Full transcript with speakers, timestamps. 51 segments for 10-min meeting |
| `create_transcript_share_link` | 4/5 | Generates public share URLs |
| `stop_bot` | 4/5 | Clean bot removal |
| `update_meeting_data` | 4/5 | Set name, participants, languages, notes |
| `get_bot_status` | 4/5 | Works but no historical data |
| `get_recording` | 4/5 | Clean response |
| `list_recordings` | 3/5 | Has pagination (limit/offset) |
| `update_bot_config` | 3/5 | Only supports language change |
| `delete_meeting` | 3/5 | Only works on completed/failed |
| `get_recording_config` | 3/5 | Simple config read |
| `update_recording_config` | 3/5 | Toggle recording on/off |
| `list_meetings` | **2/5** | Returns ALL 211 meetings (2.7MB), zero filtering/pagination |
| `get_recording_media_download` | **2/5** | **BUG: returns internal `minio:9000` URL** |

### Prompts

| Prompt | Rating | Notes |
|--------|--------|-------|
| `vexa.meeting_prep` | 4/5 | Parse link → request bot → store notes |
| `vexa.post_meeting` | 4/5 | Fetch bundle → summary/decisions/action items |
| `vexa.teams_link_help` | 4/5 | Targeted troubleshooting |
| `vexa.during_meeting` | 3/5 | Could be richer with live state awareness |

---

## MCP Protocol Gaps

Vexa uses 2 of 8 MCP protocol features:

| Feature | Used? | Opportunity for Vexa |
|---------|-------|---------------------|
| Tools | Yes | Add search, interactive bot, participants |
| Prompts | Yes | Good coverage |
| **Resources** | No | Expose meetings/transcripts as browsable data in Claude Desktop sidebar |
| **Resource Templates** | No | `vexa://meeting/{platform}/{id}/transcript` — parameterized |
| **Subscriptions** | No | **Highest-impact**: live transcript push via existing WebSocket |
| **Sampling** | No | Server uses client's LLM for real-time analysis (issue #139) |
| **Elicitation** | No | Ask user for passcode, confirm speaker identity |
| **Logging** | No | Structured log events to client |

### Resources — what they'd look like

```
vexa://meetings                              → browsable meeting list
vexa://meeting/{platform}/{id}/transcript    → full transcript (resource template)
vexa://meeting/{platform}/{id}/status        → bot status + metadata
vexa://meeting/{platform}/{id}/participants  → who's in the meeting
vexa://recordings/{id}                       → recording metadata
```

Resources are **application-controlled** (user decides when to load) vs tools which are **model-controlled**. Users could browse meetings in Claude Desktop sidebar and drag transcripts into context.

### Subscriptions — the biggest differentiator

No competitor does live MCP subscriptions. Vexa already has WebSocket real-time streaming (dashboard uses it). Bridging this to MCP subscriptions:

```
MCP Client subscribes to vexa://meeting/{platform}/{id}/transcript
  → MCP server opens internal WebSocket to Vexa's real-time stream
  → On each new segment: notifications/resources/updated
  → Client calls resources/read for updated transcript
```

This turns Vexa from polling-based to push-based real-time. An AI agent could react to what's being said as it happens.

### Sampling — real-time meeting intelligence

Issue #139 describes a real-time LLM decision listener. MCP Sampling is the protocol-native way to do this:
- Server receives live transcript segments
- Uses sampling to ask client LLM "Is this an action item?"
- No server-side LLM inference needed

---

## Missing Tools

### Gateway endpoints NOT exposed as MCP tools

These endpoints exist at `localhost:8066` but have no MCP tool:

| Endpoint | MCP Tool Name | Priority |
|----------|--------------|----------|
| `POST /bots/{platform}/{id}/chat` | `send_chat_message` | **HIGH** |
| `GET /bots/{platform}/{id}/chat` | `read_chat_messages` | **HIGH** |
| `POST /bots/{platform}/{id}/speak` | `bot_speak` | **HIGH** |
| `POST /bots/{platform}/{id}/screen` | `bot_screen_share` | HIGH |
| `PUT /user/webhook` | `configure_webhook` | MEDIUM |
| `POST /meetings/{id}/transcribe` | `transcribe_recording` | MEDIUM |
| `DELETE /bots/{platform}/{id}/speak` | `stop_speaking` | MEDIUM |
| `PUT /bots/{platform}/{id}/avatar` | `set_avatar` | LOW |

### New tools that should exist

| Tool | Priority | Rationale |
|------|----------|-----------|
| `search_meetings` (keyword, date, participant) | **HIGH** | `list_meetings` returns 2.7MB with zero filtering. Unusable at scale. |
| `search_transcripts` (keyword across all meetings) | **HIGH** | "Find meetings where X was discussed" — killer feature for org memory |
| `get_meeting_participants` (with talk-time stats) | HIGH | Essential context for live meeting agents |
| `get_meeting_summary` (action items, decisions) | MEDIUM | Every competitor does this |
| `export_transcript` (txt, srt, vtt, docx) | MEDIUM | Different formats for downstream use |
| `schedule_bot` (calendar integration) | MEDIUM | Meeting-BaaS has this |

---

## Competitive Landscape

### Meeting-BaaS (closest competitor)

Two MCP servers:
- **meeting-mcp**: bot management, transcript search, calendar integration, AI avatars, meeting highlights
- **speaking-bots-mcp**: separate server for AI-powered speaking participants

What they have that Vexa lacks: transcript search, calendar OAuth, speaking bots as MCP tools, AI avatars, meeting highlights.

### Fireflies, Otter, MeetGeek

All offer MCP servers focused on **search and intelligence** — semantic search, topic extraction, cross-meeting insights. Position meetings as "organizational memory."

### What Vexa does better

- Better meeting URL parsing (Teams edge cases)
- `meeting_bundle` aggregation tool
- Self-hosted deployment option
- Multi-platform in single API

---

## Bugs Found (live testing)

1. **`get_recording_media_download` returns `http://minio:9000/...`** — internal Docker hostname, not externally accessible
2. **`list_meetings` returns 2.7MB** — all 211 meetings with no pagination or filtering

---

## Recommendations

### P0 — Fix now
- Fix `get_recording_media_download` internal URL bug
- Add `limit`, `offset`, `status`, `platform`, `since`, `before` params to `list_meetings`

### P1 — Quick wins (1-2 days each)
1. Expose chat send/read as MCP tools (`send_chat_message`, `read_chat_messages`)
2. Expose speak as MCP tool (`bot_speak`)
3. Add `search_meetings` tool with keyword + date range + participant
4. Expose webhook configuration tool
5. Add `get_meeting_participants` with talk-time stats

### P2 — Medium effort (1 week)
6. Implement MCP Resources for meetings and transcripts
7. Add `search_transcripts` with keyword across all meetings
8. Add `export_transcript` with format options
9. Add `get_meeting_summary` (server-side or via sampling)

### P3 — Differentiators (multi-week)
10. MCP Subscriptions for live transcript streaming (bridge WebSocket)
11. MCP Sampling for real-time meeting intelligence (#139)
12. Elicitation for interactive flows (passcode, speaker confirmation)
13. Calendar integration (auto-join scheduled meetings)
14. Cross-meeting search with embeddings

### P4 — Platform (months)
15. Speaking bot tools with voice selection
16. Screen sharing tools
17. Cross-meeting analytics and trends
18. OAuth 2.1 auth (MCP spec 2025-11-25 standardizes this)
