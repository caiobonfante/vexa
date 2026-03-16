# Zoom Platform Agent

## Scope
Zoom SDK integration via shared meetingFlow pattern. Strategies: join, admission, prepare, recording, removal, leave.

## What you know
- index.ts: delegates to runMeetingFlow() with Zoom-specific PlatformStrategies.
- strategies/: join.ts, admission.ts, prepare.ts, recording.ts, removal.ts, leave.ts — each a standalone strategy.
- native/zoom_meeting_sdk/: proprietary SDK binaries (not in repo, must be provided).
- sdk-manager.ts: manages SDK lifecycle, OBF token auth (limited).
- Self-hosted only — not available on hosted service. Requires own Zoom Marketplace app.
- Web app mode (Playwright-based) in development — working code in strategies/src/, not released.

## Critical questions
- Are SDK binaries present in native/zoom_meeting_sdk/?
- Does the SDK initialize without errors? (sdk-manager.ts)
- Do all 6 strategies (join/admission/prepare/recording/removal/leave) execute without throwing?
- Web app mode: what's the completion state of strategies/src/?

## After every run
Update SDK binary status and strategy execution results.
