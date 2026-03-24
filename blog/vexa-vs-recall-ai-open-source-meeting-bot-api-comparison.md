---
title: 'Vexa vs Recall.ai: Open-Source Meeting Bot API Comparison (2026)'
date: '2026-02-21'
author: 'Dmitry Grankin'
authorImage: '/dmitry-grankin.jpg'
authorLinkedIn: 'https://www.linkedin.com/in/dmitry-grankin/'
heroImage: '/assets/vexa-vs-recall-ai-comparison.png'
slug: 'vexa-vs-recall-ai-open-source-meeting-bot-api-comparison'
summary: "Detailed comparison of Vexa and Recall.ai for meeting bot APIs. Compare pricing, features, self-hosting, open source, and real-time transcription capabilities."
---

Choosing between **Vexa** and **Recall.ai** for your meeting bot API? Both platforms let you drop bots into meetings to capture transcripts — but they take fundamentally different approaches. Recall.ai is a VC-backed proprietary SaaS ($50M+ raised, $250M valuation). Vexa is an open-source, self-hostable API under Apache 2.0 license.

This comparison covers pricing, features, self-hosting, real-time streaming, and when to pick each one — with actual numbers, not marketing speak.

---

## Quick Comparison

| Feature | Vexa | Recall.ai |
|---------|------|-----------|
| **License** | Apache 2.0 (open source) | Proprietary (closed source) |
| **Self-hosted option** | Yes — full stack, Docker | No |
| **Pricing** | From $0.45/hr; self-hosted free | ~$0.72/hr all-in (recording + transcription + storage) |
| **Platforms** | Google Meet, Microsoft Teams, Zoom | Zoom, Meet, Teams, Webex, Slack Huddles, GoTo, BlueJeans, Whereby, Skype |
| **Real-time streaming** | WebSocket, sub-second latency | Webhooks; "Low Latency" mode (English only) |
| **Languages** | 100+ (Whisper-based) | 34 |
| **Speaker diarization** | Yes | Yes (per-participant streams) |
| **MCP server** | Yes (Claude, Cursor, Windsurf) | No |
| **Funding** | Bootstrapped | $50.7M ($250M valuation) |
| **GitHub stars** | 1,700+ | N/A (closed source) |

---

## Pricing: What You Actually Pay

Pricing is where the two diverge significantly. Both charge per hour, but Vexa comes in 30% cheaper — and self-hosted is free.

### Recall.ai Pricing

| Tier | Recording Cost | Transcription | Storage |
|------|---------------|---------------|---------|
| Pay As You Go | $0.50/hr | +$0.15/hr | 7 days free, then $0.05/hr/30 days |
| Launch | Custom (contact sales) | Included | Custom |
| Enterprise | Custom (contact sales) | Included | Custom |

**Pay As You Go fine print:**
- 500-hour monthly cap
- 2-hour limit per individual recording
- First 5 hours free on signup
- Transcription is an additional cost on top of recording

**The real cost per hour:** $0.50 (recording) + $0.15 (transcription) + $0.05+ (storage beyond 7 days) = **~$0.72/hour** with basic retention. Storage costs compound the longer you keep recordings.

### Vexa Pricing

| Tier | Cost | Includes |
|------|------|----------|
| Free Trial | $0 | 1 hour of transcription |
| Individual | $12/mo | 1 bot |
| Bot Service | $0.45/hr | Bot + post-meeting transcription + 12mo storage |
| Real-time add-on | +$0.05/hr | Sub-5s latency streaming |
| Transcription API | $0.0015/min | For self-hosted bot users |
| Enterprise | Custom | Book a call |
| Self-hosted | $0 | Apache 2.0, deploy on your own infrastructure |

**Key difference:** Vexa's all-in rate with real-time transcription is **$0.50/hr** — 30% cheaper than Recall.ai's ~$0.72/hr. Storage is included for 12 months at no extra cost. Self-hosted remains completely free.

### Cost at Scale

Here's what you actually pay at different usage levels (Vexa rate includes real-time add-on):

| Monthly Usage | Recall.ai (~$0.72/hr) | Vexa ($0.50/hr) | Vexa (Self-hosted) |
|--------------|------------------------|-----------------|---------------------|
| 10 hrs/mo | $7.20 | $5.00 | $0 |
| 50 hrs/mo | $36.00 | $25.00 | $0 |
| 200 hrs/mo | $144.00 | $100.00 | $0 |
| 500 hrs/mo | $360.00 (hits cap) | $250.00 | $0 |
| 1,000 hrs/mo | Requires Launch tier (sales call) | $500.00 | $0 |

At every usage level, **Vexa is ~30% cheaper** than Recall.ai — and self-hosted is free regardless of volume.

---

## Features: Head-to-Head

### Platform Support

**Recall.ai wins on breadth.** They support 9 platforms including Webex, Slack Huddles, GoTo Meeting, BlueJeans, Whereby, and Skype. If you need Webex or GoTo Meeting, Recall.ai is currently the only option.

**Vexa covers the big three:** Google Meet, Microsoft Teams, and Zoom. These represent 90%+ of business meetings. If your users are on Meet and Teams, Vexa has you covered.

### Real-Time Transcription

This is where the approaches differ most:

**Vexa:** WebSocket streaming with sub-second latency. Connect, subscribe to a meeting, and get transcript segments as they happen. Works across all supported platforms and all languages.

```python
# Vexa: real-time transcript in 5 lines
async with websockets.connect(WS_URL, extra_headers=[("X-API-Key", API_KEY)]) as ws:
    await ws.send(json.dumps({"action": "subscribe",
        "meetings": [{"platform": "google_meet", "native_id": "abc-defg-hij"}]}))
    async for msg in ws:
        event = json.loads(msg)
        if event["type"] == "transcript.mutable":
            for s in event["payload"]["segments"]:
                print(f'{s["speaker"]}: {s["text"]}')
```

**Recall.ai** offers two real-time modes:
- **"Accurate" mode:** 3–10 minute delay for higher accuracy. Supports 34 languages.
- **"Low Latency" mode:** Seconds of delay, but **restricted to English only** with limited customization.

If you're building an agent that needs to react during a meeting (not minutes after), Vexa's sub-second WebSocket streaming is the better fit.

### Speaker Diarization

Both platforms identify speakers. Recall.ai's approach is unique — they capture per-participant audio streams and match speakers to their streams, achieving "100% perfect" diarization. Vexa uses signal-based speaker detection that works well in practice, though it doesn't have the per-participant stream advantage.

### MCP Server (AI Agent Integration)

**Vexa has a built-in MCP server.** Connect Claude Desktop, Cursor, Windsurf, or any MCP-enabled agent directly to your meeting transcripts. Ask Claude "summarize the last meeting" or "what action items did we agree on?" and it queries Vexa directly.

Recall.ai does not offer MCP server support. To connect meeting data to AI agents, you'd need to build custom integration code.

### Data & Infrastructure

| Aspect | Vexa | Recall.ai |
|--------|------|-----------|
| Where data lives | Your infrastructure (self-hosted) or Vexa cloud | Recall.ai's cloud only |
| Open source | Yes (Apache 2.0) | No |
| Self-hosted | Yes | No |
| Data residency control | Full (you choose) | Limited (request-based) |
| Vendor lock-in | None (fork & run forever) | Full (proprietary API) |
| SOC 2 | In progress | Yes |
| HIPAA | Self-hosted (your compliance) | Yes (BAA available) |

---

## When to Choose Recall.ai

Recall.ai is the right choice if:

- **You need 5+ platforms** — Webex, GoTo Meeting, Slack Huddles, or BlueJeans support is required
- **You want enterprise compliance out of the box** — SOC 2, HIPAA with BAA, ISO 27001 already in place
- **You want a single vendor** — one contract, one support channel, one invoice
- **You need the Desktop Recording SDK** — bot-less recording directly from the user's machine
- **You want the largest ecosystem** — 2,000+ companies use Recall.ai, with extensive documentation and integrations

---

## When to Choose Vexa

Vexa is the right choice if:

- **You need self-hosting** — data sovereignty, GDPR, or internal policy requires data to stay on-premises
- **You want open source** — inspect the code, modify it, contribute back, no vendor lock-in
- **You're building at scale** — $0.50/hr all-in is 30% cheaper than Recall.ai, and self-hosted is free
- **You need sub-second real-time streaming** — WebSocket delivery for meeting agents that react during calls
- **You're building with AI agents** — MCP server integration connects Claude, Cursor, and other agents directly
- **You want multilingual real-time** — 100+ languages in real-time, not just English
- **Budget is a constraint** — self-hosted Vexa is free, no minimum spend, no sales call

---

## The Fundamental Difference

Recall.ai is a platform. Vexa is infrastructure.

With Recall.ai, you get a managed service backed by $50M in funding and 2,000 customers. You don't run anything — they handle the bots, the transcription, the storage. The trade-off is vendor lock-in and per-hour costs that scale linearly.

With Vexa, you get the building blocks. Self-host the entire stack, customize transcription models, connect AI agents via MCP, and pay 30% less per hour — or zero with self-hosting. The trade-off is that you manage the infrastructure (or use the hosted API at $0.50/hr all-in).

Both are production-grade. The choice depends on whether you want to rent infrastructure or own it.

---

## Getting Started with Vexa

Try Vexa in 2 minutes — no credit card, no sales call:

1. **Get an API key:** [vexa.ai/dashboard/api-keys](https://vexa.ai/dashboard/api-keys)
2. **Send a bot to your next meeting:**

```bash
curl -X POST "https://api.cloud.vexa.ai/bots" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"platform": "google_meet", "native_meeting_id": "abc-defg-hij",
       "transcribe_enabled": true, "transcription_tier": "realtime"}'
```

3. **Stream transcripts in real-time** via WebSocket or fetch them via REST

Or self-host the entire stack:

```bash
git clone https://github.com/Vexa-ai/vexa.git
cd vexa && make setup && make up
```

---

## FAQ

### Can I migrate from Recall.ai to Vexa?

Yes. Both use REST APIs with similar patterns (send bot → get transcript). Migration typically involves changing API endpoints and adjusting field names. Since Vexa is open source, you can inspect the API contract before committing to migration.

### Does Vexa support Zoom?

Zoom support is available. Google Meet and Microsoft Teams are fully production-ready with the same API interface.

### How does transcription accuracy compare?

Both use state-of-the-art speech-to-text models. Recall.ai uses proprietary models optimized for their per-participant audio streams. Vexa uses Whisper, the industry-standard open-source model supporting 100+ languages. In practice, both achieve high accuracy for English business meetings. Vexa has an edge for multilingual scenarios due to broader language support.

### Is Recall.ai open source?

No. Recall.ai is fully proprietary and closed-source. There is no self-hosted option. All data flows through Recall.ai's cloud infrastructure.

### What if Recall.ai raises prices or changes terms?

With a proprietary API, you're dependent on Recall.ai's pricing decisions. With Vexa, the Apache 2.0 license guarantees you can fork and run the software forever — no vendor can change your terms.
