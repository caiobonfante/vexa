#!/bin/bash
# Simple webhook receiver — logs incoming POSTs to a file.
#
# Usage:
#   ./webhook-receiver.sh                  # default port 9999
#   WEBHOOK_RECEIVER_PORT=8888 ./webhook-receiver.sh

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${WEBHOOK_RECEIVER_PORT:-9999}"
LOG="$DIR/results/received-webhooks.jsonl"

mkdir -p "$DIR/results"
> "$LOG"

echo "Webhook receiver listening on :$PORT"
echo "Logging to: $LOG"
echo "Press Ctrl+C to stop"
echo ""

python3 -c "
import http.server, json, sys, datetime

LOG = '$LOG'
PORT = $PORT

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode() if length > 0 else ''
        ts = datetime.datetime.now().isoformat()

        entry = {
            'timestamp': ts,
            'path': self.path,
            'headers': dict(self.headers),
            'body': json.loads(body) if body else None
        }

        with open(LOG, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        sig = self.headers.get('X-Webhook-Signature', 'none')
        print(f'[{ts}] POST {self.path} ({length} bytes) sig={sig[:30]}...')
        if body:
            try:
                parsed = json.loads(body)
                event_type = parsed.get('event_type', parsed.get('event', '?'))
                print(f'  event_type: {event_type}')
                meeting = parsed.get('meeting', {})
                if meeting:
                    print(f'  meeting: id={meeting.get(\"id\")}, status={meeting.get(\"status\")}')
            except: pass

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{\"ok\": true}')

    def log_message(self, format, *args):
        pass  # suppress default logging

server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
server.serve_forever()
"
