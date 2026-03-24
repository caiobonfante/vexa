# Host Microsoft Teams Meeting
Confidence: 60 — used successfully for 5+ collection runs in March 2026.
Command: `CDP_URL=<cdp_url> node features/realtime-transcription/scripts/teams-host-auto.js`
Output: MEETING_URL, NATIVE_MEETING_ID, MEETING_PASSCODE to stdout. Updates .env.
Then: auto-admit runs within the script (Teams auto-admit via lobby click).
Needs:
  - Browser session with CDP access (create via bot-manager POST /sessions)
  - Microsoft account signed in via VNC (one-time human step)
  - Full stack running
Dead ends: none known — more reliable than GMeet hosting.
