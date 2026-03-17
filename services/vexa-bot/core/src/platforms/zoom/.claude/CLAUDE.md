# Zoom Platform Agent

> Shared protocol: [agents.md](../../../../../../../.claude/agents.md) — phases, diagnostics, logging, gate rules

## Scope
Zoom SDK integration via shared meetingFlow pattern. Strategies: join, admission, prepare, recording, removal, leave.

## What you know
- index.ts: delegates to runMeetingFlow() with Zoom-specific PlatformStrategies.
- strategies/: join.ts, admission.ts, prepare.ts, recording.ts, removal.ts, leave.ts — each a standalone strategy.
- native/zoom_meeting_sdk/: proprietary SDK binaries (not in repo, must be provided).
- sdk-manager.ts: manages SDK lifecycle, OBF token auth (limited).
- Self-hosted only — not available on hosted service. Requires own Zoom Marketplace app.
- Web app mode (Playwright-based) in development — working code in strategies/src/, not released.

### Gate (local)
Bot joins a Zoom meeting (or mock), SDK initializes, and audio reaches the transcription endpoint with speech. PASS: SDK init succeeds, join strategy completes, audio buffer non-empty. FAIL: SDK binary missing, init throws, or no audio captured.

### Docs
Your README links to your docs pages. Run the docs gate ([agents.md](../../../../../../../.claude/agents.md#docs-gate)) using those links as your page list.

## Critical questions
- Are SDK binaries present in native/zoom_meeting_sdk/?
- Does the SDK initialize without errors? (sdk-manager.ts)
- Do all 6 strategies (join/admission/prepare/recording/removal/leave) execute without throwing?
- Web app mode: what's the completion state of strategies/src/?

## After every run
Update SDK binary status and strategy execution results.

