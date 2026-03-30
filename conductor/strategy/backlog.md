---
last_updated: 2026-03-24
sources_checked: [vexa-github-issues, otter-ai-blog, fireflies-techcrunch, recall-ai-series-b, granola-techcrunch, tldv-blog, meetgeek-website, recall-ai-changelog, hacker-news-meeting-ai, google-meet-media-api-docs, ms-teams-api-docs, zoom-sdk-docs, nbcpalmsprings-bot-privacy, helpnetsecurity-teams-bot-id]
---

## Ranked Opportunities

| Rank | Opportunity | Signal | Gap | Feasibility | Action |
|------|------------|--------|-----|-------------|--------|
| 1 | Zoom platform support | Very High — 3rd platform, 0 score, every competitor has it | Vexa is 0/complete; Recall, Fireflies, Otter all support it | Medium — bot infra exists, Zoom SDK compliance requires Marketplace review | Build new (0 → 60) |
| 2 | Calendar integration (auto-join) | Very High — #1 enterprise ask, every competitor ships it | Vexa research-only; Recall.ai ships Calendar V2 API as core product | High — architecture researched, meeting-api POST /bots exists | Build new (0 → 60) |
| 3 | Knowledge workspace entity extraction | High — "company memory" is the dominant market narrative in 2026 | Vexa has infra + template; pipeline from transcript → entities is missing | High — transcript pipeline exists, entity extraction is one new service | Improve existing (30 → 70) |
| 4 | Chat validation (E2E test) | High — code-complete, 0 tested; speaking bot + chat = interactive agent | Competitors don't expose raw chat API; Vexa has competitive moat here | Very High — code exists, needs browser session E2E test | Improve existing (0 → 70) |
| 5 | Speaking bot stability | High — 4 browser_session bugs block agentic use cases | MeetingBaaS ships speaking bots via Pipecat; Vexa has comparable capability | High — code exists, remote-browser needs work | Improve existing (70 → 90) |
| 6 | Scheduler E2E unblock | Medium — scheduler is prerequisite for calendar integration and knowledge audit | Unit tests pass; E2E blocked by environment issues | High — known blocker, likely configuration | Improve existing (45 → 80) |
| 7 | MCP + Agentic runtime (public API) | Medium — Otter, MeetGeek both ship MCP servers; market is validating this | Vexa has 17 MCP tools + agentic runtime; needs polish and docs | Very High — already at 80-90; mostly docs/packaging | Polish and publish (80/90 → 95) |
| 8 | Bot-free / desktop recording path | Medium — growing privacy backlash, universities blocking bots; Recall.ai ships Desktop SDK | Not on Vexa roadmap; Recall.ai and Granola both go bot-free | Low — requires new recording architecture | Research only — watch trend |
| 9 | Multi-tenant / enterprise isolation | Medium — token scoping at 90, but enterprise SSO/admin controls lag Otter enterprise suite | Otter launched enterprise suite + HIPAA in late 2025 | Medium — token-scoping infra exists, HIPAA/SOC2 requires process | Plan for V2 |
| 10 | Real-time AI assistant (speak + search) | Medium — Fireflies "Talk to Fireflies" unicorn launch; Otter SDR agent | Vexa has speaking bot + agentic runtime; lacks real-time LLM-to-voice pipeline | Medium — needs Pipecat or similar to close loop | Research + prototype |

---

## Detailed Analysis

### 1. Zoom Platform Support

**Signal:** Every major competitor (Otter, Fireflies, Granola, tl;dv, Recall.ai, MeetGeek, Read.ai) supports Zoom. It is the largest enterprise meeting platform. The HN thread on Vexa's open-source API launch had Zoom as an implied gap. Vexa's own GitHub shows `multi-platform` at 70 (Teams 85, GMeet 75, Zoom 0). The competitive comparison site skribby.io lists "Zoom support" as first differentiator.

**Gap:** Vexa is the only platform-class meeting API with a zero Zoom score. Recall.ai, MeetingBaaS, and Skribby all support Zoom. This is the single biggest platform gap.

**Feasibility:** Medium. Zoom's SDK requires Marketplace review for external use, which can take weeks. The Zoom RTMS (Real-Time Media Streams) SDK launched in 2025 offers an alternative to Meeting SDK bots. The bot infrastructure (browser automation) already works — the challenge is compliance, not architecture. Recall.ai published a guide on Zoom compliance requirements.

**Action:** Build Zoom support. Prioritize RTMS SDK path over Meeting SDK bot to avoid Marketplace review delay. Target: Level 2 E2E (bot joins, transcribes) by end of April. Compliance review can run in parallel.

---

### 2. Calendar Integration (Auto-Join)

**Signal:** The #1 enterprise use case for meeting AI is "just show up." Every competitor auto-joins from calendar. Recall.ai built Calendar V2 API as a core product feature. Otter's OtterPilot joins from calendar. Granola has Slack posting on meeting end. MeetGeek auto-joins from Google Calendar. The absence of this makes manual `POST /bots` a barrier to enterprise adoption.

**Gap:** Vexa has research complete and architecture designed but zero implementation. The gap is large but well-scoped. Recall.ai's calendar API is a paid-tier feature that other platforms built on top of — Vexa could ship native calendar sync faster as a self-hosted alternative.

**Feasibility:** High. Architecture is documented in `calendar-integration/RESEARCH.md`. Google OAuth flow can reuse NextAuth's existing Google provider. Bot-manager already has `POST /bots`. New service: `calendar-service` (poll-based sync, ~2 weeks). Push notifications are V1, not MVP.

**Action:** Build calendar-service. Google Calendar first (OAuth + poll + Meet URL extraction + auto-schedule). Outlook/Teams calendar in V2.

---

### 3. Knowledge Workspace Entity Extraction

**Signal:** The dominant market narrative in 2026 is "meetings as company memory." Granola raised $43M at $250M positioning around team knowledge. Otter's enterprise suite frames itself as "turning meetings into a living knowledge base." The AI knowledge management market is growing 47% CAGR. Fireflies' 200+ AI apps and tl;dv's multi-meeting intelligence are both pointed at the same thing: meetings that feed structured knowledge.

**Gap:** Vexa has the architecture (template, MinIO persistence, agent chat with workspace context) but the critical pipeline — transcript → entity extraction — is missing. This is the blocker at score 30. The gap is not architectural; it is one new pipeline component.

**Feasibility:** High. Post-meeting transcription already produces transcripts at score 80. The entity extraction pipeline reads a transcript and writes entity files to the workspace. This is an LLM task, not a new service — it runs inside the agentic runtime. The hardest part (workspace template, persistence, agent context) is already done.

**Action:** Build entity extraction pipeline. Trigger: `meeting.completed` webhook → agent task → parse transcript → write/update entity files in knowledge/entities/. Estimate: 1 week.

---

### 4. Chat Validation (E2E)

**Signal:** Chat is code-complete and has been since at least 2026-03-23. It is a zero-score feature that Vexa has a genuine competitive moat in: no competitor exposes a raw bidirectional meeting chat API. Combined with speaking bot, it enables interactive agent scenarios (agent answers questions in meeting chat) that none of the note-takers support.

**Gap:** The code exists but selectors may have drifted. Zoom chat is not implemented. The E2E has never been run. Risk: silent failure on send (client gets 202 even if DOM injection fails).

**Feasibility:** Very High. The full stack is implemented. This is a test execution task: run `POST /bots/{id}/chat` in a live session, verify DOM, verify `GET /bots/{id}/chat` returns messages. If DOM selectors have drifted, that is a small fix.

**Action:** E2E validate chat in a live Google Meet session. Fix any drifted DOM selectors. This is low-effort, high-value (0 → 70).

---

### 5. Speaking Bot Stability

**Signal:** The speaking bot is at 70 with 4 known browser_session bugs. MeetingBaaS ships autonomous speaking bots via Pipecat and positions them as a core differentiator. Otter launched AI meeting agents (voice-activated, SDR demos) as their headline 2025 feature. The "AI agent in the meeting" narrative is the hottest market story right now — Fireflies achieved unicorn status on the back of "Talk to Fireflies" (voice + web search during meetings).

**Gap:** Vexa has speaking bot capability but it's unstable. The remote-browser component is at 50 (PoC only). Fixing the 4 browser_session bugs would bring speaking bot to 90 and unlock the full agentic-in-meeting use case.

**Feasibility:** High. The bugs are known and tracked. Remote-browser is a dependency. The speaking bot feature agent knows what needs fixing.

**Action:** Fix 4 browser_session bugs. Improve remote-browser from 50 to 80. This unblocks speaking bot 70 → 90 and enables the "agent in meeting" demo.

---

### 6. Scheduler E2E Unblock

**Signal:** Scheduler is at 45 (unit tests pass, E2E blocked). It is a hard dependency for: calendar integration (auto-join timing), knowledge workspace (scheduled audits), and any time-triggered agentic action. Without a working scheduler, calendar integration cannot ship end-to-end.

**Gap:** Unit tests pass — the logic is correct. The E2E block is likely a configuration or environment issue, not an architectural one.

**Feasibility:** High. The blocker needs diagnosis, not a rewrite.

**Action:** Diagnose E2E blocker, fix configuration, get scheduler to 80. This is a prerequisite for calendar integration.

---

### 7. MCP + Agentic Runtime (Polish and Publish)

**Signal:** Both Otter and MeetGeek now ship MCP servers. The MCP ecosystem is growing fast (Claude, ChatGPT both support it). Vexa's 17 MCP tools + agentic runtime is ahead of most competitors. Otter's MCP launched in October 2025 as part of their enterprise suite. MeetGeek lists "MCP server for custom integrations" as a headline feature. This is an area where Vexa is ahead — the opportunity is to solidify the lead.

**Gap:** Vexa MCP is at 90, agentic runtime at 80. The gap is polish: documentation, examples, public announcement. The HN thread on Vexa's open-source launch showed strong interest in the speaking bot + API combination.

**Feasibility:** Very High. Already at 80-90. Primarily docs and packaging work.

**Action:** Write developer documentation. Publish example agentic workflows. Announce MCP server on HN/Product Hunt.

---

### 8. Bot-Free / Desktop Recording Path (Watch)

**Signal:** Growing privacy backlash in 2025-2026. Oxford University blocked meeting bot SSO. NBC reported on bots capturing off-topic conversations. Fireflies faces a class-action BIPA lawsuit. A significant user segment explicitly prefers bot-free tools (Jamie, Meetily, Granola desktop, Krisp). Recall.ai launched a Desktop Recording SDK as a direct response.

**Gap:** Vexa has no bot-free path. All recording goes through browser-bot injection. This is an architectural limitation.

**Feasibility:** Low for now. Building a desktop SDK is a major new product surface area. Microsoft is adding bot identification features (rolling out May 2026) that may increase friction for bot-based approaches.

**Action:** Watch this trend. If Teams bot identification (May 2026 rollout) creates access problems, escalate to high priority. Do not build now — too large a scope for current team.

---

### 9. Enterprise Isolation / HIPAA (Plan for V2)

**Signal:** Otter achieved HIPAA compliance in July 2025 and launched enterprise admin controls in October 2025 as part of their $100M ARR milestone push. The enterprise segment dominates 72% of AI meeting assistant revenue. Token scoping at 90 is a foundation for enterprise, but HIPAA and SSO are still gaps.

**Gap:** Token scoping (score 90) is strong. Missing: HIPAA certification, enterprise SSO (SAML), audit logs, data residency controls.

**Feasibility:** Medium. Technical groundwork (token scoping) exists. HIPAA is a process/audit commitment as much as a code change.

**Action:** Plan for V2. Put HIPAA certification on roadmap once core features stabilize.

---

### 10. Real-Time AI Assistant (Speak + Search)

**Signal:** Fireflies achieved unicorn ($1B valuation) on the back of "Talk to Fireflies" — a voice-activated assistant with real-time Perplexity web search during meetings. Otter launched the Otter SDR Agent (conducts live demos autonomously). MeetGeek launched AI Voice Agents with Copilot Mode and upcoming Delegate Mode. This is the hottest market narrative.

**Gap:** Vexa has the components (speaking bot, agentic runtime, webhooks, MCP) but no pipeline that closes the loop: detect question in meeting → LLM generates answer → speaking bot delivers it.

**Feasibility:** Medium. The components exist. Pipecat (used by MeetingBaaS) is an open-source framework for exactly this. The gap is integration and latency management.

**Action:** Prototype after speaking bot is at 90. Use Pipecat as the integration layer. This becomes the flagship demo.

---

## Competitor Snapshot

### Otter.ai
- $100M ARR, ~200 employees
- **Key 2025 launches:** AI Meeting Agents (voice-activated in-meeting assistant, March 2025), SDR Agent (autonomous demo bot), Enterprise Suite with MCP server + public API + HIPAA (October 2025)
- MCP server launched — connects meeting data to Claude and ChatGPT
- **Versus Vexa:** Ahead on enterprise (admin controls, HIPAA, SSO). Behind on open-source/self-hosted. No agentic runtime concept. Bot-based only (no desktop SDK).

### Fireflies.ai
- Unicorn status ($1B valuation, June 2025) on "Talk to Fireflies" launch
- **Key 2025 launches:** Real-time notes (January), 200+ AI Apps for sales/recruiting/ops (April), Perplexity-powered voice search during meetings (June)
- Perplexity integration for real-time web search is a genuine differentiator
- **Versus Vexa:** Ahead on AI apps ecosystem and in-meeting voice assistant. Behind on open-source, self-hosted, MCP integration. No agentic runtime.

### Granola
- $43M Series B, $250M valuation (May 2025)
- **Approach:** Desktop-first, bot-free, notepad UI that captures system audio
- **Key 2025 launches:** Team collaboration, shared folders, shareable URLs, Slack posting on meeting end, reasoning model support
- Positions as privacy-first alternative to bot-based tools
- **Versus Vexa:** Different architecture (bot-free desktop vs bot API). Granola is ahead on UX polish and privacy positioning. Vexa ahead on API access, MCP, agentic runtime.

### tl;dv
- **Key focus areas (2025-2026):** Multi-meeting intelligence (search across all meetings), AI Coaching Hub (sales coaching), CRM automation
- Emphasizes "company memory" as a product direction
- 40+ language support, advanced search across meeting history
- **Versus Vexa:** Ahead on meeting analytics and cross-meeting search. Behind on API platform, open-source, bot capabilities. No agentic runtime.

### Recall.ai (API Platform)
- $38M Series B at $250M (September 2025), led by Bessemer Venture Partners
- **Key 2025 launches:** Desktop Recording SDK (bot-free), Calendar Integration V2, Storage & Playback, Mobile SDK (beta)
- 2,000+ companies using the API (HubSpot, ClickUp, Calendly, Apollo, Affinity)
- Positioned as "The API for Meeting Recording" — infrastructure layer, not end product
- **Versus Vexa:** Direct infrastructure competitor. Recall.ai is proprietary and expensive ($1K/month minimum). Vexa is open-source and self-hostable. Recall.ai has broader platform support (Webex, Slack Huddles, GoTo). Recall.ai has Desktop SDK; Vexa does not.

### MeetGeek
- **Key 2025 launches:** AI Voice Agents (August 2025) — join meetings, listen, speak, follow instructions; Copilot Mode (real-time support); Delegate Mode (upcoming, autonomous)
- MCP server for custom integrations
- 100+ language support, 60+ integrations
- **Versus Vexa:** MeetGeek and Vexa are converging on AI voice agents. MeetGeek is ahead on integrations and end-user polish. Vexa ahead on self-hosted/open-source and agentic runtime depth.

### Read.ai
- Meeting notes, transcription, insights focus
- **Status:** Multiple users reporting dissatisfaction (MeetGeek's "why people are leaving" content). Facing competitive pressure.
- **Versus Vexa:** Read.ai appears to be losing ground to more capable competitors. Not a primary benchmark.

---

## Market Narratives

### "AI agents in meetings" is the dominant 2026 story
Fireflies ($1B), Otter (SDR agent), MeetGeek (AI Voice Agents), and Zoom AI Companion 3.0 are all racing to put AI agents *inside* meetings as active participants, not passive recorders. The shift is: passive note-taker → active participant → autonomous delegate. Vexa's speaking bot + agentic runtime is architecturally aligned with this trend but not polished enough to demonstrate it.

### Privacy backlash is creating a second market
Bot-based tools are facing institutional resistance: Oxford blocked meeting bot SSO, Fireflies has a BIPA class-action, Microsoft is adding bot identification to Teams (May 2026). A significant user segment explicitly wants bot-free tools. Recall.ai responded with a Desktop SDK. This is a market Vexa is not addressing.

### "Company memory" is the enterprise pitch
Granola, tl;dv, Otter, and the whole AI knowledge management space are converging on "meetings feed a persistent, searchable organizational memory." Vexa's knowledge workspace feature is directly in this narrative but is unfinished (entity extraction missing). This is the highest-leverage incomplete feature relative to market demand.

### Open-source / self-hosted is a genuine differentiator
The HN community explicitly values Vexa's open-source, self-hosted approach as a response to Recall.ai's $1K/month minimum. The "no vendor lock-in" narrative is strong in technical communities. Vexa should lean into this positioning more explicitly.

### MCP is becoming table stakes
Otter launched MCP. MeetGeek launched MCP. The MCP ecosystem is growing fast. Vexa at 17 tools is ahead of most competitors but needs to publish this more loudly.

---

## Platform Changes

### Google Meet Media API
- Google launched the Meet Media API (official real-time media access) but it is in Developer Preview and requires enrollment in the Developer Preview Program
- Restrictions: requires all participants enrolled, host permission needed, blocked for encrypted meetings and consumer (@gmail.com) accounts when initiator is absent
- This is a limited path for now — browser-bot approach remains more permissive for general use
- Long-term: Google may restrict browser-based bots and push toward Media API

### Microsoft Teams
- Multi-tenant bot creation deprecated after July 31, 2025 (existing connections still work, new ones blocked in Azure)
- Microsoft is rolling out bot identification for meeting admins (scheduled: May 2026, all platforms)
- This is a significant threat: if admins can block bots pre-join, bot-based Teams access gets harder
- PSTN transfer licensing changes (September 2025) — not directly relevant to transcription bots

### Zoom
- RTMS (Real-Time Media Streams) SDK launched in 2025 — enables direct audio/video/transcription access without Meeting SDK bot
- Meeting SDK bots that join external accounts require Marketplace review (weeks to months)
- RTMS is the faster path to Zoom support for Vexa

### General trend
The platforms are gradually tightening bot access (Teams bot ID, Google Meet Media API restrictions) while opening official SDK paths (Zoom RTMS, Google Media API). The window for unrestricted browser-bot access is closing. Vexa should be aware of this trajectory and plan for official SDK paths alongside browser automation.

---

## Priority Scoring

Using: `market_signal * (1 - current_score/100) * feasibility` where each is 0-10.

| Feature | Market Signal | (1 - score) | Feasibility | Priority Score |
|---------|--------------|-------------|-------------|----------------|
| Zoom support | 10 | 1.0 | 6 | 60 |
| Calendar integration | 9 | 1.0 | 8 | 72 |
| Knowledge workspace entity extraction | 8 | 0.7 | 9 | 50 |
| Chat validation | 7 | 1.0 | 9 | 63 |
| Speaking bot stability | 8 | 0.3 | 8 | 19 |
| Scheduler E2E | 6 | 0.55 | 9 | 30 |
| MCP polish/publish | 7 | 0.1 | 10 | 7 |

**Top 3 by priority score:** Calendar Integration (72) > Chat Validation (63) > Zoom Support (60)

Note: Calendar integration has a hard dependency on Scheduler E2E (score 45). Scheduler must be unblocked first.

**Recommended execution order:**
1. Scheduler E2E fix (prerequisite for #1)
2. Calendar Integration + Chat Validation (parallel)
3. Knowledge workspace entity extraction
4. Zoom support (can run in parallel with #3)
5. Speaking bot stability (depends on remote-browser improvement)
