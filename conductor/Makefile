# Conductor — self-improvement loop
#
# Quick start:
#   make mission M=fix-playback     # launch a mission (file must exist in missions/)
#   make missions                   # list all mission files
#   make jobs                       # list running missions
#   make web                        # open web dashboard
#
# From repo root, prefix with conductor-:
#   make conductor-mission M=fix-playback

SHELL := /bin/bash
.DEFAULT_GOAL := help

RUN     := ./run.sh
CHECKER := python3 ./check-completion.py

# =============================================================================
# Main commands
# =============================================================================

## Launch a mission: make mission M=<name>
## The mission file must exist at missions/<name>.md
mission:
ifndef M
	@echo "Usage: make mission M=<name>"
	@echo ""
	@echo "Available missions:"
	@ls -1 missions/*.md 2>/dev/null | grep -v template | sed 's|missions/||;s|\.md||;s|^|  |' || echo "  (none)"
	@echo ""
	@echo "Create one in chat, then: make mission M=<name>"
else
	@if [ ! -f missions/$(M).md ]; then echo "No mission file: missions/$(M).md"; exit 1; fi
	@echo "=== Launching mission: $(M) ==="
	@cat missions/$(M).md
	@echo ""
	@$(RUN) --mission $(M) --max-iterations $(or $(N),10) &
	@sleep 1
	@echo ""
	@echo "Mission '$(M)' running. Monitor:"
	@echo "  make web                         # web dashboard"
	@echo "  make jobs                        # list active"
	@echo "  make logs M=$(M)                 # stream logs"
	@echo "  make stop M=$(M)                 # halt"
	@echo "  make merge M=$(M)                # merge results back"
endif

## List mission files
missions:
	@echo "=== Mission Files ==="
	@ls -1 missions/*.md 2>/dev/null | grep -v template | sed 's|missions/||;s|\.md||;s|^|  |' || echo "  (none)"

## List running missions
jobs:
	@$(RUN) --list

## Web dashboard
web:
	@python3 dashboard.py --web

## Terminal dashboard
dashboard:
	@python3 dashboard.py

## Stream logs for a mission
logs:
ifndef M
	@tail -f ../conductor/conductor.log 2>/dev/null || echo "Usage: make logs M=<name>"
else
	@tail -f ../.worktrees/$(M)/conductor/conductor.log 2>/dev/null || echo "No logs for '$(M)'"
endif

## Stop a mission
stop:
ifndef M
	@touch mission.stop
	@echo "Default mission stop signal created."
else
	@touch ../.worktrees/$(M)/conductor/mission.stop 2>/dev/null || echo "No worktree for '$(M)'"
	@echo "Stop signal created for '$(M)'"
endif

## Merge a completed mission back
merge:
ifndef M
	$(error Usage: make merge M=<name>)
endif
	@cd .. && conductor/run.sh --merge $(M)

## Show status
status:
ifndef M
	@$(RUN) --status
else
	@$(RUN) --mission $(M) --status
endif

## Seed/reseed state from findings
seed:
	@$(CHECKER) --seed

## Show help
help:
	@echo "Conductor — self-improvement loop"
	@echo ""
	@echo "  make mission M=<name>     Launch a mission"
	@echo "  make missions             List mission files"
	@echo "  make jobs                 List running missions"
	@echo "  make web                  Web dashboard (localhost:8899)"
	@echo "  make dashboard            Terminal dashboard"
	@echo "  make logs M=<name>        Stream mission logs"
	@echo "  make stop M=<name>        Stop a mission"
	@echo "  make merge M=<name>       Merge results back"
	@echo "  make status [M=<name>]    Show scores"
	@echo ""
	@echo "Workflow: describe mission in chat → I create the file → make mission M=<name>"

.PHONY: mission missions jobs web dashboard logs stop merge status seed help
