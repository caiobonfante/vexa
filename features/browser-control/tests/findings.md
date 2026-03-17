# Browser Control Findings

## Certainty Table

| Check | Score | Evidence | Last checked | To reach next level |
|-------|-------|----------|-------------|---------------------|
| Dockerfile exists in vexa | 0 | Not integrated — lives at playwright-vnc-poc | — | Copy/adapt Dockerfile |
| Browser builds and starts | 30 | Works in playwright-vnc-poc (41h uptime) | 2026-03-17 | Build from vexa context |
| CDP creates Google Meet | 80 | meet.new works, 3 meetings created via CDP | 2026-03-17 | Move script into vexa |
| CDP creates Teams meeting | 80 | Meet sidebar → create link, tested via CDP | 2026-03-17 | Move script into vexa |
| PulseAudio plays WAV as mic | 0 | PulseAudio exists in container but WAV→mic not tested | — | `paplay --device=virtual_mic` |
| Lobby admission via CDP | 85 | Tested on real Teams meeting, host clicked admit | 2026-03-17 | Generalize for Google Meet |
| Full automated test loop | 0 | Not built | — | Wire all pieces together |
| Cookie persistence across restart | 30 | Docker volumes persist data, but not tested after restart | — | Restart container, verify auth |
| Cookie export to DB | 0 | share-cookies.js exists but no DB integration | — | Build encrypt→store→restore pipeline |
| Auth URL API endpoint | 0 | Not built | — | POST /auth/browser → VNC URL |
| Bot joins org-restricted meeting | 0 | Not tested (currently out of scope) | — | Authenticate + join org meeting |

**Overall: 30/100** — Components exist separately, not integrated.
