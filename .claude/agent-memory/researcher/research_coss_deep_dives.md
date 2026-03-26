---
name: COSS Deep Dives — Docker, GitLab, Elastic, Redis, Sentry
description: Detailed case studies of 5 major COSS companies — business model evolution, licensing decisions, revenue impact, forks, and practical lessons for new infra projects in 2026
type: project
---

# COSS Deep Dives: Docker, GitLab, Elastic, Redis, Sentry (March 2026)

**Why:** To extract practical, evidence-based lessons from the most significant commercial open-source business model experiments of the last decade, informing our own licensing and monetization decisions.

**How to apply:** Use these case studies as a decision framework — specifically the failure modes (Docker Swarm, Elastic SSPL backlash, Redis Valkey fork) and the success modes (Docker PLG pivot, GitLab buyer-based open core, Sentry FSL).

## Full analysis delivered in conversation on 2026-03-26.

Key takeaways:
1. Docker: Selling to ops teams failed ($335M burned); pivoting to developer PLG succeeded ($11M to $207M ARR in 4 years)
2. GitLab: Buyer-based open core at $759M revenue — features never move from free to paid, only paid to free
3. Elastic: SSPL triggered AWS OpenSearch fork (300M+ downloads); reversed to AGPL in 2024 but community trust not recovered
4. Redis: BSD→SSPL triggered Valkey fork (Linux Foundation, AWS, Google); reversed to AGPL in 2025, but Valkey already in Fedora
5. Sentry: FSL (source-available, converts to Apache-2.0 after 2 years) — cleanest new model, $100M ARR, adopted by ~10 companies
6. MongoDB: SSPL pioneer, $1.7B ARR — worked because they moved first (2018) and had Atlas cloud product
7. HashiCorp: BSL triggered OpenTofu fork, then sold to IBM for $6.4B — license change may have been exit preparation
8. The Pattern: permissive→restrictive license changes always trigger forks; choose your license deliberately from day one
