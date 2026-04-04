# Mission: dashboard-bugs

Focus: 3 dashboard bugs + collect more along the way
Target: Fix all bugs, validate each fix
Stop-when: All 3 bugs fixed and verified OR 10 iterations

## Bugs to fix

### Bug 1: WS subscribe error "meetings[0] not authorized or not found for user"
- Error in `use-live-transcripts.ts:292`
- Server-side: `services/meeting-api/meeting_api/collector/endpoints.py:392`
- The collector queries `Meeting.user_id == current_user.id, Meeting.platform == platform_value, Meeting.platform_specific_id == native_id`
- Root cause investigation: check what platform/native_id the dashboard sends vs what's in DB. Also check if the auth token resolves to the correct user.
- `/bots/status` returns `platform: null` for browser_session containers — dashboard proxy hardcodes `status: "active"` with null platform, which then gets subscribed

### Bug 2: Meeting jumps straight to "active" — no status transition shown
- `services/dashboard/src/app/api/vexa/[...path]/route.ts:30-83` — meeting list merges `/bots/status` (hardcoded "active") with `/meetings` (TC history)
- No WS `meeting.status` events published for `requested` → `joining` → `active` transitions
- The dashboard does poll via `refreshMeeting` but status_transition data in meeting.data exists — need to show it in UI
- Check: does the gateway publish meeting.status WS events? Does the dashboard subscribe before the transition happens?

### Bug 3: Dashboard doesn't show live transcription, even on page reload (REST should load)
- `use-live-transcripts.ts:101-117` bootstrapFromRest calls `vexaAPI.getTranscripts(platform, nativeId)`
- This calls `/api/vexa/transcripts/{platform}/{nativeId}` which proxies to collector
- If Bug 1's auth/platform issue also affects REST, bootstrap silently fails (error caught at line 114)
- Also: check if the transcript-viewer component actually renders when transcripts array is populated

## Key files
- `services/dashboard/src/hooks/use-live-transcripts.ts` — WS connection + REST bootstrap
- `services/dashboard/src/stores/meetings-store.ts` — state management
- `services/dashboard/src/lib/api.ts` — API client
- `services/dashboard/src/app/api/vexa/[...path]/route.ts` — proxy layer
- `services/api-gateway/main.py` — WS handler (line ~1767)
- `services/meeting-api/meeting_api/collector/endpoints.py` — authorize-subscribe + transcripts
- `services/dashboard/src/components/meetings/meeting-card.tsx` — status display
- `services/dashboard/src/components/transcript/transcript-viewer.tsx` — transcript display

## Approach
1. Reproduce each bug by reading logs / testing API calls
2. Fix root cause (not symptoms)
3. Collect any additional bugs found along the way
4. Test each fix
