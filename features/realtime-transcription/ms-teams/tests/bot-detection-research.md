# Microsoft Teams Bot Detection Research

Date: 2026-03-25
Researcher: bot-detect-researcher
M365 Roadmap ID: 558107
Message Center: MC1251206

---

## 1. What Is Being Detected?

Microsoft's announcement targets **"external third-party meeting assistant bots"** — specifically bots that join meetings to record, transcribe, and summarize. The feature does NOT distinguish between:

- Browser-based bots (Playwright/Puppeteer joining via web client)
- Graph API bots (application-hosted media bots)
- ACS-based bots (Azure Communication Services)

All are described as "third-party recording bots." However, the detection mechanism analyzes **"meeting join metadata"** — this strongly implies it targets the JOIN pathway rather than in-meeting behavior. Browser-based bots (like ours) join as anonymous/unverified external participants, which is the primary detection surface.

**Key quote:** "This change introduces detection logic that analyzes meeting join metadata to identify external automated bots attempting to join meetings." — MC1251206

**Graph API bots** are registered Azure AD applications with explicit Teams permissions. These are "first-party" from Microsoft's perspective (registered in Azure AD, using official SDK). It is unclear whether they are treated differently, but the language consistently says "external third-party" which could exclude registered Graph bots.

---

## 2. Detection Signals (What We Know and Don't Know)

### Confirmed
- Detection occurs **at the lobby stage**, before meeting entry
- Analyzes **"meeting join metadata"** — not in-meeting behavior
- Detected bots are labeled **"Unverified"** trust indicator
- Appear in a **"Suspected threats"** section in the lobby UI
- Selecting a flagged bot opens a **pop-up showing details and available actions**

### Likely Signals (Inferred)
- **Anonymous join pattern**: No signed-in Microsoft account, or account from untrusted domain
- **User-Agent / client fingerprint**: Headless Chrome, Playwright-controlled browser markers (`navigator.webdriver = true`, `HeadlessChrome` in UA)
- **Join behavior patterns**: Immediate join without pre-join screen interaction, lack of camera/mic negotiation typical of human users
- **IP reputation**: Known datacenter/cloud IPs vs residential IPs (Skribby uses IP rotation as countermeasure, suggesting IP is a signal)
- **Participant metadata**: Display name patterns common to bots ("Otter.ai Notetaker", "Fireflies.ai Notetaker")
- **CAPTCHA completion**: Existing CAPTCHA feature (`-CaptchaVerificationForMeetingJoin`) already targets anonymous web joiners

### Unknown
- Exact heuristics are **not publicly documented**
- Whether WebRTC fingerprinting is used (codec preferences, ICE candidate patterns)
- Whether JavaScript API probing occurs (canvas fingerprint, WebGL, font enumeration)
- Whether timing analysis is used (how fast join flow completes)
- Whether the detection runs client-side (in Teams JS) or server-side (at SFU/lobby service)

### Microsoft's Own Assessment
> "Bot detection is not perfect and might not pick up every third-party recording bot."
> "Over time, customer reports and their own research will allow the detection algorithm to become more accurate."

This implies an evolving ML/heuristic system that will get stricter over time.

---

## 3. Lobby-Level Label vs Hard Block

**Current design (May 2026): Label + require explicit admit. NOT a hard block.**

Behavior:
1. Bot attempts to join meeting → enters lobby
2. Teams detection runs on join metadata
3. If detected: bot is labeled in **"Suspected threats"** section with **"Unverified"** badge
4. Organizer sees the bot **separately from regular attendees** (cannot be accidentally batch-admitted)
5. Organizer must **explicitly and individually approve** the bot
6. Organizer can also deny or remove the bot

**This is NOT an outright block.** The organizer retains full control. If the organizer wants the bot in the meeting, they can admit it. The friction is:
- Bot is no longer invisible among human attendees
- Cannot be batch-admitted ("Admit all")
- Organizer must take deliberate action

### Future Trajectory
Microsoft says they plan **"more granular controls in the future"** — this likely means:
- Option to auto-block all detected bots (no organizer choice)
- Allowlist/blocklist for specific bot providers
- Potentially harder detection that prevents lobby entry entirely

---

## 4. Admin Policy Settings

### New Bot Detection Policy
- **Policy location:** Teams admin center → Meetings → Meeting Policies
- **Default:** Enabled for all tenants (requires organizer approval for detected bots)
- **Options (expected):**
  - Do not detect bots (disable detection)
  - Require approval (default — organizer must explicitly admit)
- **PowerShell cmdlet:** Not yet published (policy not yet in admin center as of March 2026)
- **Scope:** Per-organizer (applies to meetings created by users with this policy)

### Existing CAPTCHA Policy (Complementary)
- **PowerShell:** `Set-CsTeamsMeetingPolicy -Identity <policy> -CaptchaVerificationForMeetingJoin AnonymousUsersAndUntrustedOrganizations`
- **Default:** NotRequired
- **Effect:** Requires CAPTCHA (text or audio) for anonymous/unverified joiners
- **Bypass:** Add bot's email domain to trusted external domains list
- **Note:** CAPTCHA is a separate, already-available feature — not part of the new bot detection

### Recall.ai's Recommended Workaround for CAPTCHA
Add the bot's email domain to the tenant's trusted external domains:
1. Teams admin center → Users → External Access
2. Set "Teams and Skype for Business users in external organizations" → "Allow only specific external domains"
3. Add the bot's email domain (e.g., `vexa.ai`)

This makes the bot a "trusted external" rather than "anonymous/unverified" — bypasses CAPTCHA. **May or may not bypass the new bot detection** (unknown — the new detection may have different criteria than the CAPTCHA check).

---

## 5. Personal Teams (teams.live.com) vs Enterprise

**No sources differentiate personal vs enterprise treatment.**

What we know:
- Bot detection is described as a **tenant-level admin policy**
- Personal Teams (teams.live.com) has **limited admin controls** — no IT admin center
- The announcement mentions rollout for "all tenants" including GCC
- Personal meetings may not have the same policy granularity

**Likely scenario:**
- Enterprise tenants: full admin control (enable/disable/customize)
- Personal Teams: either always-on with limited controls, or not applied (since there's no admin to manage it)
- Personal Teams already has limited bot protection (no CAPTCHA, simpler lobby)

**Strategic implication:** Personal Teams meetings may remain easier for bots to join, at least initially. This could be a temporary advantage for our use case.

---

## 6. Competitor Responses

### Recall.ai — Desktop Recording SDK (Hedge Strategy)
- Launched **Desktop Recording SDK** as alternative to browser bots
- Captures audio, video, transcripts **on-device** (Mac + Windows)
- No bot joins the meeting — completely invisible to detection
- Requires user to install a desktop app (friction vs. zero-install bot)
- Works across Zoom, Google Meet, Teams, Slack Huddles
- "10 lines of code" integration claim
- **Clear response to anticipated platform restrictions**
- Also maintains browser bot product (not abandoning it)

### Skribby — Auto-Retry with IP Rotation
- Offers **auto-retry on bot detection (up to 3 attempts with IP rotation)**
- Suggests IP address is a detection signal they've observed
- Most aggressive countermeasure among competitors
- $0.35/hour pricing

### MeetingBaaS — No Documented Response
- No public bot detection countermeasures mentioned
- Token-based pricing model (changed from hourly in late 2025)

### Otter.ai — Bot Fatigue Awareness
- OtterPilot joins as visible named participant ("Otter.ai")
- Growing "Bot Fatigue" in market — visible bots seen as intrusive
- No public pivot to bot-free recording announced
- HIPAA compliance launched 2025 (enterprise focus)
- $100M ARR suggests enterprise relationships may provide policy exemptions

### Fireflies.ai — No Public Response
- Joins as visible bot participant
- Facing BIPA class-action lawsuit over recording practices
- $1B valuation — likely investing in alternatives behind the scenes

### Read.ai — No Public Response
- Cross-platform transcription
- No documented bot detection strategy

### Industry Trend: Bot-Free Recording
Multiple new entrants positioning as "bot-free" alternatives:
- **Tactiq**: Browser extension, no bot
- **MeetGeek**: Browser + desktop app, no-bot mode
- **Granola**: Desktop app, no bot joins
- **Omi AI**: Hardware device, no bot

---

## 7. Timeline

| Date | Event |
|------|-------|
| March 2026 | MC1251206 announced, Roadmap ID 558107 published |
| Mid-May 2026 | Targeted Release rollout begins |
| Early June 2026 | General Availability worldwide + GCC begins |
| Mid-June 2026 | GA rollout complete |
| Future (undated) | "More granular controls" — likely harder blocking options |

**Platforms:** Desktop (Windows), Mac, Linux, iOS, Android
**Note:** Web client not explicitly listed but implied (detection is at lobby/server level, not client-specific)

---

## 8. Can a Well-Configured Playwright Instance Avoid Detection?

### Arguments FOR evasion possibility

1. **Microsoft admits detection is imperfect**: "might not pick up every third-party recording bot"
2. **Detection is metadata-based**: If we control join metadata, we may control detection
3. **Playwright stealth exists**: `playwright-stealth` removes `navigator.webdriver`, `HeadlessChrome` UA, and other fingerprint leaks
4. **Headless Chrome unified codebase**: Since Nov 2022, headless Chrome uses same codebase as headful — traditional fingerprinting is harder
5. **Signed-in bots**: If bot joins with a real Microsoft account from a trusted domain, it's no longer "anonymous/unverified"
6. **Domain whitelisting**: If bot's domain is in tenant's trusted list, CAPTCHA is bypassed — new detection may also be softer

### Arguments AGAINST evasion possibility

1. **Server-side detection**: If detection runs at Microsoft's SFU/lobby service (not in browser JS), client-side stealth is irrelevant
2. **Join metadata is server-controlled**: Microsoft sees the auth token (or lack thereof), IP, connection pattern at the server level
3. **Evolving heuristics**: Even if evasion works today, Microsoft will improve detection via "customer reports and ongoing research"
4. **Cat-and-mouse game**: Investing in evasion is a losing long-term strategy — Microsoft has infinite resources to improve detection
5. **IP reputation**: Datacenter IPs are flagged differently than residential IPs
6. **Behavioral signals**: Bot join patterns (no camera, immediate audio capture, no pre-join interaction beyond minimum) are distinctive

### Assessment

**Short-term (May-June 2026):** A well-configured Playwright instance with stealth measures, signed-in account, and residential IP **may** avoid initial detection. Microsoft's own admission of imperfect detection supports this.

**Medium-term (2026 H2):** As Microsoft improves detection via customer reports, evasion becomes progressively harder. Each detected bot teaches the system.

**Long-term (2027+):** Evasion is not a viable strategy. Microsoft controls the platform and will converge on reliable detection. Plan for a world where bots are always detected.

### Recommended Stealth Measures (for short-term survival)

If pursuing browser-based approach:
1. Use `playwright-stealth` or equivalent to remove automation markers
2. Use **headful** mode (not headless) — some detection checks headless-specific properties
3. Use a **signed-in Microsoft account** (not anonymous join) from a trusted domain
4. Use **residential IP** or at minimum rotate IPs (per Skribby's approach)
5. Simulate human-like pre-join behavior (pause on pre-join screen, toggle camera, etc.)
6. Set realistic display name (not "Bot" or "[Company] Notetaker")
7. Enable camera briefly with a static image / avatar to appear more human-like

**IMPORTANT:** These are short-term mitigations, not a long-term strategy. The real answer is one of the strategic pivots below.

---

## 9. Strategic Implications

### For Zoom and Google Meet Importance

Teams bot detection **increases the strategic value of Zoom and Google Meet support:**

- **Zoom**: No equivalent bot detection announced. Zoom's approach is more permissive (web client access, no CAPTCHA). Zoom Web SDK and native SDK provide legitimate bot paths.
- **Google Meet**: No bot detection announced. Meet Media API (Dev Preview) provides a legitimate API path. Browser automation remains unblocked.
- **Teams**: Becoming the hardest platform for third-party bots. Microsoft is actively hostile to the approach.

**Recommendation:** Accelerate Zoom and GMeet support. Teams bot support becomes a differentiator that's increasingly expensive to maintain.

### Strategic Options for Teams

| Option | Effort | Detection Risk | User Experience | Long-term Viability |
|--------|--------|---------------|-----------------|---------------------|
| **A. Browser bot + stealth** | Low | HIGH (detected eventually) | Seamless if admitted | LOW — cat-and-mouse |
| **B. Browser bot + organizer education** | Low | ACCEPTED (labeled, admitted) | Requires organizer action | MEDIUM — works while label-only |
| **C. Signed-in bot (org-approved account)** | Medium | LOWER (trusted external) | Requires org setup | MEDIUM — depends on policy |
| **D. Desktop Recording SDK** (like Recall.ai) | HIGH | ZERO (no bot in meeting) | Requires user app install | HIGH — platform-independent |
| **E. Graph API bot (.NET/Windows)** | VERY HIGH | LOWEST (official API) | Microsoft-sanctioned | HIGH — but C#/.NET requirement |
| **F. Post-meeting only (Graph transcripts)** | Medium | ZERO | No real-time capability | HIGH — but different product |

### Recommended Strategy

**Phase 1 (Now → May 2026):** Option B — Accept detection, educate organizers. Our bot will be labeled but can still be admitted. This buys time.

**Phase 2 (May → Dec 2026):** Option C — Support signed-in bots with org-approved accounts. Reduces detection surface. Requires customer to provision a Microsoft account for the bot.

**Phase 3 (2027+):** Option D or E — Either Desktop SDK (capture at OS level, no bot in meeting) or Graph API (.NET rewrite for official unmixed audio access). The choice depends on whether real-time capability or zero-friction is more important.

**Parallel:** Invest heavily in Zoom and GMeet where the platform is not hostile.

---

## 10. Original Announcement

**Microsoft 365 Message Center:** MC1251206 (published March 13, 2026)
**Microsoft 365 Roadmap:** Feature ID 558107

Key sources:
- [Office365 IT Pros: Third-Party Recording Bots Blocked](https://office365itpros.com/2026/03/16/third-party-recording-bots/)
- [Bleeping Computer: Teams will tag third-party bots](https://www.bleepingcomputer.com/news/microsoft/microsoft-teams-will-tag-third-party-bots-in-meeting-lobbies/)
- [Help Net Security: Microsoft Teams bot detection](https://www.helpnetsecurity.com/2026/03/06/microsoft-teams-third-party-bot-identification/)
- [Windows Central: Teams ready to boot bots out](https://www.windowscentral.com/software-apps/do-you-know-everyone-in-your-meeting-microsoft-teams-is-ready-to-boot-bots-out)
- [Neowin: Fight unwanted bots in Teams meetings](https://www.neowin.net/news/microsoft-is-making-it-easier-to-fight-unwanted-bots-in-teams-meetings/)
- [Heise: Microsoft Teams gets bot detection](https://www.heise.de/en/news/Microsoft-Teams-gets-bot-detection-11203541.html)
- [AdminDroid: Block AI Assistants in Teams](https://blog.admindroid.com/how-to-block-ai-assistants-in-microsoft-teams-meetings/)
- [M365 Admin HandsOnTek: Identify external bots](https://m365admin.handsontek.net/microsoft-teams-identify-external-bots-joining-teams-meetings/)
- [Windows Forum: Teams to Label External Bots by May 2026](https://windowsforum.com/threads/microsoft-teams-to-label-external-third-party-bots-in-lobby-by-may-2026.404206/)
- [Recall.ai: Desktop Recording SDK](https://www.recall.ai/product/desktop-recording-sdk)
- [Recall.ai: CAPTCHA bypass configuration](https://recall-knowledge-base.help.usepylon.com/articles/2427974610-configuring-microsoft-teams-settings-for-bot-access)
- [Microsoft Learn: CAPTCHA verification for meetings](https://learn.microsoft.com/en-us/microsoftteams/join-verification-check)
- [Skribby: Meeting Bot API Comparison 2026](https://skribby.io/blog/meeting-bot-api-comparison-2026)

---

## Summary for Team

| Question | Answer |
|----------|--------|
| What's detected? | All external third-party bots (browser, API, ACS) |
| How? | "Meeting join metadata" analysis — exact heuristics undisclosed |
| Block or label? | **Label only** (May 2026) — organizer must explicitly admit |
| Hard block coming? | Likely — "more granular controls" promised for future |
| Admin control? | New meeting policy, enabled by default, can disable |
| Personal Teams? | Unknown — likely less affected (no admin controls) |
| Can Playwright evade? | Short-term maybe, long-term no |
| Competitor response? | Recall.ai → Desktop SDK; Skribby → IP rotation; others → nothing public |
| Strategic impact? | Zoom/GMeet become more important; Teams bots increasingly risky |
| Timeline | Mid-May 2026 targeted release → mid-June 2026 GA |
