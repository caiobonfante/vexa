---
name: MS Teams Authenticated Bots Research
description: Consumer MS accounts get locked for bot automation; M365 Business Basic with disabled security defaults is industry standard. Bot detection rolling out May 2026.
type: project
---

MS Teams authenticated bot research completed 2026-03-29.

Key findings:
- Consumer Microsoft accounts (Gmail-linked or Outlook.com) are NOT viable for bot automation -- they get compliance-locked
- Recall.ai and all competitors use M365 Business Basic ($6/mo) with a dedicated tenant
- Must disable Security Defaults in Entra ID to prevent MFA challenges on bot accounts
- Microsoft rolling out third-party bot detection in Teams meetings mid-May 2026 (MC1077547)
- Bot Framework / Graph API not viable: C#/.NET only, Windows Server, requires per-tenant app install
- Our existing S3 browser data sync infrastructure already covers Teams session persistence needs

**Why:** The `dmitryvexabot@gmail.com` account was locked by Microsoft's automated abuse detection (cloud IPs + headless browser + consumer account).

**How to apply:** When implementing MS Teams authenticated bots, set up an M365 Business Basic tenant first. Do not attempt to use consumer accounts. Full research at `conductor/missions/research-msteams-auth.md`.
