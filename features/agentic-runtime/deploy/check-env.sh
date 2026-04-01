#!/bin/bash
# check-env.sh — Pre-delivery environment validation
# Validates all services have required env vars and ports are reachable.
# Run this BEFORE telling a human "it's ready".
#
# Usage: ./check-env.sh [--quiet]
# Exit code: 0 = all pass, 1 = failures found

set -uo pipefail

QUIET=${1:-}
PASS=0
FAIL=0
WARN=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}PASS${NC} $1"; PASS=$((PASS + 1)); }
fail() { echo -e "${RED}FAIL${NC} $1"; FAIL=$((FAIL + 1)); }
warn() { echo -e "${YELLOW}WARN${NC} $1"; WARN=$((WARN + 1)); }
section() { [[ -z "$QUIET" ]] && echo -e "\n${BLUE}=== $1 ===${NC}"; }

# ─── Step 1: Compose .env required vars ──────────────────────────────────────
section "Compose .env required vars"

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  fail ".env file missing at $ENV_FILE"
  echo "Copy from .env.example or create it. Required vars: BOT_API_TOKEN, CLAUDE_CREDENTIALS_PATH, CLAUDE_JSON_PATH, TRANSCRIPTION_SERVICE_URL"
  exit 1
fi

source "$ENV_FILE" 2>/dev/null || true

check_var() {
  local var="$1"
  local required="${2:-yes}"
  local val="${!var:-}"
  if [[ -n "$val" ]]; then
    pass "$var is set"
  elif [[ "$required" == "yes" ]]; then
    fail "$var is MISSING (required)"
  else
    warn "$var is not set (optional)"
  fi
}

check_var BOT_API_TOKEN yes
check_var CLAUDE_CREDENTIALS_PATH yes
check_var CLAUDE_JSON_PATH yes
check_var TRANSCRIPTION_SERVICE_URL yes
check_var TELEGRAM_BOT_TOKEN no
check_var ADMIN_TOKEN no

# Check CLAUDE credentials files exist on host
if [[ -n "${CLAUDE_CREDENTIALS_PATH:-}" ]]; then
  if [[ -f "$CLAUDE_CREDENTIALS_PATH" ]]; then
    pass "CLAUDE_CREDENTIALS_PATH file exists: $CLAUDE_CREDENTIALS_PATH"
  else
    fail "CLAUDE_CREDENTIALS_PATH file NOT found: $CLAUDE_CREDENTIALS_PATH"
  fi
fi
if [[ -n "${CLAUDE_JSON_PATH:-}" ]]; then
  if [[ -f "$CLAUDE_JSON_PATH" ]]; then
    pass "CLAUDE_JSON_PATH file exists: $CLAUDE_JSON_PATH"
  else
    fail "CLAUDE_JSON_PATH file NOT found: $CLAUDE_JSON_PATH"
  fi
fi

# ─── Step 2: Port reachability from host ─────────────────────────────────────
section "Port reachability (host → services)"

check_port() {
  local name="$1"
  local host="$2"
  local port="$3"
  local path="${4:-/}"
  if curl -sf --max-time 3 "http://$host:$port$path" > /dev/null 2>&1; then
    pass "$name reachable at $host:$port"
  else
    # Try without -f (some services return 4xx on /)
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://$host:$port$path" 2>/dev/null || echo "000")
    if [[ "$code" != "000" ]]; then
      pass "$name reachable at $host:$port (HTTP $code)"
    else
      fail "$name NOT reachable at $host:$port"
    fi
  fi
}

check_redis() {
  local host="$1"
  local port="$2"
  if command -v redis-cli &>/dev/null; then
    if redis-cli -h "$host" -p "$port" ping 2>/dev/null | grep -q PONG; then
      pass "redis reachable at $host:$port"
    else
      fail "redis NOT reachable at $host:$port"
    fi
  else
    # No redis-cli: try TCP connection
    if timeout 3 bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
      pass "redis TCP reachable at $host:$port (redis-cli not available for PING)"
    else
      fail "redis NOT reachable at $host:$port"
    fi
  fi
}

REDIS_PORT="${REDIS_PORT:-6389}"
POSTGRES_PORT="${POSTGRES_PORT:-5458}"
API_GATEWAY_PORT="${API_GATEWAY_PORT:-8066}"
ADMIN_API_PORT="${ADMIN_API_PORT:-8067}"
CHAT_API_PORT="${CHAT_API_PORT:-8100}"
RUNTIME_API_PORT="${RUNTIME_API_PORT:-8090}"
MEETING_API_PORT="${MEETING_API_PORT:-8070}"
TC_PORT="${TC_PORT:-8060}"

check_port "api-gateway" localhost "$API_GATEWAY_PORT" "/"
check_port "admin-api" localhost "$ADMIN_API_PORT" "/"
check_port "agent-api" localhost "$CHAT_API_PORT" "/health"
check_port "runtime-api" localhost "$RUNTIME_API_PORT" "/health"
check_port "meeting-api" localhost "$MEETING_API_PORT" "/"
check_port "transcription-collector" localhost "$TC_PORT" "/health"
check_redis localhost "$REDIS_PORT"
check_port "minio" localhost "${MINIO_PORT:-9010}" "/minio/health/live"

# ─── Step 3: Container env vars ──────────────────────────────────────────────
section "Container env vars"

check_container_var() {
  local container_filter="$1"
  local var_name="$2"
  local required="${3:-yes}"
  local cid
  cid=$(docker ps --filter "name=$container_filter" -q 2>/dev/null | head -1)
  if [[ -z "$cid" ]]; then
    fail "Container $container_filter not running"
    return
  fi
  local val
  val=$(docker exec "$cid" env 2>/dev/null | grep "^${var_name}=" | cut -d= -f2- || echo "")
  if [[ -n "$val" ]]; then
    pass "$container_filter: $var_name is set"
  elif [[ "$required" == "yes" ]]; then
    fail "$container_filter: $var_name is MISSING"
  else
    warn "$container_filter: $var_name is not set (optional)"
  fi
}

# agent-api critical vars
check_container_var "vexa-agentic-agent-api" BOT_API_TOKEN yes
check_container_var "vexa-agentic-agent-api" REDIS_URL yes
check_container_var "vexa-agentic-agent-api" RUNTIME_API_URL yes
check_container_var "vexa-agentic-agent-api" MINIO_ENDPOINT yes
check_container_var "vexa-agentic-agent-api" CLAUDE_CREDENTIALS_PATH yes
check_container_var "vexa-agentic-agent-api" CLAUDE_JSON_PATH yes

# runtime-api critical vars
check_container_var "vexa-agentic-runtime-api" REDIS_URL yes
check_container_var "vexa-agentic-runtime-api" DOCKER_NETWORK yes
check_container_var "vexa-agentic-runtime-api" BOT_API_TOKEN yes
check_container_var "vexa-agentic-runtime-api" MINIO_ENDPOINT yes

# meeting-api critical vars
check_container_var "vexa-agentic-meeting-api" REDIS_URL yes
check_container_var "vexa-agentic-meeting-api" DOCKER_NETWORK yes
check_container_var "vexa-agentic-meeting-api" ADMIN_TOKEN yes
check_container_var "vexa-agentic-meeting-api" TRANSCRIPTION_SERVICE_URL yes
check_container_var "vexa-agentic-meeting-api" MINIO_ENDPOINT yes

# admin-api
check_container_var "vexa-agentic-admin-api" ADMIN_API_TOKEN yes
check_container_var "vexa-agentic-admin-api" DB_HOST yes

# api-gateway
check_container_var "vexa-agentic-api-gateway" ADMIN_API_URL yes
check_container_var "vexa-agentic-api-gateway" MEETING_API_URL yes
check_container_var "vexa-agentic-api-gateway" REDIS_URL yes

# transcription-collector
check_container_var "vexa-agentic-transcription-collector" REDIS_HOST yes
check_container_var "vexa-agentic-transcription-collector" DB_HOST yes

# ─── Step 4: Token consistency check ─────────────────────────────────────────
section "Token consistency (must match across services)"

# BOT_API_TOKEN must be the same in agent-api, runtime-api, and compose .env
AGENT_API_CID=$(docker ps --filter "name=vexa-agentic-agent-api" -q 2>/dev/null | head -1)
RUNTIME_API_CID=$(docker ps --filter "name=vexa-agentic-runtime-api" -q 2>/dev/null | head -1)

if [[ -n "$AGENT_API_CID" && -n "$RUNTIME_API_CID" ]]; then
  TOKEN_AGENT=$(docker exec "$AGENT_API_CID" env 2>/dev/null | grep "^BOT_API_TOKEN=" | cut -d= -f2-)
  TOKEN_RUNTIME=$(docker exec "$RUNTIME_API_CID" env 2>/dev/null | grep "^BOT_API_TOKEN=" | cut -d= -f2-)
  TOKEN_ENV="${BOT_API_TOKEN:-}"

  if [[ "$TOKEN_AGENT" == "$TOKEN_RUNTIME" && "$TOKEN_AGENT" == "$TOKEN_ENV" ]]; then
    pass "BOT_API_TOKEN matches across agent-api, runtime-api, and .env"
  else
    fail "BOT_API_TOKEN MISMATCH: agent-api='${TOKEN_AGENT:0:20}...' runtime-api='${TOKEN_RUNTIME:0:20}...' .env='${TOKEN_ENV:0:20}...'"
    echo "      Fix: ensure all services use the same BOT_API_TOKEN from deploy/.env"
  fi
fi

# ADMIN_TOKEN: meeting-api ADMIN_TOKEN must match admin-api ADMIN_API_TOKEN
MEETING_API_CID=$(docker ps --filter "name=vexa-agentic-meeting-api" -q 2>/dev/null | head -1)
ADMIN_API_CID=$(docker ps --filter "name=vexa-agentic-admin-api" -q 2>/dev/null | head -1)

if [[ -n "$MEETING_API_CID" && -n "$ADMIN_API_CID" ]]; then
  TOKEN_MEETING=$(docker exec "$MEETING_API_CID" env 2>/dev/null | grep "^ADMIN_TOKEN=" | cut -d= -f2-)
  TOKEN_ADMIN=$(docker exec "$ADMIN_API_CID" env 2>/dev/null | grep "^ADMIN_API_TOKEN=" | cut -d= -f2-)

  if [[ "$TOKEN_MEETING" == "$TOKEN_ADMIN" ]]; then
    pass "ADMIN_TOKEN (meeting-api) matches ADMIN_API_TOKEN (admin-api)"
  else
    fail "ADMIN_TOKEN MISMATCH: meeting-api='$TOKEN_MEETING' admin-api='$TOKEN_ADMIN'"
  fi
fi

# Dashboard AGENT_API_TOKEN must match container BOT_API_TOKEN
DASHBOARD_ENV="/home/dima/dev/vexa-agentic-runtime/services/dashboard/.env"
if [[ -f "$DASHBOARD_ENV" ]]; then
  DASH_AGENT_TOKEN=$(grep "^AGENT_API_TOKEN=" "$DASHBOARD_ENV" | cut -d= -f2- | tr -d '"')
  CONTAINER_BOT_TOKEN="${BOT_API_TOKEN:-}"
  if [[ -n "$DASH_AGENT_TOKEN" && -n "$CONTAINER_BOT_TOKEN" ]]; then
    if [[ "$DASH_AGENT_TOKEN" == "$CONTAINER_BOT_TOKEN" ]]; then
      pass "Dashboard AGENT_API_TOKEN matches deploy/.env BOT_API_TOKEN"
    else
      fail "Dashboard AGENT_API_TOKEN does not match deploy/.env BOT_API_TOKEN"
      echo "      dashboard/.env AGENT_API_TOKEN='${DASH_AGENT_TOKEN:0:20}...'"
      echo "      deploy/.env BOT_API_TOKEN='${CONTAINER_BOT_TOKEN:0:20}...'"
    fi
  fi
fi

# ─── Step 5: Cross-service connectivity (inside containers) ──────────────────
section "Cross-service connectivity (inside containers)"

check_internal_reach() {
  local from_filter="$1"
  local label="$2"
  local url="$3"
  local cid
  cid=$(docker ps --filter "name=$from_filter" -q 2>/dev/null | head -1)
  if [[ -z "$cid" ]]; then
    warn "Container $from_filter not running — skipping connectivity check"
    return
  fi
  # Use Python (available in all service containers) for HTTP check
  local result
  result=$(docker exec "$cid" python3 -c "
import urllib.request, sys
try:
    r = urllib.request.urlopen('$url', timeout=3)
    print(r.status)
except Exception as e:
    print(f'ERR:{e}')
    sys.exit(1)
" 2>/dev/null || echo "ERR:exec failed")
  if [[ "$result" =~ ^[0-9]+$ ]]; then
    pass "$label ($from_filter → $url, HTTP $result)"
  else
    fail "$label ($from_filter → $url) UNREACHABLE: $result"
  fi
}

check_internal_redis() {
  local from_filter="$1"
  local cid
  cid=$(docker ps --filter "name=$from_filter" -q 2>/dev/null | head -1)
  if [[ -z "$cid" ]]; then
    warn "Container $from_filter not running"
    return
  fi
  local result
  result=$(docker exec "$cid" python3 -c "
import redis, sys
try:
    r = redis.from_url('redis://redis:6379')
    r.ping()
    print('OK')
except Exception as e:
    print(f'FAIL: {e}')
    sys.exit(1)
" 2>/dev/null || echo "FAIL: python not available")
  if [[ "$result" == "OK" ]]; then
    pass "$from_filter → redis:6379"
  else
    fail "$from_filter → redis:6379: $result"
  fi
}

check_internal_redis "vexa-agentic-agent-api"
check_internal_redis "vexa-agentic-runtime-api"
check_internal_redis "vexa-agentic-meeting-api"

check_internal_reach "vexa-agentic-agent-api" "agent-api → runtime-api" "http://runtime-api:8090/health"
check_internal_reach "vexa-agentic-meeting-api" "meeting-api → agent-api webhook" "http://agent-api:8100/health"
check_internal_reach "vexa-agentic-api-gateway" "api-gateway → admin-api" "http://admin-api:8001/"
check_internal_reach "vexa-agentic-api-gateway" "api-gateway → meeting-api" "http://meeting-api:8080/"
check_internal_reach "vexa-agentic-api-gateway" "api-gateway → transcription-collector" "http://transcription-collector:8000/health"

# ─── Step 6: Dashboard .env sanity ───────────────────────────────────────────
section "Dashboard .env sanity"

DASHBOARD_ENV="/home/dima/dev/vexa-agentic-runtime/services/dashboard/.env"
if [[ ! -f "$DASHBOARD_ENV" ]]; then
  fail "Dashboard .env not found at $DASHBOARD_ENV"
else
  check_env_in_file() {
    local file="$1"
    local var="$2"
    local required="${3:-yes}"
    if grep -q "^${var}=" "$file" 2>/dev/null; then
      pass "dashboard/.env: $var is set"
    elif [[ "$required" == "yes" ]]; then
      fail "dashboard/.env: $var is MISSING"
    else
      warn "dashboard/.env: $var is not set (optional)"
    fi
  }

  check_env_in_file "$DASHBOARD_ENV" VEXA_API_URL yes
  check_env_in_file "$DASHBOARD_ENV" VEXA_ADMIN_API_URL yes
  check_env_in_file "$DASHBOARD_ENV" VEXA_ADMIN_API_KEY yes
  check_env_in_file "$DASHBOARD_ENV" AGENT_API_URL yes
  check_env_in_file "$DASHBOARD_ENV" AGENT_API_TOKEN yes
  check_env_in_file "$DASHBOARD_ENV" NEXTAUTH_SECRET yes
  check_env_in_file "$DASHBOARD_ENV" JWT_SECRET yes
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────"
TOTAL=$((PASS + FAIL + WARN))
echo -e "Results: ${GREEN}$PASS PASS${NC}  ${RED}$FAIL FAIL${NC}  ${YELLOW}$WARN WARN${NC}  ($TOTAL checks)"
echo "────────────────────────────────────────"

if [[ $FAIL -gt 0 ]]; then
  echo -e "${RED}ENVIRONMENT NOT READY — fix failures above before delivering${NC}"
  echo "Reference: features/agentic-runtime/PORT-MAP.md"
  exit 1
elif [[ $WARN -gt 0 ]]; then
  echo -e "${YELLOW}ENVIRONMENT READY with warnings — review warnings above${NC}"
  exit 0
else
  echo -e "${GREEN}ENVIRONMENT READY — all checks pass${NC}"
  exit 0
fi
