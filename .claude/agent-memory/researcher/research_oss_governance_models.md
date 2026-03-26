---
name: OSS Governance Models for Small Projects
description: Governance models (BDFL, company-controlled, foundation), CONTRIBUTING.md patterns, CoC, CLA vs DCO, and foundation donation — practical recommendations for a 1-2 person team extracting a ~764 line Python project
type: project
---

# Open Source Governance Models Research (March 2026)

**Why:** Informing governance setup for vexa-agentic-runtime open-source extraction. A ~764 line Python CaaS tool needs the right governance scaffolding to accept contributions without creating overhead.

**How to apply:** Use the tiered recommendations below — start with Tier 1 (launch day), add Tier 2 when community arrives, consider Tier 3 only at 1000+ stars.

## Full analysis delivered in conversation on 2026-03-26.

Key conclusions:
1. BDFL model is correct for 0-100 stars; formalize governance only when you have 3+ regular contributors
2. Apache 2.0 is the right license for a CaaS tool (patent protection, enterprise-friendly, E2B/K8s/Docker precedent)
3. DCO over CLA for small projects — lower friction, `git commit -s` is enough
4. Contributor Covenant 2.1 (or 3.0) as Code of Conduct — industry standard, adopted by 9/10 largest OSS projects
5. Don't apply to CNCF/foundations until you have real traction (sandbox has no minimum stars but needs cloud-native fit and velocity)
6. E2B's CONTRIBUTING.md is just one paragraph; Temporal's is detailed and process-heavy — target something in between
7. GitHub's Minimum Viable Governance (MVG) framework is the right starting template
