---
name: CaaS Platform Research
description: Comprehensive comparison of container-as-a-service platforms (Coder, DevPod, Gitpod, Sablier, Coolify, CapRover, Tsuru) for possible Runtime API evolution
type: reference
---

Research completed 2026-03-26. See findings at tests/findings.md or the researcher's detailed output.

Key takeaway: Sablier is the closest match for idle-management-only needs. Coder is the most complete but heaviest. Our Runtime API already covers 80% of what we need — the gap is webhooks/callbacks on lifecycle events, not container CRUD.
