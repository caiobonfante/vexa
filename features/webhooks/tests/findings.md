# Webhooks Test Findings

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| Webhook URL configurable | 0 | Not tested | — | PUT /user/webhook, verify stored |
| Bot status webhook fires | 0 | Not tested | — | Start bot, check receiver for status event |
| Transcript ready webhook fires | 0 | Not tested | — | Complete transcription, check receiver |
| Payload schema correct | 0 | Not tested | — | Compare received payload to shared-models schema |
| End-to-end delivery | 0 | Not tested | — | Full cycle: configure → trigger → receive → validate |
