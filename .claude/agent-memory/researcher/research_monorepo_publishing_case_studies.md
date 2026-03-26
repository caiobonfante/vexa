---
name: Monorepo-to-Package Publishing Case Studies
description: Deep dives into Laravel, Babel, React, Apollo publishing from monorepos — exact tooling, CI workflows, versioning strategies, gotchas, mirror repo star dynamics
type: project
---

# Monorepo-to-Package Publishing: Four Case Studies

## 1. Laravel/Symfony — splitsh-lite Subtree Splitting (PHP)

### Architecture
- **Source:** `laravel/framework` monorepo (34.6k stars)
- **Targets:** ~28 read-only repos under `github.com/illuminate/*` (e.g., illuminate/database: 2.8k stars)
- **Package registry:** Packagist (PHP's npm equivalent)

### Exact Tooling
- **splitsh-lite** (Go binary) — faster reimplementation of `git subtree split`
- Creates SHA1 hash per component, force-pushes to mirror repos
- Maintains a local SQLite database (`splitsh.db`) tracking processed commits/trees for efficiency

### CI Workflow
Three key files:
1. **`bin/split.sh`** — defines `split()` function calling `splitsh-lite --prefix=$1`, adds git remotes for each illuminate package, force-pushes split commits
2. **`bin/release.sh`** — tags all split repos simultaneously
3. **`.github/workflows/releases.yml`** — orchestrates via SSH to a **dedicated splitter server** (IP: 104.248.56.26)

**Why a dedicated server, not GitHub Actions runner?** splitsh-lite's local database caches previously processed commits. A fresh GHA container loses this cache, requiring full history re-scan. For Laravel's large repo with frequent splits, this is too expensive. The persistent server keeps the cache warm.

### Versioning Strategy
- **Lockstep** — all illuminate packages share the framework version (e.g., illuminate/database v11.x = laravel/framework v11.x)
- Tags are created simultaneously across all mirror repos
- Mirror repos are strictly READ-ONLY — all PRs go to laravel/framework

### Mirror Repo Stars
- laravel/framework: **34.6k stars**
- illuminate/database: **2.8k stars** (~8% of parent)
- Other illuminate packages: 200-1,500 stars
- **Pattern:** Mirror repos get a fraction of parent stars. Users star the main repo; mirrors are for Packagist discoverability.

### Symfony Comparison (same tooling)
Symfony pioneered splitsh-lite (the creator, Fabien Potencier, founded Symfony). Key difference: **Symfony stopped tagging unchanged packages on patch releases** (March 2021) because:
- Empty tags triggered CI pipelines across thousands of downstream projects unnecessarily
- `composer show` falsely reported updates for unchanged packages
- Team became reluctant to release quick patches because of cascading empty-tag overhead

**Solution:** Only tag packages that actually changed on patch releases. Always tag all packages on minor/major releases (.0 versions).

### Known Gotchas
1. **File renames break history** — splitsh-lite doesn't follow renames across directories
2. **Shallow clones break splits** — must use `fetch-depth: 0` for full history
3. **Force-push is mandatory** on first split to existing repos with signed commits
4. **SSH to splitter server is a single point of failure** — if the server goes down, releases stall
5. **No community PRs to mirror repos** — all contributions must go to the monorepo, which can confuse newcomers

---

## 2. Babel — Yarn Workspaces + Custom release-tool (JavaScript)

### Architecture
- **Source:** `babel/babel` monorepo (~44k stars)
- **Targets:** npm packages under `@babel/*` scope (e.g., @babel/core, @babel/parser, @babel/preset-env)
- **No separate GitHub repos** — packages exist only as npm packages, NOT as split repos

### Exact Tooling
- **Yarn workspaces** (NOT Lerna, despite common belief) — custom plugin for dependency management
- **Custom `release-tool` CLI** — Babel-specific tool for versioning, dry-runs, and multi-package npm publishing
- **Makefile.source.mjs** — Node.js-based Makefile for build targets (`prepublish-build`, npmignore generation, bundle building)
- Environment variables: `IS_PUBLISH`, `NODE_ENV`, `BABEL_ENV` control build behavior

### CI Workflow (`.github/workflows/release.yml`)
**Triggers:**
- Push to `v*` tags (automated)
- Manual workflow_dispatch (for prereleases like `8.0.0-beta.4`)

**Six sequential jobs:**
1. **log-updates** — displays which packages will be published (`yarn release-tool version --dry`)
2. **ensure-npm-packages-exist** — validates all referenced packages exist on npm
3. **git-version** — creates version commits and tags via `yarn release-tool version`
4. **npm-release** — `make prepublish` then `yarn release-tool publish --yes --tag next`
5. **github-release** — generates changelog between git tags, creates draft GitHub release
6. **github-push** — updates CHANGELOG.md, pushes release commit to main

### Versioning Strategy
- **Fixed/lockstep mode** — ALL @babel/* packages share the same version number
- When any package has a breaking change, ALL packages get a major version bump
- Currently: all packages at v7.x.x (Babel 8 prereleases published under `next` npm tag)
- This means @babel/parser and @babel/types always have the same version even if only one changed

### Key Design Decision: No Separate Repos
Babel explicitly chose NOT to split to separate repos. Their monorepo design doc states advantages:
- Single lint, build, test, and release process
- Easy to coordinate changes across modules
- Single place to report issues
- Cross-module testing catches integration bugs

**Trade-off:** Users cannot `npm install` directly from GitHub (must use published npm packages). This is acceptable because npm is the standard consumption path.

### Known Gotchas
1. **Custom release-tool is Babel-specific** — not reusable by other projects
2. **Fixed versioning creates noise** — @babel/types gets version bumps even when unchanged
3. **Makefile.source.mjs is unusual** — a Node.js file pretending to be a Makefile, confuses contributors
4. **Yarn workspaces + custom plugin** — harder for new contributors than standard Lerna/Changesets

---

## 3. React/Meta — Fully Custom Build + Release Pipeline (JavaScript)

### Architecture
- **Source:** `facebook/react` monorepo (~235k stars)
- **Targets:** npm packages: `react`, `react-dom`, `react-is`, `react-test-renderer`, `scheduler`
- **No separate GitHub repos** — packages exist only on npm
- **Custom Rollup-based build system** in `scripts/rollup/build.js`

### Exact Tooling
- **Custom scripts** in `scripts/release/` directory (22+ files)
- **Rollup** for bundling (with custom Babel plugins for error handling and console transforms)
- **No Lerna, no Nx, no Changesets** — entirely bespoke
- Key scripts: `prepare-release-from-ci.js`, `publish.js`, `prepare-release-from-npm.js`

### CI Workflow — Multi-Channel Strategy
**Three release channels:**

1. **next** — Automated weekday cron job publishes from tip of `main`. Pre-release quality.
2. **experimental** — Same automation, but with experimental features enabled via feature flags.
3. **stable/latest** — Manually promoted from `next` channel (never built directly from source).

**The "promote, don't rebuild" pattern:**
- Stable releases are NEVER built from scratch
- They are promoted from `next` (which has been running in pre-production)
- Uses `prepare-release-from-npm.js` to take an already-published `next` version and re-tag it as `latest`
- This ensures the exact artifacts that were tested are what gets released

**Publication workflow:**
1. Commit triggers Circle CI build of all release bundles
2. CI runs unit tests against both source code AND built bundles
3. Automated cron publishes to `next`/`experimental` channels
4. Manual promotion: `prepare-release-from-npm` + `publish` scripts move `next` to stable

### Versioning Strategy
- **Lockstep** — `react`, `react-dom`, and `scheduler` all share the same version
- Version numbers updated in multiple places: root package.json, `src/ReactVersion.js`, all packages/*/package.json
- `yarn version-check` ensures consistency across all version declarations
- Semver, but with a twist: the same artifacts get multiple version identifiers across channels

### Release Checklist (from Issue #10620)
1. Verify all commits tested at Facebook (Meta internal dogfooding)
2. Check npm owner permissions for all packages
3. Validate CI passes, dependencies are consistent
4. Run full test suite: `yarn test`, `yarn lint`, `yarn flow`
5. Build: `yarn build -- --extract-errors`
6. Smoke test via packaging fixtures
7. Publish: `npm publish` (stable) or `npm publish --tag next` (prerelease)
8. Create GitHub Release with built artifacts
9. Update website version configuration
10. Test with create-react-app

### Known Gotchas
1. **Completely bespoke** — no reusable tooling for other projects
2. **Meta internal testing is a gatekeeper** — "ensure all commits were tested at Facebook" means external-only changes still need internal validation
3. **Multi-location version tracking** — version in 5+ files, easy to miss one (hence `version-check` script)
4. **No automated changelog** — manual CHANGELOG.md with contributor credits
5. **Bower repository sync** was still mentioned in older checklists — legacy maintenance burden

---

## 4. Apollo GraphQL — Changesets + Git Subtrees (Mixed)

### Two Different Patterns in One Organization

**Apollo Client (npm packages):** Changesets-based monorepo publishing
**Apollo iOS (Swift packages):** Git subtree splitting to separate repos

### Apollo Client — Changesets

**Architecture:**
- Source: `apollographql/apollo-client` monorepo
- Targets: npm packages (`@apollo/client` and related packages)
- No separate repos for npm packages

**Exact Tooling:**
- **Changesets** (`@changesets/cli`) — version management and changelog generation
- GitHub Actions for automated release PR and publishing

**Workflow (`.github/workflows/release.yml`):**
1. Developer runs `npx changeset` alongside code changes
2. CLI prompts for version impact (patch/minor/major) + markdown description
3. Creates `.changeset/gorgeous-buses-laugh.md` with frontmatter specifying affected packages
4. PR is merged to main
5. Changesets bot opens a "Version Packages" PR that:
   - Consumes all pending changeset files
   - Bumps package.json versions (intelligently: one minor + one patch = minor)
   - Updates CHANGELOG.md with combined entries
6. Merging the "Version Packages" PR triggers npm publish + GitHub Release

**Prerelease strategy (clever):**
- Prereleases use `release-x` branches, NOT `main`
- Auto-enters "pre mode" via `pre.json` file
- Monotonically increasing versions: `3.8.0-alpha.0`, `3.8.0-alpha.1`
- Separate `prerelease.yml` workflow detects `pre.json` and publishes to npm only (no GitHub Release)
- `check-prerelease.yml` prevents accidental `pre.json` commits to `main`

**Versioning:**
- Lockstep — all packages in the monorepo versioned together
- But Changesets can handle independent versioning if needed
- Changeset frontmatter can specify multiple packages with different bump levels

### Apollo iOS — Git Subtrees

**Architecture:**
- Source: `apollographql/apollo-ios-dev` (development monorepo)
- Targets: 3 separate repos:
  - `apollo-ios` — main client library
  - `apollo-ios-codegen` — code generation
  - `apollo-ios-pagination` — pagination utilities

**Workflow (`.github/workflows/pr-subtree-push.yml`):**
1. Developer makes changes across multiple packages in single PR
2. PR is reviewed and merged in the dev monorepo
3. GitHub Actions detects merge to main
4. Runs `git subtree split --rejoin` for each subtree
5. Detects which subtrees have changes
6. Pushes changed subtrees to their respective remote repos

**Why subtrees over submodules for iOS:**
- SPM (Swift Package Manager) requires packages to be in their own repos
- Users shouldn't download the entire dev monorepo for one feature
- Independent versioning per feature package
- But development and review stays unified

**Gotcha: GitHub Actions token scope.**
The default `GITHUB_TOKEN` only has access to the current repo. Pushing to OTHER repos requires either deploy keys or a custom PAT with cross-repo permissions. This is a common stumbling block.

### Historical Note: Apollo Server
Apollo Server started with Lerna, then the ecosystem moved to Changesets. The switch was driven by:
- Lerna's lockstep versioning meant breaking changes in one package forced major bumps for ALL packages
- Users of `apollo-server-express` wouldn't get bug fixes unless they manually updated when a different package had a breaking change
- Changesets offered more flexible version coordination

---

## Comparative Summary

| Dimension | Laravel | Babel | React | Apollo |
|-----------|---------|-------|-------|--------|
| **Monorepo tool** | splitsh-lite | Yarn workspaces + custom | Fully custom | Changesets |
| **Separate repos?** | Yes (read-only mirrors) | No (npm only) | No (npm only) | Mixed (iOS: yes, JS: no) |
| **Versioning** | Lockstep | Lockstep (fixed) | Lockstep | Lockstep (configurable) |
| **CI mechanism** | SSH to dedicated server | GitHub Actions (6 jobs) | Circle CI + cron + manual | GitHub Actions + Changesets bot |
| **Package registry** | Packagist | npm | npm | npm + SPM |
| **Changelog** | Manual | Custom release-tool | Manual | Auto-generated by Changesets |
| **Mirror repo stars** | ~8% of parent | N/A | N/A | Separate repos have own stars |
| **Community PRs** | Monorepo only | Monorepo only | Monorepo only | Dev repo only (iOS) |
| **Reusable tooling?** | splitsh-lite (generic) | No (Babel-specific) | No (React-specific) | Changesets (generic) |

## Key Patterns and Lessons

### 1. "npm-only" is the dominant JS pattern
Babel, React, and Apollo Client all publish to npm WITHOUT maintaining separate GitHub repos. The npm package IS the distribution mechanism. Separate repos are a PHP/Swift pattern driven by package manager requirements (Packagist needs a repo; SPM needs a repo).

### 2. Lockstep versioning dominates
All four projects use lockstep (or near-lockstep) versioning. Independent versioning creates cognitive overhead for users who must figure out compatible version combinations. The trade-off: unchanged packages get "phantom" version bumps.

### 3. Symfony's "skip unchanged tags" optimization
Worth adopting: only tag/publish packages that actually changed on patch releases. Always tag all on minor/major. Reduces CI churn downstream.

### 4. Changesets is the reusable winner
Of the four, only Changesets (Apollo) is easily adoptable by other projects. Babel and React's tooling is bespoke. splitsh-lite is reusable but PHP/Go-ecosystem-specific.

### 5. Mirror repos are second-class citizens
- They get a fraction of parent stars (~8% for Laravel)
- Issues/PRs are redirected to the monorepo
- They exist for package manager discoverability, not community engagement
- Do NOT expect mirror repos to build their own community

### 6. Dedicated infrastructure for large splits
Laravel's SSH-to-server pattern exists because splitsh-lite's caching matters at scale. For smaller projects (<50 packages), GitHub Actions runners are fine.

### 7. React's "promote, don't rebuild" is gold
Building stable releases from source is risky. React's pattern of testing `next` channel in production, then promoting the exact same artifacts to `latest`, is the safest release strategy. Applicable to any multi-channel release.

## Sources
- Laravel split.sh: github.com/laravel/framework/blob/6.x/bin/split.sh
- Laravel discussion: github.com/laravel/framework/discussions/51059
- Babel monorepo design: github.com/babel/babel/blob/main/doc/design/monorepo.md
- Babel release.yml: github.com/babel/babel/blob/main/.github/workflows/release.yml
- React release scripts: github.com/facebook/react/tree/main/scripts/release
- React release checklist: github.com/facebook/react/issues/10620
- Apollo iOS subtrees: apollographql.com/blog/how-apollo-manages-swift-packages-in-a-monorepo-with-git-subtrees
- Apollo Client Changesets: aless.co/automatic-release-management
- Symfony tagging policy: symfony.com/blog/symfony-packages-are-not-tagged-anymore-when-nothing-changes-between-versions
- splitsh-lite issues: github.com/splitsh/lite/issues
