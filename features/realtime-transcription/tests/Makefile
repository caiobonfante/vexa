ROOT := $(shell git rev-parse --show-toplevel)
BOT  := $(ROOT)/services/vexa-bot
FEATURE := $(ROOT)/features/realtime-transcription
TEST := $(shell cd "$(dir $(lastword $(MAKEFILE_LIST)))" && pwd)
PLAYER := $(shell which paplay 2>/dev/null || which aplay 2>/dev/null || which ffplay 2>/dev/null)

# Load feature .env if it exists (infra config lives there, not here)
# Create from .env.example: cp $(FEATURE)/.env.example $(FEATURE)/.env
-include $(FEATURE)/.env
export

# Fallback defaults if no .env (CI, quick local runs)
export TRANSCRIPTION_URL ?= http://localhost:8085/v1/audio/transcriptions
export TRANSCRIPTION_TOKEN ?=

AUDIO := $(TEST)/audio
WAVS := $(AUDIO)/short-sentence.wav $(AUDIO)/medium-paragraph.wav $(AUDIO)/long-monologue.wav $(AUDIO)/long-dialogue.wav

.PHONY: audio unit play play-short play-medium play-long play-noisy-office play-noisy-cafe play-noisy-silence play-speakers play-all test env-check smoke help

help:
	@echo "Usage:"
	@echo ""
	@echo "  Env setup (Stage 0):"
	@echo "    make env-check  — verify .env exists and show config"
	@echo "    make smoke      — one utterance end-to-end, verify infra works"
	@echo ""
	@echo "  Collection run (Stage 1):"
	@echo "    make audio      — generate test WAV files from scripts (needs tts-service)"
	@echo ""
	@echo "  Sandbox iteration (Stage 2):"
	@echo "    make unit        — unit tests (mocked Whisper, instant)"
	@echo "    make play        — replay medium-paragraph (default)"
	@echo "    make play-short  — replay short-sentence (~3s)"
	@echo "    make play-medium — replay medium-paragraph (~14s)"
	@echo "    make play-long   — replay long-monologue (~43s)"
	@echo "    make play-noisy-office — replay with office noise"
	@echo "    make play-noisy-cafe   — replay with cafe noise"
	@echo "    make play-noisy-silence — replay with 30s silence gap"
	@echo "    make play-speakers     — 3-speaker attribution replay"
	@echo "    make play-replay       — replay real meeting collected data"
	@echo "    make play FILE=x       — replay custom WAV"
	@echo "    make play-all          — all replays sequentially"
	@echo "    make test              — unit + all replays"
	@echo ""
	@echo "  Config (from $(FEATURE)/.env):"
	@echo "    Transcription: $(TRANSCRIPTION_URL)"
	@echo "    Model: $(or $(MODEL_SIZE),not set)"
	@echo "    Platform: $(or $(PLATFORM),not set)"
	@echo "    Audio playback: $(if $(PLAYER),$(PLAYER),NOT AVAILABLE)"

# --- Stage 0: Env setup ---

env-check:
	@if [ ! -f "$(FEATURE)/.env" ]; then \
		echo "ERROR: $(FEATURE)/.env not found"; \
		echo "Create it: cp $(FEATURE)/.env.example $(FEATURE)/.env"; \
		echo "Then fill in actual values for your environment."; \
		exit 1; \
	fi
	@echo "Feature .env: $(FEATURE)/.env"
	@echo "---"
	@grep -v '^#' "$(FEATURE)/.env" | grep -v '^$$' | sort
	@echo "---"
	@echo "Transcription URL: $(TRANSCRIPTION_URL)"
	@echo "Model: $(or $(MODEL_SIZE),not set in .env)"

smoke: env-check $(AUDIO)/short-sentence.wav
	@echo "Smoke test: sending short-sentence.wav through pipeline..."
	@cd $(BOT) && npx ts-node core/src/services/speaker-streams.wav-test.ts $(AUDIO)/short-sentence.wav
	@echo "Smoke test passed — infra is working."

# Generate audio only if files don't exist
$(WAVS): $(TEST)/generate-test-audio.sh
	@bash $(TEST)/generate-test-audio.sh

audio: $(WAVS)

unit:
	@cd $(BOT) && npx ts-node core/src/services/speaker-streams.test.ts
	@cd $(BOT) && npx ts-node core/src/services/speaker-mapper.test.ts

# Internal: run pipeline + audio playback in parallel
define run_with_audio
	@echo "" && \
	$(if $(PLAYER),$(PLAYER) $(1) &,echo "(no audio player — install pulseaudio-utils to hear playback)" &&) \
	cd $(BOT) && npx ts-node core/src/services/speaker-streams.wav-test.ts $(1)
endef

play-short: $(AUDIO)/short-sentence.wav
	$(call run_with_audio,$(AUDIO)/short-sentence.wav)

play-medium: $(AUDIO)/medium-paragraph.wav
	$(call run_with_audio,$(AUDIO)/medium-paragraph.wav)

play-long: $(AUDIO)/long-monologue.wav
	$(call run_with_audio,$(AUDIO)/long-monologue.wav)

play-noisy-office: $(AUDIO)/noisy-monologue-office.wav
	$(call run_with_audio,$(AUDIO)/noisy-monologue-office.wav)

play-noisy-cafe: $(AUDIO)/noisy-monologue-cafe.wav
	$(call run_with_audio,$(AUDIO)/noisy-monologue-cafe.wav)

play-noisy-silence: $(AUDIO)/noisy-with-silence.wav
	$(call run_with_audio,$(AUDIO)/noisy-with-silence.wav)

play: play-medium

ifdef FILE
play:
	$(call run_with_audio,$(FILE))
endif

play-speakers:
	@cd $(BOT) && npx ts-node core/src/services/speaker-mapper.pipeline-test.ts $(TEST)/audio

play-replay:
	@cd $(BOT) && npx ts-node core/src/services/production-replay.test.ts $(AUDIO) $(TEST)

play-all: play-short play-medium play-long play-noisy-office play-noisy-cafe play-noisy-silence play-speakers

test: unit play-all
