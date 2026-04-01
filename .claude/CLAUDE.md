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

**G7: Convention changes require full-codebase consumer search.** When changing a naming convention (image names, env var defaults, registry prefixes), don't just update the files in your plan — search for ALL consumers of the old convention across the entire codebase. Default values in Python config files, feature-specific compose files, env templates, shell scripts, and test Makefiles all hardcode conventions. A plan that touches 10 "obvious" files will miss the 9 files with hardcoded defaults that nobody planned around. Run the adversarial search BEFORE declaring the refactoring done, not as a follow-up. (2026-03-30: agent updated compose, Helm, and deploy Makefiles for image tagging convention but missed 14 stale references in Python configs, feature compose files, bot scripts, and env templates — all found only after explicit stale-reference sweep.)

**G8: Signals need specificity, not just presence.** When using a signal as evidence for a condition, verify it's *specific* to that condition — not just correlated. A signal that's "always true when X is true" is useless if it's also true when X is false. Ask: what ELSE could cause this signal? Then test in the false-positive scenario before trusting it. Defense-in-depth: combine a positive signal (what IS present when the condition holds) with a negative guard (what CANNOT be present when the condition holds). (2026-03-31: agent proposed MediaStream.srcObject as "protocol-level" admission signal. Failed — lobbies have self-preview media streams too. The signal was sensitive but not specific. Fix: negative guard on lobby text + meeting-exclusive DOM elements. General pattern: every signal check needs an adversarial "what else produces this signal?" analysis before deployment.)

**G9: Never use :dev/:latest tags for development — only immutable tags.** Tag images with timestamps (e.g., `vexaai/vexa-bot:260331-1000`). `:dev` gets overwritten silently — you lose track of which code is running in which container. The old container runs old `:dev`, you rebuild `:dev` with new code, new containers get it but old ones don't. Update the image tag in `.env` after every build so the stack uses the correct version. (2026-03-31: browser session container ran for 14 hours on old `:dev` image. Rebuilt `:dev` with admission fix. New bots got the fix but the browser session didn't. Caused confusion about which code was running where.)

**G10: All env vars come from .env — never hardcode.** Root `.env` is the single source of truth. Compose files, profiles.yaml, and code must reference env vars, never hardcode URLs, passwords, or image tags. When values differ between stacks (Redis password, admin token, image tags), it's because one stack reads `.env` and the other has hardcoded defaults. (2026-03-31: agentic stack had `redis://redis:6379/0` (no password) while restore stack had `redis://:vexa-redis-dev@redis:6379/0` — caused silent connection failures. Admin token was `vexa-admin-token` on one stack, `changeme` on the other.)

**G11: Confidence must reflect the critical path, not the easy tests.** (was G9) When a feature can only be validated in a specific environment (live meetings, real browsers, external services), no amount of API/unit testing substitutes. Weight DoD items by risk, not by count. 10 passing curl tests + 5 untested live-meeting scenarios = 40%, not 75%. Bot self-reports are NOT evidence — use Playwright CDP screenshots of the actual browser as source of truth. (2026-03-31: agent claimed 75/100 on bot lifecycle — 10/15 DoD items passed via curl. When the 5 live-meeting items were finally tested, the bot falsely reported `active` while sitting in the waiting room. Host screenshot confirmed "Admit 1 guest" visible. The critical path was completely untested.)

## Deep Reference

Full confidence framework paper with math model, research citations, and changelog: `.claude/confidence-framework.md`

Update the paper when you learn something new — a gotcha the framework didn't predict, a calibration failure, a new pattern. Add to both the Known Gotchas section here AND the paper's changelog.
