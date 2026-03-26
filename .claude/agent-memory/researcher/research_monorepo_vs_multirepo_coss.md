---
name: Monorepo vs Multi-Repo for COSS
description: Deep research on how Supabase, Grafana, HashiCorp, Docker, Temporal, PostHog, GitLab manage repo structure — practical decision criteria for composable infrastructure
type: project
---

# Monorepo vs Multi-Repo: COSS Company Deep Dives

## 1. Supabase — Hybrid (Monorepo + Separate Component Repos)

**Structure:** `supabase/supabase` is a pnpm monorepo (Turbo-orchestrated) containing:
- Frontend apps: Studio (admin dashboard), Docs, WWW (marketing), design-system, ui-library
- Shared packages: UI components, auth helpers, PostgreSQL metadata, AI commands, pricing data
- Docker Compose configs for self-hosted deployment
- E2E tests

**Separate repos for backend services:**
- PostgREST (Haskell) — REST API from Postgres schemas
- GoTrue/Auth (Go) — JWT authentication
- Realtime (Elixir/Phoenix) — WebSocket subscriptions
- Storage API (TypeScript/Node.js) — file management
- Edge Runtime (Rust/Deno) — serverless functions
- postgres-meta — database introspection

**Where development happens:** Backend services are developed in their own repos (different languages: Haskell, Go, Elixir, Rust). The monorepo develops the frontend/dashboard/SDK layer.

**Version coordination:** Docker images pin service versions. The monorepo's `docker/` directory defines Docker Compose with specific image tags. pnpm workspace catalog enforces consistent versions for frontend deps.

**Tooling:** pnpm 10 workspaces + Turborepo for caching/parallel builds. Node >=22 enforced. Backend services run in Docker containers during local dev via `supabase start`.

**Star strategy:** 78k+ stars on supabase/supabase. The monorepo is the "landing page" repo — it contains the README, docs, and getting-started experience. Component repos (GoTrue ~10k, Realtime ~7k) have their own stars but the meta-repo is the marketing funnel.

**Key insight:** Supabase's monorepo is a **product shell** that orchestrates independently-developed backend services via Docker. Components are in different languages, making a true monorepo impossible. The monorepo holds the integration layer (SDK, dashboard, docs, docker-compose).

---

## 2. Grafana Labs — Multi-Repo (Separate Products)

**Structure:** Each observability product is a separate Go repository:
- grafana/grafana (66k stars) — visualization/dashboard
- grafana/loki (~25k stars) — logs
- grafana/mimir (~4k stars) — metrics (forked from Cortex)
- grafana/tempo (~4k stars) — traces
- grafana/alloy — collector (formerly Grafana Agent)
- grafana/k6 — load testing
- grafana/pyroscope — continuous profiling

**Why multi-repo:** Products serve different purposes (logs vs metrics vs traces), have different operational characteristics, and can be deployed independently. They share the Go ecosystem but have separate release cadences.

**Cross-repo coordination:**
- Helm charts coordinate deployment (lgtm-distributed chart installs all components)
- Shared tooling: `enterprise-provisioner` was recently consolidated from separate per-product provisioners into a single repo
- Each product has its own dedicated team within Grafana Labs

**The Mimir/Cortex story:** Grafana Labs was the largest Cortex contributor. They forked it in March 2022 as Mimir, relicensed from Apache-2.0 to AGPLv3 to prevent free-riding cloud vendors. They ripped out legacy storage engine and set new defaults. This was a **strategic extraction + relicense** to capture value.

**Release coordination:** Independent releases per product. Helm chart library provides coordinated deployment versions.

**Key insight:** Multi-repo works when products genuinely serve different use cases and can be deployed independently. Grafana's products are united by the dashboard (grafana/grafana) but operationally independent. The Helm chart is the integration point, not a monorepo.

---

## 3. HashiCorp — Multi-Repo (Plugin Architecture)

**Structure:** Each product is a separate Go repo:
- hashicorp/terraform (~44k stars)
- hashicorp/vault (~32k stars)
- hashicorp/consul (~29k stars)
- hashicorp/nomad (~15k stars)
- hashicorp/packer (~15k stars)

**Cross-product coordination via go-plugin:**
HashiCorp built `hashicorp/go-plugin` — a Go plugin system over gRPC/RPC. Plugins run as separate OS processes communicating over mutually-authenticated TLS channels. This is THE coordination mechanism. Products don't share code at build time; they communicate at runtime via RPC.

**SDK extraction story:** The Terraform Plugin SDK was originally inside terraform core. It was extracted to `hashicorp/terraform-plugin-sdk` in September 2019 because:
- SDK couldn't follow its own semver while embedded in core
- External developers couldn't build providers without importing all of Terraform
- Now has its own version lifecycle: terraform-plugin-sdk → terraform-plugin-framework → terraform-plugin-go (layered abstractions)

**Version coordination:**
- Go modules with semver
- Provider registry handles compatibility (provider declares terraform version constraints)
- HCP Terraform workspaces coordinate cross-product deployments
- Remote state sharing between workspaces enables cross-product data flow

**Key insight:** HashiCorp's products are **operationally independent** — you can use Terraform without Vault. The go-plugin gRPC architecture means multi-repo is natural. SDK extraction was necessary when the internal SDK constrained external developers.

---

## 4. Docker — Multi-Repo (Component Extraction + Donation)

**Structure:** Core components are separate repos, many donated to standards bodies:
- moby/moby (~70k stars) — engine (was docker/docker)
- containerd/containerd (~18k stars) — runtime (donated to CNCF 2017)
- opencontainers/runc (~12k stars) — low-level runtime (donated to OCI)
- moby/buildkit (~8k stars) — build system
- docker/compose — multi-container orchestration
- docker/cli — command-line interface

**Why extract:** Docker was originally monolithic. As adoption grew, "complementary tools couldn't build on specific pieces of Docker since nothing was componentized." External vendors had to import Docker's entire platform to use any piece of it.

**Version pinning:**
- go.mod dependencies track component versions
- Explicit version files (e.g., RUNC.md specifies required runc version)
- Docker Desktop/CE/EE pin specific versions of all components per release

**The Moby brand confusion:** Renaming docker/docker to moby/moby at DockerCon 2017 was technically correct but poorly communicated. Maintainers understood; casual community members were confused. Solomon Hykes compared it to "Moby is to Docker what Fedora is to Red Hat Enterprise Linux" — but this analogy arrived too late.

**Four-layer architecture emerged:**
1. Upstream components (containerd, runc) — standards bodies
2. Moby — community project
3. Docker CE — community edition
4. Docker EE — enterprise edition

**Key insight:** Docker's extraction was STRATEGICALLY CORRECT but TACTICALLY MESSY. The donated components (containerd, runc) became industry standards. The confusion was a branding/communication failure, not an architecture failure. For Vexa: extract components when external consumers need them, but plan the naming/branding carefully.

---

## 5. Temporal — Multi-Repo (Shared Core + Cross-SDK Testing)

**Structure:**
- temporalio/temporal — server (Go)
- temporalio/sdk-core — shared Rust core (foundational)
- temporalio/sdk-go, sdk-java, sdk-python, sdk-typescript — language SDKs
- temporalio/features — cross-SDK compatibility testing
- temporalio/ui — web interface
- temporalio/cli — command-line tool

**The sdk-core architecture (brilliant pattern):**
Three-layer design:
1. **Shared Core (Rust)** — complex, centralized business logic
2. **Rust Bridge** — thin FFI layers (PyO3 for Python, neon for JS)
3. **SDK (Host Language)** — minimal outer layer with idiomatic API

Why Rust: safety, speed, portability, strong C FFI. Dramatically reduces bugs by eliminating code duplication across SDKs. Small team scales to 6+ language SDKs.

**Cross-repo compatibility:**
- `temporalio/features` repo has test harnesses for every language
- GitHub workflows test SDK changes against server, and server changes against SDKs
- Server built into Docker image, SDK synced as path-version dependency
- History compatibility testing: generated on earliest compatible version

**Version compatibility guarantee:** SDKs are backwards-compatible with server. No need to upgrade in lockstep. Older SDKs work with newer servers (missing new features). Newer SDKs work with older servers.

**Key insight:** Temporal solved multi-repo coordination through (a) a shared Rust core that eliminates duplication, (b) a dedicated compatibility test repo, and (c) backwards-compatible protocol design. This is the gold standard for multi-language multi-repo projects.

---

## 6. PostHog — Monorepo (With ee/ Directory)

**Structure:** Single repo `posthog/posthog` (22k+ stars):
- MIT license for everything EXCEPT ee/ directory
- ee/ directory has a separate proprietary license
- `posthog-foss` is a stripped repo for 100% FOSS users

**Scale:** 98 engineers, 65 commits/day to main.

**Why NOT extract:**
- Speed over modularity — small teams working on a single product benefit from atomic changes
- All components are the same language (Python/Django backend, React/TypeScript frontend)
- Same deployment target — everything deploys as one unit
- Extracting would create coordination overhead without clear benefit

**Enterprise separation:** The ee/ directory approach avoids needing a separate repo. License file in ee/ restricts commercial use. posthog-foss is auto-generated stripped version.

**Key insight:** PostHog chose monorepo because they're building ONE PRODUCT with one deployment. The ee/ directory pattern is simpler than maintaining a separate enterprise repo. This works because PostHog has no reusable components that external projects need independently.

---

## 7. GitLab — Monorepo (Famous)

**Structure:** gitlab-org/gitlab is the main monorepo. Contains:
- Rails backend
- Vue.js frontend
- GraphQL API
- CI/CD configuration
- Database migrations

**Separate repos for:** gitlab-runner, gitlab-pages, gitaly (git storage) — because they're different languages (Go) and different deployment targets.

**Why monorepo:**
- Atomic commits across multiple systems
- Unified CI/CD pipeline
- Reduced coordination overhead
- Consistent documentation
- Single onboarding experience

**Monorepo challenges they've addressed:**
- Custom monorepo performance tooling (Gitaly is their git storage service, which handles monorepo scaling)
- CI pipeline optimization to avoid running everything on every change

**Key insight:** GitLab's monorepo works because it IS one product with one deployment. The exceptions (runner, pages, gitaly) are separate because they're Go binaries with different deployment targets. The rule: same language + same deployment = monorepo; different language/deployment = separate repo.

---

## Release Management Tooling Comparison

### Changesets (@changesets/cli)
- **Best for:** Complex monorepos with multiple publishable packages
- **Philosophy:** Explicit change declarations by developers
- **Monorepo support:** Native, designed for it
- **Pros:** Maximum control, collaborative changelogs, no surprise releases
- **Cons:** Extra step per PR (creating changeset file), easy to forget

### Release Please (Google)
- **Best for:** Small-medium teams wanting balanced automation
- **Philosophy:** PRs as release gates
- **Monorepo support:** Good, with straightforward configuration
- **Pros:** GitHub-native, audit trail, battle-tested
- **Cons:** Requires manual PR merging, less automated than alternatives

### semantic-release
- **Best for:** Fast-moving teams with strict conventional commit discipline
- **Philosophy:** Commit messages drive everything, zero manual intervention
- **Monorepo support:** POOR — fundamentally single-package, community plugin (semantic-release-monorepo) is unmaintained since 2022
- **Pros:** Fully automated, rich plugin ecosystem
- **Cons:** Less control, requires strict commit conventions, bad monorepo story

### Recommendation for small teams: **Release Please** — sufficient automation without requiring organizational commitment to conventional commits.

---

## Git Subtree vs Submodule vs Package Dependency

### Git Submodules
- **What:** Reference to a specific commit in another repo
- **Best for:** Stable, rarely-changing external dependencies
- **Gotcha:** Can't edit submodule code freely; must cd in and manage separately
- **Verdict:** PAINFUL for active development across projects. OK for pinning stable components.

### Git Subtrees
- **What:** Pulls external repo code directly into your repo at a specific path
- **Best for:** Publishing parts of a monorepo as standalone packages
- **Case study:** Apollo uses git subtrees to publish Swift packages from a monorepo. GitHub Actions auto-runs `git subtree split` on merge to push changes to component repos.
- **Verdict:** GOOD for "develop in monorepo, publish as separate packages" pattern. More complex git history.

### Package Dependencies (pip/npm/etc.)
- **What:** Published packages consumed via package registry
- **Best for:** Stable, versioned interfaces between independent projects
- **Gotcha:** Development cycle requires publish → install → test loop
- **Verdict:** BEST for truly independent components. Overhead only justified when interface is stable.

### uv Workspaces (Python-specific)
- **What:** Single lockfile + virtual env for multiple packages in one repo
- **How:** Root `pyproject.toml` defines `[tool.uv.workspace] members = ["packages/*"]`
- **Inter-package deps:** `workspace = true` source directive, installed in editable mode
- **Constraint:** All members must share compatible dependencies
- **Publishing:** Each package has its own `pyproject.toml`, can publish independently to PyPI
- **Verdict:** THE RIGHT CHOICE for Python monorepos with publishable components.

---

## Decision Framework for Small Teams (2-5 People)

### Choose MONOREPO when:
1. **Single product, single deployment** (PostHog, GitLab pattern)
2. **Same language ecosystem** throughout
3. **High coupling** — changes frequently span multiple components
4. **Small team** — coordination overhead of multi-repo exceeds monorepo tooling overhead
5. **Speed matters more than modularity** — atomic commits win

### Choose MULTI-REPO when:
1. **Components are different languages** (Supabase: Haskell/Go/Elixir/TypeScript)
2. **Components are independently deployable** and independently useful (Grafana: Loki vs Mimir)
3. **External consumers** need to use components without the product (HashiCorp: providers, Docker: containerd)
4. **Component donation** to standards bodies (Docker → OCI/CNCF)
5. **Licensing differences** between components

### Choose HYBRID when:
1. **Product shell + independent backend services** (Supabase pattern)
2. **Shared core + language-specific SDKs** (Temporal pattern)
3. **Monorepo for development, subtrees for distribution** (Apollo pattern)

### The Critical Question:
> "How often do components need to change together?"
> - Always → Monorepo
> - Sometimes → Hybrid (monorepo + published packages)
> - Rarely → Multi-repo with package dependencies

---

## Star Count Strategy

**Supabase pattern (most effective):**
- Meta-repo (supabase/supabase) is the "landing page" with README, docs, getting-started
- Component repos have their own stars but the meta-repo is THE star magnet
- 78k stars on meta-repo vs 5-10k on components

**Grafana pattern:**
- Flag product (grafana/grafana: 66k) carries the stars
- Backend components (loki: 25k, mimir: 4k) get proportionally fewer
- Each component has its own marketing presence

**General principles:**
- Stars concentrate on the repo that README/docs point to
- The "install experience" repo gets the stars
- Separate repos dilute stars but enable independent marketing
- For a 1.8k-star project: keep stars concentrated until you hit ~10k

---

## Recommendation for Vexa (1.8k Stars, 2-3 Components, 2-5 People)

### Short-term (now → 5k stars): MONOREPO with publishable packages

**Why:**
1. 2-5 people can't afford multi-repo coordination overhead
2. Changes likely span Runtime API + Agent Runtime frequently
3. Star concentration matters at this stage
4. uv workspaces solve the Python multi-package problem natively
5. PostHog proves monorepo works for teams 10x your size building one product

**Structure:**
```
vexa-runtime/
├── pyproject.toml          (workspace root)
├── uv.lock                 (single lockfile)
├── packages/
│   ├── runtime-api/        (publishable to PyPI)
│   │   └── pyproject.toml
│   ├── agent-runtime/      (publishable to PyPI)
│   │   └── pyproject.toml
│   └── vexa-product/       (internal, not published)
│       └── pyproject.toml
├── docker/                 (compose for self-hosting)
└── docs/
```

**Tooling:** uv workspaces + Release Please for versioning + GitHub Actions for PyPI publishing.

### Medium-term (5k+ stars, proven external adoption): Extract if needed

**Trigger to extract:** When external users file issues saying "I want to use Runtime API without Vexa." That's the signal — not before.

**When you extract, use the Supabase/Docker pattern:**
- Keep the monorepo as the "product shell" and star magnet
- Extract component to its own repo
- Monorepo consumes extracted component via PyPI dependency
- Meta-repo README links to component repos

### What NOT to do:
- Don't extract prematurely (HashiCorp extracted Terraform SDK because external devs needed it; you don't have that demand yet)
- Don't use git submodules (universally hated, painful for active development)
- Don't split repos for "clean architecture" — split for external consumers
- Don't relicense components differently unless you have a cloud-wrapping threat (Grafana/Mimir AGPL story)
