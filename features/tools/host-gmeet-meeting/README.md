# Host Google Meet Meeting
Confidence: 30 — script worked in March 2026 testing, not validated recently.
Command: `CDP_URL=<cdp_url> node features/realtime-transcription/scripts/gmeet-host-auto.js`
Output: MEETING_URL and NATIVE_MEETING_ID to stdout
Then: `CDP_URL=<cdp_url> node features/realtime-transcription/scripts/auto-admit.js <meeting_url>`
Needs:
  - Browser session with CDP access (create via bot-manager POST /sessions)
  - Google account signed in via VNC (one-time human step — session persists in MinIO)
  - Full stack running (api-gateway, bot-manager, admin-api)
Dead ends:
  - meet.new sometimes redirects to Google Calendar instead of creating a meeting — retry once
  - Bot gets stuck at "find name input" if using simple mock HTML — must use real meet.new
  - Admission polling may false-positive on loading spinners — fixed in selectors.ts
