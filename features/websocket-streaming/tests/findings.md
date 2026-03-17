# WebSocket Streaming Test Findings

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| WS connection established | 0 | Not tested | — | Connect to ws://host/ws, verify 101 upgrade |
| Subscribe to meeting | 0 | Not tested | — | Send subscribe message, verify acknowledgment |
| Live segments received | 0 | Not tested | — | Active meeting produces segments, verify they arrive |
| Segment format correct | 0 | Not tested | — | Check segment has text, speaker, timestamp |
| Multi-client fanout | 0 | Not tested | — | Two clients subscribe, both receive same segments |
