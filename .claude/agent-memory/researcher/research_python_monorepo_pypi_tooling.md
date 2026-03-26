---
name: Python Monorepo PyPI Publishing Tooling
description: Concrete Python examples and tooling for monorepo-to-separate-PyPI-packages pattern — uv workspaces, Pants, Hatch, splitsh-lite, Docker builds from subdirectories
type: project
---

# Python Monorepo -> Separate PyPI Packages: Tooling & Examples

## 1. Real Python Projects Doing This At Scale

### Google Cloud Python (googleapis/google-cloud-python)
- **Scale:** 60+ packages in one repo, each published separately to PyPI
- **Structure:** `packages/` directory, each package has own pyproject.toml
- **Publishing:** Individual packages published as google-cloud-bigquery, google-cloud-firestore, etc.
- **Tooling:** Code generation (.generator/), Kokoro CI, custom scripts
- **Source:** https://github.com/googleapis/google-cloud-python

### Azure SDK for Python (Azure/azure-sdk-for-python)
- **Scale:** 534+ packages published to PyPI
- **Structure:** `sdk/<service-name>/<package-name>/` — each with README, src, tests, samples
- **Policy:** "The key is that there is source for only one shipping package in this folder"
- **CI:** Azure Pipelines + custom eng/ directory tooling
- **Source:** https://github.com/Azure/azure-sdk-for-python, https://azure.github.io/azure-sdk/policies_repostructure.html

### Apache Airflow (apache/airflow)
- **Scale:** 122+ distributions (core + 120 provider packages), ~100 released biweekly
- **Structure:** uv workspaces (added with Airflow 3), providers as standalone sub-projects
- **Tooling:** uv workspaces + prek (custom hooks), uv sync resolves 900+ packages in seconds
- **Publishing:** Each provider published independently to PyPI
- **Key insight:** Airflow worked with uv team to shape workspace features
- **Source:** FOSDEM 2026 talk, Jarek Potiuk's blog series

### LlamaIndex (run-llama/llama_index)
- **Scale:** 650+ packages in one repo
- **Migration path:** Poetry + Pants -> uv + LlamaDev (custom tool)
- **Publishing:** Each package published independently to PyPI via `uv publish`
- **Evidence:** llama-index-core uploaded via uv/0.10.10 publish subcommand
- **Results:** 20% faster CI, partial runs improved from 11 to 4 minutes
- **Source:** https://www.llamaindex.ai/blog/python-tooling-at-scale-llamaindex-s-monorepo-overhaul

### Opendoor
- **Structure:** projects/ (services), lib/ (shared packages with namespace packaging), tools/
- **Tooling:** Poetry + editable path dependencies
- **Publishing:** Poetry builds wheels to internal PyPI
- **CI insight:** When library changes, CI runs tests for ALL dependent services
- **Source:** https://medium.com/opendoor-labs/our-python-monorepo-d34028f2b6fa

### Pallets (Flask, Werkzeug, Click, Jinja)
- **Pattern:** Separate repos, NOT monorepo — each project in its own repo
- **Publishing:** GitHub Actions trusted publisher -> PyPI
- **Why:** Uniform directory structure across separate repos, not a monorepo

## 2. Python Build/Publish Tooling for Monorepo Subdirectories

### uv (RECOMMENDED — current best-in-class)

**Workspace setup:**
```toml
# Root pyproject.toml
[tool.uv.workspace]
members = ["packages/*"]
```

**Building a specific package:**
```bash
uv build --package <PACKAGE>       # builds specific workspace member
uv build <SRC>                     # builds package in specified directory
```

**Publishing:**
```bash
uv publish                         # publishes dist/ contents to PyPI
uv publish --token $PYPI_TOKEN     # with explicit token
uv publish --index testpypi        # to alternative index
```

**GitHub Actions (Trusted Publishing):**
```yaml
- uses: astral-sh/setup-uv@v3
- run: uv build --package my-package
- run: uv publish
  env:
    UV_PUBLISH_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
```

**KNOWN ISSUE (uv #9811):** When building workspace members, workspace dependencies are listed WITHOUT version constraints in wheel metadata. E.g., `Requires-Dist: package-b` instead of `Requires-Dist: package-b>=0.2.0`. Workarounds:
1. Custom script to rewrite version constraints before release
2. Hatchling metadata hooks to dynamically rewrite dependencies
3. Explicit version constraints in dependencies list
- Status: "needs-design", open, no spec-compliant solution yet

**Workspace limitations:**
- Single shared venv (can't have conflicting deps between members)
- Single requires-python across all members
- No built-in "affected packages" detection for CI
- uv can't prevent cross-member import leakage

### Pants Build System

**Publishing support:** `python_distribution` BUILD target publishes module to PyPI
- Best for: Large Python-first monorepos
- Key feature: Detects which tests to trigger when upstream changes
- Aggressive caching, dependency inference, fine-grained invalidation
- Source: https://www.pantsbuild.org/

**LlamaIndex abandoned Pants for uv** — maintaining Pants caching server on AWS was too much overhead for their team. uv + custom tooling replaced it.

### Hatch

**Status: NO native monorepo support** (issue #233, open since May 2022)
- Can configure multiple projects via `hatch config set dirs.project`
- `--project` / `-p` flag to switch between projects
- No unified lockfile, no workspace concept
- Workaround: custom metadata hooks for dependency modification
- Apache Airflow expressed interest but went with uv instead
- Source: https://github.com/pypa/hatch/issues/233

### Flit

**Works from subdirectories:** Each subdirectory needs own pyproject.toml
- `flit publish` from each package directory, or `flit -f path/to/pyproject.toml publish`
- No workspace or monorepo concept
- Simple but manual — need to script multi-package publishing
- Source: https://flit.pypa.io/

### Poetry

**NO native monorepo support** — requires plugins:
1. **poetry-workspaces:** `poetry workspace build/publish` — target specific workspaces
2. **poetry-monorepo-dependency-plugin:** Rewrites path deps to version deps when building
3. **poetry-multiproject-plugin:** Adds build-project command for relative includes

**Key problem:** Path dependencies (development) must be rewritten to version dependencies (publishing). This is the fundamental tension all tools address.

**LlamaIndex migrated away from Poetry to uv** for this reason.
- Source: https://github.com/python-poetry/poetry/issues/6850

### python-semantic-release (PSR) for Versioning

Can orchestrate multi-package releases from uv workspace:
- Conventional commits trigger version bumps per package
- Tag format per package: `core-{version}`, `api-{version}`
- Builds via `uv build`, publishes via PyPI token
- Each package needs own changelog, tag, GitHub release
- Source: https://medium.com/@asafshakarzy/releasing-a-monorepo-using-uv-workspace-and-python-semantic-release-0dafc889f4cc

## 3. splitsh-lite for Python

**Can it work with Python? YES** — it's language-agnostic, operates on git directories.
- Written in Go, faster than `git subtree split`
- Generates same SHA1s as `git subtree split`
- Used heavily by PHP ecosystem (Symfony ~50 components, Laravel)
- **No known Python projects using it** — Python ecosystem prefers uv workspaces or package extraction

**GitHub Actions available:**
- `acrobat/subtree-splitter` — synchronize monorepo to standalone repos using splitsh-lite
- `symplify/monorepo-split-github-action` — matrix-based splits to multiple target repos
- `antalaron/action-splitsh` — subtree synchronization

**Verdict for Python:** Unnecessary if using uv workspaces. splitsh-lite solves the "develop in monorepo, publish to separate repos" problem. But Python's packaging ecosystem (uv build --package + uv publish) already handles "develop in monorepo, publish to PyPI" without needing separate repos. Use splitsh-lite only if you need separate GitHub repos for community visibility.

## 4. Docker Image Publishing from Monorepo Subdirectory

**Best practice: Root context + subdirectory Dockerfile**

```bash
# From monorepo root:
docker build -t my-service -f packages/my-service/Dockerfile .
```

**Why root context:** COPY instructions can't access parent directories. BuildKit doesn't need to upload entire context (unlike legacy builder).

**docker-compose.yml pattern:**
```yaml
services:
  api:
    build:
      context: .                              # monorepo root
      dockerfile: packages/api/Dockerfile     # service-specific
```

**Key practices:**
1. Use .dockerignore aggressively (must be at context root)
2. Enable BuildKit (DOCKER_BUILDKIT=1) — doesn't copy entire context
3. Multi-stage builds: deps stage copies only pyproject.toml/uv.lock, source stage copies code
4. For shared libraries in monorepo: COPY packages/shared-lib/ first, then COPY packages/my-service/

**Advanced: Dagger for complex dependency graphs**
- Programmatically parses uv.lock to identify local dependencies
- Selectively copies only necessary source code into Docker context
- End-to-end pipeline caching including post-build steps
- Source: https://gafni.dev/blog/cracking-the-python-monorepo/

## 5. PEP 660 / src-layout in Monorepos

**PEP 660 (editable installs):** Enables `pip install -e .` for pyproject.toml-based projects
- uv workspaces use editable installs by default between workspace members
- `{ workspace = true }` source directive = editable install

**src-layout per package:**
```
packages/
  my-package/
    pyproject.toml
    src/
      my_package/
        __init__.py
```
- Prevents accidental imports from source tree during testing
- Works cleanly with uv workspaces
- Each package can use src-layout independently

## Summary: Recommended Stack for Vexa

| Need | Tool | Confidence |
|------|------|------------|
| Workspace management | uv workspaces | High |
| Building packages | `uv build --package X` | High |
| Publishing to PyPI | `uv publish` | High |
| Versioning | Release Please or python-semantic-release | Medium |
| CI/CD | GitHub Actions + trusted publisher | High |
| Docker builds | Root context + -f flag + BuildKit | High |
| Separate GitHub repos | splitsh-lite (only if needed) | Low priority |
| Monorepo build system | NOT Pants (overkill for small team) | High |
