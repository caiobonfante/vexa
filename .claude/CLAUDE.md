# Vexa Agentic Runtime

## Confidence Protocol

Confidence is evidence-based, never self-reported. "Code looks correct" = 0 confidence. Observable signals only: tests pass, curl returns expected response, visible in browser, logs show expected output.

**At every step:** Report what you verified and what confidence that gives you.

**At 80+:** Run adversarial self-assessment — "what bugs can you find in what I just did?" — before declaring done. This reduces overconfidence ~15pp.

**When delivery fails:** Stop. Don't patch. Diagnose root cause first. Report confidence at each diagnostic step. If confidence isn't rising after 3 steps, escalate.

**After human reveals you were wrong:** Extract the root gap WITH the human (not a shallow patch). What assumption failed? Store as a gotcha.

## Known Gotchas

Read these before starting work. These are lessons from past failures.

**G1: Test the system, not just the feature.** Before reporting confidence above 70, verify the basic user entry point: can the user load the dashboard? Does the API respond? Your own testing (curl bombardment, process restarts) can break the environment. (2026-03-29: 8/8 Playwright tests passed, agent claimed 80/100, dashboard was unreachable.)

**G2: Don't flail — diagnose before fixing.** When something breaks, the protocol is: (1) stop, don't touch code, (2) read logs, form hypothesis, (3) report confidence and what evidence would raise it, (4) only then attempt ONE fix per hypothesis, verify after. Don't restart services hoping it helps. (2026-03-29: agent tried allowedDevOrigins, process restart, cookie analysis, another restart — none based on diagnosis.)

**G3: CLAUDE.md changes don't reach running sessions.** If framework rules are updated mid-session, restart the session to pick them up.

**G4: "Cleanup" missions still need functional DoD.** A rename/refactor that touches live wiring (env vars, proxy routes, service URLs) can break every route. Grep-clean != working. If the mission touches anything that carries traffic at runtime, the DoD must include curl/deploy verification of the affected routes. (2026-03-30: agent wrote mission with DoD = "grep returns clean + compose config validates", reported 90/100. Human caught it — grep would pass even if all 20 proxy routes returned 502.)

**G5: Don't default to fallbacks — clean-cut renames, not shims.** When renaming env vars, config keys, or service references, replace everywhere. Don't propose `NEW_VAR or OLD_VAR` backward-compat logic unless the user explicitly asks for a transition period. Fallbacks add complexity, mask incomplete migrations, and keep dead names alive. The only things that survive a rename are frozen external contracts (API paths, token issuers, wire protocols that external clients depend on). (2026-03-30: agent proposed BOT_MANAGER_URL fallback in mission DoD — user corrected: "no fallbacks, bot-manager is dead, we hate fallbacks unless explicitly a design choice.")

**G6: Search ALL case variants when renaming.** When cleaning up references to a renamed component, search every casing pattern: `kebab-case` (bot-manager), `snake_case` (bot_manager), `SCREAMING_SNAKE` (BOT_MANAGER), `camelCase` (botManager), `PascalCase` (BotManager). Missing one pattern leaves live references in wire protocols, type definitions, and config keys. (2026-03-30: team grepped bot-manager/bot_manager/BOT_MANAGER across 107 files, reported 90/100 confidence. Human found 14 `botManagerCallbackUrl` references in live wire protocol code + `VEXA_BOT_MANAGER` env var in vexa-agent — all missed because camelCase was never searched.)

## Deep Reference

Full confidence framework paper with math model, research citations, and changelog: `.claude/confidence-framework.md`

Update the paper when you learn something new — a gotcha the framework didn't predict, a calibration failure, a new pattern. Add to both the Known Gotchas section here AND the paper's changelog.
