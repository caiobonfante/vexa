---
name: OSS Extraction Playbook
description: Complete research on extracting Runtime API as standalone open-source CaaS — patterns, repo structure, API design, dependency direction, governance, stripping checklist
type: project
---

# OSS Extraction Playbook for Runtime API

Comprehensive research across 6 dimensions, synthesized from 20+ real-world extraction case studies.

## Key Recommendations Summary

1. **Extraction strategy**: Separate repo from day 1 + PyPI package (Django model)
2. **Repo structure**: Standalone repo, NOT monorepo/subtree/submodule
3. **API abstraction**: Three-layer architecture (Core → Profiles → Domain Services)
4. **Dependency direction**: Microservice (Pattern 2) + Upstream-First (Pattern 5)
5. **Governance**: BDFL + Apache 2.0 + DCO + Contributor Covenant
6. **Stripping**: Auth → Protocol, Profiles → config file, env injection → caller responsibility

## Sources

See individual research files:
- research_oss_extraction_case_studies.md — 6 company case studies
- research_oss_repo_structure_extraction.md — Repo structure tradeoffs
- research_api_extraction_patterns.md — API surface design
- research_oss_consumption_patterns.md — Dependency direction patterns
- (governance and stripping research inline in this file)
