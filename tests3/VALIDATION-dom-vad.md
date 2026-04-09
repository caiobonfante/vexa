# Teams DOM+VAD Routing — Testing Plan

Validate that Teams transcription works with DOM speaking indicators + VAD gate instead of caption-driven audio routing.

**Branch:** `feat/teams-dom-vad-routing`

## Summary checklist

| # | Test | Command | Status |
|---|------|---------|--------|
| 1 | Static locks (16/16) | `make -C tests3 locks` | |
| 2 | Compose build + up | `make -C deploy/compose build up` | |
| 3 | Smoke on compose | `make -C tests3 smoke` | |
| 4 | Teams meeting — segments arrive | `make -C tests3 meeting-tts-teams` | |
| 5 | Teams DOM+VAD strict gate | `make -C tests3 teams-dom-vad` | |
| 6 | Data collection | `make -C tests3 collect-teams` | |
