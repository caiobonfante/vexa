# Mission: Authenticated Bots

## Goal
Bots join meetings authenticated via stored user credentials (browser sessions saved to S3), bypassing the guest "enter name + ask to join" flow. Two platforms: Google Meet (working) and MS Teams (blocked).

---

## Subfeature 1: Google Meet Authenticated Join ✅

**Status:** Implemented and validated.

Bots join Google Meet as a signed-in Google user, skipping guest flow. Uses browser session saved to S3.

### DoD (met)
1. API wires `authenticated` to bot_config — `POST /bots` with `authenticated=true` passes credentials through to bot container
2. Google Meet join handles authenticated session — bot skips "enter name + Ask to join" guest flow
3. Live E2E on hosted Google Meet — bot joins without manual admission, appears as authenticated user, transcription flows

### Key files
- `services/meeting-api/meeting_api/meetings.py` — bot_config construction
- `services/meeting-api/meeting_api/schemas.py` — BotRequest schema
- `services/vexa-bot/core/src/platforms/googlemeet/join.ts` — Google Meet join flow
- `services/vexa-bot/core/src/s3-sync.ts` — S3 browser data sync

---

## Subfeature 2: MS Teams Authenticated Join 🔴

**Status:** Blocked — Microsoft account locked.

### The Problem

The bot account `dmitryvexabot@gmail.com` has been locked by Microsoft:

> "Your account has been locked. We've detected some activity that violates our Microsoft Services Agreement and have locked your account."

Microsoft offers a phone verification appeal flow. Until the account is unlocked (or a new account is created), Teams authenticated join cannot be developed or tested.

### Questions to Research
1. **What triggers Microsoft account locks for bot/automation accounts?** Is this recoverable or will it keep happening?
2. **What's the appeal process?** Phone verification → what's the success rate? How long does it take?
3. **Alternative approaches:** Can we use a Microsoft 365 org account instead of a personal Gmail-linked account? Would that be more stable for automation?
4. **MS Teams bot authentication architecture:** How does Teams handle authenticated joins differently from Google Meet? What browser session data needs to be preserved?
5. **Known issues with Puppeteer/Playwright + Teams:** Are there specific anti-automation measures Teams employs that trigger account locks?

### DoD (not started)
1. Bot account unlocked or replacement account provisioned
2. Browser session for Teams saved to S3 (same flow as Google Meet)
3. Bot joins Teams meeting as authenticated user, skips lobby/guest flow
4. Live E2E on hosted Teams meeting — bot joins without manual admission

### Key files (anticipated)
- `services/vexa-bot/core/src/platforms/msteams/join.ts` — Teams join flow (needs authenticated path)
- `services/vexa-bot/core/src/s3-sync.ts` — S3 browser data sync (shared)

---

## Out of scope
- Zoom authenticated join
- Credential setup workflow (browser_session mode already handles this)
- Token refresh / credential expiry
