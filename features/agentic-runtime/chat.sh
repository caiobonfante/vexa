#!/bin/bash
# Interactive chat with a Vexa agent container
# Usage: ./chat.sh [user_id]
API="http://localhost:8100"
USER="${1:-dima}"

echo "Vexa Agent Chat (user: $USER)"
echo "Type a message and press Enter. Ctrl+C to quit."
echo "---"

while true; do
  printf "\nyou> "
  read -r MSG
  [ -z "$MSG" ] && continue

  printf "\nagent> "
  curl -sf -N -X POST "$API/api/chat" \
    -H 'Content-Type: application/json' \
    -d "$(printf '{"user_id":"%s","message":"%s"}' "$USER" "$(echo "$MSG" | sed 's/"/\\"/g')")" 2>/dev/null | \
  python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line or not line.startswith('data: '): continue
    try:
        d = json.loads(line[6:])
        t = d.get('type','')
        if t == 'text_delta':
            print(d.get('text',''), end='', flush=True)
        elif t == 'tool_use':
            print(f\"\n  [{d.get('tool')}: {d.get('summary','')}]\", flush=True)
        elif t in ('done', 'stream_end'):
            break
        elif t == 'error':
            print(f\"\n  ERROR: {d.get('message','')}\", flush=True)
            break
    except: pass
print()
"
done
