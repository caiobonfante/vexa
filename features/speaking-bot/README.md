# Speaking Bot

> **Confidence: 0** — Code complete, **not E2E tested.** TTS service + PulseAudio pipeline exist but have never been validated in a live meeting end-to-end.
> **Tested:** Nothing end-to-end. Components exist: tts-service generates audio, bot-manager relays commands, PulseAudio virtual mic configured.
> **Not tested:** Full pipeline (speak command → TTS → PulseAudio → participants hear it), audio quality, latency, voice selection.
> **Contributions welcome:** E2E test in live meeting, local TTS model ([#130](https://github.com/Vexa-ai/vexa/issues/130)), Ultravox voice assistant ([#131](https://github.com/Vexa-ai/vexa/issues/131)).

## Why

Your AI agent doesn't just listen to meetings — it speaks in them. Text-to-speech turns the bot from a passive recorder into an active meeting participant that can answer questions, provide real-time translations, facilitate discussions, or whisper coaching to presenters.

**Competitive context:** Recall.ai launched their Output Media API in 2025 — bots that talk in meetings. It's a closed, paid API. Vexa has the same capability, open-source, self-hosted, and controllable via MCP (so Claude can call `speak` during a live meeting).

**Use cases beyond "read a summary":**

| Use case | How it works |
|----------|-------------|
| **AI facilitator** | Bot tracks agenda, announces time checks, prompts quiet participants |
| **Real-time translator** | Bot transcribes in English, speaks translation in Spanish for remote team |
| **Sales coach** | Bot whispers objection responses to rep via earpiece/chat while customer speaks |
| **Standup bot** | Bot reads yesterday's action items aloud, asks each person for updates |
| **Accessibility** | Bot speaks visual content descriptions for blind participants |

**MCP integration:** An AI agent connected via MCP can call `bot_speak` to respond verbally during a live meeting — no custom integration, just a tool call.

## What

This feature converts text to speech and plays it into the meeting audio so participants hear the bot speaking.

### Documentation
- [Interactive Bots](../../docs/interactive-bots.mdx)
- [Interactive Bots API](../../docs/api/interactive-bots.mdx)

### Components

- **tts-service**: converts text to audio (text-to-speech)
- **vexa-bot**: plays generated audio into the meeting via PulseAudio virtual mic
- **bot-manager**: relays speak commands from API to bot
- **api-gateway**: exposes the speak endpoint

### Data flow

```
client → api-gateway → bot-manager → vexa-bot → tts-service (text→audio)
                                          ↓
                                    vexa-bot (plays audio)
                                          ↓
                                    PulseAudio virtual mic
                                          ↓
                                    meeting audio output
```

### Key behaviors

- POST speak command with text triggers TTS generation
- tts-service converts text to audio
- Bot plays audio into meeting via PulseAudio virtual microphone
- Meeting participants hear the bot speaking
- Speak commands are queued (not overlapping)

### Data stages

| Stage | Contents | Produced by | Consumed by |
|-------|----------|-------------|-------------|
| **raw** | Text input + TTS-generated audio (WAV) | Speak API + tts-service | PulseAudio pipeline |
| **rendered** | Audio heard by meeting participants | PulseAudio virtual mic | Meeting participants |

No collected datasets yet. When testing matures, capture text→audio→playback traces for quality scoring.

## How

This is a cross-service feature. Testing requires the full compose stack with tts-service and a mock meeting.

### Verify

1. Start the compose stack: `make all` (from `deploy/compose/`)
2. Start a bot in a mock meeting
3. Send speak command: `POST /bots/{id}/speak` with `{"text": "Hello everyone"}`
4. Verify tts-service generates audio (check service logs)
5. Verify PulseAudio virtual mic receives audio output

### Known limitations

- Audio quality depends on TTS model and network latency
- No voice selection or customization documented
- PulseAudio virtual mic setup is container-specific
