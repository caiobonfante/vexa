# Risk-Weighted DoD with Mechanical Confidence Calculation

Research findings on best practices and existing patterns for weighted Definition of Done items with ceiling-based confidence scoring.

**Date:** 2026-03-31
**Purpose:** Inform the design of a system where:
- Each DoD item has a **weight** (points when passing) and a **ceiling** (max overall confidence if NOT passing)
- Confidence = min(weighted_sum, lowest_ceiling_of_any_failing_item)
- Critical-path items act as hard caps

---

## 1. Risk-Based Testing (RBT) Frameworks

### Key Pattern: Risk Priority Number (RPN)

ISO/IEC/IEEE 29119 mandates that all testing should be risk-based. The core formula:

```
Risk Exposure = Probability of Failure × Impact of Failure
```

For finer granularity, the FMEA (Failure Mode and Effects Analysis) approach:

```
RPN = Severity × Occurrence × Detectability
```

Each factor scored 1-10. A test case with Severity=9, Occurrence=3, Detectability=2 gets RPN=54. This drives test prioritization — high-RPN items get tested first and most thoroughly.

**ISTQB Risk-Based Testing** classifies test cases into risk categories and allocates effort proportionally. Key insight: risk assessment directly influences test estimation, planning, and control. Over 1 million certified testers use this approach globally.

### How It Maps to Our Model

| RBT Concept | Our Model |
|---|---|
| RPN score | **Weight** — higher risk items get more points |
| Severity component | **Ceiling** — high-severity failures cap overall confidence regardless of other passes |
| Detectability | Inversely related to weight — hard-to-detect failures need more testing weight |
| Risk categories (High/Medium/Low) | Tier classification for DoD items |

### What We Steal

1. **Two-dimensional risk scoring.** Don't just weight items by importance — weight by (impact × detection difficulty). A critical-path item that's easy to test (curl returns 200) gets moderate weight. A critical-path item that's hard to test (live meeting admission) gets maximum weight.
2. **RPN drives effort allocation, not just scoring.** In our system, high-weight items should be tested FIRST, not saved for last.

**Sources:**
- [Risk-Based Testing — Wikipedia](https://en.wikipedia.org/wiki/Risk-based_testing)
- [ISTQB Risk-Based Testing Methodologies](https://oboe.com/learn/advanced-istqb-test-management-1y2ivns/risk-based-testing-methodologies-advanced-istqb-test-management-2)
- [ISO/IEC/IEEE 29119 — arc42](https://quality.arc42.org/standards/iso-iec-ieee-29119)
- [Risk-Based Testing for AI — ISO 29119](https://softwaretestingstandard.org/2024/11/03/risk-based-testing-for-ai/)

---

## 2. Deployment Confidence Scoring

### Key Pattern: Spinnaker/Kayenta Canary Analysis

Netflix and Google's open-source canary analysis system is the closest production analog to our model. The scoring algorithm:

```
1. Classify each metric: Pass / High / Low / Nodata / NodataFailMetric
2. Group Score = (Pass count / Total count) × 100
3. Summary Score = weighted average of group scores
4. Decision = compare score against passThreshold and marginalThreshold
```

**Critical metrics bypass group averaging entirely.** Any metric marked `critical: true` that fails sets the score to 0 — automatic failure regardless of all other metrics. This is exactly our ceiling concept.

**Metric groups with configurable weights:**
- Groups can have explicit weights (e.g., latency group = 40, error rate group = 60)
- Within a group, metrics are evenly balanced
- A group with weight=40 and 50% pass rate contributes 20 to the summary score

**Three-tier decision:**
- **Pass:** Score ≥ passThreshold → promote canary, continue deployment
- **Marginal:** Score ≥ marginalThreshold → trigger human review
- **Fail:** Score < marginalThreshold → automatic rollback

### Key Pattern: SRE Error Budgets as Confidence Ceiling

Google's error budget policy implements a **binary gate** with clear escalation:

- **SLO met (budget > 0%):** Releases proceed normally
- **SLO breached (budget ≤ 0%):** All non-P0 changes frozen until service returns to SLO
- **Single incident > 20% of quarterly budget:** Mandatory postmortem with P0 remediation items

The error budget acts as a **ceiling on deployment velocity**, not a score. You can't "earn" more deployments by being reliable elsewhere — if the error budget is spent, you're gated.

**Burn rate as early warning:**
- Fast burn (14.4x rate over 1 hour): immediate alert
- Slow burn (3x rate over 6 hours): warning alert
- This maps to confidence trending — not just current score but direction

### Key Pattern: Google Launch Readiness Review

Google's Production Readiness Review uses a checklist where "every question's importance must be substantiated, ideally by a previous launch disaster." Items are binary (pass/fail), not weighted — but the set of required items acts as a hard gate. A single "no" on a critical item blocks launch.

### How It Maps to Our Model

| Deployment Concept | Our Model |
|---|---|
| Kayenta critical metrics | **Ceiling items** — one failure = score 0 |
| Kayenta metric groups with weights | **Weighted DoD groups** (API tests, live tests, etc.) |
| Kayenta passThreshold / marginalThreshold | **Confidence delivery thresholds** (85 deliver, 70 deliver-with-note) |
| Error budget as binary gate | **Ceiling** — failing items impose max confidence regardless of score |
| Error budget burn rate | **Confidence trending** — track direction, not just position |
| PRR checklist substantiated by disasters | **Gotcha-driven DoD items** — each item exists because of a past failure |

### What We Steal

1. **Critical metrics that bypass averaging.** Kayenta's `critical: true` is exactly our ceiling. One critical failure = score 0, regardless of everything else.
2. **Weighted group scoring, not item scoring.** Group DoD items logically (API tests, live tests, environment health), weight groups, score within groups evenly. This prevents gaming by piling up easy items in one group.
3. **Three-tier decision (pass/marginal/fail)** maps directly to our deliver/deliver-with-note/continue stopping criteria.
4. **Burn rate monitoring.** Track confidence direction — if it's dropping across steps, escalate before it hits zero.

**Sources:**
- [How Canary Judgment Works — Spinnaker](https://spinnaker.io/docs/guides/user/canary/judge/)
- [Automated Canary Analysis at Netflix — Kayenta](https://netflixtechblog.com/automated-canary-analysis-at-netflix-with-kayenta-3260bc7acc69)
- [Google SRE Error Budget Policy](https://sre.google/workbook/error-budget-policy/)
- [Google SRE Launch Checklist](https://sre.google/sre-book/launch-checklist/)
- [Introducing Kayenta — Google Cloud Blog](https://cloud.google.com/blog/products/gcp/introducing-kayenta-an-open-automated-canary-analysis-tool-from-google-and-netflix)

---

## 3. Bayesian/Probabilistic Test Confidence

### Key Pattern: Mutation Testing as Confidence Signal

Mutation testing measures test suite quality by introducing small code changes (mutants) and checking if tests catch them:

```
Mutation Score = Killed Mutants / Total Mutants
```

Research finding (Papadakis et al., ICSE 2018): mutation scores are **strongly correlated with real fault detection**. Average improvement of 8-46% fault detection for top-ranked test suites vs random.

Key insight: code coverage alone is insufficient to predict defect detection. Mutation analysis provides additional insight into when a test suite can find real faults. This maps to our model — passing tests (coverage) ≠ catching real bugs (mutation score ≈ confidence in test quality).

### Key Pattern: Defect Detection Probability (DDP)

DDP is the probability that a test suite will detect a defect if one exists. It's computed empirically:

```
DDP = (defects detected by test suite) / (total known defects)
```

This is analogous to our confidence — it's not "did my tests pass?" but "how confident am I that my tests would catch a real problem?"

### How It Maps to Our Model

| Probabilistic Concept | Our Model |
|---|---|
| Mutation score | **Quality of evidence** — not just "test passed" but "test would catch a real bug" |
| DDP | **Evidence strength** in Bayesian update — high-DDP tests give stronger positive evidence |
| Code coverage ≠ fault detection | **Observable evidence only** — "tests pass" score varies by test quality |

### What We Steal

1. **Evidence quality scaling.** Not all passing tests give equal confidence. A test that exercises the critical path with real data (high mutation score analog) should give more confidence points than a test that checks a happy path with mock data.
2. **The adequacy criterion.** A test suite is "adequate" when its mutation score exceeds a threshold. For us: confidence can only rise above a threshold when evidence quality exceeds a threshold (e.g., live-meeting tests required for >50%).

**Sources:**
- [Are Mutation Scores Correlated with Real Fault Detection? — ICSE 2018](https://dl.acm.org/doi/pdf/10.1145/3180155.3180183)
- [Mutation Testing — Wikipedia](https://en.wikipedia.org/wiki/Mutation_testing)
- [Predicting Mutation Score Using Source Code and Test Suite Metrics](https://dl.acm.org/doi/abs/10.5555/2666527.2666536)
- [Test Suite Effectiveness Metric Evaluation — arXiv](https://arxiv.org/pdf/2204.09165)

---

## 4. Ceiling/Gate Patterns in Practice

### Key Pattern: SonarQube Quality Gates

SonarQube quality gates are the most widely deployed ceiling pattern in software. They enforce binary pass/fail conditions:

- **Conditions on new code:** Coverage ≥ 80%, duplications ≤ 3%, no new blocker issues
- **Conditions on overall code:** Maintainability rating ≥ A, reliability rating ≥ A
- **Binary outcome:** PASS or FAIL — no partial credit
- **Default gate (Sonar Way):** Built-in with industry-standard thresholds
- **AI-specific gate (Sonar Way for AI Code):** Stricter thresholds for AI-generated code

Key insight: quality gates don't score — they **block**. A project that passes 19/20 conditions but fails one is FAILED. This is the purest ceiling pattern.

### Key Pattern: Google Test Certified

Google's internal Test Certified framework used **leveled prerequisites** with hard gates:

| Level | Requirements | Gate Type |
|---|---|---|
| **Level 1** | Continuous build, test coverage metrics, test size classification, flaky test identification | Foundation — achievable in 1-5 days |
| **Level 2** | Written no-untested-code policy, numeric coverage goals, test size balance targets | Governance — weeks to months |
| **Level 3** | High coverage across all test sizes, low flaky/broken tolerance, sustained compliance | Sustained excellence — ongoing commitment |
| **Level 4-5** | More stringent coverage goals, static analysis integration | Advanced — added later |

Critical rule: **"The highest class of a component determines the class of the entire system."** One high-risk component elevates everything. This is the ceiling principle applied to system classification.

Certification required peer review by volunteer mentors — not self-assessed. Teams couldn't advance without external validation.

### Key Pattern: IEC 62304 Safety Classes (Medical Devices)

IEC 62304 classifies medical software into three safety classes with escalating requirements:

| Class | Risk Level | Required Activities | Gate |
|---|---|---|---|
| **A** | No injury possible | Requirements + release only | Minimal documentation |
| **B** | Non-serious injury | A + architecture + verification | Architecture review |
| **C** | Death/serious injury | B + detailed design + full V&V | Complete lifecycle documentation |

**Hard ceiling rule:** The highest class of any component determines the class of the entire system. A Class A system with one Class C component becomes Class C.

This directly maps to our ceiling: **one high-risk untested item caps the entire confidence**, regardless of how many low-risk items pass.

### Key Pattern: Progressive Delivery with Circuit Breakers

Feature flags + monitoring create confidence-gated rollouts:

1. Deploy to 1% → monitor metrics → confidence check
2. Expand to 10% → monitor → confidence check
3. Expand to 50% → monitor → confidence check
4. Full rollout

**Circuit breaker:** If any monitored metric crosses a threshold, the feature is automatically disabled. This is a real-time ceiling — one bad metric kills the rollout regardless of how well everything else performs.

### How It Maps to Our Model

| Gate Pattern | Our Model |
|---|---|
| SonarQube binary pass/fail | **Ceiling at 0** — any critical gate failure = confidence 0 |
| Google Test Certified levels | **Tiered DoD** — Level 1 items (API tests) gate Level 2 (live tests) |
| IEC 62304 "highest class rules" | **Ceiling propagation** — the riskiest untested item sets the ceiling |
| Circuit breaker auto-disable | **Hard stop** — any critical failure during testing stops progress |

### What We Steal

1. **Binary gates for critical items.** SonarQube doesn't give partial credit. Neither should we for critical-path items. If the bot can't join a meeting, confidence = 0, period.
2. **Leveled prerequisites (Test Certified).** Some DoD items gate others. You can't claim "live meeting test passed" if "bot deploys successfully" hasn't passed first. Build the dependency chain.
3. **Highest-class-rules-all (IEC 62304).** The riskiest untested item sets the confidence ceiling. 10 passing API tests don't compensate for 1 untested live-meeting scenario. Exactly our model.
4. **External validation.** Test Certified required peer review, not self-assessment. Our evaluator agent serves this role — the implementing agent can't declare its own confidence.

**Sources:**
- [SonarQube Quality Gates Documentation](https://docs.sonarsource.com/sonarqube-server/latest/quality-standards-administration/managing-quality-gates/introduction-to-quality-gates/)
- [Google Test Certified — Mike Bland](https://mike-bland.com/2011/10/18/test-certified.html)
- [IEC 62304 Safety Classes — Johner Institute](https://blog.johner-institute.com/iec-62304-medical-software/safety-class-iec-62304/)
- [IEC 62304 Safety Classifications — Greenlight Guru](https://www.greenlight.guru/glossary/iec-62304)
- [Progressive Delivery with Feature Flags — Flagsmith](https://www.flagsmith.com/blog/progressive-delivery)

---

## 5. Agentic/AI-Specific Confidence Calibration

### Key Finding: Agents Are Systematically Overconfident

**Kaddour et al. (2026) "Agentic Uncertainty":** Agents that succeed 22% of the time predict 77% success. Post-execution review is worse than pre-execution prediction for calibration. Adversarial framing ("find bugs in what you did") reduces overconfidence by ~15 percentage points.

**Dunning-Kruger in LLMs (March 2026):** Worst-performing models express highest confidence:
- Kimi K2: 23.3% accuracy, 95.7% mean confidence (ECE = 0.726)
- Claude Haiku 4.5: 75.4% accuracy, best calibration (ECE = 0.122)
- Extreme case: 3.9% accuracy with 97.9% confidence on TriviaQA (94-point gap)

**GPT-5.2-Codex agents:** Predict 73% success against true rate of 35% on SWE-Bench-Pro.

### Key Finding: Trajectory-Based Calibration Works

**Zhang et al. (2026) "Holistic Trajectory Calibration":** Instead of using agent's self-reported confidence, extract 48 features from the agent's entire trajectory (actions taken, tool calls, retries, error patterns) and train a classifier to predict success. This:
- Surpasses all baselines on 8 benchmarks
- Generalizes across LLMs and agent frameworks
- Works with ~400 samples
- Provides interpretability — reveals which trajectory signals predict failure

### Key Finding: Devin Uses Self-Assessed Confidence

Devin 2.1 uses a 0-100 confidence score. When confidence is low, it asks for clarification. This is self-reported confidence — our research shows this is unreliable (5.5x more likely to be confidently wrong).

### Key Finding: Verbalized Confidence Clusters at 80-100

**ICLR 2024 "Can LLMs Express Their Uncertainty?":** When asked for confidence scores, LLMs cluster responses in the 80-100 range regardless of actual accuracy. Token-level probabilities are better calibrated than verbalized scores, but not accessible in most agent frameworks.

### Key Finding: Multi-Agent Deliberation Improves Calibration

**Collaborative Calibration (2024):** Having multiple agents debate and reach consensus on confidence achieves calibration comparable to supervised methods — training-free. This maps to our evaluator agent role.

### How It Maps to Our Model

| AI Calibration Concept | Our Model |
|---|---|
| Agent self-reported confidence is unreliable | **Mechanical scoring only** — confidence computed from evidence, never self-assessed |
| Adversarial framing reduces overconfidence | **Adversarial self-assessment at 80+** — already in our framework |
| Trajectory features predict success | **Evidence accumulation** — the pattern of test passes/fails, not just the final count |
| Multi-agent deliberation | **Evaluator agent** validates confidence claims independently |
| Verbalized confidence clusters 80-100 | **Never trust "looks correct"** — observable signals only |
| Devin 0-100 self-assessed score | **Anti-pattern** — exactly what we avoid |

### What We Steal

1. **Mechanical scoring eliminates self-assessment bias.** Our weighted DoD model is inherently mechanical — confidence is computed from item pass/fail status and weights, not from the agent's feeling about correctness. This is the right approach per all research.
2. **Adversarial framing at threshold crossings.** Kaddour's finding that asking "find bugs" reduces overconfidence 15pp validates our existing protocol. Apply it specifically when the weighted score crosses delivery thresholds (70, 85).
3. **Trajectory signals as secondary evidence.** Number of retries, errors encountered, tools used — these are trajectory features that could modulate evidence strength. Many retries before a test passes = lower confidence than first-try pass.
4. **Independent evaluator validation.** Multi-agent deliberation's effectiveness validates our evaluator role. The evaluator should independently compute confidence from the same evidence.

**Sources:**
- [Agentic Uncertainty Reveals Agentic Overconfidence — arXiv 2602.06948](https://arxiv.org/abs/2602.06948)
- [Dunning-Kruger Effect in LLMs — arXiv 2603.09985](https://arxiv.org/html/2603.09985v1)
- [Agentic Confidence Calibration (HTC) — arXiv 2601.15778](https://arxiv.org/abs/2601.15778)
- [Language Models (Mostly) Know What They Know — Kadavath et al. 2022](https://arxiv.org/abs/2207.05221)
- [Can LLMs Express Their Uncertainty? — ICLR 2024](https://arxiv.org/abs/2306.13063)
- [Collaborative Calibration — arXiv 2404.09127](https://arxiv.org/abs/2404.09127)

---

## 6. Adjacent Patterns Worth Stealing

### Earned Value Management (EVM)

EVM uses weighted milestone completion to track project progress:

```
Planned Value (PV) = budget for scheduled work
Earned Value (EV) = budget value of completed work
Actual Cost (AC) = what was actually spent

Schedule Performance Index (SPI) = EV / PV
Cost Performance Index (CPI) = EV / AC
```

**Weighted milestones technique:** Each deliverable gets a budget value based on its importance. EV only accrues when the milestone is accomplished — partial credit is rare.

**Key insight for our model:** EVM distinguishes between "work done" and "value earned." An agent can do a lot of work (many tests run) without earning much value (critical path untested). Our weighted DoD makes this distinction explicit.

### DORA Metrics

DORA's four key metrics balance velocity and stability:

| Metric | Type | What It Measures |
|---|---|---|
| Deployment Frequency | Velocity | How often code ships |
| Lead Time for Changes | Velocity | Time from commit to production |
| Change Failure Rate | Stability | % of deployments requiring rollback |
| Failed Deployment Recovery Time | Stability | MTTR after failed deployment |

**2026 addition:** Deployment Rework Rate — direct measure of "did this change cause more work?"

**Key insight for our model:** DORA explicitly prevents over-indexing on speed at expense of reliability (or vice versa). Our model should similarly prevent gaming — can't reach high confidence by doing many easy tests (velocity) while ignoring hard tests (stability).

### Safety Integrity Levels (SIL)

IEC 61508 defines four levels with exponentially increasing rigor:

| SIL | Probability of Dangerous Failure per Hour | Target |
|---|---|---|
| SIL 1 | 10^-5 to 10^-6 | Basic |
| SIL 2 | 10^-6 to 10^-7 | Standard |
| SIL 3 | 10^-7 to 10^-8 | High |
| SIL 4 | 10^-8 to 10^-9 | Very high |

**Two dimensions of capability:**
1. **Hardware reliability** — probabilistic failure rates
2. **Systematic Capability (SC)** — design quality measure (not probabilistic)

**Hard gate rule:** SIL assessment determines requirements. SIL 3 mandates formal methods, independent V&V, and defensive programming. There's no trading "more testing" for "less formal methods." Each SIL level has hard prerequisites.

**Key insight for our model:** SIL separates probabilistic confidence (can this fail randomly?) from systematic quality (was this designed correctly?). Our model should similarly distinguish between "tests that verify behavior" (probabilistic) and "evidence of correct architecture" (systematic).

### IEC 62304 Risk-Based V&V (Medical Devices)

The safety classification drives verification depth:
- **Class A:** Requirements-level testing only
- **Class B:** A + architecture verification
- **Class C:** B + detailed design verification + full integration testing

**Ceiling rule:** The highest class of any component determines the class of the entire system. One Class C component makes everything Class C.

### What We Steal

1. **EVM's earned value ≠ effort.** Work done without testing the critical path earns zero value. Make this explicit: confidence only accrues from weighted items that actually pass.
2. **DORA's velocity/stability balance.** Prevent gaming by requiring both easy-to-test items (velocity — confirms basic function) AND hard-to-test items (stability — confirms critical path).
3. **SIL's hard prerequisites per level.** No trading between dimensions. If live-meeting testing is required at confidence >50%, no amount of API testing substitutes.
4. **IEC 62304's "highest class rules all."** This IS our ceiling. The riskiest untested item determines maximum possible confidence.

**Sources:**
- [Earned Value Management — Wikipedia](https://en.wikipedia.org/wiki/Earned_value_management)
- [EVM Explained — monday.com](https://monday.com/blog/project-management/earned-value-in-project-management/)
- [DORA Metrics — dora.dev](https://dora.dev/guides/dora-metrics/)
- [Safety Integrity Levels — Ektos](https://www.ektos.net/articles/safety-integrity-levels-sil-what-they-are-and-how-to-calculate-them/)
- [IEC 61508 and SILs — Perforce](https://www.perforce.com/blog/qac/what-iec-61508-safety-integrity-levels-sils)
- [IEC 62304 Safety Classifications — Greenlight Guru](https://www.greenlight.guru/glossary/iec-62304)

---

## Synthesis: Best-in-Class Weighted DoD Model

### The Model

Combining the strongest patterns from all six research areas:

```
Given:
  DoD items D1..Dn
  Each item has:
    - weight: points earned when passing (0-20)
    - ceiling: max overall confidence if NOT passing (0-100, default 100)
    - tier: "critical" | "high" | "medium" | "low"
    - group: logical grouping (e.g., "api", "live", "environment")
    - evidence_quality: scaling factor for how trustworthy the evidence is (0.0-1.0)

Scoring:
  raw_score = Σ(weight_i × pass_i × evidence_quality_i) / Σ(weight_i) × 100

  active_ceilings = [ceiling_i for each item_i where pass_i = false]
  effective_ceiling = min(active_ceilings) if any, else 100

  confidence = min(raw_score, effective_ceiling)
```

### Design Principles (from research)

| Principle | Source | Implementation |
|---|---|---|
| Critical items bypass averaging | Kayenta canary analysis | `ceiling: 0` for critical DoD items — one failure = confidence 0 |
| Highest risk rules all | IEC 62304, IEC 61508 | Riskiest untested item sets confidence ceiling |
| Binary gates for critical items | SonarQube quality gates | No partial credit on critical items |
| Risk = Impact × Detectability | ISO 29119, ISTQB RBT | Weight accounts for both importance and test difficulty |
| Earned value ≠ effort | EVM weighted milestones | Only passing items earn confidence points |
| Velocity/stability balance | DORA metrics | Require both easy API tests AND hard live tests |
| No self-assessed confidence | Kaddour 2026, Dunning-Kruger LLMs | Mechanical scoring from item status only |
| Hard prerequisites per tier | Google Test Certified, SIL | Live tests gated behind API tests passing first |
| External validation | Google Test Certified, multi-agent calibration | Evaluator agent independently validates |
| Three-tier decision | Kayenta pass/marginal/fail | Map to deliver (85+) / deliver-with-note (70+) / continue |
| Evidence quality matters | Mutation testing, DDP | CDP screenshot evidence > bot self-report > code review |

### Example: Bot Lifecycle DoD

```yaml
groups:
  environment:
    weight_share: 10   # 10% of total
    items:
      - name: "Services healthy"
        weight: 5
        ceiling: 20    # Can't be above 20% if services aren't running
        evidence: "curl health endpoints return 200"
      - name: "Bot image built and deployed"
        weight: 5
        ceiling: 15    # Can't proceed without bot image
        evidence: "docker ps shows running container"

  api:
    weight_share: 25   # 25% of total
    items:
      - name: "Create meeting returns 200"
        weight: 5
        ceiling: 40
        evidence: "curl POST /meetings returns meeting_id"
      - name: "Bot joins via API"
        weight: 10
        ceiling: 35
        evidence: "curl POST /bots returns bot_id, status transitions to joining"
      - name: "Automatic leave API works"
        weight: 10
        ceiling: 50
        evidence: "curl POST /leave returns 200, bot status transitions"

  live_meeting:
    weight_share: 50   # 50% of total — the critical path
    items:
      - name: "Bot admitted to meeting"
        weight: 15
        ceiling: 30    # HARD CAP — can't be above 30% without this
        evidence: "CDP screenshot shows bot in meeting, NOT in waiting room"
        evidence_quality: 1.0   # Screenshot is gold standard
      - name: "Bot captures audio/transcript"
        weight: 15
        ceiling: 25
        evidence: "Transcript segments appear in API response"
      - name: "Full lifecycle (join → capture → leave)"
        weight: 20
        ceiling: 20    # Can't claim any confidence without this
        evidence: "Complete session from join to leave with transcript data"

  dashboard:
    weight_share: 15   # 15% of total
    items:
      - name: "Meeting visible in dashboard"
        weight: 8
        ceiling: 60
        evidence: "Browser screenshot shows meeting in list"
      - name: "Transcript visible in dashboard"
        weight: 7
        ceiling: 55
        evidence: "Browser screenshot shows transcript content"
```

**Scenario analysis:**
- All API tests pass, no live tests run: raw_score = 25%, ceiling = min(30, 25, 20) = 20% → **confidence = 20%**
- All API + environment pass, no live tests: raw_score = 35%, ceiling = 20% → **confidence = 20%**
- All pass except dashboard: raw_score = 85%, ceiling = 55% → **confidence = 55%**
- Everything passes: raw_score = 100%, ceiling = 100 → **confidence = 100%**

The ceiling mechanic makes it **mathematically impossible** to reach high confidence without testing the critical path. This is the core insight from IEC 62304, SIL, Kayenta, and SonarQube — all converging on the same pattern.

### Implementation Priority

| Step | What | Effort |
|---|---|---|
| 1 | Define DoD items with weights and ceilings per feature | Low — document only |
| 2 | Mechanical scoring function (Python) that reads DoD YAML and item statuses | Low — simple math |
| 3 | Integrate with evaluator agent — it checks items and computes score | Medium |
| 4 | Evidence quality scaling (bot self-report < API response < CDP screenshot) | Medium |
| 5 | Dependency chains between tiers (live tests gated behind API tests) | Medium |
| 6 | Historical calibration tracking (predicted confidence vs actual human verdict) | Later |

### Open Questions

1. **Should groups have independent weights, or should items be weighted individually?** Kayenta uses group weights with even distribution within groups. ISO 29119 weights individual test cases. Recommendation: start with individual item weights (simpler to reason about), consider groups later if DoD lists grow large.

2. **How to handle "partially passing" items?** Some items have degrees (e.g., "transcript captures 80% of spoken words" vs "100%"). SonarQube uses thresholds (coverage ≥ 80%). Recommendation: define pass/fail thresholds per item, no partial credit for critical items. Partial credit only for "low" tier items where degree matters.

3. **What ceiling for newly-added gotcha-driven items?** When a gotcha creates a new DoD item, what should its initial ceiling be? Recommendation: ceiling = 100 - gotcha.severity × 100 (a severity 0.8 gotcha creates a ceiling of 20).

---

*Research compiled 2026-03-31. Update when new patterns emerge from practice.*
