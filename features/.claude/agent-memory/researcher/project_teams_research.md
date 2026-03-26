---
name: teams_realtime_research_march_2026
description: MS Teams real-time audio architecture, bot detection timeline, competitor approaches, Graph API vs browser automation tradeoffs — researched March 25, 2026
type: project
---

Deep research on MS Teams audio/video implementation completed 2026-03-25.

**Why:** Building Teams meeting bot with Playwright browser automation. Need to understand audio architecture, speaker identification, and upcoming platform changes.

**Key findings to apply:**

1. Teams browser client delivers SINGLE mixed audio stream (unlike GMeet/Zoom which give per-speaker). Speaker separation requires caption-driven routing with ring buffer lookback.

2. Graph Communications API provides per-speaker unmixed audio BUT requires C#/.NET/Windows/Azure — not viable for our Node.js/Playwright stack.

3. **CRITICAL RISK: Bot detection rolling out mid-May 2026.** Third-party bots will be labeled in lobby, organizers must explicitly admit them. Enabled by default for all tenants. Detection "not perfect" per Microsoft.

4. Recall.ai uses same approach (Playwright + caption scraping). They also launched Desktop SDK as hedge against platform restrictions.

5. ACS (Azure Communication Services) does NOT provide raw audio access or caption support for Teams meetings — dead end.

6. teams.live.com (personal) vs teams.microsoft.com (enterprise) use same DOM/client; difference is backend policies only.

7. Classic Teams client ended July 2025 — all users on new WebView2 client. Single DOM target.

8. URL params `?msLaunch=false&suppressPrompt=true` bypass app-launch dialog (Recall.ai technique).

**How to apply:** Bot detection timeline is the #1 strategic risk. When discussing Teams features, flag this. For implementation, caption-driven routing is correct and matches competitor approaches. No need to pivot to Graph API unless we can absorb C#/.NET requirement.
