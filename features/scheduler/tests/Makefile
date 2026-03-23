ROOT := $(shell git rev-parse --show-toplevel)
FEATURE := $(ROOT)/features/scheduler
TEST := $(shell cd "$(dir $(lastword $(MAKEFILE_LIST)))" && pwd)
SHARED := $(ROOT)/libs/shared-models

-include $(FEATURE)/.env
export

export REDIS_URL ?= redis://localhost:6379
export API_GATEWAY_URL ?= http://localhost:8056

.PHONY: help env-check test-unit test-e2e test test-schedule test-cancel test-retry test-idempotency

help:
	@echo "Usage:"
	@echo ""
	@echo "  Env setup:"
	@echo "    make env-check        — verify .env exists, Redis reachable"
	@echo ""
	@echo "  Tests:"
	@echo "    make test-unit        — shared-models unit tests (16 tests, no services)"
	@echo "    make test-e2e         — end-to-end: schedule job, verify execution"
	@echo "    make test-schedule    — test job scheduling via Redis"
	@echo "    make test-cancel      — test job cancellation"
	@echo "    make test-retry       — test retry on failure"
	@echo "    make test-idempotency — test duplicate prevention"
	@echo "    make test             — run all tests"
	@echo ""
	@echo "  Config (from $(FEATURE)/.env):"
	@echo "    Redis: $(REDIS_URL)"
	@echo "    Gateway: $(API_GATEWAY_URL)"

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
	@python3 -c "import redis; r=redis.from_url('$(REDIS_URL)'); r.ping(); print('Redis: PONG')" 2>/dev/null \
		|| echo "WARNING: Redis not reachable at $(REDIS_URL)"

test-unit:
	@cd $(SHARED) && python3 -m pytest shared_models/test_scheduler.py -v

test-e2e: env-check
	@bash $(TEST)/test-scheduler-e2e.sh all

test-schedule: env-check
	@bash $(TEST)/test-scheduler-e2e.sh schedule

test-cancel: env-check
	@bash $(TEST)/test-scheduler-e2e.sh cancel

test-retry: env-check
	@bash $(TEST)/test-scheduler-e2e.sh retry

test-idempotency: env-check
	@bash $(TEST)/test-scheduler-e2e.sh idempotency

test: test-unit test-e2e
