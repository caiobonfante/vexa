# Mission

Focus: meeting-aware-agent
Problem: agent has no knowledge of user's active meetings — users must manually ask or paste meeting IDs
Target: gateway injects active meeting context into agent-api, agent responds with meeting awareness. Score >= 90: real meeting with bot + Telegram chat where agent knows what's happening in the meeting without being told.
Stop-when: target met OR 5 iterations
Constraint: gateway owns injection — agent-api never calls meeting-api. Use existing endpoints. No new database tables. meeting_aware is per-session flag. After code changes, rebuild and restart affected containers before testing.
