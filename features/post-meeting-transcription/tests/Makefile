ROOT := $(shell git rev-parse --show-toplevel)
FEATURE := $(ROOT)/features/post-meeting-transcription
TEST := $(shell cd "$(dir $(lastword $(MAKEFILE_LIST)))" && pwd)

# Load feature .env if it exists
-include $(FEATURE)/.env
export

# Fallback defaults
export API_GATEWAY_URL ?= http://localhost:8066
export MEETING_API_URL ?= http://localhost:8066
export TRANSCRIPTION_SERVICE_URL ?= http://localhost:8083/v1/audio/transcriptions
export MINIO_ENDPOINT ?= localhost:9000
export ADMIN_PORT ?= 8057

.PHONY: help env-check smoke check-recording check-speaker-events check-transcribe check-playback test

help:
	@echo "Post-Meeting Transcription Tests"
	@echo ""
	@echo "  Stage 0: Infra verification"
	@echo "    make env-check           — verify .env exists and show config"
	@echo "    make smoke               — verify transcription-service, MinIO, meeting-api are reachable"
	@echo ""
	@echo "  Stage 1: Pipeline checks (after a meeting completes)"
	@echo "    make check-recording  MEETING_ID=N  — verify recording exists in MinIO"
	@echo "    make check-speaker-events MEETING_ID=N — verify speaker_events in meeting.data"
	@echo "    make check-transcribe MEETING_ID=N  — trigger POST /meetings/N/transcribe and show result"
	@echo "    make check-playback   MEETING_ID=N  — verify GET /transcripts returns segments"
	@echo "    make test MEETING_ID=N              — run all checks in sequence"
	@echo ""
	@echo "  Config (from $(FEATURE)/.env):"
	@echo "    API Gateway:  $(API_GATEWAY_URL)"
	@echo "    TX Service:   $(TRANSCRIPTION_SERVICE_URL)"
	@echo "    MinIO:        $(MINIO_ENDPOINT)"

# --- Stage 0: Env setup ---

env-check:
	@if [ ! -f "$(FEATURE)/.env" ]; then \
		echo "ERROR: $(FEATURE)/.env not found"; \
		echo "Create it: cp $(FEATURE)/.env.example $(FEATURE)/.env"; \
		exit 1; \
	fi
	@echo "Feature .env: $(FEATURE)/.env"
	@echo "---"
	@grep -v '^#' "$(FEATURE)/.env" | grep -v '^$$' | sort
	@echo "---"

smoke: env-check
	@echo "1/3 Checking transcription-service..."
	@curl -sf $(TRANSCRIPTION_SERVICE_URL)/../health > /dev/null 2>&1 \
		&& echo "  OK: transcription-service reachable" \
		|| echo "  FAIL: transcription-service not reachable at $(TRANSCRIPTION_SERVICE_URL)"
	@echo "2/3 Checking meeting-api..."
	@curl -sf $(MEETING_API_URL)/health > /dev/null 2>&1 \
		&& echo "  OK: meeting-api reachable" \
		|| echo "  FAIL: meeting-api not reachable at $(MEETING_API_URL)"
	@echo "3/3 Checking MinIO..."
	@curl -sf http://$(MINIO_ENDPOINT)/minio/health/live > /dev/null 2>&1 \
		&& echo "  OK: MinIO reachable" \
		|| echo "  FAIL: MinIO not reachable at $(MINIO_ENDPOINT)"

# --- Stage 1: Pipeline checks ---

check-recording:
	@if [ -z "$(MEETING_ID)" ]; then echo "ERROR: MEETING_ID required"; exit 1; fi
	@echo "Checking recording for meeting $(MEETING_ID)..."
	@curl -sf "$(MEETING_API_URL)/meetings/$(MEETING_ID)" \
		-H "X-API-Key: $(API_TOKEN)" | jq '.data.recordings // "no recordings in meeting.data"'

check-speaker-events:
	@if [ -z "$(MEETING_ID)" ]; then echo "ERROR: MEETING_ID required"; exit 1; fi
	@echo "Checking speaker_events for meeting $(MEETING_ID)..."
	@curl -sf "$(MEETING_API_URL)/meetings/$(MEETING_ID)" \
		-H "X-API-Key: $(API_TOKEN)" | jq '{speaker_events_count: (.data.speaker_events | length), speaker_events: .data.speaker_events[:5]}'

check-transcribe:
	@if [ -z "$(MEETING_ID)" ]; then echo "ERROR: MEETING_ID required"; exit 1; fi
	@echo "Triggering transcription for meeting $(MEETING_ID)..."
	@curl -sf -X POST "$(MEETING_API_URL)/meetings/$(MEETING_ID)/transcribe" \
		-H "X-API-Key: $(API_TOKEN)" \
		-H "Content-Type: application/json" \
		-d '{}' | jq .

check-playback:
	@if [ -z "$(MEETING_ID)" ]; then echo "ERROR: MEETING_ID required"; exit 1; fi
	@if [ -z "$(PLATFORM)" ] || [ -z "$(NATIVE_MEETING_ID)" ]; then \
		echo "ERROR: PLATFORM and NATIVE_MEETING_ID required"; exit 1; \
	fi
	@echo "Checking transcript for $(PLATFORM)/$(NATIVE_MEETING_ID)..."
	@curl -sf "$(MEETING_API_URL)/transcripts/$(PLATFORM)/$(NATIVE_MEETING_ID)" \
		-H "X-API-Key: $(API_TOKEN)" | jq '{segment_count: (.segments | length), speakers: [.segments[].speaker] | unique, first_segment: .segments[0]}'

score:
	@if [ -z "$(MEETING_ID)" ] || [ -z "$(DATASET)" ]; then echo "ERROR: MEETING_ID and DATASET required"; exit 1; fi
	@python3 $(TEST)/score.py --gt $(FEATURE)/data/raw/$(DATASET)/ground-truth.txt --meeting-id $(MEETING_ID)

test: check-recording check-speaker-events check-transcribe check-playback
	@echo "All checks complete."
