# Mission: Browser View for Any Active Meeting

## Goal
Make the bot's browser view (VNC) available on the dashboard for ANY active meeting — not just browser sessions.

## Why
When a bot joins a Google Meet, Teams, or Zoom call, users should be able to see what the bot sees. This helps with debugging, monitoring, and human intervention.

## Current State
- vexa-bot container runs Xvfb on :99 for ALL modes (Playwright renders to it non-headless)
- VNC stack (x11vnc + websockify) only starts in browser_session mode
- session_token (needed for gateway VNC proxy) only created for browser sessions
- Dashboard only shows BrowserSessionView for mode=browser_session
- Escalation mechanism already proves the pattern works for meeting bots

## Changes Required

### 1. vexa-bot entrypoint.sh
- Start x11vnc + websockify for meeting mode too (not just browser_session)
- Don't need fluxbox, SSH, or CDP proxy for meeting view — just VNC viewer

### 2. meeting-api meetings.py (bot creation)
- When creating a regular meeting bot, also generate a session_token
- Store in Redis as `browser_session:{token}` (same format gateway expects)
- Store token in meeting.data so dashboard can access it

### 3. Dashboard meeting detail page
- Add a "Browser View" tab/toggle for active meetings alongside transcript
- Reuse BrowserSessionView component (or a simplified version) for the VNC iframe
- Show for any active meeting that has a session_token in its data

## Definition of Done
- [ ] Active Google Meet/Teams/Zoom meeting shows "Browser View" option on dashboard
- [ ] Clicking it shows the live browser view (noVNC iframe) of what the bot sees
- [ ] Transcript view still available alongside or as a tab
- [ ] Works for new meetings (existing meetings don't need to be retrofitted)
