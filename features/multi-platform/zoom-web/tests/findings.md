# Zoom Web — Findings

## Gate verdict: NOT MERGED (PR #181 pending evaluation)

## Score: 0

## Implementation status (2026-03-24)

PR #181 by jbschooley adds a **complete Zoom web client via Playwright** — the same browser-based approach used for Google Meet and Teams. This is NOT the Zoom SDK path (which requires Marketplace review).

### What PR #181 adds

| Component | File | Lines | Description |
|-----------|------|-------|-------------|
| Join flow | `platforms/zoom/web/join.ts` | 162 | Navigate to Zoom URL, handle name entry, join meeting |
| Admission | `platforms/zoom/web/admission.ts` | 118 | Detect waiting room, admission, rejection |
| Recording | `platforms/zoom/web/recording.ts` | 360 | **Caption-based** like Teams — observes Zoom caption DOM for speaker + text |
| Leave | `platforms/zoom/web/leave.ts` | 74 | Click leave button, handle confirmation dialog |
| Removal | `platforms/zoom/web/removal.ts` | 123 | Detect host removal, meeting end, connection loss |
| Prepare | `platforms/zoom/web/prepare.ts` | 75 | Pre-join setup (mute camera, etc.) |
| Selectors | `platforms/zoom/web/selectors.ts` | 104 | DOM selectors for Zoom web UI |
| Index | `platforms/zoom/web/index.ts` | 29 | Platform strategy exports |
| Video recording | `services/video-recording.ts` | 362 | ffmpeg-based video capture (all platforms) |

### Architecture

Same pattern as Teams:
1. Bot joins via browser (Playwright)
2. Zoom web captions provide speaker attribution (like Teams data-tid selectors)
3. Audio captured from browser
4. Transcription via Whisper (realtime) or post-meeting

### Key dependencies

- Zoom web client accessible without SDK (browser-based, no Marketplace review)
- Captions must be enabled in Zoom meeting settings
- Same caption reliability concerns as Teams (if captions unavailable, fallback?)

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Zoom web join flow | 0 | PR #181 code exists, not merged/tested | 2026-03-24 | Merge PR, test with real Zoom meeting |
| Zoom admission handling | 0 | PR code covers waiting room + rejection | 2026-03-24 | Test waiting room + direct join |
| Zoom caption-based recording | 0 | PR uses DOM caption observation | 2026-03-24 | Test with Zoom captions enabled |
| Zoom speaker attribution | 0 | Caption-driven like Teams | 2026-03-24 | Test with 2+ speakers |
| Zoom leave/removal detection | 0 | PR covers leave + host removal | 2026-03-24 | Test all leave scenarios |
| Video recording (all platforms) | 0 | PR adds ffmpeg-based capture | 2026-03-24 | Test video output quality |
| Post-meeting transcription for Zoom | 0 | Should work via existing pipeline if recording saved | 2026-03-24 | Test POST /meetings/{id}/transcribe on Zoom recording |

## Risks

- Zoom web client may require authentication for some meeting types
- Caption availability depends on meeting host settings
- DOM selectors will drift as Zoom updates their web client
- No fallback if captions unavailable (same gap as Teams)
- Zoom may block browser automation (bot detection)

## Path to merge

1. Evaluate PR #181 conflicts with our recent changes
2. Resolve conflicts (orchestrator_utils.py, chat.ts, types.ts)
3. Merge PR
4. Rebuild vexa-bot:dev
5. Test with real Zoom meeting
6. Score moves based on test results
