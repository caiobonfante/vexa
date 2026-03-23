"""Chat API configuration from environment variables."""

import os

# Docker
AGENT_IMAGE = os.getenv("AGENT_IMAGE", "vexa-agent:dev")
DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "vexa-agentic_vexa_agentic")
CONTAINER_PREFIX = os.getenv("CONTAINER_PREFIX", "vexa-agent-")
IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "300"))
IDLE_CHECK_INTERVAL = int(os.getenv("IDLE_CHECK_INTERVAL", "30"))

# Claude credentials (host paths for bind mount into agent containers)
CLAUDE_CREDENTIALS_PATH = os.getenv("CLAUDE_CREDENTIALS_PATH", "")
CLAUDE_JSON_PATH = os.getenv("CLAUDE_JSON_PATH", "")

# MinIO / S3
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "vexa-access-key")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "vexa-secret-key")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "vexa-agentic")

# Runtime API
RUNTIME_API_URL = os.getenv("RUNTIME_API_URL", "http://runtime-api:8090")

# Agent API (ex Chat API)
CHAT_API_PORT = int(os.getenv("CHAT_API_PORT", "8100"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "")
