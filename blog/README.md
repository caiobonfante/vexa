# Blog

Open-source blog articles for [vexa.ai/blog](https://vexa.ai/blog). Published from this repo — what you see here is what's on the website.

## Rules

1. **Articles point to features, not duplicate them.** The source of truth for any capability is `features/{name}/README.md`. Blog articles link there for details.
2. **Keep articles honest.** If a feature's confidence is 0, don't write "battle-tested." Reference the actual status from the feature README.
3. **SEO matters.** Every article targets specific keywords. Keep them in the title, first paragraph, and H2 headers.
4. **Frontmatter required.** Every article needs: title, date, author, slug, summary.

## Article index

### Existing (published on vexa.ai)

| Article | SEO Target | Feature |
|---------|-----------|---------|
| [Vexa vs Recall.ai comparison](vexa-vs-recall-ai-open-source-meeting-bot-api-comparison.md) | "recall.ai alternative open source" | multi-platform, realtime-transcription |
| [Build a meeting bot with Python](how-to-build-a-meeting-bot-with-python.md) | "meeting bot python" | realtime-transcription, multi-platform |
| [Self-hosted meeting transcription setup](how-to-set-up-self-hosted-meeting-transcription-5-minutes.md) | "self-hosted meeting transcription" | realtime-transcription |
| [Open-source transcription API guide](open-source-transcription-api-complete-guide.md) | "open source transcription API" | realtime-transcription |
| [Privacy-first meeting transcription](privacy-first-meeting-transcription-why-self-hosted-matters.md) | "privacy meeting transcription self-hosted" | realtime-transcription |
| [Vexa MCP for Claude + Google Meet](seo_article_tutorial_vexa_mcp_for_claude_real_time_google_meet_transcripts.md) | "MCP server meetings Claude" | mcp-integration |
| [n8n workflow integration](n8n.md) | "meeting transcription n8n" | webhooks |
| [Open-source meeting dashboard](open-source-meeting-dashboard-clone-run-vibe-code.md) | "open source meeting dashboard" | realtime-transcription |
| [Microsoft Teams support (v0.6)](vexa-v0-6-microsoft-teams-support.md) | "Microsoft Teams transcription API" | multi-platform |

### New (covering agent runtime narratives)

| Article | SEO Target | Feature |
|---------|-----------|---------|
| [Zero-cost meeting agents](zero-cost-meeting-agents-ephemeral-containers.md) | "meeting agent runtime", "ephemeral containers" | agentic-runtime |
| [Meetings that build your knowledge](meetings-that-build-your-knowledge-workspace.md) | "AI meeting knowledge management" | knowledge-workspace |
| [Proactive meeting agents](proactive-meeting-agents-scheduled-standup-automation.md) | "proactive AI meeting agent", "scheduled meeting automation" | scheduler, calendar-integration |
| [OpenClaw vs Vexa](openclaw-vs-vexa-multi-tenant-agent-platform.md) | "OpenClaw alternative multi-user" | agentic-runtime, token-scoping |
| [Open-source speaking bot API](open-source-speaking-bot-api-recall-alternative.md) | "meeting bot speak API open source" | speaking-bot |
| [Post-meeting automation pipeline](post-meeting-automation-pipeline-agent-summarize-slack.md) | "post-meeting automation API" | webhooks, scheduler, agentic-runtime |
| [Authenticated browser sessions for bots](authenticated-browser-sessions-meeting-bots.md) | "authenticated meeting bot persistent browser" | remote-browser |

## For agents updating articles

When you update a feature, check if a blog article references it. If the article claims something that's no longer true (API changed, feature renamed, confidence changed), update the article or flag it.

Articles should be thin wrappers around feature READMEs — narrative + code examples + links to the feature for details.
