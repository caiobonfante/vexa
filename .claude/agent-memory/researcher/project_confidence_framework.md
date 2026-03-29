---
name: Confidence Framework Research
description: Research findings for designing confidence-driven agent framework — Bayesian updating beats exponential decay, adversarial self-assessment reduces overconfidence by 15pp, agents are 5.5x more likely to be confidently wrong than unsure about correct work
type: project
---

Comprehensive research completed 2026-03-29 on confidence calibration for agentic AI.

**Why:** The team is designing a confidence-driven agent loop where agents track confidence at every step, collect gotchas in memory, and don't stop until high confidence or hard blocker.

**How to apply:**
- Full report at `/home/dima/dev/vexa-agentic-runtime/features/agentic-runtime/tests/confidence-calibration-research.md`
- Key recommendation: Use Bayesian updating in log-odds space instead of exponential decay — handles negative evidence, has diminishing returns near extremes
- Critical finding: LLMs are 5.5x more likely to be overconfident on failures than underconfident on successes (Kaddour et al., arxiv 2602.06948)
- Most actionable technique: Adversarial self-assessment ("what could go wrong?") reduces overconfidence by ~15 percentage points
- Gotcha memory must have decay to prevent learned helplessness
- Post-delivery ECE tracking for ongoing calibration
