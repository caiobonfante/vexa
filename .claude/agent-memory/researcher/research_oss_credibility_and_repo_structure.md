---
name: OSS Credibility and Standalone Repo Structure
description: What makes an infra OSS project credible on GitHub/HN/Reddit; minimum viable file layout; Python-specific patterns; testing standalone; concrete examples from 15+ projects
type: project
---

# What Makes an Open-Source Infrastructure Project Credible

Research conducted 2026-03-26. Surveyed 15 recently successful infra/platform projects
and 10+ HN launch threads.

---

## 1. Minimum Viable Standalone Package Structure

### Projects Surveyed (root file inventory)

| File/Dir | Hatchet | Infisical | Windmill | Coolify | Dokploy | Pocketbase | Valkey | E2B | FastAPI | Celery | Prefect | Dagster | Airflow |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **README.md** | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y(.rst) | Y | Y | Y |
| **LICENSE** | Y(MIT) | Y(MIT+ee) | Y(AGPL) | Y | Y | Y | Y(BSD) | Y | Y(MIT) | Y(BSD) | Y(Apache) | Y(Apache) | Y(Apache) |
| **CONTRIBUTING.md** | Y | Y | - | Y | Y | Y | Y | - | Y | Y(.rst) | - | - | Y(.rst) |
| **SECURITY.md** | - | Y | - | Y | Y | - | Y | - | Y | Y | Y | - | - |
| **CODE_OF_CONDUCT.md** | - | Y | - | Y | - | - | Y | - | - | - | Y | - | Y |
| **CHANGELOG.md** | - | - | Y | Y | - | Y | - | - | - | Y(.rst) | - | Y | Y |
| **docker-compose.yml** | Y(3 files) | Y(5 files) | Y | Y(5 files) | - | - | - | - | - | - | - | - | - |
| **Dockerfile** | - | Y(2) | Y | - | Y(5) | - | - | - | - | - | Y(2) | - | Y(2) |
| **.gitignore** | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| **.dockerignore** | - | Y | Y | Y | Y | - | - | - | - | Y | Y | Y | Y |
| **Makefile/Taskfile** | Taskfile | Makefile | - | - | - | Makefile | Makefile | Makefile | - | Makefile | justfile | Makefile | - |
| **pyproject.toml** | - | - | - | - | - | - | - | - | Y | Y | Y | Y | Y |
| **.env.example** | - | Y(4 files) | Y | Y(4 files) | - | - | - | - | - | - | - | - | - |
| **.pre-commit-config.yaml** | Y | - | - | - | - | - | - | - | Y | Y | Y | Y | Y |
| **.github/** | Y | Y | Y | Y | Y | Y | Y | Y | - | Y | Y | Y | Y |
| **GOVERNANCE.md** | - | - | - | - | - | - | Y | - | - | - | - | - | Y |
| **examples/** | Y | - | Y | - | - | Y | - | - | - | Y | Y | Y | - |
| **tests/** | - | - | - | Y | - | Y | Y | - | Y | - | Y | - | - |
| **docs/** | - | Y | Y | - | - | - | - | - | Y | Y | Y | Y | Y |

### Universal Files (present in 12+ of 13 projects)

Every single project has these:
1. **README.md** -- 13/13
2. **LICENSE** -- 13/13
3. **.gitignore** -- 13/13

### Near-Universal (10+ of 13)

4. **CONTRIBUTING.md** (or .rst) -- 10/13
5. **.github/** directory with issue templates, CI workflows -- 12/13
6. **.dockerignore** -- 9/13

### Common (7+ of 13)

7. **Makefile** or equivalent (Taskfile, justfile) -- 8/13
8. **SECURITY.md** -- 7/13
9. **.pre-commit-config.yaml** -- 6/13 (but 5/5 Python projects)
10. **CHANGELOG.md** -- 6/13

### Platform-Specific Patterns

**Self-hosted infra projects** (Hatchet, Infisical, Coolify, Windmill):
- Always have `docker-compose.yml` -- this is the "one-command deploy"
- Multiple compose variants: `docker-compose.dev.yml`, `docker-compose.prod.yml`
- `.env.example` files -- critical for showing what config is needed

**Python projects** (FastAPI, Celery, Prefect, Dagster, Airflow):
- Always have `pyproject.toml`
- 5/5 have `.pre-commit-config.yaml`
- 4/5 have Makefile/justfile
- `uv.lock` is the new pattern (Prefect, Dagster, Airflow, FastAPI all use it)

### The Minimum Viable Root for a Python Infra Project

Based on the survey, the absolute minimum:

```
README.md                    -- must have
LICENSE                      -- must have
.gitignore                   -- must have
CONTRIBUTING.md              -- must have (HN will notice absence)
pyproject.toml               -- must have for Python
docker-compose.yml           -- must have for self-hosted infra
.env.example                 -- must have for self-hosted infra
Dockerfile                   -- must have
Makefile                     -- strongly expected (8/13)
SECURITY.md                  -- expected (fill in real content, not template)
.dockerignore                -- expected
.github/                     -- expected (issue templates, CI workflows)
.pre-commit-config.yaml      -- expected for Python
```

---

## 2. What HN/Reddit Reviewers Look For

### Concrete Findings from HN Launch Threads

**What gets praised:**
- "The site looks visually very good" (OpenStatus) -- clean README presentation matters
- MIT licensing gets explicit positive callouts ("MIT or bust" -- Hatchet's philosophy)
- One-command self-hosting: `docker compose up` with no extra steps
- Technical depth in launch comments; going deep earns respect
- Clear problem statement: "I wanted to improve Temporal, Gabe wanted to improve Celery" (Hatchet)
- Backstory and personal motivation shared authentically

**What gets criticized:**
- **SaaS dependencies in an "open-source" project**: OpenStatus got hammered for depending on 4 external services (Tinybird, Turso, Clerk, Resend). "Why are we paying companies to do it for us?"
- **Database lock-in**: Novu's MongoDB requirement was called "a deal breaker"
- **Template/placeholder content**: Unfilled SECURITY.md templates are worse than having none
- **Inconsistent positioning**: OpenStatus confused people by being "synthetic monitoring vs incident management vs status pages"
- **Missing SDK quality**: Novu's .NET SDK was criticized for "incompatible with AOT, does not use System.Text.Json"
- **Pricing mismatch**: Free tier too limited, paid tier too expensive vs alternatives
- **"Open core" bait-and-switch**: Infisical's `ee/` directory noted, but MIT base tolerated
- **Competitors getting combative**: "never lands well" on HN

**What HN reviewers specifically look at in the repo:**
- License file (first thing checked)
- README quality (logo, badges, one-liner, quick start)
- Whether `docker compose up` actually works
- Code structure and organization ("Broken Windows Theory for codebases")
- CI/CD presence (do tests actually run?)
- Commit history activity
- Issue resolution speed

**Red flags for HN:**
- Superlatives in README ("fastest", "best", "revolutionary")
- Corporate/marketing voice instead of engineer voice
- No license = "not open source by definition"
- Sales-pitch launch posts
- Having friends post supportive comments (detected and punished)
- Empty sections in README or placeholder docs

### Reddit r/selfhosted Signals

- Docker Compose is table stakes. No compose = probably won't try it
- One-command deploy is the expectation
- Commercial backing matters to some (but community trust is earned via merits)
- Licensing changes post-adoption create lasting distrust (Budibase, Elastic, Redis precedents)
- "Does it actually work on my hardware?" -- ARM64 support increasingly expected

### Star-Driving README Structure (from Daytona's 4K-star analysis)

1. Logo + trust badges (build status, coverage, license, PyPI version)
2. One-liner + subtitle with context
3. GIF/screenshot showing it working
4. Feature highlights (bullet list)
5. Quick start (as few commands as possible)
6. Why this exists (backstory/motivation)
7. Contributing + community links

---

## 3. Python Infra Project File Layout (Detailed)

### FastAPI (78K stars)
```
.gitignore
.pre-commit-config.yaml
.python-version
CITATION.cff
CONTRIBUTING.md
LICENSE
README.md
SECURITY.md
pyproject.toml
uv.lock
fastapi/              # package
fastapi-slim/         # slim variant
docs/
docs_src/
scripts/
tests/
```
Key: Extremely minimal root. No Makefile, no docker-compose, no Dockerfile. Pure library pattern.

### Celery (25K stars)
```
.gitignore
.pre-commit-config.yaml
.readthedocs.yaml
.editorconfig
.dockerignore
CONTRIBUTING.rst
Changelog.rst
LICENSE
Makefile              # 30+ targets: test, lint, cov, docker-*, release, clean
README.rst
SECURITY.md
bandit.json
pyproject.toml
setup.cfg
setup.py
tox.ini
celery/               # package
docker/               # docker support
docs/
examples/
t/                    # tests (unusual naming)
requirements/         # split requirements files
```
Key: Full Makefile with docker-* targets. Docker in subdirectory, not root compose.

### Prefect (18K stars)
```
.gitignore
.pre-commit-config.yaml
.dockerignore
CODE_OF_CONDUCT.md
Dockerfile
LICENSE
README.md
SECURITY.md
justfile              # modern Makefile alternative
pyproject.toml
uv.lock
src/                  # src layout
tests/
integration-tests/
examples/
docs/
ui/
```
Key: Uses `justfile` instead of Makefile. src layout. Separate integration-tests dir.

### Dagster (12K stars)
```
.gitignore
.pre-commit-config.yaml
.dockerignore
CLAUDE.md
LICENSE
Makefile              # pyright, ruff, prettier, install, graphql, sanity_check
README.md
conftest.py           # ROOT conftest: warning filters, test splitting, CI hooks
pyproject.toml
uv.lock
python_modules/       # monorepo packages
js_modules/
docs/
examples/
integration_tests/
scripts/
```
Key: Root conftest.py for test infrastructure. Makefile focused on DX, not docker.

### Airflow (38K stars)
```
.gitignore
.pre-commit-config.yaml
.dockerignore
.editorconfig
CLAUDE.md
CODE_OF_CONDUCT.md
CONTRIBUTING.rst
Dockerfile
Dockerfile.ci
GOVERNANCE.md
LICENSE
NOTICE
README.md
codecov.yml
pyproject.toml
uv.lock
airflow-core/         # monorepo packages
providers/
task-sdk/
contributing-docs/
docker-tests/
docker-context-files/
docs/
```
Key: Separate Dockerfile.ci for test infrastructure. Contributing docs in own dir.

### Common Makefile Targets in Python Infra

From Celery, Dagster, Infisical, Pocketbase:

```makefile
# Essential (every project has these)
make test              # run test suite
make lint              # run linters (ruff/flake8/pylint)
make help              # show available targets

# Very Common
make install           # install dev dependencies
make format            # auto-format code (black/ruff format)
make clean             # remove build artifacts, .pyc, __pycache__
make build             # build package or docker image

# Self-Hosted Projects
make up                # docker compose up
make down              # docker compose down
make up-dev            # docker compose -f docker-compose.dev.yml up
make logs              # docker compose logs

# Release/CI
make release           # build + publish
make cov               # test with coverage
make check             # all quality checks (lint + format-check + type-check)
```

---

## 4. Testing in Standalone Context

### How Projects Test Without a Monorepo

**Pattern 1: Testcontainers (modern, preferred)**
- Used by: Prefect, newer Python projects
- Session-scoped fixtures in conftest.py spin up Postgres/Redis containers
- No docker-compose needed for tests; containers managed programmatically
- Package: `testcontainers[postgres,redis]` on PyPI

```python
# conftest.py pattern
@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("postgres:16") as pg:
        yield pg.get_connection_url()
```

**Pattern 2: docker-compose.test.yml (established, widely used)**
- Used by: Infisical (docker-compose.bdd.yml, docker-compose.e2e-dbs.yml)
- Separate compose file with just test infrastructure (db, redis, etc.)
- pytest-docker or pytest-docker-compose plugins integrate with pytest
- conftest.py fixture points to the test compose file

```python
# conftest.py pattern
@pytest.fixture(scope="module")
def docker_compose_file(pytestconfig):
    return os.path.join(str(pytestconfig.rootdir), "docker-compose.test.yml")
```

**Pattern 3: Root conftest.py for CI/test organization (Dagster)**
- Root conftest.py contains NO fixtures for services
- Instead: warning suppression, test splitting (--split 1/2), CI detection
- Each package has its own conftest.py with actual fixtures
- Clean separation: root = orchestration, package = fixtures

Dagster's root conftest.py (79 lines):
```python
# Suppress framework warnings
try:
    import warnings
    from dagster import BetaWarning, PreviewWarning
    warnings.filterwarnings("ignore", category=BetaWarning)
except ImportError:
    pass

# Add --split CLI option for parallel CI
def pytest_addoption(parser):
    parser.addoption("--split", type=str, action="store")

# Skip integration tests when CI_DISABLE_INTEGRATION_TESTS set
def pytest_runtest_setup(item):
    if os.getenv("CI_DISABLE_INTEGRATION_TESTS"):
        for mark in item.iter_markers(name="integration"):
            pytest.skip("Integration tests disabled")
```

**Pattern 4: Fixture vendoring**
- Test fixtures (sample data, configs) live in `tests/fixtures/` or `tests/data/`
- Committed to repo, not generated
- Small representative datasets, not production dumps

### CI That Runs Independently

Every surveyed project has independent CI via GitHub Actions. Common workflow structure:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install ruff
      - run: ruff check .
      - run: ruff format --check .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e ".[dev]"
      - run: pytest --cov

  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose build
      - run: docker compose up -d
      - run: docker compose ps  # smoke test
      - run: docker compose down
```

### Who Uses docker-compose.test.yml Pattern

| Project | Test Compose File | What's In It |
|---|---|---|
| Infisical | docker-compose.bdd.yml, docker-compose.e2e-dbs.yml | Postgres, Redis for BDD/E2E |
| Hatchet | docker-compose.infra.yml | Infrastructure dependencies only |
| Coolify | docker-compose.dev.yml + .env.testing | Dev stack with test env vars |
| Celery | docker/ directory with compose | RabbitMQ, Redis, various backends |

### conftest.py Patterns for Test Infrastructure

**Service-per-package pattern** (most common in monorepos):
```
repo/
  conftest.py              # Root: warning filters, CLI options, markers
  packages/
    service-a/
      tests/
        conftest.py        # Service-specific: mock DB, API client fixtures
    service-b/
      tests/
        conftest.py        # Different fixtures for different service
```

**Standalone library pattern** (FastAPI, Celery):
```
repo/
  tests/
    conftest.py            # All fixtures: test client, DB, mocks
    test_core.py
    test_api.py
```

**Session-scoped infrastructure pattern** (for integration tests):
```python
# conftest.py
import pytest

@pytest.fixture(scope="session")
def db(tmp_path_factory):
    """Spin up test database once for entire test session."""
    # testcontainers or subprocess docker
    ...

@pytest.fixture(autouse=True)
def reset_db(db):
    """Clean state between tests."""
    db.execute("TRUNCATE ALL TABLES CASCADE")
```

---

## 5. Gap Analysis: Vexa Current State vs Standard

### What Vexa Has
- README.md (good quality, logo, badges, quickstart)
- LICENSE (Apache 2.0)
- CONTRIBUTING.md (real content)
- SECURITY.md (template placeholder -- red flag)
- .gitignore
- .dockerignore
- Makefile (delegates to deploy/compose)
- docker-compose.override.yml (partial)
- .github/ISSUE_TEMPLATE/ (bug, feature)
- CLA/ directory
- Multiple .env.example files in features/

### What Vexa is Missing (vs standard)
- **No root .env.example** -- every self-hosted project has this
- **No root docker-compose.yml** -- delegated to deploy/compose/, but HN expects it at root
- **No root pyproject.toml** -- Python projects need this
- **No .github/workflows/** -- no CI at all (major credibility gap)
- **No .pre-commit-config.yaml** -- 5/5 Python projects have this
- **SECURITY.md is unfilled template** -- worse than not having one
- **No CODE_OF_CONDUCT.md** -- present in ~half of projects
- **No CHANGELOG.md** -- present in ~half of projects
- **No root Dockerfile** -- present in most self-hosted projects
- **No examples/ directory** -- present in 7/13 projects
- **No uv.lock** -- modern Python standard
- **node_modules committed to repo** -- immediate credibility destroyer

### Priority Fixes for Credibility

1. **Remove node_modules from repo** -- this alone would tank credibility on HN
2. **Add .github/workflows/ci.yml** -- lint + test + docker build
3. **Fill in SECURITY.md** with real content (supported versions, reporting process)
4. **Add root docker-compose.yml** or symlink to deploy/compose/
5. **Add root .env.example**
6. **Add .pre-commit-config.yaml**
7. **Add CODE_OF_CONDUCT.md**
8. **Add root pyproject.toml** for the main package
9. **Add CHANGELOG.md**

---

## Sources

### Project Repos Surveyed
- Hatchet: https://github.com/hatchet-dev/hatchet
- Infisical: https://github.com/Infisical/infisical
- Windmill: https://github.com/windmill-labs/windmill
- Coolify: https://github.com/coollabsio/coolify
- Dokploy: https://github.com/Dokploy/dokploy
- Pocketbase: https://github.com/pocketbase/pocketbase
- Valkey: https://github.com/valkey-io/valkey
- E2B: https://github.com/e2b-dev/E2B
- FastAPI: https://github.com/tiangolo/fastapi
- Celery: https://github.com/celery/celery
- Prefect: https://github.com/PrefectHQ/prefect
- Dagster: https://github.com/dagster-io/dagster
- Airflow: https://github.com/apache/airflow

### HN Discussions
- Hatchet Launch HN: https://news.ycombinator.com/item?id=40810986
- Infisical Launch HN: https://news.ycombinator.com/item?id=34955699
- Novu notification infra: https://news.ycombinator.com/item?id=38419513
- OpenStatus Show HN: https://news.ycombinator.com/item?id=37740870
- Coolify: https://news.ycombinator.com/item?id=43555996

### Guides
- Hatchet blog on OSS learnings: https://hatchet.run/blog/two-years-open-source
- How to launch dev tool on HN: https://www.markepear.dev/blog/dev-tool-hacker-news-launch
- How to crush HN launch: https://dev.to/dfarrell/how-to-crush-your-hacker-news-launch-10jk
- 4000-star README guide: https://www.daytona.io/dotfiles/how-to-write-4000-stars-github-readme-for-your-project
- Python project structure 2024: https://matt.sh/python-project-structure-2024
- Open source checklist: https://github.com/libresource/open-source-checklist
- OSS repo readiness: https://gist.github.com/PurpleBooth/6f1ba788bf70fb501439
- pytest-docker: https://github.com/avast/pytest-docker
- testcontainers-python: https://github.com/testcontainers/testcontainers-python
