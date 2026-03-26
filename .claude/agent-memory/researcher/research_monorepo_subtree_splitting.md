---
name: Monorepo subtree splitting patterns
description: Symfony/Laravel/Babel/React/Apollo/Python patterns for publishing monorepo components as separate repos + packages, with splitsh-lite tooling and GitHub Actions workflow
type: reference
---

## Two Patterns in the Wild

1. **Subtree split to mirror repos** (Symfony, Laravel, Apollo iOS) — when package manager requires a repo. Tool: splitsh-lite.
2. **Monorepo publish to registry only** (Babel, React, Apollo Client, Airflow, LlamaIndex) — no mirror repos, just publish packages. Tool: uv workspaces / Yarn workspaces / Changesets.

## Key Findings

### splitsh-lite
- Go binary wrapping libgit2, replaces `git subtree split` (100x faster)
- v1.0.1 works, v2.0.0 has no binaries, git2go dependency is dying (issue #81)
- Fallback: plain `git subtree split` (slower but zero deps)

### Best GH Action: danharrin/monorepo-split-github-action@v2.4.0
- Bundles splitsh-lite in Docker container
- Used by Filament PHP in production
- Requires fine-grained PAT with contents:write on target repo

### Python ecosystem
- No Python project uses splitsh-lite — they use uv workspaces + `uv build --package X`
- Airflow (122 packages), LlamaIndex (650), Google Cloud (60), Azure SDK (534) validate this
- Known gotcha: uv #9811 — workspace deps lack version constraints in wheel metadata

### Critical gotchas
1. `fetch-depth: 0` mandatory — shallow clones corrupt splits silently
2. GITHUB_TOKEN can't push to other repos — need PAT or deploy key
3. Auto-close PR workflow needed on mirror repos
4. File renames not followed by splitsh-lite

## Sources
- splitsh/lite GitHub, Symfony .github/, Laravel bin/split.sh
- Babel release.yml, React scripts/release/, Apollo iOS subtree blog
- Airflow FOSDEM 2026, LlamaIndex monorepo overhaul blog
- uv workspaces docs, PyPI trusted publishers docs
