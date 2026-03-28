# Mission: Authenticated Bots

## Goal
Bots join meetings authenticated via stored user credentials (browser sessions saved to S3), bypassing the guest "enter name + ask to join" flow.

## DoD

1. **API wires `authenticated` to bot_config** — `POST /bots` with `authenticated=true` passes `authenticated`, `userdataS3Path`, and S3 credentials (endpoint, bucket, keys) through to the bot container.

2. **Google Meet join handles authenticated session** — When `authenticated=true`, bot skips "enter name + Ask to join" guest flow. Joins directly as the signed-in Google user.

3. **Live E2E on hosted Google Meet** — Host a real Google Meet via gateway browser session. Launch a bot with `authenticated=true` using stored credentials. Bot joins the live meeting without manual admission. Verified via:
   - Bot status reaches `admitted`
   - Bot appears in meeting as the authenticated user (not "VexaBot-xxx")
   - Transcription flows normally

## Out of scope
- Teams/Zoom authenticated join
- Credential setup workflow (browser_session mode already handles this)
- Token refresh / credential expiry

## Key files
- `packages/meeting-api/meeting_api/meetings.py` — bot_config construction (lines 701-745)
- `packages/meeting-api/meeting_api/schemas.py` — BotRequest schema (line 438)
- `services/vexa-bot/core/src/index.ts` — authenticated persistent context launch (line 2050)
- `services/vexa-bot/core/src/platforms/googlemeet/join.ts` — Google Meet join flow
- `services/vexa-bot/core/src/types.ts` — BotConfig type
- `services/vexa-bot/core/src/s3-sync.ts` — S3 browser data sync
