ROOT := $(shell git rev-parse --show-toplevel)
FEATURE := $(ROOT)/features/token-scoping
TEST := $(shell cd "$(dir $(lastword $(MAKEFILE_LIST)))" && pwd)

-include $(FEATURE)/.env
export

export API_GATEWAY_URL ?= http://localhost:8066
export ADMIN_API_URL ?= http://localhost:8067
export ADMIN_TOKEN ?= changeme

.PHONY: help env-check smoke test test-create test-enforce test-legacy clean

help:
	@echo "Usage:"
	@echo ""
	@echo "  Env setup (Stage 0):"
	@echo "    make env-check     — verify .env exists and show config"
	@echo "    make smoke         — create one scoped token, verify prefix"
	@echo ""
	@echo "  Tests:"
	@echo "    make test-create   — test scoped token creation (all scopes)"
	@echo "    make test-enforce  — test scope enforcement (in-scope, out-of-scope)"
	@echo "    make test-legacy   — test legacy unscoped token backward compat"
	@echo "    make test          — run all tests"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean         — revoke test tokens created during this run"
	@echo ""
	@echo "  Config (from $(FEATURE)/.env):"
	@echo "    Admin API: $(ADMIN_API_URL)"
	@echo "    Gateway:   $(API_GATEWAY_URL)"

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
	@echo "Admin API: $(ADMIN_API_URL)"
	@echo "Gateway:   $(API_GATEWAY_URL)"

smoke: env-check
	@bash $(TEST)/test-token-scoping.sh smoke

test-create: env-check
	@bash $(TEST)/test-token-scoping.sh create

test-enforce: env-check
	@bash $(TEST)/test-token-scoping.sh enforce

test-legacy: env-check
	@bash $(TEST)/test-token-scoping.sh legacy

test: env-check
	@bash $(TEST)/test-token-scoping.sh all

clean:
	@bash $(TEST)/test-token-scoping.sh clean
