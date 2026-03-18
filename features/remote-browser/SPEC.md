# Remote Browser — Integration with Meetings (IMPLEMENTED)

## WHY

Browser sessions are currently implemented as a separate page (`/browser`) with their own lifecycle, but they store data in the `meetings` table with `platform=browser_session`. This causes:

1. **Browser sessions show in Meetings list** with no way to manage them
2. **Stop is broken** — dashboard sends `meeting.id` but endpoint expects `platform_specific_id`
3. **Stale sessions pile up** — containers die but DB stays "active" (22 stale in testing)
4. **No concurrency check** — browser sessions bypass `max_concurrent_bots`, so a user can't start a real meeting bot while browser sessions are "active"
5. **Two pages for one concept** — browser sessions ARE meetings, they should be managed from the Meetings page

## WHAT

Browser sessions become first-class meetings:

- **Meetings page** shows browser sessions with proper icon (Monitor), actions (VNC, Stop, Connect Agent)
- **Meeting detail page** (`/meetings/[id]`) detects `browser_session` mode and shows VNC view instead of transcript viewer
- **"Join Meeting" modal** gets a "Browser Session" option alongside Google Meet/Teams/Zoom
- **Concurrency check** — browser sessions count against `max_concurrent_bots`
- **Stop works** — fix the meeting ID vs platform_specific_id mismatch
- **Stale cleanup** — reconcile on page load, mark orphaned sessions as completed
- **`/browser` page removed** from sidebar — everything through Meetings

### Meeting detail for browser_session shows:
- VNC iframe (same as current `/browser` page)
- Toolbar: Save, Connect Agent (sidebar), Fullscreen, Stop
- Connect Agent sidebar: CDP instructions, SSH, MCP endpoint

### Git workspace settings:
- Stored in localStorage (user-level, not per-session)
- Configured from a settings panel accessible in the browser session view
- Automatically passed when creating browser sessions

## HOW

### 1. Bot-manager: concurrency check for browser sessions
- Remove the early return at line 651 that bypasses `max_concurrent_bots`
- Browser sessions count like any other bot

### 2. Fix stop endpoint
- Dashboard sends `DELETE /bots/{meeting_id}` using meeting ID
- Bot-manager looks up by `meetings.id` directly, not `platform_specific_id`
- Or: dashboard sends the correct `platform_specific_id` ("bs-xxx")

### 3. Meeting detail page: browser_session branch
- In `/meetings/[id]/page.tsx`, check `currentMeeting.data?.mode === "browser_session"`
- If true: render VNC view + toolbar + agent sidebar (lifted from `/browser` page)
- If false: existing transcript viewer

### 4. Meetings page: platform filter + icon
- Add `browser_session` to platform filter dropdown
- `PlatformIcon` renders Monitor icon for `browser_session`
- MeetingRow: for active browser sessions, show Stop button inline

### 5. Join Meeting modal: browser session option
- Add "Browser Session" tab/option in the join modal
- Shows git workspace settings inline
- Creates session via existing `POST /bots {mode: "browser_session"}`

### 6. Remove `/browser` page
- Delete `services/dashboard/src/app/browser/page.tsx`
- Remove "Browser" from sidebar navigation

### 7. Stale session cleanup
- On meetings page load (or on a timer), check active browser_sessions
- For each: verify container exists via `/bots/status`
- Mark orphaned ones as `completed`

## Architecture

```
Meetings Page (list)
  ├── Regular meetings → click → /meetings/[id] → transcript viewer
  └── Browser sessions → click → /meetings/[id] → VNC view + agent panel

Join Meeting Modal
  ├── Google Meet URL
  ├── Teams URL
  ├── Zoom URL
  └── Browser Session (git workspace settings)

Container lifecycle:
  POST /bots {mode: "browser_session"}
    → check max_concurrent_bots (SAME as regular)
    → INSERT meetings (platform="browser_session")
    → start container (VNC + CDP + SSH)
    → store session_token in meeting.data + Redis

  DELETE /bots/{platform}/{platform_specific_id}
    → stop container
    → UPDATE meetings SET status="completed"
```
