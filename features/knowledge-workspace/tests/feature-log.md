# Feature Log

## 2026-03-24

[STAGE] Feature created — extracted from features/agentic-runtime/workspaces/. Now a standalone feature with its own README, CLAUDE.md, and gate.

[OBSERVE] Knowledge template exists and is comprehensive (ported from Quorum). Agent chat with workspace context works via Telegram and dashboard. MinIO persistence verified. But no code connects meetings → workspace knowledge graph. Entity extraction, wiki-linking, and timeline population are all manual (agent does it if instructed, but no automated pipeline).

[DECIDE] Priority: git-backed workspaces (safety net for compaction), then workspace index injection (agent awareness each turn), then entity extraction from transcripts (the killer feature).

[STATUS] Confidence 60. Template + persistence + agent chat working. Entity extraction, git, index injection, scripts not started.

## 2026-03-25

[EXTERNAL] Granola approach: entity graph built from meeting attendees via calendar integration + transcript NER. Key insight: people entities anchored to calendar contacts, not just transcript speaker names. Source: Granola product docs and reviews.

[EXTERNAL] tl;dv "Library" feature: tracks people/companies across meetings with searchable context. Each entity page shows all meetings they appeared in. Implementation: two-pass extraction (1. raw NER, 2. dedup against existing). Source: tl;dv docs.

[EXTERNAL] OpenClaw SOUL.md/MEMORY.md pattern (direct inspiration for this workspace): entity files are created by the agent itself via LLM prompting, not by a separate extraction service. The "extraction" IS the agent writing files. Source: OpenClaw repo.

[RESEARCH] Trigger mechanism is ALREADY WIRED — `POST /internal/webhooks/meeting-completed` at `services/agent-api/app/main.py:473`. Bot-manager calls this after meeting ends. The agent runs `_run_chat_turn(user_id, message)`. The gap is NOT in plumbing — it's that the message is too vague and the workspace CLAUDE.md has no entity file format specification.

[RESEARCH] Transcript format from `vexa meeting transcript {id}`: flat text, one line per segment: `Speaker Name: text content`. No timestamps, no confidence scores. Sufficient for entity extraction.

[RESEARCH] Entity directories already exist in template (as .gitkeep): contacts/, companies/, products/, meetings/, action-items/. Zero seed files — agent creates on first extraction.

[DECIDE] Two-file fix to reach score 30→60:
  1. Strengthen webhook message in main.py (both endpoints) with explicit step-by-step extraction protocol
  2. Add "Knowledge Extraction" section to workspace CLAUDE.md with entity file format templates
  No new services, no new APIs — the agent IS the extraction pipeline.

[PRACTICE] Entity extraction in this architecture = better prompting, not new code. The agent (Claude Code in container) writes files. The trigger is the webhook. The format is markdown. Keep it simple.
