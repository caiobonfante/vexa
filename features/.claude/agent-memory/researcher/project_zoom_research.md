---
name: Zoom platform integration research
description: Zoom support approaches (browser web client, native SDK, RTMS), current codebase state, competitor patterns, blockers as of March 2026
type: project
---

Zoom Web (Playwright) path is already fully implemented in `services/vexa-bot/core/src/platforms/zoom/web/` — 8 modules, compiled, infrastructure-routed via ZOOM_WEB=true. Score 0 reflects lack of real meeting testing, not lack of code.

**Why:** Zoom is the #1 gap vs every competitor. Browser approach avoids Marketplace review (4-8 weeks) and OBF token requirements that the native SDK needs since March 2, 2026.

**How to apply:** When Zoom testing begins, start with browser web client — it only needs a real Zoom meeting URL. CAPTCHA on guest join is the biggest risk. RTMS is strategic but requires paid Zoom Developer Pack with unknown pricing. Full research at `features/multi-platform/tests/zoom-research.md`.
