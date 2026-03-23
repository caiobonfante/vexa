ROOT := $(shell git rev-parse --show-toplevel)
FEATURE := $(ROOT)/features/webhooks
TEST := $(shell cd "$(dir $(lastword $(MAKEFILE_LIST)))" && pwd)

-include $(FEATURE)/.env
export

export API_GATEWAY_URL ?= http://localhost:8066
export ADMIN_API_URL ?= http://localhost:8067
export ADMIN_TOKEN ?= changeme
export WEBHOOK_RECEIVER_PORT ?= 9999

.PHONY: help env-check smoke test test-config test-bot-status test-payload receiver clean

help:
	@echo "Usage:"
	@echo ""
	@echo "  Env setup (Stage 0):"
	@echo "    make env-check      — verify .env exists and show config"
	@echo "    make smoke          — configure webhook URL, verify stored"
	@echo ""
	@echo "  Tests:"
	@echo "    make receiver       — start a local webhook receiver (foreground)"
	@echo "    make test-config    — test webhook URL configuration (PUT /user/webhook)"
	@echo "    make test-bot-status — trigger bot status change, check webhook fires"
	@echo "    make test-payload   — validate webhook payload against schema"
	@echo "    make test           — run all tests"
	@echo ""
	@echo "  Config (from $(FEATURE)/.env):"
	@echo "    Gateway:  $(API_GATEWAY_URL)"
	@echo "    Receiver: http://localhost:$(WEBHOOK_RECEIVER_PORT)"

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
	@bash $(TEST)/test-webhooks.sh smoke

test-config: env-check
	@bash $(TEST)/test-webhooks.sh config

test-bot-status: env-check
	@bash $(TEST)/test-webhooks.sh bot-status

test-payload: env-check
	@bash $(TEST)/test-webhooks.sh payload

test: env-check
	@bash $(TEST)/test-webhooks.sh all

receiver:
	@bash $(TEST)/webhook-receiver.sh
