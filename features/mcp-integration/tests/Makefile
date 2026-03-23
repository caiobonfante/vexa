ROOT := $(shell git rev-parse --show-toplevel)
FEATURE := $(ROOT)/features/mcp-integration
TEST := $(shell cd "$(dir $(lastword $(MAKEFILE_LIST)))" && pwd)

-include $(FEATURE)/.env
export

export API_GATEWAY_URL ?= http://localhost:8066
export MCP_URL ?= http://localhost:8070

.PHONY: help env-check smoke test test-proxy test-tools test-auth test-errors

help:
	@echo "Usage:"
	@echo ""
	@echo "  Env setup (Stage 0):"
	@echo "    make env-check     — verify .env exists and show config"
	@echo "    make smoke         — MCP endpoint reachable via gateway"
	@echo ""
	@echo "  Tests:"
	@echo "    make test-proxy    — verify gateway proxies to MCP service"
	@echo "    make test-tools    — call MCP tools (list_meetings, parse_meeting_link)"
	@echo "    make test-auth     — verify auth required (401 without token)"
	@echo "    make test-errors   — test error handling (invalid tool, bad params)"
	@echo "    make test          — run all tests"
	@echo ""
	@echo "  Config (from $(FEATURE)/.env):"
	@echo "    Gateway: $(API_GATEWAY_URL)"
	@echo "    MCP:     $(MCP_URL)"

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
	@bash $(TEST)/test-mcp.sh smoke

test-proxy: env-check
	@bash $(TEST)/test-mcp.sh proxy

test-tools: env-check
	@bash $(TEST)/test-mcp.sh tools

test-auth: env-check
	@bash $(TEST)/test-mcp.sh auth

test-errors: env-check
	@bash $(TEST)/test-mcp.sh errors

test: env-check
	@bash $(TEST)/test-mcp.sh all
