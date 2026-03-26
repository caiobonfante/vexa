---
name: COSS Business Models Research
description: Comprehensive COSS research — 9 company case studies, licensing comparison, timing/risks analysis, and FSL recommendation for Runtime API extraction
type: project
---

# COSS Business Models for Infrastructure Tools (March 2026)

**Why:** Informing licensing, monetization, and timing decisions for extracting Runtime API as standalone open-source project.

**How to apply:** Use specific patterns when deciding what to open-source vs keep proprietary, license choice, and go-to-market timing.

## Key Finding: License on Day One, Never Change It

Industry pattern 2018-2025: permissive→restrictive→fork→reverse to AGPL (too late). Fork playbook now well-rehearsed — Valkey forked Redis within days.

## Two Credible License Options for New Infra (2026)

1. **AGPL v3** — OSI-approved, network copyleft prevents cloud wrapping. Grafana/Redis/Elastic converged here. Some enterprise legal depts ban it.
2. **FSL (Functional Source License)** — Sentry's creation. Non-compete only, converts to Apache-2.0 after 2 years. Standardized. ~10 adopters (Sentry $100M ARR, GitButler, Codecov, Liquibase).

**Avoid:** SSPL (Redis/Elastic reversed), BSL (FSL strictly better), starting permissive with plan to switch.

## Recommendation: FSL for Runtime API

- Non-compete prevents competitors from wrapping as competing service
- Zero copyleft friction (unlike AGPL)
- 2-year sunset to Apache-2.0 builds trust
- Open: generic CaaS, orchestration, profiles, lifecycle
- Commercial: meeting intelligence, managed cloud, enterprise support

## Company Case Studies Summary

| Company | License | Model | Scale | Verdict |
|---------|---------|-------|-------|---------|
| Grafana | AGPLv3 | OSS + enterprise unlock key + cloud | $400M+ ARR, $6B | AGPL + enterprise binary trick works |
| Temporal | MIT | 100% OSS + managed cloud | $5B val | Ops complexity IS the moat |
| PostHog | MIT + ee/ | Gate volume not features | ~$100M ARR, $1.4B | Cloud-first, self-hosted enterprise dead end |
| Supabase | Apache-2.0 | 100% OSS + cloud | ~$70M ARR, $2B | Velocity gap as moat |
| GitLab | MIT(CE) + proprietary(EE) | Buyer-based open core | $759M rev | Golden rule: features only move paid→free |
| Sentry | FSL→Apache-2.0 (2yr) | Fair Source + cloud | $100M+ ARR | Created FSL, proved it works |
| Docker | Apache-2.0 + proprietary | PLG on dev tools | $207M ARR | Nearly died, saved by developer PLG pivot |
| HashiCorp | MPL→BSL | License change → acquisition | Sold $6.4B | BSL didn't save company, enabled exit |
| Elastic | Apache→SSPL→+AGPL | Multiple license pivots | Public | Fork (OpenSearch) permanent, trust broken |
| Redis | BSD→SSPL→+AGPL | Multiple pivots | — | Valkey fork overtook in distro defaults |
| MinIO | Apache→AGPL→gutted | Feature stripping | Dead as OSS | Anti-pattern: destroyed community |

## Timing: Open-Source Before PMF

Every successful COSS company (Temporal, Grafana, PostHog, Supabase, HashiCorp) open-sourced before PMF. PostHog model: 18 months pure OSS → community fit → commercial PMF on top.

## COSS Financial Performance (Linux Foundation 2025)
- Series A 20% faster, Series B 34% faster than closed-source
- 7x greater IPO valuations, 14x at M&A
- 90% of COSS in infrastructure software

## Meeting Bot Competitive Landscape
- Recall.ai: closed-source, $51M raised, $250M val
- MeetingBaaS: BSL license (validates wrapping concern)
- Attendee: MIT open-source
- Cloud wrapping risk from AWS: LOW (too niche)
