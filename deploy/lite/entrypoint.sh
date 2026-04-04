#!/bin/bash
# =============================================================================
# Vexa Lite - Container Entrypoint
# =============================================================================
# 1. Waits for external services (PostgreSQL, Redis)
# 2. Initializes database schema
# 3. Starts all services via supervisord
# =============================================================================

set -e

echo "=============================================="
echo "  Vexa Lite - Starting Container"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# Environment Setup
# -----------------------------------------------------------------------------

# Redis configuration - supports REDIS_URL or individual vars
USE_INTERNAL_REDIS=false
if [ -z "$REDIS_HOST" ] || [ "$REDIS_HOST" = "localhost" ] || [ "$REDIS_HOST" = "127.0.0.1" ]; then
    USE_INTERNAL_REDIS=true
    export REDIS_HOST="localhost"
    export REDIS_PORT="${REDIS_PORT:-6379}"
    export REDIS_USER=""
    export REDIS_PASSWORD=""
    export REDIS_URL="redis://localhost:${REDIS_PORT}/0"
elif [ -n "$REDIS_URL" ]; then
    REDIS_URL_NO_SCHEME="${REDIS_URL#*://}"
    if [[ "$REDIS_URL_NO_SCHEME" == *"@"* ]]; then
        REDIS_AUTH="${REDIS_URL_NO_SCHEME%%@*}"
        REDIS_HOSTPORTDB="${REDIS_URL_NO_SCHEME#*@}"
        if [[ "$REDIS_AUTH" == *":"* ]]; then
            export REDIS_USER="${REDIS_AUTH%%:*}"
            export REDIS_PASSWORD="${REDIS_AUTH#*:}"
        else
            export REDIS_USER="$REDIS_AUTH"
            export REDIS_PASSWORD=""
        fi
    else
        REDIS_HOSTPORTDB="$REDIS_URL_NO_SCHEME"
        export REDIS_USER=""
        export REDIS_PASSWORD=""
    fi
    REDIS_HOSTPORT="${REDIS_HOSTPORTDB%%/*}"
    export REDIS_HOST="${REDIS_HOSTPORT%%:*}"
    export REDIS_PORT="${REDIS_HOSTPORT#*:}"
else
    export REDIS_HOST="${REDIS_HOST:-localhost}"
    export REDIS_PORT="${REDIS_PORT:-6379}"
    export REDIS_USER=""
    export REDIS_PASSWORD=""
    export REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}/0"
fi

# Database configuration
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-vexa}"
export DB_USER="${DB_USER:-postgres}"
export DB_PASSWORD="${DB_PASSWORD:-}"

if [ -z "$DATABASE_URL" ]; then
    if [ -n "$DB_PASSWORD" ]; then
        export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    else
        export DATABASE_URL="postgresql://${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    fi
else
    export DATABASE_URL="${DATABASE_URL/postgres:\/\//postgresql:\/\/}"
    DB_URL_BASE="${DATABASE_URL%%\?*}"
    DB_URL_NO_SCHEME="${DB_URL_BASE#*://}"
    DB_USERPASS="${DB_URL_NO_SCHEME%%@*}"
    DB_HOSTPORTDB="${DB_URL_NO_SCHEME#*@}"
    if [[ "$DB_USERPASS" == *":"* ]]; then
        export DB_USER="${DB_USERPASS%%:*}"
        export DB_PASSWORD="${DB_USERPASS#*:}"
    else
        export DB_USER="$DB_USERPASS"
    fi
    DB_HOSTPORT="${DB_HOSTPORTDB%%/*}"
    export DB_NAME="${DB_HOSTPORTDB#*/}"
    if [[ "$DB_HOSTPORT" == *":"* ]]; then
        export DB_HOST="${DB_HOSTPORT%%:*}"
        export DB_PORT="${DB_HOSTPORT#*:}"
    else
        export DB_HOST="$DB_HOSTPORT"
    fi
    if [[ "$DATABASE_URL" == *"sslmode="* ]]; then
        SSL_MODE_PARAM="${DATABASE_URL##*sslmode=}"
        SSL_MODE_PARAM="${SSL_MODE_PARAM%%&*}"
        export DB_SSL_MODE="$SSL_MODE_PARAM"
    fi
fi

export DB_SSL_MODE="${DB_SSL_MODE:-disable}"
export LOG_LEVEL="${LOG_LEVEL:-info}"
export DISPLAY="${DISPLAY:-:99}"

echo "Configuration:"
echo "  - Redis URL: ${REDIS_URL}"
echo "  - Database URL: ${DATABASE_URL}"
echo "  - Database SSL Mode: ${DB_SSL_MODE}"
echo "  - Transcriber URL: ${TRANSCRIBER_URL:-NOT SET}"
echo "  - Log Level: ${LOG_LEVEL}"
echo "  - Storage Backend: ${STORAGE_BACKEND:-local}"
echo ""

# -----------------------------------------------------------------------------
# Wait for PostgreSQL
# -----------------------------------------------------------------------------

if [ -n "$DB_HOST" ] && [ "$DB_HOST" != "localhost" ]; then
    echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
    max_attempts=30
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q 2>/dev/null; then
            echo "PostgreSQL is ready!"
            break
        fi
        attempt=$((attempt + 1))
        echo "  Attempt $attempt/$max_attempts - PostgreSQL not ready, waiting..."
        sleep 2
    done
    if [ $attempt -eq $max_attempts ]; then
        echo "WARNING: Could not connect to PostgreSQL after $max_attempts attempts"
    fi
    echo ""
fi

# -----------------------------------------------------------------------------
# Setup Internal Redis (if using localhost)
# -----------------------------------------------------------------------------

if [ "$USE_INTERNAL_REDIS" = "true" ]; then
    echo "Using internal Redis server..."
    mkdir -p /var/lib/redis /var/run/redis
    chmod 755 /var/lib/redis /var/run/redis
    echo ""
else
    echo "Waiting for external Redis at ${REDIS_HOST}:${REDIS_PORT}..."
    max_attempts=30
    attempt=0
    REDIS_CLI_CMD="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
    if [ -n "$REDIS_PASSWORD" ]; then
        REDIS_CLI_CMD="$REDIS_CLI_CMD -a $REDIS_PASSWORD --no-auth-warning"
    fi
    while [ $attempt -lt $max_attempts ]; do
        if $REDIS_CLI_CMD ping 2>/dev/null | grep -q PONG; then
            echo "Redis is ready!"
            break
        fi
        attempt=$((attempt + 1))
        echo "  Attempt $attempt/$max_attempts - Redis not ready, waiting..."
        sleep 2
    done
    if [ $attempt -eq $max_attempts ]; then
        echo "WARNING: Could not connect to Redis after $max_attempts attempts"
    fi
    echo ""
fi

# -----------------------------------------------------------------------------
# Database Schema Initialization
# -----------------------------------------------------------------------------

echo "Initializing database schema..."
if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q 2>/dev/null; then
    # Use schema-sync ensure_schema() — handles both fresh and existing databases
    cd /app/meeting-api
    python3 -c "
import asyncio
import sys
sys.path.insert(0, '/app/admin-models')
sys.path.insert(0, '/app/schema-sync')
from meeting_api.database import init_db
asyncio.run(init_db())
print('Database schema initialized')
" 2>&1 || echo "  WARNING: Schema initialization failed (may already be up to date)"
    cd /app
else
    echo "  WARNING: Database not accessible, skipping schema init"
fi
echo ""

# -----------------------------------------------------------------------------
# Verify Database Connection
# -----------------------------------------------------------------------------

echo "Verifying database connection..."
if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q 2>/dev/null; then
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -c "SELECT 1;" >/dev/null 2>&1; then
        echo "  Database connection successful"
    else
        echo "  ERROR: Cannot connect to database '$DB_NAME'"
        exit 1
    fi
else
    echo "  ERROR: PostgreSQL server at $DB_HOST:$DB_PORT is not reachable"
    exit 1
fi
echo ""

# -----------------------------------------------------------------------------
# Verify Transcription Service
# -----------------------------------------------------------------------------

echo "Verifying transcription service..."
TRANSCRIBER_URL="${TRANSCRIBER_URL:-${REMOTE_TRANSCRIBER_URL:-}}"
TRANSCRIBER_API_KEY="${TRANSCRIBER_API_KEY:-${REMOTE_TRANSCRIBER_API_KEY:-}}"

if [ -z "$TRANSCRIBER_URL" ]; then
    echo "  WARNING: TRANSCRIBER_URL is not set — transcription will not work"
    echo "  Set TRANSCRIBER_URL and TRANSCRIBER_API_KEY for transcription"
elif [ "${SKIP_TRANSCRIPTION_CHECK:-false}" = "true" ]; then
    echo "  Skipping transcription connectivity check (SKIP_TRANSCRIPTION_CHECK=true)"
else
    if [[ "$TRANSCRIBER_URL" =~ ^(https?://[^/]+) ]]; then
        BASE_URL="${BASH_REMATCH[1]}"
        if curl -s -f --max-time 5 "$BASE_URL/health" >/dev/null 2>&1 || \
           curl -s -f --max-time 5 "$BASE_URL" >/dev/null 2>&1; then
            echo "  Transcription service reachable at $BASE_URL"
        else
            echo "  WARNING: Cannot reach transcription service at $BASE_URL"
            echo "  Container will start anyway — set SKIP_TRANSCRIPTION_CHECK=true to suppress"
        fi
    fi
fi
echo ""

# -----------------------------------------------------------------------------
# PulseAudio & ALSA Configuration
# -----------------------------------------------------------------------------

echo "Configuring PulseAudio and ALSA..."
cat > /root/.asoundrc <<'ALSA_EOF'
pcm.!default {
    type pulse
}
ctl.!default {
    type pulse
}
ALSA_EOF

cat > /usr/local/bin/setup-pulseaudio-sinks.sh <<'PA_EOF'
#!/bin/bash
for i in $(seq 1 15); do
    if pactl info >/dev/null 2>&1; then break; fi
    sleep 1
done
if ! pactl info >/dev/null 2>&1; then
    echo "[PulseAudio Setup] ERROR: PulseAudio not available after 15s"
    exit 1
fi
pactl load-module module-null-sink sink_name=zoom_sink sink_properties=device.description="ZoomAudioSink" 2>/dev/null || true
pactl load-module module-null-sink sink_name=tts_sink sink_properties=device.description="TTSAudioSink" 2>/dev/null || true
pactl load-module module-remap-source master=tts_sink.monitor source_name=virtual_mic source_properties=device.description="VirtualMicrophone" 2>/dev/null || true
pactl set-default-source virtual_mic 2>/dev/null || true
echo "[PulseAudio Setup] Done"
PA_EOF
chmod +x /usr/local/bin/setup-pulseaudio-sinks.sh
echo "  Done"
echo ""

# -----------------------------------------------------------------------------
# Create Required Directories
# -----------------------------------------------------------------------------

mkdir -p /var/log/supervisor /var/log/vexa-bots /var/run /var/lib/redis /var/run/redis
chmod 755 /var/lib/redis /var/run/redis
mkdir -p "${LOCAL_STORAGE_DIR:-/var/lib/vexa/recordings}"
mkdir -p /var/lib/vexa/recordings/spool

# -----------------------------------------------------------------------------
# Start Services
# -----------------------------------------------------------------------------

echo "=============================================="
echo "  Starting Vexa Services via Supervisor"
echo "=============================================="
echo ""
echo "Service Endpoints:"
echo "  - API Gateway:    http://localhost:8056"
echo "  - Admin API:      http://localhost:8057"
echo "  - Meeting API:    http://localhost:8080"
echo "  - Runtime API:    http://localhost:8090"
echo "  - Agent API:      http://localhost:8100"
echo "  - Dashboard:      http://localhost:3000"
echo "  - API Docs:       http://localhost:8056/docs"
echo ""

exec "$@"
