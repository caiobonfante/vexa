# Confidence Calibration in Agentic AI Systems: Research Report

**Date:** 2026-03-29
**Purpose:** Research foundation for designing a confidence-driven agent framework with exponential confidence levels, gotcha memory, and post-delivery calibration.

---

## Table of Contents

1. [A) Calibration in LLM/Agent Systems](#a-calibration-in-llmagent-systems)
2. [B) Mathematical Models for Confidence Accumulation](#b-mathematical-models-for-confidence-accumulation)
3. [C) Confidence-Driven Stopping Criteria](#c-confidence-driven-stopping-criteria)
4. [D) Metacognitive Agents / Self-Reflection](#d-metacognitive-agents--self-reflection)
5. [E) Gotcha Memory / Failure Catalogs](#e-gotcha-memory--failure-catalogs)
6. [F) Known Pitfalls](#f-known-pitfalls)
7. [G) Practical Implementations](#g-practical-implementations)
8. [Synthesis: Recommendations for Our Framework](#synthesis-recommendations-for-our-framework)

---

## A) Calibration in LLM/Agent Systems

### The Core Problem: LLMs Are Systematically Overconfident

The research is unambiguous: LLMs are poorly calibrated, and the problem is **worse** in agentic settings than in single-turn Q&A.

**Key findings from recent papers:**

1. **Verbalized confidence clusters near the top.** When asked to self-report confidence (0-100), LLMs compress their outputs into the 80-100 range regardless of actual accuracy. RLHF and instruction tuning **exacerbate** this — they train models to sound confident, not to be calibrated. ([Xiong et al., 2023 — ICLR 2024](https://arxiv.org/abs/2306.13063))

2. **Agentic overconfidence is dramatically worse.** The paper "Agentic Uncertainty Reveals Agentic Overconfidence" (Kaddour et al., Feb 2026) found that coding agents predict 73% success against an actual 35% rate (GPT-5.2-Codex on SWE-Bench-Pro). The asymmetry is striking: **62% of predictions on failing tasks are overconfident (predicted >= 0.7), while only 11% on passing tasks are underconfident (predicted < 0.3).** Agents are 5.5x more likely to confidently predict success on a task they will fail. ([arxiv 2602.06948](https://arxiv.org/abs/2602.06948))

3. **The confidence-faithfulness gap.** Even when models express lower confidence in internal token probabilities, their verbalized confidence remains inflated. There is a measurable gap between what the model "knows it doesn't know" internally and what it reports. ([arxiv 2603.25052](https://arxiv.org/html/2603.25052))

4. **Consistency-based methods beat verbalized confidence.** Sampling multiple responses and measuring agreement (self-consistency) reliably outperforms both logit-based and verbalized confidence estimates, especially in black-box settings. ([Multiple studies, synthesized in NAACL 2024 survey](https://aclanthology.org/2024.naacl-long.366/))

### Actionable Insight for Our Framework

**Do not trust the agent's self-reported confidence number at face value.** A raw "I'm 85% confident" from an LLM is nearly meaningless without calibration. Our framework must either:
- Apply post-hoc calibration (temperature scaling, Platt scaling) to reported numbers
- Use behavioral signals (number of tool calls, retries, error patterns) as confidence proxies
- Use adversarial self-questioning ("what could go wrong?") instead of direct self-assessment

---

## B) Mathematical Models for Confidence Accumulation

### Your Proposed Model: Exponential Decay Growth

The proposed formula is essentially: `confidence = 100 - 50 * exp(-k * steps)`, starting at 50, asymptotically approaching 100.

**Assessment: This is a reasonable starting point but has specific limitations.**

### Alternative Models Ranked by Suitability

#### 1. Bayesian Updating (RECOMMENDED PRIMARY)

**Formula:** `P(correct | evidence) = P(evidence | correct) * P(correct) / P(evidence)`

**Why it's better:** Bayesian updating naturally handles both positive AND negative evidence. Each observation (successful tool call, test pass, error encountered, gotcha triggered) updates the posterior. It doesn't just grow — it can shrink when disconfirming evidence arrives.

**Key property:** The update magnitude is proportional to how surprising the evidence is. Expected successes barely move confidence; unexpected failures cause large drops. This matches human expert behavior.

**Practical implementation:** Use log-odds space for numerical stability:
```
log_odds += log(P(evidence | correct) / P(evidence | incorrect))
confidence = sigmoid(log_odds)
```

**Research support:** Cognitive science research shows human confidence follows Bayesian-like updates with an asymptotic ceiling — confidence approaches a maximum for very long evidence accumulation but never quite reaches it. ([Dynamic expressions of confidence within an evidence accumulation framework, Cognition 2020](https://www.sciencedirect.com/science/article/abs/pii/S0010027720303413))

#### 2. Sigmoid / Logistic Curve

**Formula:** `confidence = L / (1 + exp(-k * (x - x0)))` where L=max, k=steepness, x0=midpoint

**Why it's interesting:** S-curves model the realistic pattern where early evidence provides rapid confidence growth, middle evidence provides steady growth, and late evidence has diminishing returns. The inflection point can be tuned per task type.

**Advantage over exponential decay:** S-curves start slow (uncertainty in the first steps is high) whereas exponential decay gives the fastest growth at the very beginning — which contradicts how confidence should actually work (early steps should contribute less because the agent hasn't verified anything yet).

#### 3. Exponential Decay (Your Proposal)

**Formula:** `confidence = max - (max - base) * exp(-k * steps)`

**Limitation:** Growth is fastest at step 0 and slows monotonically. This means the first step contributes the most confidence gain, which is counterintuitive — the first step is when the agent knows the least. Also, this formula can only grow, never shrink. It has no mechanism for incorporating negative evidence.

**When it works:** For simple tasks where each step is genuinely incremental and failures are rare (e.g., file-by-file processing with no interdependencies).

#### 4. Evidence Accumulation with Decay (RECOMMENDED HYBRID)

**Formula:** Combine Bayesian updating with a recency-weighted decay:
```
effective_evidence = sum(evidence_i * decay^(current_step - i))
confidence = sigmoid(effective_evidence)
```

**Why this is powerful:** Old evidence decays, so if the agent found a working approach 10 steps ago but has encountered 3 errors since, confidence drops appropriately. This prevents the "ancient success masks recent failures" problem.

### Recommendation

**Use Bayesian updating in log-odds space with sigmoid output, not exponential decay.** The exponential decay model is a special case of the sigmoid applied to monotonically increasing evidence — it only works when every step is positive. Real agent work involves setbacks, and the model must handle bidirectional updates.

---

## C) Confidence-Driven Stopping Criteria

### State of the Art in Agent Stopping

Most production agent systems use **hard limits**, not confidence-based stopping:

| System | Stopping Mechanism | Confidence-Based? |
|--------|-------------------|-------------------|
| SWE-agent | Max iterations (25-100) | No |
| Devin | Task completion + max budget | No (implicit) |
| AutoGPT | Max iterations or user stop | No — known infinite loop problem |
| DeepResearch (OpenAI) | `max_tool_calls` parameter | No — acknowledged weakness |
| Claude Code | Token budget + model decides "done" | Partially |
| BATS/SelfBudgeter | Adaptive token budget based on difficulty | Yes (emerging) |

**Key insight:** No major production system currently uses explicit confidence scoring for stopping. This is an open problem and an opportunity.

### Emerging Research on Confidence-Driven Stopping

1. **SelfBudgeter** (2025): Trains models to predict their own token budget needs based on task difficulty, then enforces that budget. Achieves 62.88% token savings while maintaining accuracy. The key insight: **let the model assess task difficulty upfront, then allocate resources accordingly.** ([arxiv 2505.11274](https://arxiv.org/abs/2505.11274))

2. **BATS (Budget Aware Test-time Scaling):** A plug-in module that surfaces real-time budget state inside the agent's reasoning loop. The agent dynamically decides whether to "dig deeper" on a promising lead or "pivot" to new paths based on remaining resources. ([arxiv 2511.17006](https://arxiv.org/html/2511.17006v1))

3. **Deep Think with Confidence:** Generates verification questions at intermediate steps; if confidence drops below threshold, allocates more compute. If confidence is high, proceeds. ([jiaweizzhao.github.io/deepconf/](https://jiaweizzhao.github.io/deepconf/))

4. **Confidence-Aware Self-Consistency:** Analyzes a single completed reasoning trajectory to adaptively select between single-path and multi-path reasoning. Uses up to 80% fewer tokens by avoiding redundant verification when confidence is already high. ([arxiv 2603.08999](https://arxiv.org/abs/2603.08999))

### Design Pattern for Our Framework

Based on the research, the recommended stopping criteria architecture:

```
CONTINUE if:
  - confidence < threshold AND budget remaining AND no hard blocker

STOP (success) if:
  - confidence >= threshold AND verification_passed

STOP (blocker) if:
  - hard_blocker_detected AND attempts_exhausted

ESCALATE if:
  - confidence stagnant for N steps (no movement in either direction)
  - contradictory evidence (confidence oscillating)
  - budget approaching limit with low confidence
```

**Critical: Never stop on confidence alone.** The Agentic Uncertainty paper shows agents are overconfident on failures. Confidence must be paired with verification (test pass, observable outcome, adversarial check).

---

## D) Metacognitive Agents / Self-Reflection

### Reflexion: The Foundational Framework

Reflexion (Shinn et al., NeurIPS 2023) introduced "verbal reinforcement learning" — instead of weight updates, agents maintain a text-based memory of reflections from prior attempts. ([arxiv 2303.11366](https://arxiv.org/abs/2303.11366))

**Three components:**
1. **Actor:** Generates actions (CoT/ReAct)
2. **Evaluator:** Scores the trajectory (binary or scalar)
3. **Self-Reflection:** Generates natural language analysis of what went wrong, stored in episodic memory

**Key insight for our framework:** Self-reflection works best when it produces **specific, actionable** observations, not vague summaries. "The function failed because the API returns dates in ISO format but I parsed them as Unix timestamps" is useful. "The approach didn't work well" is not.

### Self-Reflection Effectiveness: Nuanced Picture

Research on self-reflection in LLM agents (Renze & Guven, 2024) found that reflection **significantly improves performance** but with important caveats:
- Self-correction without external feedback is unreliable — LLMs cannot consistently recognize their own errors through introspection alone
- The upper bound of "intrinsic self-correction" (without external signal) may be fundamentally limited by the model's metacognitive capacity
([arxiv 2405.06682](https://arxiv.org/abs/2405.06682))

### Chain-of-Verification

Generates verification questions to check each claim in a response. However, detection methods like self-consistency lack quantitative confidence measures, and correction methods like CoVe fix things uniformly without identifying which outputs need correction. ([ACL 2024](https://aclanthology.org/2024.findings-acl.212.pdf))

### Adversarial Self-Assessment (MOST PROMISING)

The Agentic Uncertainty paper found that **reframing self-assessment as bug-finding** ("what bugs can you find?" instead of "is this correct?") reduced overconfidence by up to 15 percentage points and achieved the best calibration across all models tested.

**This is the single most actionable finding for our framework.** When the agent reaches high confidence, instead of asking "am I done?", ask "what could be wrong with this?"

### Collaborative Calibration (Multi-Agent)

Using multiple LLM agents in a deliberation process — where agents argue different stances and adjust their confidence based on feedback — achieves calibration comparable to or better than supervised methods, with no training required. The "trim-and-average" method (remove outlier estimates, average the rest) is surprisingly effective. ([arxiv 2404.09127](https://arxiv.org/abs/2404.09127))

---

## E) Gotcha Memory / Failure Catalogs

### Established Patterns

#### 1. Voyager Skill Library (Gold Standard for Learned Behaviors)

Voyager (Wang et al., 2023) maintains a growing library of executable skills indexed by semantic embeddings. When facing a new task, it retrieves relevant skills by similarity. This is the closest production-proven analog to a "gotcha catalog." ([arxiv 2305.16291](https://arxiv.org/abs/2305.16291))

**Key design choices:**
- Skills are stored as **executable code**, not natural language descriptions
- Each skill is indexed by its description embedding for retrieval
- Failed skills are NOT stored — only verified successes
- Skills are compositional: complex skills build on simpler ones
- The library grows monotonically and is never pruned

**Adaptation for gotchas:** Unlike Voyager's success-only library, a gotcha catalog should store **failures and their root causes**, indexed by the error pattern or situation that triggered them.

#### 2. Reflexion Episodic Memory

Reflexion stores natural language reflections from failed attempts. These are retrieved and injected into the prompt for future attempts at similar tasks.

**Limitation:** Reflexion's memory is task-specific and session-bound. It doesn't transfer across different tasks or persist across sessions.

#### 3. Letta/MemGPT Persistent Memory

Letta implements a tiered memory architecture inspired by OS memory management:
- **Core memory** (in-context): Always present, analogous to RAM
- **Archival memory** (external): Long-term storage, retrieved by query
- **Recall memory** (external): Conversation history, searchable

Letta recently added **Skill Learning** — agents learn from experience and store learned behaviors for future use. This is the production framework closest to what we need. ([Letta docs](https://docs.letta.com/concepts/memgpt/), [Letta blog on agent memory](https://www.letta.com/blog/agent-memory))

#### 4. Context Repositories (Letta, 2025-2026)

Letta introduced "Context Repositories" — git-based memory for coding agents. This allows agents to maintain versioned, persistent knowledge that survives across sessions and even across model generations. ([Letta blog](https://www.letta.com/blog/context-repositories))

### Recommended Gotcha Memory Architecture

Based on the research, a gotcha catalog should have:

```
gotcha_entry:
  id: unique identifier
  pattern: what situation triggers this gotcha (semantic description)
  pattern_embedding: vector for retrieval
  severity: how much to lower confidence (0.0 to 1.0)
  evidence: what happened when this was encountered
  root_cause: why this is a problem
  mitigation: what to do instead
  times_triggered: counter
  last_triggered: timestamp
  false_positive_count: times it fired but was wrong
  confidence_impact: actual measured impact on outcomes
```

**Critical design decision:** Gotchas must be **falsifiable.** If a gotcha fires 5 times but the feared outcome never materializes, its severity should decay. This prevents the system from accumulating false alarms that make it overly cautious.

---

## F) Known Pitfalls

### 1. The Dunning-Kruger Effect in LLMs

Recent empirical study (March 2026, [arxiv 2603.09985](https://arxiv.org/html/2603.09985v1)) tested 4 models across 24,000 trials:

| Model | Accuracy | ECE (lower=better) | Pattern |
|-------|----------|---------------------|---------|
| Claude Haiku 4.5 | 75.4% | 0.122 | Best calibrated, slight underconfidence |
| Kimi K2 | 23.3% | 0.726 | Severe overconfidence (97.9% confidence, 3.9% accuracy on TriviaQA) |
| Gemini 2.5 Pro | ~70% | ~0.25 | Rigid 95-99% confidence regardless of accuracy |
| Gemini 2.5 Flash | ~65% | ~0.30 | Same rigidity pattern |

**The Dunning-Kruger pattern is clear:** Poorly performing models express the highest confidence. The models that know the least are the most sure of themselves.

**Implication for our framework:** The model used for confidence self-assessment matters enormously. Claude models appear better calibrated than alternatives, but even Claude exhibits significant overconfidence in agentic settings (predicting 61% success against 27% actual in the Kaddour et al. study).

### 2. Calibration Drift

Confidence calibration degrades over time as:
- The distribution of tasks shifts (new task types the system hasn't seen)
- The model is updated (new model versions may have different calibration profiles)
- The gotcha catalog grows (accumulating false alarms or outdated gotchas)
- The environment changes (APIs, dependencies, infrastructure)

**Mitigation:** Periodic recalibration against ground truth. Track predicted confidence vs. actual outcomes over rolling windows.

### 3. The Overconfidence Asymmetry (Most Dangerous)

From the Agentic Uncertainty paper: agents are **5.5x more likely to be confidently wrong than to be unsure about something correct.** This means:
- False confidence is the dominant failure mode
- The system will more often ship broken work confidently than fail to ship working solutions
- Confidence thresholds must be set **higher than intuition suggests** to compensate

### 4. Confirmation Bias in Self-Assessment

Post-execution self-assessment ("is this correct?") triggers confirmation bias — the agent looks for evidence supporting its work rather than evidence against it. The adversarial framing ("what bugs can you find?") partially mitigates this.

### 5. The Gotcha Accumulation Problem

If gotchas only accumulate and never decay, the system becomes increasingly paralyzed:
- Every new gotcha lowers confidence
- Confidence threshold becomes unreachable
- Agent stops making progress
- This mimics learned helplessness in psychology

**Mitigation:** Gotcha severity must decay if not confirmed. Implement "gotcha expiry" — if a gotcha hasn't been triggered/confirmed in N tasks, reduce its severity.

### 6. False Blocker Escalation

Agents may hallucinate blockers that don't exist (e.g., claiming an API is unreachable when the URL was wrong, claiming a test framework doesn't support a feature when it does). In multi-agent systems, a hallucinated fact from one agent can cascade through the system.

**Mitigation from research:** Multi-agent validation (one agent executes, another verifies, a third approves). Separation of planning from execution prevents single hallucinations from cascading. ([7 Agent Failure Modes, Galileo](https://galileo.ai/blog/agent-failure-modes-guide))

### 7. Infinite Loops from Confidence Oscillation

If positive and negative evidence alternate rapidly, confidence can oscillate without converging. The agent never reaches the confidence threshold and loops forever.

**Mitigation:** Detect oscillation patterns. If confidence swings more than X points in both directions within N steps, escalate to human review rather than continuing.

---

## G) Practical Implementations

### Open-Source Frameworks

1. **DeepEval (Confident AI)** — Python framework for LLM evaluation with 30+ built-in metrics, threshold-based pass/fail, regression detection. All scores 0-1. ([github.com/confident-ai/deepeval](https://github.com/confident-ai/deepeval))

2. **Letta (formerly MemGPT)** — Production framework for stateful agents with tiered memory, skill learning, and persistence. REST API deployment. The new V1 agent architecture draws lessons from ReAct, MemGPT, and Claude Code. ([github.com/letta-ai/letta](https://github.com/letta-ai/letta))

3. **OpenSearch Agent Health** — Zero-install observability tool that compares agent behavior against a "golden path" trajectory, scoring deviations. ([opensearch.org/blog/opensearch-agent-health](https://opensearch.org/blog/opensearch-agent-health-open-source-observability-and-evaluation-for-ai-agents/))

4. **Langfuse** — Agent observability, tracing, and evaluation platform with confidence scoring integration. ([langfuse.com](https://langfuse.com/blog/2024-07-ai-agent-observability-with-langfuse))

### Research Implementations

1. **Holistic Trajectory Calibration (HTC)** — Extracts 48-dimensional features from agent trajectories (cross-step dynamics, intra-step stability, positional indicators, structural attributes) and trains a lightweight linear model to predict success probability. Works with 400-500 trajectory samples. The L1-regularized variant (HTC-Reduced) selects 15-25 features and is robust in small-data settings. ([arxiv 2601.15778](https://arxiv.org/abs/2601.15778))

2. **Collaborative Calibration** — Multi-agent deliberation for training-free calibration. Agents generate initial answers, cluster into stances with averaged confidence, then argue, provide feedback, and revise. Final majority vote produces calibrated estimate. ([arxiv 2404.09127](https://arxiv.org/abs/2404.09127))

3. **Confidence-Aware Self-Consistency** — Analyzes a single trajectory to decide between single-path and multi-path reasoning. Saves up to 80% of tokens when confidence is already high. ([arxiv 2603.08999](https://arxiv.org/abs/2603.08999))

---

## Synthesis: Recommendations for Our Framework

### 1. Replace Exponential Decay with Bayesian Updating

**Instead of:** `confidence = 100 - 50 * exp(-k * steps)`

**Use:** Log-odds Bayesian updating with sigmoid output:
```python
class ConfidenceTracker:
    def __init__(self, prior=0.5):
        self.log_odds = log(prior / (1 - prior))  # Start at 0 for 50%
        self.history = []

    def update(self, evidence_strength: float, is_positive: bool):
        """
        evidence_strength: 0.0 (weak) to 1.0 (strong)
        is_positive: True if evidence supports success
        """
        # Convert to log-likelihood ratio
        if is_positive:
            lr = 1.0 + evidence_strength * 3.0  # weak=1, strong=4
        else:
            lr = 1.0 / (1.0 + evidence_strength * 3.0)  # inverse

        self.log_odds += log(lr)
        # Clamp to prevent extreme values (maps to ~2% - ~98%)
        self.log_odds = clamp(self.log_odds, -4.0, 4.0)
        self.history.append(self.confidence)

    @property
    def confidence(self) -> float:
        return 1.0 / (1.0 + exp(-self.log_odds))

    @property
    def confidence_100(self) -> int:
        """Confidence on 0-100 scale"""
        return int(self.confidence * 100)
```

**Why:** Handles both positive and negative evidence, naturally produces diminishing returns near extremes, has solid mathematical foundations, and the clamping at +/-4.0 prevents the "100% confident" trap.

### 2. Implement Adversarial Self-Assessment at High Confidence

When confidence crosses 80%, trigger an adversarial assessment step:
- Ask "What could be wrong with this?" instead of "Is this correct?"
- This reduces overconfidence by ~15 percentage points (empirically validated)
- Only then allow the agent to declare completion

### 3. Use Multi-Signal Confidence, Not Self-Reported Scores

Combine multiple signals for confidence estimation:
- **Behavioral signals:** Number of retries, error rate, tool call patterns
- **Verification signals:** Tests passing, observable outcomes matching expectations
- **Self-assessment signals:** Agent's own estimate (but calibrated down by ~15-20%)
- **Gotcha signals:** Whether any stored gotcha patterns match the current situation

Weight behavioral and verification signals higher than self-assessment.

### 4. Design Gotcha Memory with Decay

```
gotcha:
  severity: starts at measured_impact
  decay_rate: 0.9 per non-trigger  (severity *= 0.9 each time similar task succeeds without triggering)
  min_severity: 0.05  (floor — never fully forget, but impact becomes negligible)
  amplify_on_confirm: severity = min(severity * 1.5, 1.0) when gotcha is confirmed again
```

This prevents the "learned helplessness" failure mode while keeping genuine gotchas alive.

### 5. Implement Confidence Stagnation Detection

If confidence hasn't moved more than 2 points in either direction for 5 consecutive steps, the agent is spinning:
- Not finding new evidence
- Not making progress
- Should escalate or change approach

### 6. Post-Delivery Calibration Loop

After every delivery:
1. Record (predicted_confidence, actual_outcome)
2. Over rolling window of last 50 deliveries, compute ECE
3. If ECE > 0.15, adjust calibration:
   - If consistently overconfident: apply scaling factor `new_confidence = old_confidence * 0.85`
   - If consistently underconfident: apply scaling factor `new_confidence = min(old_confidence * 1.1, 0.95)`
4. Store calibration adjustment as a persistent parameter

### 7. Blocker Validation Protocol

When an agent reports a "hard blocker":
1. Record the blocker claim with evidence
2. Have a second assessment (adversarial or multi-agent) verify the blocker
3. If blocker is confirmed false after resolution: store as a gotcha with the pattern "false blocker: [description]"
4. Track false-blocker rate per agent/task-type
5. If false-blocker rate > 20%, inject a "you tend to over-report blockers" instruction

### 8. Stopping Criteria Decision Tree

```
for each step:
    update_confidence(step_result)

    if confidence >= 90 AND adversarial_check_passed:
        DELIVER
    elif confidence >= 75 AND verification_passed AND no_open_gotchas:
        DELIVER with note "moderate confidence"
    elif hard_blocker AND blocker_verified:
        STOP with blocker report
    elif budget_exhausted:
        DELIVER best effort with confidence report
    elif confidence_stagnant(5 steps):
        ESCALATE
    elif confidence_oscillating(amplitude > 15, period < 4):
        ESCALATE — contradictory evidence
    else:
        CONTINUE
```

---

## Key References

### Core Papers (Must-Read)
- [Agentic Confidence Calibration (HTC)](https://arxiv.org/abs/2601.15778) — Zhang et al., Jan 2026
- [Agentic Uncertainty Reveals Agentic Overconfidence](https://arxiv.org/abs/2602.06948) — Kaddour et al., Feb 2026
- [The Dunning-Kruger Effect in LLMs](https://arxiv.org/html/2603.09985v1) — March 2026
- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366) — Shinn et al., NeurIPS 2023
- [Confidence Calibration via Multi-Agent Deliberation](https://arxiv.org/abs/2404.09127) — 2024

### Confidence Estimation Methods
- [Can LLMs Express Their Uncertainty? (ICLR 2024)](https://arxiv.org/abs/2306.13063) — Xiong et al.
- [On Verbalized Confidence Scores for LLMs](https://arxiv.org/pdf/2412.14737) — Yang et al., 2024
- [Survey of Confidence Estimation and Calibration (NAACL 2024)](https://aclanthology.org/2024.naacl-long.366/)
- [Confidence Improves Self-Consistency in LLMs](https://arxiv.org/pdf/2502.06233) — ACL 2025
- [Confidence-Aware Self-Consistency](https://arxiv.org/abs/2603.08999) — March 2026
- [Know When You're Wrong: Aligning Confidence with Correctness](https://arxiv.org/html/2603.06604) — March 2026

### Agent Memory & Learning
- [Voyager: Open-Ended Embodied Agent with LLMs](https://arxiv.org/abs/2305.16291) — Wang et al., 2023
- [Memory in the Age of AI Agents (Survey)](https://arxiv.org/abs/2512.13564) — Dec 2025
- [Letta/MemGPT Documentation](https://docs.letta.com/concepts/memgpt/)
- [Rearchitecting Letta's Agent Loop](https://www.letta.com/blog/letta-v1-agent) — Lessons from ReAct, MemGPT, Claude Code

### Stopping Criteria & Budget
- [SelfBudgeter: Adaptive Token Allocation](https://arxiv.org/abs/2505.11274) — 2025
- [Budget-Aware Tool-Use Enables Effective Agent Scaling](https://arxiv.org/html/2511.17006v1) — 2025
- [BudgetThinker: Control Tokens for Budget-Aware Reasoning](https://arxiv.org/html/2508.17196v2) — 2025

### Agent Failure Modes
- [7 AI Agent Failure Modes Guide (Galileo)](https://galileo.ai/blog/agent-failure-modes-guide)
- [Why Multi-Agent Systems Fail](https://arxiv.org/html/2503.13657v1) — March 2025
- [Measuring Agent Autonomy (Anthropic)](https://www.anthropic.com/research/measuring-agent-autonomy)

### Frameworks
- [DeepEval (Confident AI)](https://github.com/confident-ai/deepeval)
- [Letta](https://github.com/letta-ai/letta)
- [Langfuse](https://langfuse.com)
