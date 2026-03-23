ROOT := $(shell git rev-parse --show-toplevel)
FEATURE := $(ROOT)/features/calendar-integration
TEST := $(shell cd "$(dir $(lastword $(MAKEFILE_LIST)))" && pwd)

-include $(FEATURE)/.env
export

export API_GATEWAY_URL ?= http://localhost:8066
export CALENDAR_SERVICE_URL ?= http://localhost:8071

.PHONY: help env-check smoke test test-oauth test-sync test-schedule test-extract

help:
	@echo "Usage:"
	@echo ""
	@echo "  Env setup (Stage 0):"
	@echo "    make env-check      — verify .env exists, Google OAuth configured"
	@echo "    make smoke          — OAuth flow + initial sync"
	@echo ""
	@echo "  Tests:"
	@echo "    make test-oauth     — test Google OAuth token exchange"
	@echo "    make test-sync      — test calendar event sync"
	@echo "    make test-extract   — test meeting URL extraction from events"
	@echo "    make test-schedule  — test bot auto-scheduling"
	@echo "    make test           — run all tests"
	@echo ""
	@echo "  Config (from $(FEATURE)/.env):"
	@echo "    Calendar service: $(CALENDAR_SERVICE_URL)"
	@echo "    Google Client ID: $(if $(GOOGLE_CLIENT_ID),configured,NOT SET)"

env-check:
	@if [ ! -f "$(FEATURE)/.env" ]; then \
		echo "ERROR: $(FEATURE)/.env not found"; \
		echo "Create it: cp $(FEATURE)/.env.example $(FEATURE)/.env"; \
		exit 1; \
	fi
	@echo "Feature .env: $(FEATURE)/.env"
	@echo "---"
	@grep -v '^#' "$(FEATURE)/.env" | grep -v '^$$' | grep -v 'SECRET\|TOKEN\|KEY' | sort
	@echo "---"
	@if [ -z "$(GOOGLE_CLIENT_ID)" ]; then \
		echo "WARNING: GOOGLE_CLIENT_ID not set — OAuth tests will skip"; \
	else \
		echo "Google OAuth: configured"; \
	fi

smoke: env-check
	@echo "Calendar integration smoke test..."
	@echo "NOTE: calendar-service not yet implemented"
	@echo "  This test will work once the service is built."
	@if [ -n "$(CALENDAR_SERVICE_URL)" ]; then \
		status=$$(curl -s -o /dev/null -w "%{http_code}" "$(CALENDAR_SERVICE_URL)/health" 2>/dev/null || echo "000"); \
		if [ "$$status" = "200" ]; then \
			echo "  PASS: calendar-service reachable"; \
		else \
			echo "  SKIP: calendar-service not running (HTTP $$status)"; \
		fi; \
	fi

test-oauth: env-check
	@echo "OAuth tests not yet implemented (needs calendar-service)"

test-sync: env-check
	@echo "Sync tests not yet implemented (needs calendar-service)"

test-extract: env-check
	@bash $(TEST)/test-url-extraction.sh

test-schedule: env-check
	@echo "Schedule tests not yet implemented (needs calendar-service)"

test: env-check test-extract
	@echo ""
	@echo "Note: OAuth, sync, and schedule tests require calendar-service (not yet built)"
