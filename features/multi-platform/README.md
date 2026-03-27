# Multi-Platform

> **Confidence: 0** — RESET after architecture refactoring. Bot spawning changed: meeting-api to runtime-api (was bot-manager). Platform configs in profiles.yaml. Needs re-validation.
> **Tested:** Google Meet standard + custom nickname URLs, Teams personal + enterprise URLs, platform auto-detection from URL.
> **Not tested:** Zoom (SDK requires app approval), Teams legacy deep links, Teams US Gov/DoD, cross-platform transcript consistency.
> **Contributions welcome:** Zoom browser-based implementation ([#150](https://github.com/Vexa-ai/vexa/issues/150), [#128](https://github.com/Vexa-ai/vexa/issues/128)), Teams admission bug ([#171](https://github.com/Vexa-ai/vexa/issues/171)), new meeting type coverage.

## Why

Unified bot API across Google Meet, Microsoft Teams, and Zoom. Same `POST /bots` call, same response shape, same webhook events, same transcript format. Platform auto-detected from meeting URL — no platform-specific client code needed.

## What

This feature provides a unified bot API that routes to platform-specific join flows, enabling the same `POST /bots` call to work across Google Meet, Microsoft Teams, and Zoom.

### Documentation
- [Google Meet](../../docs/platforms/google-meet.mdx)
- [Microsoft Teams](../../docs/platforms/microsoft-teams.mdx)
- [Zoom](../../docs/platforms/zoom.mdx)
- [Zoom App Setup](../../docs/zoom-app-setup.mdx)
- [Meeting IDs](../../docs/meeting-ids.mdx)

### Components

- **vexa-bot**: implements platform-specific join flows
- **googlemeet/msteams/zoom agents**: handle platform-specific DOM interactions
- **bot-manager**: routes bot requests to the correct platform handler based on meeting URL
- **api-gateway**: exposes the unified API

### Data flow

```
client -> api-gateway -> bot-manager (detect platform from URL)
                              |
              +---------------+---------------+
              v               v               v
        Google Meet       MS Teams          Zoom
        agent + bot       agent + bot       agent + bot
              v               v               v
        platform mock     platform mock     platform mock
```

### Key behaviors

- Platform is auto-detected from the meeting URL
- Same POST /bots request shape for all platforms
- Each platform has its own DOM handler (join flow, audio capture, chat)
- Zoom requires additional app setup (OAuth, webhook verification)
- Meeting ID formats differ per platform but are normalized internally

## Meeting types

### Google Meet

| Type | Format | Example |
|------|--------|---------|
| Standard | `abc-defg-hij` (3-4-3 lowercase) | `meet.google.com/cxi-ebnp-ixk` |
| Custom Workspace nickname | 5-40 chars, alphanumeric + hyphens | `meet.google.com/my-team-standup` |

All Google Meet types: bot joins as unauthenticated guest, goes through waiting room, host must admit.

**Native ID validation** (from `libs/shared-models/shared_models/schemas.py`):
- Standard: `^[a-z]{3}-[a-z]{4}-[a-z]{3}$`
- Custom nickname: `^[a-z0-9][a-z0-9-]{3,38}[a-z0-9]$`

**Out of scope:**
- Domain-restricted meetings (org-only) — bot joins as unauthenticated guest, gets rejected
- Google Classroom meetings — untested, likely same as standard

### Microsoft Teams

| Format | Host | Example |
|--------|------|---------|
| Personal | teams.live.com | `teams.live.com/meet/1234567890123?p=PASSCODE` |
| Enterprise | teams.microsoft.com | `teams.microsoft.com/meet/1234567890123?p=PASSCODE` |
| Enterprise deep link | teams.microsoft.com | `teams.microsoft.com/v2/?meetingjoin=true#/meet/...` |
| Legacy | teams.microsoft.com | `teams.microsoft.com/l/meetup-join/19%3ameeting_...` |
| US Government | gov.teams.microsoft.us | same pattern as enterprise |
| DoD | dod.teams.microsoft.us | same pattern as enterprise |

All Teams types: bot joins as anonymous guest, may go through lobby, host must admit.

**Native ID validation** (from `libs/shared-models/shared_models/schemas.py`):
- Numeric: `^\d{10,15}$`
- Hex hash: `^[0-9a-f]{16}$`

**Out of scope:**
- Org-only meetings (authenticated users only) — bot joins as anonymous guest, gets rejected
- Teams Live Events / Webinars — different URL format, untested

### Zoom

| Type | Format | Example |
|------|--------|---------|
| Standard | 9-11 digit numeric ID | `zoom.us/j/1234567890` |
| With password | numeric ID + pwd param | `zoom.us/j/1234567890?pwd=abc123` |
| Regional subdomain | regional prefix | `us05web.zoom.us/j/1234567890?pwd=abc123` |

Zoom requires OAuth + Meeting SDK (self-hosted only).

**Native ID validation** (from `libs/shared-models/shared_models/schemas.py`):
- `^\d{9,11}$`

**Out of scope:**
- Zoom Events (unique per-registrant links)
- Authenticated-only meetings

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | Meeting URLs + platform detection results | Test matrix execution | Validation |
| **core** | Join flow results per platform/meeting-type | Bot join attempts | Scoring (pass/fail per type) |

No collected datasets yet. When testing matures, capture join flow traces (URL → platform detection → join result) per meeting type.

## How

This is a cross-service feature. Testing requires platform-specific mock meetings.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Google Meet: `POST /bots` with `meet.google.com/...` URL -> verify join + transcription
3. MS Teams: `POST /bots` with `teams.microsoft.com/...` URL -> verify join + transcription
4. Zoom: `POST /bots` with `zoom.us/...` URL -> verify join + transcription
5. Compare response shapes — should be identical across platforms

### Known limitations

- Zoom requires pre-configured OAuth app credentials
- Teams may require admin consent for bot access
- Platform DOM changes can break join flows without warning
- Mock meetings may not fully replicate platform behavior
