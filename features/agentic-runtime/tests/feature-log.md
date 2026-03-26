# Feature Log — Agentic Runtime

## 2026-03-24

[BUG] Redis pub/sub payload mismatch between bot-manager publisher and agent-api subscriber.
  bot-manager publishes nested: {meeting: {id, platform}, payload: {status}, ts}
  agent-api reads flat: data.status, data.meeting_id, data.user_id
  Result: subscriber silently drops ALL meeting events. Status always "", user_id always "".
  Additionally: user_id is not included in bot-manager's published payload at all.
  Files: services/bot-manager/app/main.py:226, services/agent-api/app/main.py:175
  Impact: MVP1 "meeting started" and "meeting completed" Redis notifications are dead code.
  The webhook path (POST_MEETING_HOOKS) works for completed events only.

[EXTERNAL] Two notification paths exist for meeting.completed: Redis pub/sub subscriber + POST_MEETING_HOOKS webhook.
  Risk of duplicate processing if both are active. Need deduplication or single path.
