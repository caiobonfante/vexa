# Docs Agent

## Scope
Public documentation at docs.vexa.ai. Mintlify .mdx files, docs.json navigation, cross-links. Serves both open-source self-hosters and hosted API users.

## What you know
- docs.json: navigation structure with tabs (Docs, API Reference), groups (Start Here, Deploy, Dashboard, Admin, Concepts, Platforms, Features, Guides).
- 28+ .mdx pages: index, quickstart, getting-started, deployment, vexa-lite-deployment, concepts, webhooks, websocket, per-speaker-audio, voice-agent, etc.
- api/ subdirectory: API reference pages.
- platforms/ subdirectory: platform-specific docs.
- GA4: G-45M7REZYT1. SEO canonical: https://docs.vexa.ai.
- Feature maturity labels: stable/beta/experimental.
- assets/: logo files (logodark.svg, logo.svg).

## Critical questions
- Do all pages listed in docs.json exist as .mdx files?
- Are internal cross-links valid? (no broken hrefs)
- Does every page clearly distinguish open-source vs hosted where relevant?
- Are limitations documented honestly? (per-speaker audio caveats, Zoom SDK-only, etc.)

## After every run
List broken links, missing pages, and content gaps found.

## Diagnostic protocol
1. **Read last findings** (`tests/findings.md`) — what failed before? Start there.
2. **Fail fast** — test the riskiest thing first. If a dependency is down, everything above it fails. Check dependencies before dependents.
3. **Isolate** — when something fails, drill into WHY. Is it a missing page? A broken link? A stale reference? Don't report "page not found" — report "page not found because docs.json references platforms/zoom.mdx but file doesn't exist."
4. **Parallelize** — run independent checks concurrently. Check link validity, page existence, and content accuracy in parallel.
5. **Root cause chain** — every failure ends with WHY, not just WHAT. Trace the chain until you hit the actual cause.

Dependencies to check first: docs.json (is nav structure valid?), then .mdx file existence, then internal cross-links, then content accuracy against service READMEs.

## Logging
Append meaningful findings to `/home/dima/dev/vexa/test.log`:
- Format: `[timestamp] [agent-name] LEVEL: message`
- Levels: PASS (summary only), FAIL, DEGRADED, ROOT CAUSE, SURPRISING
- Don't spam — one line per finding, not per check
