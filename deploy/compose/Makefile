.PHONY: all env build build-bot-image up down ps logs test test-api migrate migrate-or-init makemigrations init-db stamp-db migration-status check_docker

# --- Paths ---
ROOT := $(shell git rev-parse --show-toplevel)
COMPOSE_FILE := $(ROOT)/deploy/compose/docker-compose.yml
COMPOSE_LOCAL_DB := $(ROOT)/deploy/compose/docker-compose.local-db.yml
ENV_FILE := $(ROOT)/.env
ENV_EXAMPLE := $(ROOT)/deploy/env/env-example

BOT_IMAGE_NAME ?= vexa-bot:dev

-include $(ENV_FILE)

# --- Compose files: add local-db overlay unless REMOTE_DB=true ---
COMPOSE_CMD = docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE)
ifneq ($(REMOTE_DB),true)
  COMPOSE_CMD += -f $(COMPOSE_LOCAL_DB)
endif

# ============================================================================
# Main targets
# ============================================================================

all: env build up migrate-or-init test
	@echo "Vexa is running. API: http://localhost:$${API_GATEWAY_HOST_PORT:-8056}/docs"

# --- Environment ---
env:
	@if [ ! -f $(ENV_FILE) ]; then \
		cp $(ENV_EXAMPLE) $(ENV_FILE); \
		echo "Created .env from env-example. Edit $(ENV_FILE) before running."; \
		echo "  - Set TRANSCRIPTION_SERVICE_URL to your transcription endpoint"; \
		echo "  - Set TRANSCRIPTION_SERVICE_TOKEN"; \
	else \
		echo ".env already exists. Delete it to regenerate from env-example."; \
	fi

# --- Docker check ---
check_docker:
	@if ! docker info > /dev/null 2>&1; then \
		echo "ERROR: Docker is not running."; \
		exit 1; \
	fi

# --- Build ---
build-bot-image: check_docker
	@BOT=$$(grep -E '^BOT_IMAGE_NAME=' $(ENV_FILE) 2>/dev/null | cut -d= -f2); \
	BOT=$${BOT:-$(BOT_IMAGE_NAME)}; \
	docker build --platform linux/amd64 -t $$BOT -f $(ROOT)/services/vexa-bot/Dockerfile $(ROOT)/services/vexa-bot

build: check_docker build-bot-image
	$(COMPOSE_CMD) build

# --- Up / Down ---
up: check_docker
	@if ! docker network ls | grep -q "vexa-network"; then \
		docker network create vexa-network || true; \
	fi
	$(COMPOSE_CMD) up -d
	@if grep -qE '^LOCAL_TRANSCRIPTION=true' $(ENV_FILE) 2>/dev/null; then \
		echo "LOCAL_TRANSCRIPTION=true — starting transcription-service..."; \
		cd $(ROOT)/services/transcription-service && docker compose up -d; \
	fi

down: check_docker
	$(COMPOSE_CMD) down
	@cd $(ROOT)/services/transcription-service && docker compose down 2>/dev/null || true

# --- Status ---
ps: check_docker
	$(COMPOSE_CMD) ps

logs:
	$(COMPOSE_CMD) logs -f

# --- Test ---
test: check_docker
	@API_PORT=$$(grep -E '^API_GATEWAY_HOST_PORT=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "8056"); \
	ADMIN_PORT=$$(grep -E '^ADMIN_API_HOST_PORT=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "8057"); \
	API_PORT=$${API_PORT:-8056}; ADMIN_PORT=$${ADMIN_PORT:-8057}; \
	echo "API:   http://localhost:$$API_PORT/docs"; \
	echo "Admin: http://localhost:$$ADMIN_PORT/docs"; \
	if [ -x $(ROOT)/testing/run_vexa_interaction.sh ]; then \
		if [ -n "$(MEETING_ID)" ]; then \
			$(ROOT)/testing/run_vexa_interaction.sh "$(MEETING_ID)"; \
		else \
			$(ROOT)/testing/run_vexa_interaction.sh; \
		fi; \
	fi

test-api: check_docker
	@API_PORT=$$(grep -E '^API_GATEWAY_HOST_PORT=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "8056"); \
	ADMIN_PORT=$$(grep -E '^ADMIN_API_HOST_PORT=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "8057"); \
	API_PORT=$${API_PORT:-8056}; ADMIN_PORT=$${ADMIN_PORT:-8057}; \
	if ! curl -s -f "http://localhost:$$API_PORT/docs" > /dev/null; then \
		echo "API Gateway not responding on port $$API_PORT"; exit 1; \
	fi; \
	if ! curl -s -f "http://localhost:$$ADMIN_PORT/docs" > /dev/null; then \
		echo "Admin API not responding on port $$ADMIN_PORT"; exit 1; \
	fi; \
	echo "API connectivity OK"

# ============================================================================
# Database migrations
# ============================================================================

migrate-or-init: check_docker
	@set -e; \
	if [ "$(REMOTE_DB)" != "true" ]; then \
		if ! $(COMPOSE_CMD) ps -q postgres | grep -q .; then \
			echo "ERROR: postgres not running. Run 'make up' first."; exit 1; \
		fi; \
		count=0; \
		DB_USER=$$(grep -E '^DB_USER=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "postgres"); \
		DB_NAME=$$(grep -E '^DB_NAME=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "vexa"); \
		DB_USER=$${DB_USER:-postgres}; DB_NAME=$${DB_NAME:-vexa}; \
		while ! $(COMPOSE_CMD) exec -T postgres pg_isready -U $$DB_USER -d $$DB_NAME -q; do \
			if [ $$count -ge 12 ]; then echo "ERROR: DB not ready in 60s."; exit 1; fi; \
			sleep 5; count=$$((count+1)); \
		done; \
	fi; \
	$(COMPOSE_CMD) exec -T transcription-collector python /app/libs/shared-models/fix_alembic_version.py --repair-stale; \
	HAS_ALEMBIC=$$($(COMPOSE_CMD) exec -T postgres psql -U $${DB_USER:-postgres} -d $${DB_NAME:-vexa} -t -c "SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version';" 2>/dev/null | tr -d '[:space:]' || echo ""); \
	if [ "$$HAS_ALEMBIC" = "1" ]; then \
		$(MAKE) migrate; \
	else \
		$(COMPOSE_CMD) exec -T transcription-collector python -c "import asyncio; from shared_models.database import init_db; asyncio.run(init_db())"; \
		$(COMPOSE_CMD) exec -T transcription-collector python /app/libs/shared-models/fix_alembic_version.py --create-if-missing; \
	fi

migrate: check_docker
	@set -e; \
	if [ "$(REMOTE_DB)" != "true" ]; then \
		DB_USER=$$(grep -E '^DB_USER=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "postgres"); \
		DB_NAME=$$(grep -E '^DB_NAME=' $(ENV_FILE) 2>/dev/null | cut -d= -f2 || echo "vexa"); \
		DB_USER=$${DB_USER:-postgres}; DB_NAME=$${DB_NAME:-vexa}; \
		if ! $(COMPOSE_CMD) ps postgres | grep -q "Up"; then \
			echo "ERROR: postgres not running. Run 'make up' first."; exit 1; \
		fi; \
	fi; \
	$(COMPOSE_CMD) exec -T transcription-collector python /app/libs/shared-models/fix_alembic_version.py --repair-stale; \
	current_version=$$($(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini current 2>/dev/null | grep -E '^[a-f0-9]{12}' | head -1 || echo ""); \
	if [ "$$current_version" = "dc59a1c03d1f" ]; then \
		if $(COMPOSE_CMD) exec -T postgres psql -U $${DB_USER:-postgres} -d $${DB_NAME:-vexa} -t -c "SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'data';" | grep -q 1; then \
			$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini stamp 5befe308fa8b; \
		fi; \
	fi; \
	$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini upgrade head

makemigrations: check_docker
	@if [ -z "$(M)" ]; then echo "Usage: make makemigrations M=\"your message\""; exit 1; fi
	$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini revision --autogenerate -m "$(M)"

init-db: check_docker
	$(COMPOSE_CMD) run --rm transcription-collector python -c "import asyncio; from shared_models.database import init_db; asyncio.run(init_db())"
	$(COMPOSE_CMD) run --rm transcription-collector alembic -c /app/alembic.ini stamp head

stamp-db: check_docker
	@if [ "$(REMOTE_DB)" != "true" ]; then \
		if ! $(COMPOSE_CMD) ps postgres | grep -q "Up"; then \
			echo "ERROR: postgres not running. Run 'make up' first."; exit 1; \
		fi; \
	fi
	$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini stamp head

migration-status: check_docker
	@if [ "$(REMOTE_DB)" != "true" ]; then \
		if ! $(COMPOSE_CMD) ps postgres | grep -q "Up"; then \
			echo "ERROR: postgres not running. Run 'make up' first."; exit 1; \
		fi; \
	fi
	$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini current
	$(COMPOSE_CMD) exec -T transcription-collector alembic -c /app/alembic.ini history --verbose
