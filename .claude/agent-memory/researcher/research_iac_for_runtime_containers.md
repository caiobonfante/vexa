---
name: IaC tools for runtime container management
description: Research on Pulumi Automation API and CDKTF for on-demand Docker container creation — verdict is neither is suitable for low-latency runtime use
type: project
---

Evaluated 2026-03-26 for the runtime-api container orchestration layer.

**Verdict: IaC tools add significant overhead and complexity for this use case. Direct Docker API (current approach) is correct.**

**Why:** Pulumi minimum operation time is ~4s even for trivial stacks. Current direct Docker API calls are <100ms. CDKTF is deprecated (Dec 2025).

**How to apply:** Do not adopt Pulumi or CDKTF for the runtime-api container lifecycle. If Kubernetes migration happens later, evaluate Pulumi for cluster provisioning (deploy-time), but not for on-demand pod creation (use kubernetes Python client directly).
