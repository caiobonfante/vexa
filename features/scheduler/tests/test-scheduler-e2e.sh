#!/bin/bash
# Scheduler end-to-end tests.
#
# Tests job scheduling, execution, cancellation, retry, and idempotency
# against a live Redis instance. Starts a temporary HTTP receiver to
# verify that scheduled jobs actually fire.
#
# Tests:
#   schedule     — schedule a job, verify it fires
#   cancel       — schedule then cancel, verify it doesn't fire
#   retry        — schedule job to failing endpoint, verify retries
#   idempotency  — schedule same idempotency_key twice, verify one job
#   all          — run all tests
#
# Prerequisites:
#   - Redis running (REDIS_URL)
#   - Python 3 with redis package
#
# Usage:
#   ./test-scheduler-e2e.sh all
#   REDIS_URL=redis://localhost:6379 ./test-scheduler-e2e.sh schedule

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$DIR/../.env"
RESULTS="$DIR/results/run-$(date +%Y-%m-%d-%H%M%S)"

source "$ENV_FILE" 2>/dev/null || true

REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
RECEIVER_PORT=9998
CMD="${1:-all}"

mkdir -p "$RESULTS"

PASS=0
FAIL=0

log() { echo "[$(date +%H:%M:%S)] $*"; }

# ─── Helpers ──────────────────────────────────────────────────────────────────

start_receiver() {
  local port=$1 log_file=$2
  python3 -c "
import http.server, json, datetime
LOG = '$log_file'
open(LOG, 'w').close()
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        l = int(self.headers.get('Content-Length', 0))
        b = self.rfile.read(l).decode() if l > 0 else ''
        with open(LOG, 'a') as f:
            f.write(json.dumps({'ts': datetime.datetime.now().isoformat(), 'path': self.path, 'body': json.loads(b) if b else None}) + '\n')
        self.send_response(200); self.end_headers(); self.wfile.write(b'{\"ok\":true}')
    def log_message(self, *a): pass
http.server.HTTPServer(('0.0.0.0', $port), H).serve_forever()
" &
  echo $!
}

start_failing_receiver() {
  local port=$1 log_file=$2
  python3 -c "
import http.server, json, datetime
LOG = '$log_file'
open(LOG, 'w').close()
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        l = int(self.headers.get('Content-Length', 0))
        b = self.rfile.read(l).decode() if l > 0 else ''
        with open(LOG, 'a') as f:
            f.write(json.dumps({'ts': datetime.datetime.now().isoformat(), 'path': self.path}) + '\n')
        self.send_response(500); self.end_headers(); self.wfile.write(b'{\"error\":\"fail\"}')
    def log_message(self, *a): pass
http.server.HTTPServer(('0.0.0.0', $port), H).serve_forever()
" &
  echo $!
}

cleanup_redis() {
  python3 -c "
import redis
r = redis.from_url('$REDIS_URL')
for key in r.keys('scheduler:*'):
    r.delete(key)
" 2>/dev/null
}

run_executor_for() {
  local seconds=$1
  python3 -c "
import asyncio, redis.asyncio as aioredis
from shared_models.scheduler_worker import start_executor, stop_executor

async def run():
    r = aioredis.from_url('$REDIS_URL')
    task = asyncio.create_task(start_executor(r))
    await asyncio.sleep($seconds)
    await stop_executor()
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass
    await r.close()

asyncio.run(run())
" 2>/dev/null
}

schedule_job() {
  local execute_at=$1 url=$2 idem_key=${3:-}
  python3 -c "
import asyncio, json, redis.asyncio as aioredis
from shared_models.scheduler import schedule_job

async def run():
    r = aioredis.from_url('$REDIS_URL')
    spec = {
        'execute_at': $execute_at,
        'request': {'method': 'POST', 'url': '$url', 'body': {'test': True}},
        'retry': {'max_attempts': 2, 'backoff': [2, 5], 'attempt': 0},
        'metadata': {'source': 'e2e-test'},
    }
    idem = '$idem_key'
    if idem:
        spec['idempotency_key'] = idem
    job = await schedule_job(r, spec)
    print(json.dumps({'job_id': job['job_id'], 'status': job['status']}))
    await r.close()

asyncio.run(run())
" 2>/dev/null
}

cancel_job_by_id() {
  local job_id=$1
  python3 -c "
import asyncio, json, redis.asyncio as aioredis
from shared_models.scheduler import cancel_job

async def run():
    r = aioredis.from_url('$REDIS_URL')
    result = await cancel_job(r, '$job_id')
    print(json.dumps({'cancelled': result is not None}))
    await r.close()

asyncio.run(run())
" 2>/dev/null
}

count_pending() {
  python3 -c "
import redis
r = redis.from_url('$REDIS_URL')
print(r.zcard('scheduler:jobs'))
" 2>/dev/null
}

# ─── Schedule test ────────────────────────────────────────────────────────────

run_schedule() {
  log "=== Schedule test: job fires at target time ==="
  cleanup_redis

  local recv_log="$RESULTS/schedule-received.jsonl"
  local recv_pid
  recv_pid=$(start_receiver $RECEIVER_PORT "$recv_log")
  sleep 1

  # Schedule a job to fire in 2 seconds
  local now
  now=$(python3 -c "import time; print(int(time.time()) + 2)")
  local job_json
  job_json=$(schedule_job "$now" "http://localhost:$RECEIVER_PORT/scheduled-job")
  local job_id
  job_id=$(echo "$job_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
  log "  Scheduled job $job_id for $(date -d @$now +%H:%M:%S)"

  # Run executor for 10 seconds
  run_executor_for 10 &
  local exec_pid=$!
  wait $exec_pid 2>/dev/null || true

  # Check if receiver got the request
  local count
  count=$(wc -l < "$recv_log" 2>/dev/null | tr -d ' ')
  if [ "${count:-0}" -ge 1 ]; then
    log "  PASS: job fired — receiver got $count request(s)"
    PASS=$((PASS + 1))
  else
    log "  FAIL: job did not fire — receiver got 0 requests"
    FAIL=$((FAIL + 1))
  fi

  kill $recv_pid 2>/dev/null
  cleanup_redis
}

# ─── Cancel test ──────────────────────────────────────────────────────────────

run_cancel() {
  log "=== Cancel test: cancelled job doesn't fire ==="
  cleanup_redis

  local recv_log="$RESULTS/cancel-received.jsonl"
  local recv_pid
  recv_pid=$(start_receiver $RECEIVER_PORT "$recv_log")
  sleep 1

  # Schedule a job for 3 seconds from now
  local now
  now=$(python3 -c "import time; print(int(time.time()) + 3)")
  local job_json
  job_json=$(schedule_job "$now" "http://localhost:$RECEIVER_PORT/should-not-fire")
  local job_id
  job_id=$(echo "$job_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
  log "  Scheduled job $job_id"

  # Cancel immediately
  cancel_job_by_id "$job_id"
  log "  Cancelled job $job_id"

  # Verify it's removed from queue
  local pending
  pending=$(count_pending)
  if [ "$pending" -eq 0 ]; then
    log "  PASS: job removed from queue (pending=$pending)"
    PASS=$((PASS + 1))
  else
    log "  FAIL: job still in queue (pending=$pending)"
    FAIL=$((FAIL + 1))
  fi

  # Run executor briefly to confirm it doesn't fire
  run_executor_for 6 &
  wait $! 2>/dev/null || true

  local count
  count=$(wc -l < "$recv_log" 2>/dev/null | tr -d ' ')
  if [ "${count:-0}" -eq 0 ]; then
    log "  PASS: cancelled job did not fire"
    PASS=$((PASS + 1))
  else
    log "  FAIL: cancelled job still fired ($count requests)"
    FAIL=$((FAIL + 1))
  fi

  kill $recv_pid 2>/dev/null
  cleanup_redis
}

# ─── Idempotency test ─────────────────────────────────────────────────────────

run_idempotency() {
  log "=== Idempotency test: same key → one job ==="
  cleanup_redis

  local now
  now=$(python3 -c "import time; print(int(time.time()) + 60)")

  local job1 job2 id1 id2
  job1=$(schedule_job "$now" "http://localhost:$RECEIVER_PORT/idem" "test_idem_key_123")
  job2=$(schedule_job "$now" "http://localhost:$RECEIVER_PORT/idem" "test_idem_key_123")

  id1=$(echo "$job1" | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
  id2=$(echo "$job2" | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")

  if [ "$id1" = "$id2" ]; then
    log "  PASS: same idempotency_key returned same job_id ($id1)"
    PASS=$((PASS + 1))
  else
    log "  FAIL: different job_ids ($id1 vs $id2)"
    FAIL=$((FAIL + 1))
  fi

  local pending
  pending=$(count_pending)
  if [ "$pending" -eq 1 ]; then
    log "  PASS: only 1 job in queue"
    PASS=$((PASS + 1))
  else
    log "  FAIL: $pending jobs in queue (expected 1)"
    FAIL=$((FAIL + 1))
  fi

  cleanup_redis
}

# ─── Retry test ───────────────────────────────────────────────────────────────

run_retry() {
  log "=== Retry test: failed job retries ==="
  cleanup_redis

  local recv_log="$RESULTS/retry-received.jsonl"
  local recv_pid
  recv_pid=$(start_failing_receiver $RECEIVER_PORT "$recv_log")
  sleep 1

  # Schedule a job to fire now (will fail because receiver returns 500)
  local now
  now=$(python3 -c "import time; print(int(time.time()) + 1)")
  local job_json
  job_json=$(schedule_job "$now" "http://localhost:$RECEIVER_PORT/will-fail")
  log "  Scheduled job (target returns 500)"

  # Run executor for 15 seconds (enough for first attempt + one retry at 2s backoff)
  run_executor_for 15 &
  wait $! 2>/dev/null || true

  local count
  count=$(wc -l < "$recv_log" 2>/dev/null | tr -d ' ')
  if [ "${count:-0}" -ge 2 ]; then
    log "  PASS: job retried — receiver got $count attempts (expected >=2)"
    PASS=$((PASS + 1))
  else
    log "  FAIL: job did not retry — receiver got $count attempts (expected >=2)"
    FAIL=$((FAIL + 1))
  fi

  kill $recv_pid 2>/dev/null
  cleanup_redis
}

# ─── Main ─────────────────────────────────────────────────────────────────────

case "$CMD" in
  schedule)     run_schedule ;;
  cancel)       run_cancel ;;
  idempotency)  run_idempotency ;;
  retry)        run_retry ;;
  all)          run_schedule; run_cancel; run_idempotency; run_retry ;;
  *)            echo "Unknown command: $CMD"; exit 1 ;;
esac

echo ""
log "Results: PASS=$PASS FAIL=$FAIL"
log "Output: $RESULTS"
[ "$FAIL" -eq 0 ] || exit 1
