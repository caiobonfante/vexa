# Send TTS Bots
Confidence: 80 — validated 2026-03-24: bot joined meeting 9317490635185, TTS spoke via OpenAI alloy voice, captions appeared. Needs recorder bot (separate user) for full pipeline test.
Command: `curl -X POST http://localhost:8066/bots -H "X-API-Key: $TOKEN" -d '{"platform":"google_meet","native_meeting_id":"abc-defg-hij","bot_name":"Alice","tts_text":"Hello everyone..."}'`
Output: bot joins meeting, speaks the text, captures audio
Needs:
  - Live meeting URL (from host-gmeet-meeting or host-teams-meeting tool)
  - API token with bot scope
  - meeting-api running
  - TTS service running (for bot speech generation)
  - Meeting must have auto-admit running or bot will wait in lobby
For scripted multi-bot conversations: use collection manifest (features/realtime-transcription/tests/collection-manifest-*.md) which defines utterances, speakers, timing.
Dead ends:
  - Bots with "vexa" in name get flagged by some meeting platforms — use real-sounding names
  - Short TTS utterances (<1s) may not generate Teams captions — platform limitation
