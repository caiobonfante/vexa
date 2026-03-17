# MCP Integration Test Findings

## Certainty Table

| Check | Score | Evidence | Last checked | To reach 90+ |
|-------|-------|----------|-------------|--------------|
| MCP proxy reachable | 0 | Not tested | — | Send request to MCP endpoint, verify response |
| Tool call returns data | 0 | Not tested | — | Call list-meetings tool, verify meeting data |
| Error handling correct | 0 | Not tested | — | Call invalid tool, verify JSON-RPC error format |
| Auth enforced | 0 | Not tested | — | Call without token, verify 403 |
| End-to-end pipeline | 0 | Not tested | — | Full MCP tool call → meeting data response |
