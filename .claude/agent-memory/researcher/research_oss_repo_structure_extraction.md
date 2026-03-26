---
name: OSS Repository Structure for Extraction
description: Tradeoffs between separate repo, monorepo, git subtree, git submodule, and package extraction when open-sourcing an internal component. Includes real-world examples and a recommendation for small teams extracting a ~764-line Python FastAPI CaaS.
type: project
---

# Repository Structure for Open-Source Extraction

## Context
Vexa needs to extract its Runtime API (~764 lines Python, FastAPI, Container-as-a-Service) as an open-source project while continuing to use it internally. Team is 1-2 people.

## Five Approaches Evaluated

### 1. Separate Repo from Day 1

**Examples:** Kubernetes (extracted from Borg concepts, clean start), React (separate from Facebook monorepo via fbshipit), Temporal (fork of Uber Cadence, separate repo from start), E2B (main SDK in e2b-dev/E2B, code-interpreter SDK split to e2b-dev/code-interpreter), Steel (steel-dev/steel-browser separate from commercial Steel product)

**Pros:**
- Clean git history, no proprietary artifacts to scrub
- Community can fork/clone/PR without touching product code
- Independent release cadence (semver, changelogs)
- Clear ownership boundary — CODEOWNERS, CI, issues are all self-contained
- PyPI/npm publishing is straightforward from a standalone repo
- External contributors don't need to understand your product to contribute

**Cons:**
- Cross-repo changes require coordinated PRs (product + library)
- Lose atomic commits — can't change API + consumer in one commit
- Dependency version management: product pins library version, can lag
- For 1-2 person team: overhead of maintaining two repos (two CIs, two issue trackers, two PR review flows)

**When it works:** When the component has a stable API boundary, when you want genuine external contributors, when the project is large enough to justify the overhead.

### 2. Monorepo with Product

**Examples:** Supabase (supabase/supabase contains dashboard, docs, SDKs, backend services all in one repo using pnpm + Turbo), Grafana (grafana/grafana contains everything), PostHog (posthog/posthog is the whole product)

**Pros:**
- Single CI, single PR flow, atomic commits across component + product
- Zero sync overhead — internal and open-source are literally the same code
- For tiny teams: minimal operational overhead, everything in one place
- Refactoring across boundaries is trivial
- Contributors can see how the component fits the larger system

**Cons:**
- Exposes entire product codebase (may include proprietary logic, configs, secrets in history)
- Contributors must clone the whole repo even if they only care about one component
- Issue tracker gets noisy (product bugs mixed with library bugs)
- Can't have different licenses for different parts easily
- Hard to publish a subset as a standalone package
- If product is NOT open-source, this approach is impossible

**When it works:** When the entire product IS the open-source project (Supabase, Grafana, PostHog model). Does NOT work when extracting a component from a proprietary product.

### 3. Git Subtree

**How it works:** `git subtree split --prefix=services/runtime-api` extracts all commits touching that path into a synthetic branch with the subdirectory at the root. You push that branch to a separate repo. Changes flow both ways: `git subtree push` sends changes out, `git subtree pull` brings community changes back.

**Tools:** git subtree (built-in), splitsh-lite (faster alternative), Google Copybara (declarative sync with transformations)

**Examples:** Symfony (splits monorepo into ~50 read-only component repos using splitsh-lite), Laravel (similar split approach)

**Pros:**
- Preserves commit history for the extracted component
- Bidirectional sync is possible (push changes out, pull community changes back)
- No `.gitmodules` file, transparent to collaborators
- Product repo remains source of truth
- `splitsh-lite` makes this fast even for large repos

**Cons:**
- Complexity accumulates — merge conflicts in subtree operations are notoriously painful
- History rewriting during split can produce confusing commit messages
- If the extracted component has dependencies on other parts of the monorepo, the split is messy
- External repos are typically read-only mirrors (Symfony model) — community PRs still go to the monorepo
- For a 764-line project with short history, preserving history has low value

**When it works:** Large monorepos with established components that have clear directory boundaries. PHP ecosystem uses this heavily (Symfony, Laravel). Less common in Python ecosystem.

### 4. Git Submodule

**Why people hate it (documented extensively):**
- Breaks worktrees (multi-checkout is incomplete)
- `git clone` doesn't fetch submodules by default — new contributors hit "empty directory" confusion
- Switching branches requires manual `git submodule update --init --recursive`
- Merge conflicts in submodule pointers are treated as binary — no 3-way merge
- Creates invisible coupling: developers work on stale submodule versions unknowingly
- Most IDEs and tools treat submodules as afterthoughts
- Diamond dependency problem when transitive deps overlap
- Making breaking changes across submodule boundaries is extremely painful to coordinate

**When it (barely) works:**
- Very loosely coupled relationship — the submodule is essentially a vendored third-party dep
- You never modify the submodule from the parent repo
- The submodule has its own independent release/test cycle

**Verdict for this case:** Not recommended. The Runtime API will be actively developed alongside the product. Submodules create friction at every step.

### 5. Package Extraction (publish as library)

**How it works:** Extract the component into its own repo, publish to PyPI (or private index), consume it as `pip install vexa-runtime` in the product.

**Examples:** Django (extracted from Lawrence Journal-World's CMS in 2005, published as standalone framework), FastAPI itself (tiangolo extracted it from internal projects), Celery, Pydantic — basically every popular Python library

**The Django story:** Adrian Holovaty and Simon Willison built Django inside the Lawrence Journal-World newspaper's CMS. They "built up" a generic framework from the newsroom's needs, then convinced the company to open-source it. The framework became 100x more valuable than the CMS. The CMS continued using Django as a dependency.

**Pros:**
- Cleanest separation — product consumes library via standard dependency management
- Community can install and use without any knowledge of your product
- Forces good API design (you must define a stable interface)
- Standard Python packaging workflow (pyproject.toml, PyPI, semver)
- Product pins to specific versions, upgrades deliberately

**Cons:**
- Initial extraction requires refactoring to remove product-specific coupling
- Development cycle is slower: change library -> release -> update product dependency
- For rapid iteration phase: friction of version bumping feels heavy
- Can mitigate with `pip install -e ./path/to/local/checkout` during development

**When it works:** When the component has (or should have) a clear API boundary. When you want it to be usable by others as a standalone tool. When the component is mature enough that API changes are infrequent.

## Sync Tools (if maintaining dual repos)

| Tool | Maintainer | Direction | Complexity | Status |
|------|-----------|-----------|------------|--------|
| git subtree | Git core | Bidirectional | Medium | Built-in |
| splitsh-lite | Symfony | Mono -> multi | Low | Active |
| fbshipit | Meta (archived) | Mono -> multi | High | Archived |
| Google Copybara | Google | Configurable | High | Active |
| git filter-repo | Community | One-time extraction | Low | Active, recommended over filter-branch |

## Recommendation for Vexa Runtime API

**Approach: Separate repo + package extraction (Option 1 + Option 5 combined)**

Rationale for a 1-2 person team with a ~764-line Python FastAPI project:

1. **Use `git filter-repo` for one-time extraction** — extract `services/runtime-api/` with history into a new repo. For 764 lines, this is a 5-minute operation.

2. **Publish to PyPI** — standard Python packaging, `pip install vexa-runtime`. This is the Django model and it works.

3. **Product consumes as dependency** — `pip install vexa-runtime` in the product repo. During development, use `pip install -e ../vexa-runtime` for rapid iteration without version bumping.

4. **Do NOT use git subtree or submodule** — the overhead is not justified for this project size. Bidirectional sync tools solve problems you don't have yet.

5. **Do NOT use monorepo-with-product** — Vexa's product repo contains proprietary meeting logic, bot code, dashboard, etc. Exposing all of that is not the goal.

**Why not just a separate repo without PyPI?** You could, but publishing to PyPI costs nothing and makes the project instantly usable by anyone: `pip install vexa-runtime && vexa-runtime serve`. This is the difference between "open source on GitHub" and "open source that people actually adopt."

**Development workflow:**
```
# Day-to-day: edit the library locally, product uses editable install
cd vexa-product/
pip install -e ../vexa-runtime/

# Release: bump version, push tag, CI publishes to PyPI
cd vexa-runtime/
bump2version minor
git push --tags
# GitHub Actions publishes to PyPI

# Product: pin to released version for production
pip install vexa-runtime==1.2.0
```

**Mitigating the "two repos" overhead:**
- Both repos can share a single GitHub Actions workflow template
- Use a single GitHub Project board for cross-repo issue tracking
- Dependabot or Renovate auto-creates PRs when the library releases
- For a 1-2 person team, you ARE the reviewer on both repos — there's no coordination tax

**If the team grows or the project gets big:** Revisit. The separate-repo approach scales up naturally. Starting in a monorepo and splitting later is always harder than starting separate.

## Key Sources
- HN: "What is the best way to open-source packages from a company monorepo?" (2020)
- Meta Engineering: FBShipIt for monorepo-to-GitHub sync
- Atlassian: Git Subtree tutorial
- Tim Hutt: "Reasons to avoid Git submodules"
- OmbuLabs: "Open sourcing a private project"
- Django history: Simon Willison's account of extraction from LJW
- E2B: SDK split into separate repos (e2b-dev/E2B + e2b-dev/code-interpreter)
- Supabase: monorepo structure (supabase/supabase with pnpm + Turbo)
