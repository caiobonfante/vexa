# Feature Log

## 2026-03-24

[STAGE] Feature created — extracted from features/agentic-runtime/workspaces/. Now a standalone feature with its own README, CLAUDE.md, and gate.

[OBSERVE] Knowledge template exists and is comprehensive (ported from Quorum). Agent chat with workspace context works via Telegram and dashboard. MinIO persistence verified. But no code connects meetings → workspace knowledge graph. Entity extraction, wiki-linking, and timeline population are all manual (agent does it if instructed, but no automated pipeline).

[DECIDE] Priority: git-backed workspaces (safety net for compaction), then workspace index injection (agent awareness each turn), then entity extraction from transcripts (the killer feature).

[STATUS] Confidence 60. Template + persistence + agent chat working. Entity extraction, git, index injection, scripts not started.
