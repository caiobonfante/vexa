# Advanced MCP Features Research

> Date: 2026-03-29
> Researcher: Claude (researcher agent)
> Purpose: Comprehensive survey of MCP protocol features, SDK capabilities, meeting-focused implementations, and advanced patterns to inform Vexa MCP server design.

---

## Table of Contents

1. [MCP Protocol Spec Features (2025-11-25)](#1-mcp-protocol-spec-features-2025-11-25)
2. [Meeting-Focused MCP Implementations](#2-meeting-focused-mcp-implementations)
3. [Advanced MCP Server Patterns](#3-advanced-mcp-server-patterns)
4. [What Would Make a Meeting MCP Server Stand Out](#4-what-would-make-a-meeting-mcp-server-stand-out)
5. [MCP Python SDK Features](#5-mcp-python-sdk-features)
6. [FastMCP Framework Features](#6-fastmcp-framework-features)
7. [2026 MCP Roadmap](#7-2026-mcp-roadmap)
8. [Recommendations for Vexa](#8-recommendations-for-vexa)

---

## 1. MCP Protocol Spec Features (2025-11-25)

The MCP specification (latest: 2025-11-25) defines a comprehensive set of features organized into server features, client features, and base protocol utilities.

### 1.1 Server Features

#### Tools
Functions that the AI model can execute. The bread and butter of MCP.

- **Tool definitions**: Name, description, input schema (JSON Schema), output schema
- **Tool annotations** (new in 2025-06-18): Behavioral hints for clients
  - `readOnlyHint` (default: false) - tool doesn't modify its environment
  - `destructiveHint` (default: true) - tool may perform destructive updates
  - `idempotentHint` (default: false) - calling repeatedly with same args has no additional effect
  - `openWorldHint` (default: true) - tool may interact with external entities
  - `title` - human-readable display name
- **Structured output** (new in 2025-06-18): Tools can declare an `outputSchema` using JSON Schema, enabling typed, validated responses. Tools return both `content` (for model consumption) and `structuredContent` (for programmatic consumption)
- **Icons** (new in 2025-11-25): Servers can expose icons as metadata for tools
- **Tool naming guidance** (new in 2025-11-25, SEP-986): Standardized naming conventions
- **Dynamic tool updates**: Servers can add/remove tools at runtime and notify clients via `notifications/tools/list_changed`

Source: [MCP Spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25), [Changelog](https://modelcontextprotocol.io/specification/2025-11-25/changelog)

#### Resources
Data sources that provide context to language models. Unlike tools (model-controlled), resources are application-controlled.

- **Static resources**: Fixed URIs (e.g., `config://settings`)
- **Resource templates**: Parameterized URIs using RFC 6570 URI templates (e.g., `file://documents/{name}`)
- **Resource annotations**:
  - `audience`: Array of `"user"` and/or `"assistant"` - who the resource is for
  - `priority`: 0.0-1.0 indicating importance (1 = required, 0 = optional)
  - `lastModified`: ISO 8601 timestamp
- **MIME types**: Resources specify content type (text, binary via base64)
- **Resource size**: Optional size in bytes for pre-flight checking
- **Pagination**: `resources/list` and `resources/templates/list` support cursor-based pagination
- **Custom URI schemes**: Protocol allows custom schemes (e.g., `vexa://meeting/{id}/transcript`)
- **Resource links** (new in 2025-06-18): `resource_link` content type lets tools point to URIs instead of inlining content

Source: [Resources Spec](https://modelcontextprotocol.io/specification/2025-06-18/server/resources)

#### Resource Subscriptions
Real-time updates for resources through a decoupled notification pattern.

- **List changed notifications**: Server emits `notifications/resources/list_changed` when available resources change
- **Per-resource subscriptions**: Clients subscribe via `resources/subscribe` with a specific URI
- **Update notifications**: Server emits `notifications/resources/updated` when a subscribed resource changes
- **Decoupled pattern**: Notification of change is separate from data retrieval. Client receives lightweight notification, then calls `resources/read` for updated content
- **Capability declaration**: Server declares `resources.subscribe: true` and/or `resources.listChanged: true`

**Critical for Vexa**: This is the mechanism for live transcript push. Server notifies "transcript changed" -> client fetches updated transcript. The pattern fits perfectly with Vexa's existing WebSocket infrastructure.

Source: [Resources Spec](https://modelcontextprotocol.io/specification/2025-06-18/server/resources), [mcp-observer-server](https://github.com/hesreallyhim/mcp-observer-server)

#### Prompts
Predefined templates that guide workflows. Accept dynamic arguments, pull in resources for context.

- **Prompt definitions**: Name, description, arguments (with required flag and description)
- **Multi-step**: Can orchestrate multi-step interactions
- **Resource embedding**: Prompts can reference resources for context inclusion

#### Logging
Structured server-to-client log events.

- **Log levels**: Standard levels (debug, info, warning, error)
- **Context methods**: `ctx.info()`, `ctx.debug()`, `ctx.warning()`, `ctx.error()`
- **Structured data**: Log entries can include structured metadata

### 1.2 Client Features

#### Sampling (Server-initiated LLM calls)
Allows the server to request an LLM completion from the client. The server doesn't need its own LLM credentials.

- **Basic sampling**: Server sends prompt, gets text completion back
- **Parameters**: `messages`, `system_prompt`, `temperature`, `max_tokens`, `model_preferences`
- **Multi-turn**: Pass conversation history as `SamplingMessage` objects
- **Tool-assisted sampling** (new in 2025-11-25, SEP-1577): Server can include `tools` and `toolChoice` parameters so the client LLM can call tools during sampling
- **Structured output**: Can request validated responses using Pydantic models (via FastMCP `result_type` parameter)
- **Model preferences**: Hint at preferred models (hints, not requirements)
- **Privacy controls**: Users approve sampling, control what the server sees

**Critical for Vexa**: Enables real-time meeting intelligence without server-side LLM. Server receives transcript segments, uses sampling to ask "Is this an action item?" using the client's own LLM.

Source: [MCP Spec - Sampling](https://modelcontextprotocol.io/specification/2025-11-25/client/sampling), [FastMCP Sampling](https://gofastmcp.com/servers/sampling)

#### Elicitation (Server-initiated user input)
Allows servers to request structured information from users during tool execution.

- **Form mode**: Collect structured data with JSON Schema validation
  - Define fields with types, constraints, defaults
  - Supports string, number, boolean, enum types
  - Enum supports single-select, multi-select, titled/untitled variants (2025-11-25)
  - Default values for all primitive types (2025-11-25)
  - Returns action: `"accepted"`, `"declined"`, `"cancelled"`
- **URL mode** (new in 2025-11-25, SEP-1036): Direct users to external URLs for sensitive operations
  - OAuth flows, payment processing, credential collection
  - Uses `ctx.elicit_url()` with URL, message, and elicitationId
  - Out-of-band interaction that doesn't pass through MCP client

**Critical for Vexa**: Meeting passcode entry, speaker identity confirmation, calendar OAuth authorization, meeting preference selection.

Source: [Elicitation Spec](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation), [Cisco Blog](https://blogs.cisco.com/developer/whats-new-in-mcp-elicitation-structured-content-and-oauth-enhancements)

#### Roots
Server-initiated inquiries into URI or filesystem boundaries.

- Servers can query what roots (directories, URIs) they should operate within
- Helps scope server operations to authorized areas

### 1.3 Base Protocol Utilities

#### Tasks (Experimental, new in 2025-11-25, SEP-1686)
Async, durable operations with a call-now/fetch-later pattern.

- **Lifecycle states**: `working` -> `input_required` | `completed` | `failed` | `cancelled`
- **Creation**: Add `task` parameter with `ttl` to any request
- **Operations**: `tasks/get` (poll status), `tasks/result` (block for result), `tasks/cancel`, `tasks/list`
- **Progress**: Reuses standard MCP progress notifications via `progressToken`
- **Cross-message correlation**: `_meta.io.modelcontextprotocol/related-task` for multi-RPC workflows
- **Concurrency**: Agents can fire multiple tasks and poll independently
- **Reconnection**: `tasks/list` for rediscovering in-flight work after restart
- **Per-tool support**: Tools declare `execution.taskSupport` as `forbidden`, `optional`, or `required`

**Critical for Vexa**: Long-running operations like "transcribe this 2-hour recording", "join meeting and stay until it ends", "search across all meetings for mentions of X".

Source: [MCP Tasks Blog](https://workos.com/blog/mcp-async-tasks-ai-agent-workflows), [SEP-1686](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1686)

#### Progress Tracking
Report progress for long-running operations.

- **Progress tokens**: Assigned to requests for progress tracking
- **Progress notifications**: `report_progress(progress, total, message)`
- **Percentage-based**: Progress as fraction of total

#### Cancellation
Cancel in-progress operations.

- Clients send cancellation request with request ID
- Server should stop work and clean up resources

#### OAuth 2.1 Authorization (new in 2025-11-25)
Comprehensive auth framework.

- **OAuth 2.1**: Full framework with OIDC Discovery support
- **Incremental scope consent**: Permissions granted only when workflows require them
- **Client ID Metadata Documents** (SEP-991): Recommended client registration mechanism
- **Resource Indicators** (RFC 8707): Prevent token misuse across services
- **Dynamic client registration**: Now optional rather than required

#### Streamable HTTP Transport
Production transport for remote MCP servers.

- **HTTP-based**: Works with load balancers, proxies, CDNs
- **Event resumability**: Reconnect and resume event streams
- **Session management**: `Mcp-Session-Id` header
- **CORS support**: Cross-origin configuration
- **Polling SSE**: Servers can disconnect at will; clients reconnect via GET (SEP-1699)
- **Origin validation**: HTTP 403 for invalid Origin headers

#### Other Utilities
- **Pings**: Health checking
- **Capability negotiation**: Client/server negotiate supported features during initialization
- **Error reporting**: Standard JSON-RPC error codes
- **Completions API**: Auto-complete arguments for resource templates and prompts

---

## 2. Meeting-Focused MCP Implementations

### 2.1 Fireflies.ai MCP Server (Beta, 2025)

**Status**: Beta, production deployment
**Auth**: API key-based

**Capabilities**:
- Transcript access with speaker identification and timestamps
- Meeting metadata (dates, participants, duration)
- Auto-generated meeting summaries
- Cross-meeting search and analysis
- Action item extraction across conversations

**Use cases promoted**:
- Sales intelligence: Summarize objections, list action items by company
- Product research: Extract feature requests from user interviews
- Team operations: Track decisions, identify discussion topics

**Integrations**: ChatGPT (OAuth), Claude (custom connector), API key for advanced

**What Vexa can learn**: Fireflies positions meetings as "organizational memory" with cross-meeting search as a primary use case. Their MCP server is read-only (no bot control).

Source: [Fireflies MCP Blog](https://fireflies.ai/blog/fireflies-mcp-server/)

### 2.2 Otter.ai MCP Server (2025)

**Status**: Production (launched with enterprise suite, October 2025)

**Capabilities**:
- Meeting transcript access for external AI models
- Integration with corporate meeting knowledge base
- API for custom integrations (Jira, HubSpot)
- Presentations and meeting notes search

**Position**: Shifted from "meeting notetaker" to "corporate meeting knowledge base". MCP server connects Otter data to any AI model.

Source: [Otter.ai](https://otter.ai/)

### 2.3 Meeting BaaS MCP Server (Open Source)

**Status**: Active development, updated March 2026
**Repo**: [github.com/Meeting-Baas/meeting-mcp](https://github.com/Meeting-Baas/meeting-mcp)

**Tools**:
- `createBot`: Deploy bots with customizable names, avatars, entry messages, transcription providers
- `getRecording`: Recording metadata retrieval
- `getRecordingStatus`: Active recording monitoring
- `getMeetingTranscript`: Full transcripts by speaker with timestamps
- `findKeyMoments`: AI-powered highlight identification
- `shareableMeetingLink`: Markdown link generation with speaker/topic metadata
- `listUpcomingMeetings`: Calendar integration with recording status
- `scheduleRecording`: Auto-deploy bots to calendar events
- `cancelRecording`: Remove scheduled bot deployments

**Additional features**:
- OAuth for Google and Microsoft calendars
- QR code avatar generation
- Shared team access via corporate email domains
- Event filtering by date, attendees

**Separate speaking-bots-mcp**: Dedicated server for AI-powered speaking participants

**What Vexa can learn**: Meeting BaaS has two separate MCP servers (data + speaking), calendar OAuth, and findKeyMoments. They use separate servers to avoid tool namespace collision.

Source: [Meeting BaaS](https://www.meetingbaas.com/examples/mcp-tools), [GitHub](https://github.com/Meeting-Baas/meeting-mcp)

### 2.4 Whisper MCP Servers

Several MCP servers for audio transcription:

- **mcp-server-whisper** ([GitHub](https://github.com/arcaputo3/mcp-server-whisper)): OpenAI Whisper + GPT-4o transcription
- **Fast-Whisper-MCP-Server** ([GitHub](https://github.com/BigUncle/Fast-Whisper-MCP-Server)): Faster Whisper for high-performance local transcription
- **local-stt-mcp** ([GitHub](https://github.com/SmartLittleApps/local-stt-mcp)): whisper.cpp for Apple Silicon, speaker diarization, <2GB memory
- **audio-transcription-mcp** ([GitHub](https://github.com/pmerwin/audio-transcription-mcp)): Real-time system audio capture + Whisper

### 2.5 Calendar MCP Servers

- **google-calendar-mcp** ([GitHub](https://github.com/nspady/google-calendar-mcp)): Multi-account, free/busy queries, smart scheduling, image/PDF import
- **google_workspace_mcp** ([GitHub](https://github.com/taylorwilsdon/google_workspace_mcp)): Full Google Workspace (Calendar, Gmail, Docs, Sheets, Drive)
- **microsoft-mcp** ([GitHub](https://github.com/elyxlz/microsoft-mcp)): Microsoft Graph API (Outlook, Calendar, OneDrive)
- **mcp-teams-server** ([GitHub](https://github.com/InditexTech/mcp-teams-server)): MS Teams messages (read, create, reply, mention)
- **cal-mcp**: Both Google Calendar and Microsoft Outlook, mutual free-slot finding

### 2.6 Competitive Landscape Summary

| Feature | Fireflies | Otter.ai | Meeting BaaS | Vexa (current) |
|---------|-----------|----------|-------------|----------------|
| MCP tools | Yes (read-only) | Yes (read-only) | Yes (read+write) | Yes (read+write+control) |
| Bot deployment | No | No | Yes | Yes |
| Bot speaking | No | No | Yes (separate server) | Endpoint exists, no MCP tool |
| Transcript search | Yes (semantic) | Yes | Yes | No |
| Calendar integration | No | No | Yes (OAuth) | No |
| MCP Resources | Unknown | Unknown | No | No |
| MCP Subscriptions | No | No | No | No |
| MCP Sampling | No | No | No | No |
| Self-hosted | No | No | No | Yes |

**Vexa's unique position**: Only self-hosted meeting MCP server with full bot control (join, speak, chat, screen share). No competitor uses MCP Resources, Subscriptions, or Sampling. This is the differentiation opportunity.

---

## 3. Advanced MCP Server Patterns

### 3.1 Server Composition (FastMCP 2.0+)

Mount multiple MCP servers into a unified server:

```python
main = FastMCP("MainApp")
main.mount(meeting_tools, namespace="meetings")
main.mount(calendar_tools, namespace="calendar")
main.mount(analytics_tools, namespace="analytics")
```

**Benefits**: Modular development, namespace isolation, independent testing. Child components added post-mount are immediately visible.

**Proxy pattern**: FastMCP can proxy any MCP server regardless of transport:
```python
from fastmcp.server import create_proxy
mcp.mount(create_proxy("http://backend-service/mcp"), namespace="backend")
```

Source: [FastMCP Composition](https://gofastmcp.com/servers/composition)

### 3.2 Dynamic Tool Generation

The M365 Core MCP Server auto-discovers and creates tools for all Graph API endpoints at runtime. Pattern: introspect an API schema, generate MCP tools dynamically.

**Application for Vexa**: Generate tools from the gateway's OpenAPI spec rather than manually defining each one. When a new endpoint is added to the gateway, the MCP tool appears automatically.

Source: [Microsoft Dynamics 365 ERP MCP](https://www.microsoft.com/en-us/dynamics-365/blog/it-professional/2025/11/11/dynamics-365-erp-model-context-protocol/)

### 3.3 OpenAPI-to-MCP Conversion (FastMCP 3.0)

FastMCP 3.0 can generate MCP servers directly from OpenAPI specifications:

```python
from fastmcp.providers import OpenAPIProvider
provider = OpenAPIProvider("https://api.example.com/openapi.json")
```

Combined with `ToolTransform` for renaming, improving descriptions, and curating outputs.

Source: [FastMCP 3.0 Blog](https://www.jlowin.dev/blog/fastmcp-3-whats-new)

### 3.4 Per-Component Authentication (FastMCP 3.0)

Granular auth on individual tools, resources, or prompts:

```python
@mcp.tool(auth=require_scopes("meetings:write"))
def join_meeting(url: str): ...

@mcp.tool(auth=require_scopes("meetings:read"))
def get_transcript(meeting_id: str): ...
```

With `AuthMiddleware` for server-wide enforcement and `Visibility` transforms for per-session tool filtering.

Source: [FastMCP 3.0 Blog](https://www.jlowin.dev/blog/fastmcp-3-whats-new)

### 3.5 MCP Proxy/Gateway Pattern

Aggregate multiple MCP servers behind a single HTTP entrypoint:

- **mcp-proxy** ([GitHub](https://github.com/tbxark/mcp-proxy)): Aggregate tools, prompts, resources from many servers through SSE/Streamable HTTP
- **pluggedin-mcp-proxy** ([GitHub](https://github.com/VeriTeknik/pluggedin-mcp-proxy)): Discovery, management, playground for debugging across servers

**Application for Vexa**: The gateway already proxies MCP requests. This pattern validates the architecture.

### 3.6 Resource Subscription Push Pattern

The decoupled notification pattern for real-time data:

1. Client subscribes to resource URI
2. Server watches for changes (file watcher, WebSocket, polling)
3. On change: server sends lightweight `notifications/resources/updated`
4. Client calls `resources/read` for updated content

**Implementation reference**: [mcp-observer-server](https://github.com/hesreallyhim/mcp-observer-server) uses Python watchdog for file changes. Vexa would use its WebSocket stream instead.

**Key insight**: The notification is lightweight (just the URI). The client decides when to fetch updated content. This is efficient for high-frequency updates like live transcripts.

### 3.7 Sampling for Server-Side Intelligence

Pattern: Server receives data, uses client's LLM to analyze it, returns results.

```python
@mcp.tool()
async def analyze_meeting(meeting_id: str, ctx: Context):
    transcript = await get_transcript(meeting_id)
    result = await ctx.sample(
        messages=f"Extract action items from this transcript:\n\n{transcript}",
        system_prompt="You are a meeting analyst. Return structured action items.",
        result_type=ActionItems,  # Pydantic model for validation
    )
    return result.result
```

**Tool-assisted sampling** (FastMCP 2.14.1+): The LLM can call tools during sampling:
```python
result = await ctx.sample(
    messages="Find all meetings about the product launch and summarize decisions",
    tools=[search_meetings, get_transcript],  # LLM can call these
    tool_concurrency=3,
)
```

### 3.8 Background Tasks Pattern

For long-running operations using the Tasks primitive:

```python
# Client sends
{"method": "tools/call", "params": {
    "name": "transcribe_recording",
    "arguments": {"recording_id": "abc123"},
    "task": {"ttl": 300000}  # 5 min TTL
}}

# Server returns immediately
{"result": {"task": {
    "taskId": "786512e2-...",
    "status": "working",
    "pollInterval": 5000
}}}

# Client polls
{"method": "tasks/get", "params": {"taskId": "786512e2-..."}}
```

### 3.9 Ultimate MCP Server Pattern

The [Ultimate MCP Server](https://github.com/Dicklesworthstone/ultimate_mcp_server) demonstrates an "AI agent operating system" approach:
- Multi-provider LLM delegation with fallback
- Cognitive memory systems
- Cost optimization through model routing
- Semantic + task-aware caching
- Dynamic workflow orchestration

**Takeaway**: The most advanced MCP servers aren't just tool collections -- they include intelligence, memory, and workflow orchestration.

### 3.10 OpenTelemetry Integration (FastMCP 3.0)

Production observability with standardized tracing attributes:
```python
server = FastMCP("My Server", otel_enabled=True)
```

Source: [FastMCP 3.0 Blog](https://www.jlowin.dev/blog/fastmcp-3-whats-new)

---

## 4. What Would Make a Meeting MCP Server Stand Out

Based on the competitive landscape and protocol capabilities, here's what would differentiate Vexa's MCP server:

### 4.1 Live Meeting Resources with Subscriptions (No Competitor Does This)

```
vexa://meetings                                    -> browsable meeting list
vexa://meeting/{platform}/{id}/transcript          -> live transcript (subscribable)
vexa://meeting/{platform}/{id}/status              -> bot status + metadata
vexa://meeting/{platform}/{id}/participants        -> who's in the meeting now
vexa://meeting/{platform}/{id}/chat                -> meeting chat messages
vexa://recordings/{id}                             -> recording metadata + download
```

With subscriptions, an AI agent can watch a live transcript and react in real-time. No meeting MCP server does this today.

**Implementation**: Bridge Vexa's existing WebSocket real-time stream to MCP resource subscriptions:
```
MCP Client subscribes to vexa://meeting/google_meet/abc/transcript
  -> MCP server opens internal WebSocket to Vexa's real-time stream
  -> On each new segment: notifications/resources/updated
  -> Client calls resources/read for updated transcript
```

### 4.2 Sampling-Powered Meeting Intelligence

Use the client's LLM for real-time analysis without server-side inference:

- **Real-time action item detection**: Server feeds transcript segments, asks "action item?"
- **Live meeting summarization**: Continuous rolling summary as meeting progresses
- **Speaker sentiment analysis**: Analyze tone shifts in real-time
- **Meeting quality scoring**: "How productive is this meeting right now?"
- **Decision detection**: Flag when decisions are being made
- **Cross-meeting analysis**: "What was decided about X across all meetings this month?"

```python
@mcp.tool()
async def live_meeting_intelligence(meeting_id: str, query: str, ctx: Context):
    transcript = await get_live_transcript(meeting_id)
    result = await ctx.sample(
        messages=f"Based on this live meeting transcript, answer: {query}\n\n{transcript}",
        system_prompt="You analyze live meeting content. Be concise and actionable.",
        result_type=MeetingInsight,
    )
    return result.result
```

### 4.3 Elicitation for Interactive Meeting Flows

- **Meeting passcode**: When bot can't join, elicit passcode from user
- **Speaker confirmation**: "I detected 3 speakers. Can you confirm: Alice, Bob, Charlie?"
- **Calendar OAuth**: URL mode elicitation for Google/Microsoft calendar authorization
- **Meeting preferences**: Collect language, recording, transcription preferences
- **Bot customization**: Name, avatar, entry message before joining

```python
@mcp.tool()
async def join_meeting_with_preferences(url: str, ctx: Context):
    result = await ctx.elicit(
        message="Configure your bot before joining",
        schema={
            "type": "object",
            "properties": {
                "bot_name": {"type": "string", "default": "Vexa Bot"},
                "language": {"type": "string", "enum": ["en", "es", "fr", "de", "ja"]},
                "record": {"type": "boolean", "default": True},
            }
        }
    )
    if result.action == "accepted":
        return await deploy_bot(url, **result.data)
```

### 4.4 Tasks for Long-Running Operations

- **Transcribe recording** (may take minutes for long meetings)
- **Cross-meeting search** (searching across thousands of transcripts)
- **Batch export** (export multiple meetings in various formats)
- **Meeting attendance** (bot stays in meeting for hours)

### 4.5 Full Bot Control as MCP Tools

No competitor exposes interactive bot controls. Vexa's unique tools:

| Tool | Annotation | Description |
|------|-----------|-------------|
| `join_meeting` | destructive, open-world | Deploy bot to a meeting |
| `leave_meeting` | destructive | Remove bot from meeting |
| `send_chat_message` | destructive, open-world | Chat in the meeting |
| `bot_speak` | destructive, open-world | Bot speaks with TTS |
| `stop_speaking` | destructive | Stop current speech |
| `screen_share` | destructive, open-world | Share content in meeting |
| `set_avatar` | destructive | Change bot's avatar |

With proper tool annotations:
```python
@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    openWorldHint=True,
    idempotentHint=False,
))
async def send_chat_message(meeting_id: str, message: str): ...
```

### 4.6 Meeting Search and Analytics

- **Transcript search**: Full-text search across all meeting transcripts
- **Speaker analytics**: Talk-time distribution, interruption patterns
- **Topic extraction**: Identify key topics per meeting and across meetings
- **Sentiment trends**: How sentiment evolves over a series of meetings
- **Action item tracking**: Cross-meeting action item status

### 4.7 Calendar Integration

- **OAuth via URL elicitation**: Authenticate with Google/Microsoft calendars
- **Upcoming meetings**: List scheduled meetings across calendars
- **Auto-schedule bots**: Deploy bots to future calendar events
- **Availability check**: Find free slots across participants
- **Meeting creation**: Create meetings with auto-bot deployment

### 4.8 Meeting Summarization Patterns

- **Instant post-meeting summary**: Triggered automatically or on-demand
- **Customizable templates**: Different summary formats (executive, technical, action-focused)
- **Cross-meeting digest**: "Summarize all meetings from this week about Project X"
- **Sampling-based**: Use client's LLM, so no server-side inference cost

### 4.9 Webhook Subscriptions

- **Configure via MCP tool**: `configure_webhook` tool to set up event notifications
- **Event types**: meeting.started, meeting.ended, transcript.ready, action_items.extracted
- **MCP resource link**: Tools return `resource_link` content pointing to meeting resources

---

## 5. MCP Python SDK Features

### 5.1 Current Versions

- **Official SDK**: `mcp` package on PyPI
  - v1.26.0 (January 24, 2026) - latest stable v1.x
  - v1.25.0 (December 18, 2025) - branching: `main` for v2, `v1.x` for maintenance
  - v1.23.0 (December 2, 2025) - aligned with spec 2025-11-25, tasks, SSE polling, URL elicitation
  - v2 in pre-alpha on main branch
- **FastMCP** (standalone): v3.x (latest), used by 70% of MCP servers

### 5.2 Core Decorators

```python
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession

mcp = FastMCP(name="Vexa Meeting Server")

# Tool
@mcp.tool()
async def get_transcript(meeting_id: str, ctx: Context) -> str: ...

# Resource (static)
@mcp.resource("config://settings")
def get_settings() -> str: ...

# Resource (template)
@mcp.resource("vexa://meeting/{platform}/{id}/transcript")
def get_meeting_transcript(platform: str, id: str) -> str: ...

# Prompt
@mcp.prompt()
def post_meeting_summary(meeting_id: str) -> str: ...
```

### 5.3 Context Object Capabilities

The `Context[ServerSession, AppContext]` provides:
- `ctx.report_progress(progress, total, message)` - progress for long ops
- `ctx.info()`, `ctx.debug()`, `ctx.warning()`, `ctx.error()` - logging
- `ctx.session.create_message()` - low-level sampling
- `ctx.request_context.lifespan_context` - access to lifespan dependencies

### 5.4 Transport Options

- **stdio**: Direct process communication (for local MCP clients)
- **Streamable HTTP**: Web-based with CORS, session management, event resumability
- **SSE (Server-Sent Events)**: Real-time streaming
- **ASGI mounting**: Integration with existing web servers (FastAPI, Starlette)

### 5.5 Structured Output

```python
from pydantic import BaseModel

class MeetingSummary(BaseModel):
    title: str
    participants: list[str]
    action_items: list[str]
    decisions: list[str]
    next_steps: str

@mcp.tool()
def summarize_meeting(meeting_id: str) -> MeetingSummary:
    """Returns validated structured output."""
    return MeetingSummary(
        title="Q1 Planning",
        participants=["Alice", "Bob"],
        action_items=["Review budget", "Schedule follow-up"],
        decisions=["Approved project timeline"],
        next_steps="Follow-up meeting next Tuesday"
    )
```

### 5.6 Lifespan Management

```python
from dataclasses import dataclass
from contextlib import asynccontextmanager

@dataclass
class AppContext:
    db: Database
    redis: Redis
    ws_pool: WebSocketPool

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    db = await Database.connect()
    redis = await Redis.connect()
    ws_pool = WebSocketPool()
    try:
        yield AppContext(db=db, redis=redis, ws_pool=ws_pool)
    finally:
        await db.disconnect()
        await redis.close()
        await ws_pool.close()

mcp = FastMCP("Vexa MCP", lifespan=app_lifespan)
```

### 5.7 Key Features by SDK Version

| Version | Key Features |
|---------|-------------|
| v1.23.0 | Tasks (SEP-1686), SSE polling (SEP-1699), URL elicitation (SEP-1036), spec 2025-11-25 |
| v1.24.0 | Sampling with tools (SEP-1577), JSON-RPC error fixes |
| v1.25.0 | Branch strategy (v1.x maintenance, main for v2), URL elicitation fixes |
| v1.26.0 | Resource/ResourceTemplate metadata, HTTP 404 for unknown sessions |

### 5.8 Pin Version

For production stability, pin to v1.x:
```
mcp>=1.26,<2
```

---

## 6. FastMCP Framework Features

FastMCP is the high-level framework that powers most Python MCP servers. Available both as standalone (`fastmcp` package) and integrated into the official SDK.

### 6.1 FastMCP 2.0 (Composition + Proxy)

- **mount()**: Live-link child servers to parent, all components immediately visible
- **import_server()**: Static copy of components (no live link)
- **Proxy**: Bridge any transport to any other transport
- **create_proxy()**: Proxy remote servers, npm packages, uvx packages
- **Namespace prefixing**: Prevent naming collisions

### 6.2 FastMCP 3.0 (Production-Ready)

- **OpenAPI-to-MCP**: Generate tools from OpenAPI specs
- **Per-component auth**: `@mcp.tool(auth=require_scopes("admin"))`
- **Visibility transforms**: Per-session tool filtering, automatic `ToolListChangedNotification`
- **ToolTransform**: Rename, improve descriptions, curate outputs
- **Structured output**: `ToolResult`, `ResourceResult`, `PromptResult` classes
- **OpenTelemetry**: Standardized tracing
- **Background tasks**: Via Docket integration (SEP-1686)
- **Tool timeouts**: 30+ second limits
- **Pagination**: Large component sets
- **Hot reload**: `--reload` flag for development
- **Composable lifespans**: `|` operator

### 6.3 Sampling with FastMCP

```python
# Simple
result = await ctx.sample("Summarize this transcript:\n\n" + transcript)

# With parameters
result = await ctx.sample(
    messages="Extract action items from this meeting",
    system_prompt="You are a meeting analyst.",
    temperature=0.2,
    max_tokens=500,
    result_type=ActionItems,  # Pydantic model
)

# With tool use
result = await ctx.sample(
    messages="Find related discussions across recent meetings",
    tools=[search_meetings, get_transcript],
    tool_concurrency=3,
)

# Step-by-step control
while True:
    step = await ctx.sample_step(messages=messages, tools=tools)
    if not step.is_tool_use:
        return step.text
    messages = step.history

# Fallback for clients without sampling
server = FastMCP(
    sampling_handler=OpenAISamplingHandler(default_model="gpt-4o-mini"),
    sampling_handler_behavior="fallback",
)
```

---

## 7. 2026 MCP Roadmap

### 7.1 Four Priority Areas

1. **Transport Evolution**: Horizontal scaling, explicit session handling, `.well-known` metadata for discoverability without live connections. No new transports this cycle.

2. **Agent Communication**: Tasks primitive refinement (retry semantics, expiry policies). MCP servers as autonomous participants that receive tasks, evaluate policy, negotiate scope, and delegate sub-work to peers.

3. **Governance Maturation**: Contributor ladder, Working Group delegation, expedited review for priority-aligned SEPs.

4. **Enterprise Readiness**: Audit trails, SSO-integrated auth, gateway behavior, configuration portability. Most work as extensions, not core spec changes.

### 7.2 Key Implications for Vexa

- **Tasks primitive** will be production-ready soon -- invest in async operations now
- **Agent-to-agent communication** enables Vexa MCP server as an autonomous meeting participant
- **Transport scalability** improvements will solve session management issues at scale
- **Enterprise auth** (SSO/OIDC) aligns with Vexa's dashboard auth model

Source: [2026 MCP Roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/), [Roadmap page](https://modelcontextprotocol.io/development/roadmap)

---

## 8. Recommendations for Vexa

### 8.1 Migration Path: fastapi-mcp -> Official SDK or FastMCP 3.0

Current Vexa MCP uses `fastapi-mcp` (thin wrapper). Consider migrating to:
- **Option A**: Official `mcp` SDK v1.26 with FastMCP integration -- stable, well-supported
- **Option B**: Standalone `fastmcp` v3.x -- most features, fastest iteration, but separate dependency

FastMCP 3.0's OpenAPI-to-MCP conversion could auto-generate tools from the gateway's OpenAPI spec, reducing maintenance burden.

### 8.2 Priority Implementation Order

**Tier 1 -- Quick Wins (days)**
1. Add tool annotations to all 17 existing tools (readOnlyHint, destructiveHint, etc.)
2. Add structured output schemas to key tools (Pydantic models instead of raw dicts)
3. Expose chat/speak/screen as MCP tools (endpoints exist, just not MCP-wrapped)
4. Add progress reporting to long-running tools

**Tier 2 -- Differentiators (1-2 weeks)**
5. Implement MCP Resources for meetings and transcripts with custom `vexa://` URI scheme
6. Add resource subscriptions for live transcript updates (bridge WebSocket)
7. Add search tools (transcript search, meeting search with filters)
8. Implement elicitation for meeting passcode, speaker confirmation

**Tier 3 -- Intelligence Layer (2-4 weeks)**
9. Implement sampling for meeting intelligence (action items, summaries, decisions)
10. Add Tasks support for long-running operations (transcription, batch search)
11. Calendar integration with URL mode elicitation for OAuth
12. Cross-meeting analytics tools

**Tier 4 -- Platform (months)**
13. Server composition with namespaces (meetings, calendar, analytics sub-servers)
14. OpenAPI-to-MCP auto-generation
15. Per-component auth with scope-based access
16. OpenTelemetry integration
17. Agent-to-agent communication (meeting bot as autonomous MCP peer)

### 8.3 Architectural Recommendations

1. **Custom URI scheme**: Use `vexa://` for all resources. Examples:
   - `vexa://meetings` (list)
   - `vexa://meeting/{platform}/{id}/transcript` (template)
   - `vexa://meeting/{platform}/{id}/participants` (template)
   - `vexa://recording/{id}` (template)

2. **Lifespan for connections**: Use FastMCP lifespan to manage DB connections, WebSocket pool, and Redis connections as shared context.

3. **Namespace composition**: Split into sub-servers:
   - `meetings` namespace: CRUD, search, transcripts
   - `bot` namespace: join, leave, speak, chat, screen
   - `calendar` namespace: OAuth, events, scheduling
   - `analytics` namespace: insights, trends, speaker stats

4. **Subscription bridge**: Map Vexa WebSocket events to MCP resource notifications:
   - WebSocket `transcript_segment` -> `notifications/resources/updated` for `vexa://meeting/.../transcript`
   - WebSocket `participant_joined` -> `notifications/resources/updated` for `vexa://meeting/.../participants`
   - WebSocket `meeting_ended` -> `notifications/resources/list_changed`

5. **Sampling fallback**: Configure server with `sampling_handler_behavior="fallback"` so sampling-based tools work even with clients that don't support sampling.

---

## Sources

### MCP Protocol
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Spec Changelog](https://modelcontextprotocol.io/specification/2025-11-25/changelog)
- [Resources Spec](https://modelcontextprotocol.io/specification/2025-06-18/server/resources)
- [Elicitation Spec](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)
- [2026 MCP Roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/)
- [MCP Tasks Blog (WorkOS)](https://workos.com/blog/mcp-async-tasks-ai-agent-workflows)
- [SEP-1686: Tasks](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1686)
- [Tool Annotations Blog](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/)
- [MCP November 2025 Spec Analysis (Medium)](https://medium.com/@dave-patten/mcps-next-phase-inside-the-november-2025-specification-49f298502b03)
- [Cisco: Elicitation, Structured Content, OAuth](https://blogs.cisco.com/developer/whats-new-in-mcp-elicitation-structured-content-and-oauth-enhancements)

### SDKs & Frameworks
- [MCP Python SDK (GitHub)](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Python SDK Releases](https://github.com/modelcontextprotocol/python-sdk/releases)
- [MCP Python SDK (PyPI)](https://pypi.org/project/mcp/)
- [FastMCP 2.0 Blog](https://www.jlowin.dev/blog/fastmcp-2)
- [FastMCP 3.0 Blog](https://www.jlowin.dev/blog/fastmcp-3-whats-new)
- [FastMCP Proxy Blog](https://www.jlowin.dev/blog/fastmcp-proxy)
- [FastMCP Composition Docs](https://gofastmcp.com/servers/composition)
- [FastMCP Sampling Docs](https://gofastmcp.com/servers/sampling)
- [FastMCP Tools Docs](https://gofastmcp.com/servers/tools)
- [SDK Elicitation Example](https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/snippets/servers/elicitation.py)

### Meeting Implementations
- [Meeting BaaS MCP (GitHub)](https://github.com/Meeting-Baas/meeting-mcp)
- [Meeting BaaS MCP Tools](https://www.meetingbaas.com/examples/mcp-tools)
- [Fireflies MCP Server Blog](https://fireflies.ai/blog/fireflies-mcp-server/)
- [Otter.ai](https://otter.ai/)

### Whisper/Transcription MCP
- [mcp-server-whisper (GitHub)](https://github.com/arcaputo3/mcp-server-whisper)
- [Fast-Whisper-MCP-Server (GitHub)](https://github.com/BigUncle/Fast-Whisper-MCP-Server)
- [local-stt-mcp (GitHub)](https://github.com/SmartLittleApps/local-stt-mcp)
- [audio-transcription-mcp (GitHub)](https://github.com/pmerwin/audio-transcription-mcp)

### Calendar MCP
- [google-calendar-mcp (GitHub)](https://github.com/nspady/google-calendar-mcp)
- [google_workspace_mcp (GitHub)](https://github.com/taylorwilsdon/google_workspace_mcp)
- [microsoft-mcp (GitHub)](https://github.com/elyxlz/microsoft-mcp)
- [mcp-teams-server (GitHub)](https://github.com/InditexTech/mcp-teams-server)

### Advanced Patterns
- [Ultimate MCP Server (GitHub)](https://github.com/Dicklesworthstone/ultimate_mcp_server)
- [mcp-proxy (GitHub)](https://github.com/tbxark/mcp-proxy)
- [pluggedin-mcp-proxy (GitHub)](https://github.com/VeriTeknik/pluggedin-mcp-proxy)
- [mcp-observer-server (GitHub)](https://github.com/hesreallyhim/mcp-observer-server)
- [MCP Push Notifications Blog](https://gelembjuk.com/blog/post/using-mcp-push-notifications-in-ai-agents/)
- [Spring AI Dynamic Tool Updates](https://spring.io/blog/2025/05/04/spring-ai-dynamic-tool-updates-with-mcp/)
- [Microsoft MCP for Beginners: Real-time Streaming](https://deepwiki.com/microsoft/mcp-for-beginners/6.9-real-time-streaming-and-notifications)

### General
- [WorkOS: Everything About MCP in 2026](https://workos.com/blog/everything-your-team-needs-to-know-about-mcp-in-2026)
- [Awesome MCP Servers (GitHub)](https://github.com/wong2/awesome-mcp-servers)
- [MCP Wikipedia](https://en.wikipedia.org/wiki/Model_Context_Protocol)
