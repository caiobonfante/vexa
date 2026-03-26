---
name: splitsh-lite and GitHub Actions subtree splitting research
description: Deep dive on splitsh-lite (mechanics, maintenance status, limitations), all GitHub Actions for monorepo splitting, authentication patterns, and end-to-end workflow for split+PyPI+Docker
type: project
---

# splitsh-lite and GitHub Actions Subtree Splitting

## 1. splitsh-lite Technical Deep Dive

### How It Works
- Written in Go (79.5%) with Shell (20.5%)
- Uses libgit2 via git2go bindings (CGO dependency) to walk the git DAG
- For each commit in origin, it creates a synthetic commit containing only files under the specified `--prefix` directory, with paths rewritten to be at the root
- Maintains a **persistent cache** of already-split commits, so incremental splits only process new commits
- Guarantees **deterministic SHA1s**: same input always produces same output hashes
- Compatible with `git subtree split` output (same SHA1s, assuming modern git >= 2.8.0)

### Installation
```bash
# From binary (v1.0.1 -- last version with prebuilt binaries)
curl -sL https://github.com/splitsh/lite/releases/download/v1.0.1/lite_linux_amd64.tar.gz | tar xz
sudo mv splitsh-lite /usr/local/bin/splitsh-lite

# From source (v2.0.0 -- requires libgit2 1.5)
apt-get install libgit2-dev  # or equivalent
go build -o splitsh-lite github.com/splitsh/lite
```

### Command-Line Usage
```bash
# Basic split
splitsh-lite --prefix=services/runtime-api/

# Split with target branch creation
splitsh-lite --prefix=services/runtime-api/ --target=heads/split-runtime-api

# Full workflow: split and push
splitsh-lite --prefix=services/runtime-api/ --target=heads/split-runtime-api
git push https://github.com/org/runtime-api.git refs/heads/split-runtime-api:refs/heads/main

# Flags:
#   --prefix=<dir>     Directory to split (supports from:to and exclusion)
#   --path=<dir>       Repository path (defaults to cwd)
#   --origin=<ref>     Git reference (HEAD, heads/xxx, tags/xxx)
#   --target=<ref>     Create reference for split tip (heads/xxx, tags/xxx)
#   --progress         Show progress bar
#   --scratch          Flush cache (after force push or corruption)
```

### Performance
- Benchmark: 7,197 commits traversing 9,984 commits in **4.09 seconds**
- Incremental updates are near-instant due to caching
- `git subtree split` is pure shell/git, can take minutes on large repos
- splitsh-lite is orders of magnitude faster for repos with >1000 commits

### History Preservation
- YES: full commit history for the subdirectory is preserved
- Each original commit that touched the prefix gets a corresponding commit in the split
- Commit messages, authors, dates are all preserved
- Merge commits are preserved as merge commits

### CRITICAL: Maintenance Status (RED FLAG)

**Stars:** 1.6k | **Open Issues:** 16 | **Latest release:** v2.0.0 (Oct 2023)

**Issue #82 (May 2025):** No prebuilt binaries for v2.0.0. Users must compile from source.

**Issue #81 (Jan 2025):** git2go (the Go bindings for libgit2) is "all but dead." libgit2 is at v1.9 but git2go can't keep up. This threatens splitsh-lite's long-term viability.

**PR #86 (open):** A community member ported splitsh-lite to use go-git (pure Go) instead of git2go/libgit2. This would eliminate the CGO dependency entirely. Status: **open, not merged.** Some hash mismatch in merge tests but aligns with both `git subtree` and original libgit2 implementation.

**Verdict on splitsh-lite health:**
- v1.0.1 binaries work fine for CI (linux_amd64 available)
- v2.0.0 requires building from source with libgit2 -- painful in CI
- Long-term risk: git2go dependency may break as libgit2 advances
- The go-git port (PR #86) would fix this but isn't merged
- For a new project, consider alternatives or plain `git subtree split`

### Known Limitations
1. **File renames not followed:** If `src/foo.py` was renamed to `services/runtime-api/foo.py`, the pre-rename history is lost in the split
2. **Empty commits dropped:** Commits that result in no changes to the prefix directory are skipped (can cause commit count discrepancies)
3. **Requires full clone:** `fetch-depth: 0` mandatory. Shallow clones produce broken splits
4. **No prebuilt v2.0.0 binaries:** Must use v1.0.1 binary or compile from source
5. **Merge commit hashes:** Can differ from `git subtree split` in edge cases involving merges

---

## 2. GitHub Actions for Monorepo Splitting

### Option A: danharrin/monorepo-split-github-action (RECOMMENDED)
**GitHub Marketplace:** [Monorepo Split](https://github.com/marketplace/actions/monorepo-split)
**Stars:** Most widely used. Used by Filament PHP in production.

```yaml
name: 'Monorepo Split'
on:
  push:
    branches: [main]
    tags: ['*']

env:
  GITHUB_TOKEN: ${{ secrets.SPLIT_ACCESS_TOKEN }}

jobs:
  split:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        package:
          - local_path: 'services/runtime-api'
            split_repository: 'runtime-api'

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # Branch push (no tag)
      - if: "!startsWith(github.ref, 'refs/tags/')"
        uses: danharrin/monorepo-split-github-action@v2.4.0
        with:
          package_directory: '${{ matrix.package.local_path }}'
          repository_organization: 'your-org'
          repository_name: '${{ matrix.package.split_repository }}'
          user_name: "ci-bot"
          user_email: "ci@your-org.com"

      # Tag push
      - if: "startsWith(github.ref, 'refs/tags/')"
        uses: danharrin/monorepo-split-github-action@v2.4.0
        with:
          tag: ${GITHUB_REF#refs/tags/}
          package_directory: '${{ matrix.package.local_path }}'
          repository_organization: 'your-org'
          repository_name: '${{ matrix.package.split_repository }}'
          user_name: "ci-bot"
          user_email: "ci@your-org.com"
```

**Auth:** Requires PAT with repo scope stored as secret. Supports GitHub and GitLab.
**How it works internally:** Uses Docker container with splitsh-lite inside.
**Params:** `package_directory`, `repository_organization`, `repository_name`, `repository_host` (optional, for GitLab/self-hosted), `user_name`, `user_email`, `tag` (optional).

### Option B: acrobat/subtree-splitter
**GitHub Marketplace:** [subtree-splitter](https://github.com/marketplace/actions/subtree-splitter)

Uses a JSON config file for multiple splits:

```json
// .github/subtree-splitter-config.json
{
    "subtree-splits": [
        {
            "name": "runtime-api",
            "directory": "services/runtime-api",
            "target": "git@github.com:your-org/runtime-api.git"
        }
    ]
}
```

```yaml
name: Subtree Split
on:
  push:
    branches: ['*']
    paths: ['services/runtime-api/**']
    tags-ignore: ['*']
  create:
    tags: ['*']
  delete:
    tags: ['*']

jobs:
  split:
    runs-on: ubuntu-latest
    if: github.repository == 'your-org/monorepo'
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: false

      - uses: frankdejonge/use-github-token@1.0.2
        with:
          authentication: 'username:${{ secrets.SPLIT_ACCESS_TOKEN }}'
          user_name: 'ci-bot'
          user_email: 'ci@your-org.com'

      - name: Cache splitsh-lite
        uses: actions/cache@v4
        with:
          path: './splitsh'
          key: '${{ runner.os }}-splitsh-v101'

      - uses: acrobat/subtree-splitter@v1.1.3
        with:
          config-path: .github/subtree-splitter-config.json
```

**Advantages:** JSON config, caching, batch-size control, path-filtered triggers.

### Option C: nxtlvlsoftware/git-subtree-action
Uses native `git subtree split` (no splitsh-lite dependency). SSH deploy key auth.

```yaml
name: Subtree Sync
on: [push]
jobs:
  sync:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        path: [runtime-api]
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: nxtlvlsoftware/git-subtree-action@1.1
        with:
          repo: 'your-org/${{ matrix.path }}'
          path: 'services/${{ matrix.path }}'
          deploy_key: ${{ secrets.DOWNSTREAM_DEPLOY_KEY }}
          force: true
```

Tag sync on release:
```yaml
on:
  release:
    types: [published]
steps:
  - uses: nxtlvlsoftware/git-subtree-action@1.1
    with:
      repo: 'your-org/runtime-api'
      path: 'services/runtime-api'
      deploy_key: ${{ secrets.DOWNSTREAM_DEPLOY_KEY }}
      tag: true
```

### Option D: antalaron/action-splitsh
Simple splitsh-lite wrapper:

```yaml
- uses: antalaron/action-splitsh@master
  with:
    split: 'your-org/runtime-api'
    split_deploy_key: ${{ secrets.GITHUB_SSH_KEY }}
    split_prefix: 'services/runtime-api/'
```

### Option E: DIY with plain git subtree split (NO external dependencies)
```yaml
name: Subtree Split
on:
  push:
    branches: [main]

jobs:
  split:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Split subtree
        run: |
          git subtree split --prefix=services/runtime-api -b split-branch

      - name: Push to downstream
        run: |
          git remote add downstream https://x-access-token:${{ secrets.SPLIT_PAT }}@github.com/your-org/runtime-api.git
          git push downstream split-branch:main --force
```

**Pros:** No external action dependency, no splitsh-lite binary needed.
**Cons:** Slower on large repos (no caching), shell-based implementation.

---

## 3. Authentication Methods for Cross-Repo Push

### Method 1: Personal Access Token (PAT) -- Simplest
```yaml
env:
  GITHUB_TOKEN: ${{ secrets.SPLIT_ACCESS_TOKEN }}
# or in git remote URL:
git push https://x-access-token:${PAT}@github.com/org/repo.git branch:main
```
- Create fine-grained PAT with `contents: write` on target repo
- Store as repository secret
- Simple but scoped to a user account

### Method 2: SSH Deploy Key -- Most Secure for single repo
```bash
# Generate key pair
ssh-keygen -t ed25519 -a 100 -f deploy_key -N ""
```
- Add **public** key as deploy key on target repo (with write access)
- Add **private** key as secret on source repo
- Use `webfactory/ssh-agent` or action's deploy_key param

```yaml
- uses: webfactory/ssh-agent@v0.9.0
  with:
    ssh-private-key: ${{ secrets.DEPLOY_KEY }}
- run: git push git@github.com:org/repo.git split-branch:main
```

### Method 3: GitHub App Token -- Best for org-wide
- Create a GitHub App with repo permissions
- Install on target repos
- Generate installation token in workflow
- Most scalable for multiple target repos

**Recommendation:** Deploy key for single-target split (our case). PAT if you need simplicity during initial setup.

---

## 4. End-to-End Workflow: Split + PyPI + Docker

This is the complete workflow for our use case:

```yaml
name: Release Runtime API
on:
  push:
    branches: [main]
    paths: ['services/runtime-api/**']
    tags: ['v*']

jobs:
  # Job 1: Split subtree to downstream repo
  split:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v')
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - if: "!startsWith(github.ref, 'refs/tags/')"
        uses: danharrin/monorepo-split-github-action@v2.4.0
        env:
          GITHUB_TOKEN: ${{ secrets.SPLIT_ACCESS_TOKEN }}
        with:
          package_directory: 'services/runtime-api'
          repository_organization: 'your-org'
          repository_name: 'runtime-api'
          user_name: "ci-bot"
          user_email: "ci@your-org.com"

      - if: "startsWith(github.ref, 'refs/tags/')"
        uses: danharrin/monorepo-split-github-action@v2.4.0
        env:
          GITHUB_TOKEN: ${{ secrets.SPLIT_ACCESS_TOKEN }}
        with:
          tag: ${GITHUB_REF#refs/tags/}
          package_directory: 'services/runtime-api'
          repository_organization: 'your-org'
          repository_name: 'runtime-api'
          user_name: "ci-bot"
          user_email: "ci@your-org.com"

  # Job 2: Build and publish to PyPI (on tag only)
  pypi:
    runs-on: ubuntu-latest
    needs: split
    if: startsWith(github.ref, 'refs/tags/v')
    permissions:
      id-token: write  # Required for OIDC trusted publisher
      contents: read
    environment:
      name: pypi
      url: https://pypi.org/p/runtime-api
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install build tools
        run: pip install --upgrade pip build

      - name: Build distribution
        working-directory: services/runtime-api
        run: python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: services/runtime-api/dist/
          print-hash: true

  # Job 3: Build and push Docker image (on tag only)
  docker:
    runs-on: ubuntu-latest
    needs: split
    if: startsWith(github.ref, 'refs/tags/v')
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract version
        id: version
        run: echo "VERSION=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT

      - uses: docker/build-push-action@v5
        with:
          context: services/runtime-api
          push: true
          tags: |
            ghcr.io/${{ github.repository_owner }}/runtime-api:${{ steps.version.outputs.VERSION }}
            ghcr.io/${{ github.repository_owner }}/runtime-api:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## 5. Comparison Matrix

| Feature | danharrin/monorepo-split | acrobat/subtree-splitter | nxtlvlsoftware/git-subtree | DIY git subtree split |
|---------|------------------------|-------------------------|---------------------------|----------------------|
| Engine | splitsh-lite (Docker) | splitsh-lite | git subtree split | git subtree split |
| Auth | PAT (env var) | PAT (token action) | SSH deploy key | PAT or deploy key |
| Tag support | Yes (conditional) | Yes (create/delete events) | Yes (release event) | Manual |
| Config | Inline YAML | JSON file | Inline YAML | Shell script |
| Caching | Internal (Docker) | Explicit cache step | None | None |
| Multiple packages | Matrix strategy | JSON array | Matrix strategy | Loop/matrix |
| Maintenance | Active | Active | Low activity | N/A |
| External deps | Docker pull | splitsh binary + cache | None (git built-in) | None |

---

## 6. Recommendation for Vexa

**For initial setup (Phase 1):** Use `danharrin/monorepo-split-github-action@v2.4.0`
- Most widely adopted (Filament PHP uses it in production)
- Handles both branch and tag splitting
- Containers splitsh-lite so you don't manage the binary
- Simple matrix config for future multi-package splits

**Fallback if splitsh-lite dies:** Switch to DIY `git subtree split` approach
- Zero external dependencies
- Slower but reliable
- 5-line shell script

**Auth:** Start with PAT for simplicity, migrate to deploy key when hardening.

**PyPI publishing:** Use trusted publisher (OIDC) -- no stored tokens needed.
- Configure on PyPI: Settings > Publishing > Add GitHub Actions publisher
- Workflow needs `permissions: id-token: write`
- Use `pypa/gh-action-pypi-publish@release/v1`

**Docker:** GHCR with built-in `GITHUB_TOKEN` -- zero additional secrets needed.
