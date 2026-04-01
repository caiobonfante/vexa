# Feature Log — Agentic Runtime

## 2026-03-24

[BUG] Redis pub/sub payload mismatch between meeting-api publisher and agent-api subscriber.
  meeting-api publishes nested: {meeting: {id, platform}, payload: {status}, ts}
  agent-api reads flat: data.status, data.meeting_id, data.user_id
  Result: subscriber silently drops ALL meeting events. Status always "", user_id always "".
  Additionally: user_id is not included in meeting-api's published payload at all.
  Files: services/meeting-api/meeting_api/meetings.py, services/agent-api/app/main.py:175
  Impact: MVP1 "meeting started" and "meeting completed" Redis notifications are dead code.
  The webhook path (POST_MEETING_HOOKS) works for completed events only.

[EXTERNAL] Two notification paths exist for meeting.completed: Redis pub/sub subscriber + POST_MEETING_HOOKS webhook (from meeting-api).
  Risk of duplicate processing if both are active. Need deduplication or single path.
