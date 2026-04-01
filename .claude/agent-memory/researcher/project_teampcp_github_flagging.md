---
name: TeamPCP Supply Chain Attack - GitHub Account Flagging Research
description: DmitriyG228/Vexa-ai flagged by GitHub after TeamPCP attack (March 2026). 73 stolen tokens used for spam. Support ticket #4199834 open. Comprehensive attack timeline and escalation strategies documented.
type: project
---

## Context
DmitriyG228 account and Vexa-ai org flagged by GitHub around 2026-03-24, returning 404. This coincides exactly with the TeamPCP supply chain attack campaign. The user is a VICTIM whose token was likely stolen and used for spam on BerriAI/litellm#24512 and/or other TeamPCP activities.

## Key Facts
- Support ticket #4199834 is open with GitHub
- The Vexa-ai organization returns 404 (consistent with flagged/suspended accounts)
- The flagging date aligns with TeamPCP's spam campaign on March 24, 2026

## TeamPCP Attack Summary
- March 19-24, 2026: Cascading supply chain attack across Trivy, Checkmarx KICS, LiteLLM
- Stolen GitHub PATs from CI/CD runner memory used to: clone repos, create PRs, create docs-tpcp exfiltration repos, post spam
- 88 bot comments from 73 unique COMPROMISED DEVELOPER accounts in 102 seconds on litellm#24512
- 76% account overlap between Trivy and LiteLLM spam campaigns
- Accounts were previously compromised developers, NOT purpose-created

## Escalation Strategies That Worked for Others
1. GitHub Appeal form: support.github.com/contact/reinstatement (6-month window)
2. Social media pressure (Hacker News, Twitter/X) - documented as accelerating response
3. Reply to existing ticket instead of opening new ones
4. Organization admin filing ticket may help
5. Reference the TeamPCP CVE/advisory explicitly: GHSA-69fq-xp46-6x23
6. Typical timeline: 24-72 hours but can be weeks/months for complex cases

**Why:** Account and org access is critical for the Vexa project. The flagging appears to be a false positive from GitHub's automated spam detection reacting to activity performed using stolen credentials.

**How to apply:** Reference this research when composing appeal communications. The key argument is that the account was a VICTIM of the TeamPCP supply chain attack, not a participant.
