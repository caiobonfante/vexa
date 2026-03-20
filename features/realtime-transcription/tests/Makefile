ROOT := $(shell git rev-parse --show-toplevel)
BOT  := $(ROOT)/services/vexa-bot
TEST := $(shell cd "$(dir $(lastword $(MAKEFILE_LIST)))" && pwd)
PLAYER := $(shell which paplay 2>/dev/null || which aplay 2>/dev/null || which ffplay 2>/dev/null)

# Transcription service — override to test against a different instance
export TRANSCRIPTION_URL ?= http://localhost:8085/v1/audio/transcriptions
export TRANSCRIPTION_TOKEN ?= 32c59b9f654f1b6e376c6f020d79897d

AUDIO := $(TEST)/audio
WAVS := $(AUDIO)/short-sentence.wav $(AUDIO)/medium-paragraph.wav $(AUDIO)/long-monologue.wav $(AUDIO)/long-dialogue.wav

.PHONY: audio unit play play-short play-medium play-long play-all test help

help:
	@echo "Usage:"
	@echo "  make audio       — generate test WAV files (needs tts-service)"
	@echo "  make unit        — run unit tests (mocked Whisper)"
	@echo "  make play        — play medium-paragraph (audio + transcription)"
	@echo "  make play-short  — short-sentence (~3s)"
	@echo "  make play-medium — medium-paragraph (~14s)"
	@echo "  make play-long   — long-monologue (~43s)"
	@echo "  make play FILE=x — custom WAV file"
	@echo "  make play-all    — all test files sequentially"
	@echo "  make test        — unit + all pipeline tests"
	@echo "  make play TRANSCRIPTION_URL=... TRANSCRIPTION_TOKEN=..."
	@echo ""
	@echo "Transcription: $(TRANSCRIPTION_URL)"
	@echo "Audio playback: $(if $(PLAYER),$(PLAYER),NOT AVAILABLE — install pulseaudio-utils)"

# Generate audio only if files don't exist
$(WAVS): $(TEST)/generate-test-audio.sh
	@bash $(TEST)/generate-test-audio.sh

audio: $(WAVS)

unit:
	@cd $(BOT) && npx ts-node core/src/services/speaker-streams.test.ts

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

play: play-medium

ifdef FILE
play:
	$(call run_with_audio,$(FILE))
endif

play-all: play-short play-medium play-long

test: unit play-all
