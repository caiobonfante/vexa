# Vexa — delegates to deploy/compose/Makefile
# Usage: make all, make up, make down, make logs, make test
.DEFAULT_GOAL := all
MAKEFLAGS += --no-print-directory

# Conductor — stream logs from active missions
conductor-logs:
	@echo "=== Streaming all conductor logs (Ctrl+C to stop) ==="
	@tail -f .worktrees/*/conductor/conductor.log conductor/conductor.log 2>/dev/null || echo "No active logs."

conductor-logs-post-meeting:
	@tail -f .worktrees/post-meeting/conductor/conductor.log 2>/dev/null || echo "No post-meeting log."

conductor-logs-telegram:
	@tail -f .worktrees/telegram-chat/conductor/conductor.log 2>/dev/null || echo "No telegram-chat log."

conductor-batch-post-meeting:
	@ls -t .worktrees/post-meeting/conductor/batches/batch-*.log 2>/dev/null | head -1 | xargs tail -f 2>/dev/null || echo "No batch log."

conductor-batch-telegram:
	@ls -t .worktrees/telegram-chat/conductor/batches/batch-*.log 2>/dev/null | head -1 | xargs tail -f 2>/dev/null || echo "No batch log."

conductor-list:
	@/home/dima/dev/vexa-agentic-runtime/conductor/run.sh --list

conductor-status:
	@/home/dima/dev/vexa-agentic-runtime/conductor/run.sh --status

conductor-dashboard:
	@$(MAKE) -C conductor dashboard

conductor-dashboard-watch:
	@$(MAKE) -C conductor dashboard-watch

conductor-web:
	@$(MAKE) -C conductor web

.PHONY: conductor-logs conductor-logs-post-meeting conductor-logs-telegram
.PHONY: conductor-batch-post-meeting conductor-batch-telegram
.PHONY: conductor-list conductor-status conductor-dashboard conductor-dashboard-watch conductor-web

%:
	@$(MAKE) -C deploy/compose $@

.PHONY: %
