# Mission: .env as Single Source of Truth

Focus: development infrastructure, all services
Problem: Environment variables are scattered across `.env`, `.env.local`, compose `environment:` blocks with hardcoded defaults, and `profiles.yaml`. Values diverge silently between services and stacks, causing auth failures, wrong image tags, and unreachable services — discovered only at runtime.
Target: Root `.env` is the sole place a developer sets configuration. `make up` (and `npm run dev` for dashboard) produces a fully working stack with no manual env file creation, no `.env.local`, no surprises.
Stop-when: A fresh clone + `cp .env.example .env` + `make up` produces a working stack. Dashboard `npm run dev` works without `.env.local`. Every compose service's env vars trace back to `.env`.
Constraint: Dev/local only. No hosted/SaaS deployment, no Helm/K8s changes.

---

## Context: Why This Mission Exists

Reference: Gotcha G10 — "All env vars come from .env — never hardcode."

Observed on 2026-03-31 during agentic runtime development:

1. **Dashboard needs `.env.local` with duplicated vars.** `npm run dev` fails without hand-crafted `.env.local` containing `VEXA_API_URL`, `VEXA_API_KEY`, `NEXT_PUBLIC_VEXA_API_URL`. These duplicate values already in root `.env`.

2. **Compose services hardcode divergent defaults.** `ADMIN_TOKEN` vs `ADMIN_API_TOKEN` — different names for the same secret across services. Redis passwords: one stack uses `redis://redis:6379/0` (no auth), another uses `redis://:vexa-redis-dev@redis:6379/0`. Neither reads from `.env`.

3. **Missing env vars in compose.** `INTERNAL_API_SECRET` was absent from compose `environment:` but required for gateway-to-admin-api auth. `BOT_IMAGE_NAME` was absent from runtime-api compose, so browser sessions defaulted to `:latest` instead of the built tag.

4. **Port drift.** Dashboard port changed to 3002 because a stale process held 3001. `.env` said 3001 but the running stack used 3002. No single place governed the port.

5. **Two stacks, divergent values.** Restore and agentic stacks running simultaneously with different Redis passwords, different admin tokens, different image tags — all because env values were hardcoded in multiple places instead of read from one.

6. **SSR vs client URL split.** Dashboard `VEXA_API_URL` needs `http://api-gateway:8000` for server-side rendering (Docker network) but `http://localhost:8056` for client-side fetches. Two different values for the "same" var, managed ad-hoc.

7. **Multi-step auth provisioning.** `VEXA_API_KEY` requires running a Makefile target, then manually appending the result to `.env`. Fragile and undocumented.

---

## Phase 1: Audit and Inventory

**Goal:** Complete map of every env var across every service — where it's defined, where it's consumed, what its default is, and whether it diverges.

### Tasks

- [ ] Grep all `docker-compose*.yml` files for `environment:` blocks. For each var: note whether it references `${VAR}` (from `.env`) or hardcodes a value.
- [ ] Grep all `profiles.yaml` files for `${...}` references. Note which vars are expected but never passed through compose.
- [ ] Grep dashboard code (`services/dashboard/`) for `process.env.*` and `NEXT_PUBLIC_*` references. Map each to its source (`.env.local`, `next.config.js`, nowhere).
- [ ] Grep all Python service code for `os.environ`, `os.getenv`, `config.*` patterns that read env vars. Map each to its compose `environment:` entry (or note if missing).
- [ ] Produce a single inventory table: `VAR_NAME | service | source (compose/code/profiles) | default | .env present? | diverges?`
- [ ] Identify var name conflicts (same concept, different names across services — e.g., `ADMIN_TOKEN` vs `ADMIN_API_TOKEN`).

### DoD

- [ ] Inventory table exists (in this mission file or a scratch doc) covering all services
- [ ] Every var name conflict is listed with resolution (which name wins)
- [ ] Every var missing from `.env` but needed at runtime is listed

---

## Phase 2: Normalize Compose Environment Blocks

**Goal:** Every compose service reads its env vars from root `.env` via `${VAR}` syntax. No hardcoded defaults in compose files. Compose `env_file:` directive points to root `.env` where appropriate.

### Tasks

- [ ] For each compose service, replace hardcoded `environment:` values with `${VAR_NAME}` references
- [ ] Resolve var name conflicts — pick one canonical name per concept, update all consumers
- [ ] Add missing vars to compose `environment:` blocks (e.g., `INTERNAL_API_SECRET`, `BOT_IMAGE_NAME` for runtime-api)
- [ ] Add all required vars to `.env.example` with safe defaults and comments
- [ ] Ensure `profiles.yaml` vars are passed through compose `environment:` into the container that reads them

### DoD

- [ ] `grep -r "environment:" docker-compose*.yml` shows only `${VAR}` references, zero hardcoded values (except Docker-internal hostnames like service names that are compose topology, not config)
- [ ] `docker compose config` with only `.env` populated shows fully resolved values — no empty vars, no `${MISSING}`
- [ ] `profiles.yaml` vars all resolve — `docker compose exec runtime-api env | grep BOT_IMAGE` shows the correct tag
- [ ] Verify: `make up` starts all services, `curl localhost:8056/health` returns 200, admin API responds with correct token

---

## Phase 3: Dashboard Environment Unification

**Goal:** `npm run dev` works using root `.env` values. No `.env.local` needed. SSR vs client URL split is handled cleanly.

### Tasks

- [ ] Configure Next.js to read from root `.env` (via `next.config.js` env key, dotenv preload, or symlink — pick simplest)
- [ ] Resolve the SSR/client URL split: `VEXA_API_URL` (server-side, Docker-internal or localhost depending on context) vs `NEXT_PUBLIC_VEXA_API_URL` (client-side, always localhost). Document the distinction in `.env.example`.
- [ ] Remove `.env.local` from the required setup steps. If it exists, it should only override for personal preferences, not be required.
- [ ] Dashboard port: governed by `DASHBOARD_PORT` in `.env`, used by both `npm run dev` and compose

### DoD

- [ ] `rm services/dashboard/.env.local && cd services/dashboard && npm run dev` starts successfully and loads in browser
- [ ] Dashboard can fetch data from API (SSR works, client-side works)
- [ ] `.env.example` documents all dashboard vars with comments explaining SSR vs client distinction
- [ ] No `.env.local` in any setup documentation as a required step

---

## Phase 4: Auth Token Provisioning

**Goal:** `VEXA_API_KEY` provisioning is automated as part of `make up` or a single `make setup-env` command — not a manual multi-step process.

### Tasks

- [ ] Create a `make setup-env` target (or integrate into `make up`) that:
  - Copies `.env.example` to `.env` if `.env` doesn't exist
  - Provisions `VEXA_API_KEY` via admin API and appends/updates it in `.env`
  - Validates all required vars are present
- [ ] Document the one-command setup in the root README or Makefile help

### DoD

- [ ] Fresh clone: `make setup-env && make up` produces a working stack with valid auth
- [ ] `VEXA_API_KEY` in `.env` is valid — `curl -H "Authorization: Bearer $VEXA_API_KEY" localhost:8056/api/health` returns 200
- [ ] No manual steps between clone and working stack (beyond `make setup-env && make up`)

---

## Phase 5: .env.example as Living Documentation

**Goal:** `.env.example` is complete, grouped, commented, and stays in sync.

### Tasks

- [ ] Group vars by service/concern: Database, Redis, Auth, API Gateway, Dashboard, Bot Config, Image Tags
- [ ] Mark required vs optional (optional = has a safe default)
- [ ] Add comments explaining non-obvious vars (especially the SSR/client URL split, internal secrets, image tag convention)
- [ ] Add a CI/lint check or Makefile target: `make check-env` that diffs `.env` against `.env.example` and warns about missing vars

### DoD

- [ ] `.env.example` has every var from the Phase 1 inventory
- [ ] Every var has a comment explaining its purpose
- [ ] `make check-env` reports missing vars when `.env` is incomplete
- [ ] A new developer can read `.env.example` and understand what each var does without reading source code

---

## Verification Method

Verify by running, not reading code. The ultimate test:

```bash
# Simulate fresh clone
git stash  # or use a clean worktree
rm -f .env services/dashboard/.env.local

# One-command setup
make setup-env

# Start everything
make up

# Verify stack
curl -s localhost:8056/health          # gateway
curl -s localhost:8056/api/meetings    # admin-api through gateway (needs auth)
cd services/dashboard && npm run dev   # dashboard without .env.local
# Open browser → dashboard loads, can see meetings
```

Each phase has its own DoD verified against the running system before proceeding.

---

## Anti-Patterns to Avoid

Per project gotchas:

- **No fallbacks** (G5). Don't do `NEW_VAR or OLD_VAR`. Pick the canonical name, update everywhere, old name dies.
- **Search all case variants** (G6). When renaming vars, search `kebab-case`, `snake_case`, `SCREAMING_SNAKE`, `camelCase`, `PascalCase`.
- **Full consumer search** (G7). When changing a default, find ALL files that hardcode that default — Python configs, shell scripts, test Makefiles, feature compose files.
- **No hardcoded defaults in compose** (G10). `${VAR}` references only. If a service needs a default, the service code provides it, not the compose file.
- **Functional DoD** (G4). Grep-clean is not done. Every phase ends with a curl/run verification.
