# Host Microsoft Teams Meeting
Confidence: 80 — created meeting 9317490635185, joined as host. Validated 2026-03-24 via CDP on port 9222.
Command: `CDP_URL=<cdp_url> node features/realtime-transcription/scripts/teams-host-auto.js`
Output: MEETING_URL, NATIVE_MEETING_ID, MEETING_PASSCODE to stdout. Updates .env.
Then: auto-admit runs within the script (Teams auto-admit via lobby click).
Needs:
  - Browser session with CDP access (create via meeting-api POST /sessions)
  - Microsoft account signed in via VNC (one-time human step)
  - Full stack running
Dead ends: none known — more reliable than GMeet hosting.
