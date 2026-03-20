ROOT := $(shell git rev-parse --show-toplevel)
BOT  := $(ROOT)/services/vexa-bot
TEST := $(shell cd "$(dir $(lastword $(MAKEFILE_LIST)))" && pwd)

.PHONY: audio unit play play-short play-medium play-long play-all test help

help:
	@echo "Usage:"
	@echo "  make audio       — generate test WAV files (needs tts-service)"
	@echo "  make unit        — run unit tests (mocked Whisper)"
	@echo "  make play        — play medium-paragraph in real-time"
	@echo "  make play-short  — play short-sentence (~3s)"
	@echo "  make play-medium — play medium-paragraph (~14s)"
	@echo "  make play-long   — play long-monologue (~43s)"
	@echo "  make play FILE=x — play custom WAV file"
	@echo "  make play-all    — play all test files sequentially"
	@echo "  make test        — unit + all pipeline tests"

audio:
	@bash $(TEST)/generate-test-audio.sh

unit:
	@cd $(BOT) && npx ts-node core/src/services/speaker-streams.test.ts

play-short: audio
	@cd $(BOT) && npx ts-node core/src/services/speaker-streams.wav-test.ts $(TEST)/audio/short-sentence.wav

play-medium: audio
	@cd $(BOT) && npx ts-node core/src/services/speaker-streams.wav-test.ts $(TEST)/audio/medium-paragraph.wav

play-long: audio
	@cd $(BOT) && npx ts-node core/src/services/speaker-streams.wav-test.ts $(TEST)/audio/long-monologue.wav

play: play-medium

ifdef FILE
play:
	@cd $(BOT) && npx ts-node core/src/services/speaker-streams.wav-test.ts $(FILE)
endif

play-all: play-short play-medium play-long

test: unit play-all
