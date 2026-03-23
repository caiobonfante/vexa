"""Runtime API configuration."""

import os

# Docker
DOCKER_HOST = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "vexa-agentic_vexa_agentic")

# Container images
AGENT_IMAGE = os.getenv("AGENT_IMAGE", "vexa-agent:dev")
BROWSER_IMAGE = os.getenv("BROWSER_IMAGE", "vexa-bot:dev")
MEETING_IMAGE = os.getenv("MEETING_IMAGE", "vexa-bot:dev")

# Timeouts (seconds)
AGENT_IDLE_TIMEOUT = int(os.getenv("AGENT_IDLE_TIMEOUT", "900"))  # 15min default
BROWSER_IDLE_TIMEOUT = int(os.getenv("BROWSER_IDLE_TIMEOUT", "600"))
IDLE_CHECK_INTERVAL = int(os.getenv("IDLE_CHECK_INTERVAL", "30"))

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# MinIO (for browser profile sync)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "vexa-access-key")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "vexa-secret-key")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "vexa-recordings")

# Claude credentials (host paths for bind mount into agent containers)
CLAUDE_CREDENTIALS_PATH = os.getenv("CLAUDE_CREDENTIALS_PATH", "")
CLAUDE_JSON_PATH = os.getenv("CLAUDE_JSON_PATH", "")

# Bot API token (for agent containers to call bot-manager)
BOT_API_TOKEN = os.getenv("BOT_API_TOKEN", "")
