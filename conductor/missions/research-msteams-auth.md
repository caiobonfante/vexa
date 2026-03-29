# Research: MS Teams Authenticated Bots

**Date:** 2026-03-29
**Researcher:** Claude (researcher agent)
**Status:** Complete
**Trigger:** `dmitryvexabot@gmail.com` Microsoft account locked with "violates our Microsoft Services Agreement" message

---

## Table of Contents

1. [Account Lock Root Cause Analysis](#1-account-lock-root-cause-analysis)
2. [Appeal & Unlock Process](#2-appeal--unlock-process)
3. [Account Type Recommendations](#3-account-type-recommendations)
4. [MS Teams Session Architecture](#4-ms-teams-session-architecture)
5. [Anti-Automation Detection Mechanisms](#5-anti-automation-detection-mechanisms)
6. [Competitor Analysis](#6-competitor-analysis)
7. [Bot Framework Alternative](#7-bot-framework-alternative)
8. [Community Solutions](#8-community-solutions)
9. [Critical: Upcoming Microsoft Bot Detection (May 2026)](#9-critical-upcoming-microsoft-bot-detection-may-2026)
10. [Recommendations](#10-recommendations)

---

## 1. Account Lock Root Cause Analysis

### What triggered the lock

The `dmitryvexabot@gmail.com` account is a **personal Microsoft account linked to Gmail**. This is the weakest account type for automation. The lock was almost certainly triggered by a combination of:

**Primary triggers (high confidence):**
- **Datacenter/cloud IP login:** Bot containers run from cloud infrastructure. Microsoft flags logins from known datacenter IPs as suspicious activity. Multiple Q&A threads confirm VPN and datacenter IPs trigger locks ([MS Q&A: VPN usage](https://learn.microsoft.com/en-us/answers/questions/4539763/microsoft-account-being-locked-due-to-vpn-usage)).
- **Automated browser fingerprint:** Even with stealth plugins, the browser's profile (headless flags, `--no-sandbox`, missing GPU, fake media devices) differs from a human user. Microsoft's login flow detects automation signals.
- **Rapid/unusual login patterns:** The bot container restarts create multiple sequential login attempts from the same or different IPs, which Microsoft interprets as account compromise.
- **New device on every container spin-up:** Each container is a "new device" with no device trust history. Frequent new-device logins from cloud IPs are a classic abuse signal.

**MS Services Agreement clauses violated (Section 3.b):**
- "Using bots to create accounts, spoofing or reusing information across multiple accounts"
- "Interfering with Microsoft networks or systems"
- Creating automated access patterns that resemble credential stuffing or account hijacking

**Why a Gmail-linked account is especially vulnerable:**
- Personal Microsoft accounts (consumer) have aggressive automated abuse detection
- Gmail-linked accounts lack the advanced security features available to native `@outlook.com` accounts ([MS Support: Advanced Outlook.com security](https://support.microsoft.com/en-us/office/advanced-outlook-com-security-for-microsoft-365-subscribers-882d2243-eab9-4545-a58a-b36fee4a46e2))
- No admin controls to disable security defaults, MFA requirements, or compliance policies
- No tenant-level configuration possible

### Sources
- [Microsoft account has been locked (official)](https://support.microsoft.com/en-us/account-billing/microsoft-account-has-been-locked-805e8b0d-4141-29b2-7b65-df6ff6c9ce27)
- [VPN triggers account lock](https://learn.microsoft.com/en-us/answers/questions/4529549/unusual-sign-in-activity-alert-because-of-using-vp)
- [Compliance lock Q&A](https://learn.microsoft.com/en-us/answers/questions/4559792/microsoft-account-locked-(compliance-lock))

---

## 2. Appeal & Unlock Process

### Phone verification flow
1. Sign in at `account.microsoft.com`
2. Microsoft shows the lock message with a "Next" button
3. Request a security code via SMS to **any phone number** (does not need to be associated with the account)
4. Enter the code within 10 minutes
5. May need to create a new password

**Success rate:** Moderate. Many users report success on first attempt for simple locks. However:
- If the account has Two-Step Verification (TSV) enabled, **Microsoft support cannot assist** -- TSV takes recovery completely out of customer service's control
- If phone verification doesn't work, the fallback is the **Reinstatement Form** at `aka.ms/compliancelock`
- Reinstatement review takes ~24 hours; Microsoft contacts by email
- Multiple users report being stuck in cycles where the form is rejected and they must resubmit

### Will the account get re-locked?
**Yes, almost certainly.** If the same automation patterns continue (cloud IPs, headless browser, rapid login cycles), Microsoft's systems will re-lock the account. The lock is not a one-time warning -- it is a detection system that will trigger again under the same conditions.

### Recommendation
Unlock the current account for data recovery if needed, but **do not plan to use it for ongoing automation**. The investment in unlocking is wasted if it gets locked again within days.

### Sources
- [How to appeal locked account](https://learn.microsoft.com/en-us/answers/questions/4738300/how-to-appeal-locked-account-when-phone-number-ver)
- [Account locked and support stuck in cycle](https://learn.microsoft.com/en-us/answers/questions/1437330/account-locked-and-microsoft-support-team-stuck-in)
- [Account locked - appeal submitted](https://learn.microsoft.com/en-us/answers/questions/5538599/account-locked-appeal-submitted)

---

## 3. Account Type Recommendations

### Option A: Microsoft 365 Business Basic (RECOMMENDED)

This is what **Recall.ai uses and explicitly recommends** in their documentation.

**Setup:**
1. Purchase Microsoft 365 Business Basic license (~$6/user/month)
2. Create a **separate Microsoft organization** (new tenant) -- do NOT use your real org
3. Create a dedicated bot user within that tenant (e.g., `bot@vexabots.onmicrosoft.com`)
4. In Microsoft Entra ID, configure:
   - **Disable Security Defaults** (Overview > Properties > Manage Security Defaults > Disabled)
   - **Disable "Show keep users signed in"** toggle (Users > User Settings)
   - **Disable Self-Service Password Reset** (Password reset > Properties > "None")
5. Store email + password for the bot account

**Advantages:**
- Full admin control over security policies (disable MFA, security defaults)
- No automated compliance locks (you control the tenant)
- Bot appears as "(External)" rather than "(Guest)" in meetings -- more legitimate
- Stable across container restarts -- session management is predictable
- Account won't get locked because you control the tenant's security policies
- This is the industry-standard approach (Recall.ai, MeetStream)

**Disadvantages:**
- Monthly cost per bot account (~$6/month)
- Initial setup complexity (tenant creation, Entra ID configuration)
- Bot name is fixed to the account display name (cannot override via `bot_name` parameter)
- Multiple bots in same meeting require separate accounts (Teams merges same-email participants)

### Option B: Native Outlook.com personal account

**Setup:** Create `vexabot@outlook.com` (or similar)

**Advantages over Gmail-linked:**
- Advanced security features available for `@outlook.com` accounts
- Less likely to trigger "linked to external provider" detection
- Can add phone number for 2FA

**Disadvantages:**
- Still a personal consumer account with automated abuse detection
- No admin controls to disable security defaults
- Will eventually get locked under the same automation patterns
- Not a long-term solution

### Option C: Keep Gmail-linked (NOT RECOMMENDED)

The current approach. Will keep getting locked. Dead end.

### Verdict

**Option A (M365 Business Basic) is the only production-viable path.** It costs ~$6/month and gives you full control over security policies, preventing the account lock entirely. This is exactly what Recall.ai uses, and they documented the setup publicly.

### Sources
- [Recall.ai: Setting up Signed-in Bots for Microsoft Teams](https://docs.recall.ai/docs/setting-up-signed-in-bots-for-microsoft-teams)
- [Recall.ai: Signed-in Teams Bots Overview](https://docs.recall.ai/docs/signed-in-teams-bots-overview)

---

## 4. MS Teams Session Architecture

### How Teams handles browser-based authentication

Teams web client (`teams.microsoft.com` / `teams.live.com`) uses a combination of:

**Cookies (critical for session persistence):**
- `skypetoken_asm` -- Authentication token for Skype/Teams services
- `platformid_asm` -- Platform identification credential
- `authtoken` -- Primary Teams authentication token
- `SSOAUTHCOOKIE` -- Single sign-on cookie
- Standard Azure AD / Entra ID session cookies

**Local Storage / Session Storage:**
- Teams stores access tokens in localStorage (built on Electron/Chromium)
- These tokens bypass MFA and conditional access (they represent already-authenticated sessions)
- Tokens are stored in `Default/Local Storage/leveldb` in the Chromium user data directory

**What our S3 sync already preserves (from `s3-sync.ts`):**
Our existing `AUTH_ESSENTIAL_FILES` list already covers the critical files:
- `Default/Cookies` + journal
- `Default/Login Data` + journal
- `Default/Local Storage` (entire directory, synced)
- `Default/Session Storage` (entire directory, synced)
- `Default/Network Persistent State`
- `Default/Preferences` and `Secure Preferences`
- `Local State`

**Gap analysis:** Our S3 sync infrastructure is **already designed to handle Teams sessions**. The `syncBrowserDataToS3` / `syncBrowserDataFromS3` functions upload and download the exact files needed. The architecture that works for Google Meet authenticated bots should work for Teams with minimal changes. The main difference:

| Aspect | Google Meet | MS Teams |
|--------|-------------|----------|
| Login domain | `accounts.google.com` | `login.microsoftonline.com` |
| Session cookies | Google SSID, HSID, SID | skypetoken_asm, SSOAUTHCOOKIE |
| Token storage | Cookies only | Cookies + Local Storage + leveldb |
| Session duration | Days to weeks | Hours to days (shorter-lived) |
| MFA handling | App-based TOTP | Configurable (can be disabled with M365 Business) |
| Bot detection | Yes (but manageable) | Yes (getting stronger, see Section 9) |

### Key technical consideration
Teams tokens are **shorter-lived** than Google session cookies. The M365 Business setup with disabled security defaults addresses this by preventing token refresh challenges. Without that, the bot would need to re-authenticate frequently, which is what triggers account locks.

### Sources
- [MS Teams stores auth tokens as cleartext](https://www.bleepingcomputer.com/news/security/microsoft-teams-stores-auth-tokens-as-cleartext-in-windows-linux-macs/)
- [Teams session hijacking and bypass](https://www.pentestpartners.com/security-blog/you-cant-stop-me-ms-teams-session-hijacking-and-bypass/)

---

## 5. Anti-Automation Detection Mechanisms

### Microsoft login (`login.microsoftonline.com`)

1. **Device fingerprinting:** Browser environment analysis (canvas, WebGL, audio context, screen resolution, installed fonts). Headless/containerized browsers have distinct fingerprints.
2. **CDP detection:** Microsoft can detect Chrome DevTools Protocol connections, which Playwright uses for browser control. This is a growing detection vector.
3. **Behavioral analysis:** Mouse movement patterns, typing cadence, click timing. Automated clicks are instantaneous and lack human variance.
4. **IP reputation:** Cloud/datacenter IPs have lower trust scores. AWS, GCP, Azure IP ranges are well-known.
5. **Device trust:** New devices require additional verification. Each container is a new device unless persistent browser data is maintained.
6. **Risk-based authentication:** Combines all signals into a risk score. High risk triggers additional challenges (MFA, CAPTCHA, account lock).

### Teams meeting join (`teams.microsoft.com`)

1. **CAPTCHA verification:** Anonymous users currently face CAPTCHA when joining meetings. This is being **retired in August 2026** in favor of bot detection.
2. **Third-party bot detection (NEW, May 2026):** See Section 9 -- this is a major upcoming change.
3. **User-Agent analysis:** Recall.ai locks User-Agent to a specific build to maintain DOM consistency. Our codebase already does this (`constans.ts` line 2).
4. **WebRTC fingerprinting:** How the browser negotiates media can reveal automation.

### What helps evade detection

- `--disable-blink-features=AutomationControlled` (already in our `getAuthenticatedBrowserArgs()`)
- `--password-store=basic` (already in our args)
- `ignoreDefaultArgs: ['--enable-automation']` (already in our code)
- `puppeteer-extra-plugin-stealth` (already imported in `index.ts`)
- Persistent browser context with real user data (our S3 sync handles this)
- Using MS Edge channel for Teams (already in our code: `channel: 'msedge'`)

### What our codebase already does well
Looking at `constans.ts` and `index.ts`, the authenticated bot path already uses:
- Minimal, clean browser flags (not the aggressive `--disable-web-security`)
- StealthPlugin from puppeteer-extra
- Persistent context with S3-synced browser data
- `ignoreDefaultArgs: ['--enable-automation']`

The missing piece is not in the browser flags -- it is in the **account type** (consumer vs. business).

### Sources
- [From Puppeteer stealth to Nodriver: anti-detect evolution](https://blog.castle.io/from-puppeteer-stealth-to-nodriver-how-anti-detect-frameworks-evolved-to-evade-bot-detection/)
- [Avoiding bot detection with Playwright Stealth](https://brightdata.com/blog/how-tos/avoid-bot-detection-with-playwright-stealth)

---

## 6. Competitor Analysis

### Recall.ai

**Approach:** Browser automation (Playwright + Chromium) for both anonymous and signed-in modes.

- **Anonymous mode:** Bot joins as guest, enters name, clicks "Join now". No authentication needed. Works for `teams.live.com` personal meetings.
- **Signed-in mode:** Uses Microsoft 365 Business Basic accounts with disabled security defaults. Bot authenticates with email/password, then joins. Required for enterprise meetings that block anonymous guests.
- **Session management:** Credentials stored in their dashboard. They handle login flow automatically.
- **Key limitation:** Signed-in bot name comes from the Microsoft account, overriding `bot_name`. Multiple bots in same meeting need separate M365 accounts.
- **Open-source reference:** [recallai/microsoft-teams-meeting-bot](https://github.com/recallai/microsoft-teams-meeting-bot) -- caption-scraping approach with Playwright/Puppeteer.

### Meeting BaaS (Meeting-Baas)

**Approach:** Open-source, Playwright-based.

- [meet-teams-bot](https://github.com/Meeting-Baas/meet-teams-bot) -- joins Teams meetings, streams audio.
- **Limitation explicitly documented:** "Meetings that require users to sign in to the platform before joining are not supported."
- Uses Docker containers with real Ubuntu + Google Chrome (not headless Chromium) for better compatibility.

### ScreenApp.ai

**Approach:** Open-source Playwright bot.

- [screenappai/meeting-bot](https://github.com/screenappai/meeting-bot) -- universal bot for Meet, Teams, Zoom.
- TypeScript + Playwright.
- One job at a time, automatic retry on failures.
- No authenticated/signed-in mode documented.

### Fireflies.ai

**Approach:** Joins as guest, requires host org to enable "guest access" in Teams Admin Center.

- No browser-based authentication -- relies on guest access being enabled.
- Users authorize Fireflies via OAuth, but the bot itself joins as anonymous.

### Otter.ai

**Approach:** Joins meetings via calendar integration + meeting links.

- Primarily anonymous join.
- Advanced "Meeting Agent" (2025) can answer questions in meetings.
- No public documentation on authenticated join approach.

### MeetStream.ai

**Approach:** SOC 2 certified API. Likely browser automation under the hood.

- Enterprise-focused, no public technical details on authentication approach.

### Key insight from competitor analysis

**All competitors that support authenticated Teams join use M365 Business accounts with disabled security defaults.** No one is successfully using personal Microsoft accounts for this purpose. The industry consensus is clear: consumer accounts are a dead end for bot automation.

### Sources
- [Recall.ai blog: How to build a MS Teams Bot](https://www.recall.ai/blog/how-to-build-a-microsoft-teams-bot)
- [Recall.ai open-source Teams bot](https://github.com/recallai/microsoft-teams-meeting-bot)
- [Meeting BaaS Teams bot](https://github.com/Meeting-Baas/meet-teams-bot)
- [ScreenApp meeting bot](https://github.com/screenappai/meeting-bot)
- [Fireflies Teams integration](https://guide.fireflies.ai/articles/8966445661-how-to-set-up-fireflies-microsoft-teams-integration)

---

## 7. Bot Framework Alternative

### Microsoft Bot Framework + Graph API

**What it is:** Microsoft's official SDK for building Teams bots. Uses Graph API `POST /communications/calls` to join meetings programmatically.

**Capabilities:**
- Programmatic meeting join via API (no browser automation)
- Real-time media access (audio/video frames)
- Official, supported approach -- no DOM scraping fragility

**Severe limitations:**
1. **C#/.NET only:** Real-time media SDK only exists for `Microsoft.Graph.Communications.Calls.Media` (.NET). No Python, Node.js, or TypeScript SDK for real-time audio.
2. **Windows Server required:** Application-hosted media bots must run on Windows Server (on-premises or Azure). Cannot run in Linux containers.
3. **Tenant installation required:** The bot app must be installed on the **host tenant** that created the meeting. This means every customer org needs to install your app. This is a deal-breaker for a "join any meeting" product.
4. **Complex Azure setup:** Requires Azure Bot Service registration, Azure Communication Services, Graph API permissions (`Calls.AccessMedia.All`), specific port ranges opened.
5. **No cross-org support without tenant install:** This is why Recall.ai and others use browser automation instead.

**Alternative: Graph Meeting Transcripts API**
- Can fetch transcripts **after** a meeting ends (not real-time)
- Does not require real-time media SDK
- Works from any language
- But: only works for meetings where transcription was enabled, and it is post-meeting only

### Verdict

The Bot Framework is **not viable for our use case**. The requirement for per-tenant installation, Windows-only runtime, and C#-only SDK make it incompatible with our architecture (Linux containers, TypeScript, cross-org meeting join). Browser automation is the correct approach for a "join any meeting" product.

### Sources
- [Graph Communications Bot Media SDK](https://microsoftgraph.github.io/microsoft-graph-comms-samples/docs/bot_media/index.html)
- [Bot joining Teams meetings and receiving real-time audio](https://learn.microsoft.com/en-au/answers/questions/5807336/bot-joining-teams-meetings-and-receiving-real-time)
- [Recall.ai blog on Graph API limitations](https://www.recall.ai/blog/how-to-build-a-microsoft-teams-bot)

---

## 8. Community Solutions

### GitHub issues and discussions

**Playwright + Microsoft login:**
- [Playwright issue #5053: Automate SSO Login Prompt](https://github.com/microsoft/playwright/issues/5053) -- discussion about handling Microsoft SSO popups
- [Playwright issue #7096: User Authentication](https://github.com/microsoft/playwright/issues/7096) -- authentication state persistence
- [Elio Struyf: Automating M365 login with MFA in Playwright](https://www.eliostruyf.com/automating-microsoft-365-login-mfa-playwright-tests/) -- TOTP-based MFA automation using `OTPAuth` library
- [Hoop.dev: Configure Entra ID Playwright for secure access](https://hoop.dev/blog/how-to-configure-microsoft-entra-id-playwright-for-secure-repeatable-access/)

**Key pattern from community:**
The working approach for Entra ID / M365 authentication with Playwright:
1. Use persistent browser context (we already do this)
2. Disable MFA/security defaults at tenant level (requires M365 Business)
3. If MFA is required, use TOTP with a shared secret (automatable with `OTPAuth` library)
4. Save and restore `storageState` between sessions (our S3 sync covers this)
5. Avoid aggressive browser flags that trigger detection

**Account lock discussions:**
- No specific GitHub issues found about Playwright causing Microsoft account compliance locks
- Multiple Microsoft Q&A threads confirm this is a consumer account issue, not a Playwright issue
- The lock is triggered by Microsoft's abuse detection systems, not by Playwright-specific detection

### Stack Overflow patterns

The consensus on SO is:
- Consumer accounts + automation = locked accounts (inevitable)
- M365/Azure AD accounts with disabled security defaults = stable long-term
- Persistent browser profiles reduce re-authentication frequency

---

## 9. Critical: Upcoming Microsoft Bot Detection (May 2026)

### MC1077547: Third-party bot detection in Teams meetings

**This is the most important finding in this research.**

Microsoft is rolling out automatic detection and labeling of third-party bots in Teams meetings:

- **Targeted release:** Mid-May 2026
- **General availability:** Early June 2026, complete by mid-June
- **GCC:** Same schedule

**How it works:**
1. When a participant attempts to join a Teams meeting, Microsoft's systems analyze whether it is a third-party bot
2. Detected bots are **labeled distinctly in the lobby** (visual indicator that it is a bot, not a human)
3. Meeting organizers must **explicitly and individually admit** each detected bot
4. Bots cannot be accepted as part of a bulk "admit all" action
5. No admin configuration required -- this is enabled automatically for all tenants

**Detection accuracy:**
Microsoft acknowledges the detection "might not pick up every third-party recording bot" but expects accuracy to improve through customer reports and research.

**Impact on us:**
- Our bots (both anonymous and authenticated) will likely be detected and labeled
- The feature targets "external 3P bots" -- meaning bots not managed by the host organization
- Even authenticated bots from a separate M365 tenant will appear as "(External)" and may be flagged
- Meeting organizers will have explicit visibility that a bot is joining
- This does NOT block bots -- it gives organizers the choice to admit or reject them

**Impact on the industry:**
- This affects ALL browser-based meeting bot companies (Recall.ai, Fireflies, Otter, MeetStream, etc.)
- Companies will need to adapt their UX to handle explicit bot admission by organizers
- The "stealth" approach of bots blending in with human participants is ending

**Additional context:**
- Microsoft is also **retiring CAPTCHAs** for meeting joins in August 2026, replacing them with the bot detector
- A new Teams meeting policy will allow admins to control bot detection behavior
- Microsoft specifically called out that external bots "may access meetings without the knowledge or consent" of organizers

### What this means for our authenticated bot feature

1. **Account type matters more now:** An authenticated M365 Business bot that joins as "(External)" is more trustworthy to organizers than an anonymous guest. Being labeled as a known external participant is better than being labeled as an unknown bot.
2. **Bot transparency is the future:** Organizers will see bots. Our UI/UX should make it easy for users to tell meeting organizers to expect the bot.
3. **Detection is behavioral, not just authentication-based:** The article doesn't distinguish between anonymous and authenticated bots. Both types may be detected.

### Sources
- [Office365 IT Pros: Teams Meetings to Block Third-Party Recording Bots](https://office365itpros.com/2026/03/16/third-party-recording-bots/)
- [BleepingComputer: Microsoft Teams will tag third-party bots](https://www.bleepingcomputer.com/news/microsoft/microsoft-teams-will-tag-third-party-bots-in-meeting-lobbies/)
- [Help Net Security: Microsoft working on Teams feature to keep unauthorized bots at bay](https://www.helpnetsecurity.com/2026/03/06/microsoft-teams-third-party-bot-identification/)
- [MS Tech Community: Teams Meetings to Block Third-Party Recording Bots](https://techcommunity.microsoft.com/discussions/microsoftteams/teams-meetings-to-block-third-party-recording-bots/4502502)
- [AdminDroid: How to Block AI Assistants in Microsoft Teams Meetings](https://blog.admindroid.com/how-to-block-ai-assistants-in-microsoft-teams-meetings/)

---

## 10. Recommendations

### Immediate actions (this week)

1. **Unlock the current account** via phone verification at `account.microsoft.com` for any data recovery needed. Do not plan to reuse it for automation.

2. **Set up an M365 Business Basic tenant** (~$6/month):
   - Create new tenant (e.g., `vexabots.onmicrosoft.com`)
   - Create bot user (e.g., `bot@vexabots.onmicrosoft.com`)
   - Disable Security Defaults in Entra ID
   - Disable "Show keep users signed in" toggle
   - Disable Self-Service Password Reset
   - Document the setup process for reproducibility

3. **Use browser session mode** to log into the new M365 account:
   - Spin up a browser session container
   - Navigate to `login.microsoftonline.com`, log in as the bot user
   - Save browser data to S3 via existing `save_storage` command
   - Test that the session persists across container restarts

### Implementation changes for authenticated Teams join

4. **Minimal code changes needed.** The existing authenticated bot path in `index.ts` (lines 2061-2102) already:
   - Downloads browser data from S3
   - Launches persistent context with clean flags
   - Applies stealth plugin

   The gap is that this path is only triggered when `botConfig.authenticated && botConfig.userdataS3Path` is set, and it is currently only tested with Google Meet. For Teams, the code should:
   - Use the authenticated persistent context path (currently only the non-authenticated Teams path launches with `channel: 'msedge'`)
   - Consider whether MS Edge channel is needed for authenticated mode (persistent context may not support `channel` parameter -- needs testing)
   - Ensure the Teams join flow (`joinMicrosoftTeams()`) works with the authenticated context

5. **Important behavioral difference for authenticated Teams:**
   - Bot will show the M365 account's display name, NOT the `botConfig.botName`
   - Bot will appear as "(External)" instead of anonymous guest
   - Bot may bypass lobby for some meeting configurations (if external access is trusted)
   - The `teamsNameInputSelectors` step in `join.ts` (Step 4) may not appear for authenticated users

### Architecture considerations

6. **Session refresh strategy:** M365 sessions expire. The bot should:
   - Always sync browser data back to S3 after a meeting (already done in graceful leave)
   - Consider a periodic session refresh (e.g., browser session container logs in weekly)
   - Monitor for auth failures and trigger re-authentication

7. **Multiple bot accounts:** If running concurrent bots in the same meeting, each needs a separate M365 account. Plan for scaling the account pool.

8. **Bot detection preparation (for May 2026):**
   - Accept that bots will be labeled in lobbies
   - Ensure the bot's display name clearly identifies it (e.g., "Vexa Bot (Recording)")
   - Update user-facing docs to tell meeting organizers to expect and admit the bot
   - Test the bot detection behavior as soon as targeted release is available

### Cost analysis

| Item | Monthly Cost | Notes |
|------|-------------|-------|
| M365 Business Basic (1 bot account) | ~$6 | Minimum for production |
| M365 Business Basic (5 bot accounts) | ~$30 | For concurrent meeting support |
| S3 storage for browser data | ~$0.01 | Negligible |
| Current approach (consumer account) | $0 | But broken -- account locked |

### Risk matrix

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| M365 account lock | Low | High | Admin controls prevent automated locks |
| Bot detected by May 2026 feature | High | Medium | Transparent naming, user education |
| Teams DOM changes break selectors | Medium | High | Monitor Teams web client updates, maintain selector fallbacks |
| Session token expiry | Medium | Medium | Periodic refresh, re-auth pipeline |
| Multiple bots same meeting conflict | Low | Low | Separate accounts per concurrent bot |

---

## Dead Ends Confirmed

1. **Consumer Microsoft accounts (Gmail-linked or Outlook.com) for automation** -- will get locked. Industry consensus.
2. **Microsoft Bot Framework for cross-org meeting join** -- requires per-tenant app installation. Not viable.
3. **Graph API for real-time audio** -- C#/.NET only, Windows Server only. Not viable.
4. **Bypassing Microsoft's login detection long-term** -- detection is improving continuously. The correct path is a managed M365 tenant with disabled security defaults, not better evasion.

---

## External References for Feature Log

```
[EXTERNAL] MS account lock root cause: consumer accounts + cloud IP + headless browser = compliance lock.
           Gmail-linked accounts especially vulnerable. M365 Business Basic is industry standard.
           Source: Multiple MS Q&A threads, Recall.ai docs.

[EXTERNAL] Recall.ai signed-in Teams bots: M365 Business Basic, disable security defaults in Entra ID.
           Bot name fixed to account display name. One account per concurrent bot.
           Source: docs.recall.ai/docs/setting-up-signed-in-bots-for-microsoft-teams

[EXTERNAL] MS Teams third-party bot detection: rolling out mid-May 2026.
           Bots labeled in lobby, organizers must explicitly admit. Industry-wide impact.
           Source: office365itpros.com/2026/03/16/third-party-recording-bots/

[EXTERNAL] MS Bot Framework not viable for cross-org join: requires per-tenant app install,
           C#/.NET only for real-time media, Windows Server required.
           Source: learn.microsoft.com Graph Communications SDK docs

[EXTERNAL] Open-source Teams bots (Recall.ai, Meeting BaaS, ScreenApp): all use Playwright/Puppeteer
           browser automation. None support authenticated join on consumer accounts.
           Source: github.com/recallai/microsoft-teams-meeting-bot, github.com/Meeting-Baas/meet-teams-bot
```
