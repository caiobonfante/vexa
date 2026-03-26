---
name: research_temporal_repo_structure
description: Deep dive into temporalio/temporal GitHub repo structure — root files, docker-compose, Makefile, Helm, CI, DX files for reference architecture
type: reference
---

# Temporal Open-Source Repository Structure Analysis

Research date: 2026-03-26
Source: https://github.com/temporalio/temporal (main branch)

## 1. Root-Level Files (Complete List)

### Directories (21)
```
.claude/skills/review/    # AI agent review skills
.cursor/rules/            # Cursor IDE rules
.github/                  # CI, templates, CODEOWNERS
.vscode/                  # VS Code settings
api/                      # Proto API definitions
chasm/                    # CHASM module (new component)
client/                   # Service clients
cmd/                      # Binary entrypoints (server, tools)
common/                   # Shared modules
components/               # Component implementations
config/                   # YAML configs for all DB backends
develop/                  # Dev docker-compose + scripts
docker/                   # Dockerfiles + build config
docs/                     # Architecture documentation
proto/                    # Internal proto definitions
schema/                   # DB schemas (Cassandra, MySQL, Postgres, SQLite, ES)
service/                  # Main services (frontend, history, matching, worker)
temporal/                 # Core temporal package
temporaltest/             # Test framework
tests/                    # Functional/E2E tests
tools/                    # Dev tools
```

### Files (12)
```
.dockerignore             # Excludes .coverage, .testoutput, .github, IDE, *.md, binaries
.gitattributes
.gitignore
.gitmodules               # 1 submodule: Grafana dashboards
.goreleaser.yml           # Builds 5 binaries x (linux/darwin/windows) x (amd64/arm64)
AGENTS.md                 # AI coding agent instructions (Claude, Copilot)
CONTRIBUTING.md           # Build prereqs, testing tiers, server startup
LICENSE                   # MIT (Copyright Temporal Technologies + Uber Technologies)
Makefile                  # ~726 lines, 80+ targets
README.md                 # Badges, brew install, getting started, links
go.mod
go.sum
```

## 2. Docker-Compose: "Run Locally" vs "Deploy to K8s"

### Local Development (in-repo, `develop/docker-compose/`)
The main repo contains docker-compose files for **development dependencies only** (databases, ES, Grafana):

```
develop/docker-compose/
  docker-compose.yml              # Base (Cassandra, MySQL, Postgres, ES, Grafana, Prometheus)
  docker-compose.darwin.yml       # macOS overrides
  docker-compose.linux.yml        # Linux overrides
  docker-compose.windows.yml      # Windows overrides
  docker-compose.cdc.yml          # Change Data Capture setup
  docker-compose.cdc.darwin.yml
  docker-compose.cdc.linux.yml
  docker-compose.secondary-es.yml # Dual Elasticsearch
  grafana/provisioning/           # Grafana dashboards (submodule)
  mysql-init/                     # MySQL init scripts
  prometheus-darwin/
  prometheus-linux/
```

**Key pattern**: These compose files start **dependencies only** (DB, search, monitoring). The Temporal server itself runs from source (`make start`). Controlled via Makefile:
- `make start-dependencies` / `make stop-dependencies`
- `make start` (SQLite, no Docker needed)
- `make start-cass-es`, `make start-mysql`, `make start-postgres`, etc.

### Full Docker-Compose (separate repo, ARCHIVED)
`temporalio/docker-compose` (archived Jan 2026, migrated to `temporalio/samples-server/compose`):
- Ran the **full stack** including Temporal server in Docker
- 7 variants for different DB backends
- Intended for users who want to try Temporal without building from source

### Kubernetes (separate repo)
`temporalio/helm-charts` — completely separate repository:
- Single chart in `charts/temporal/`
- Deploys only server components (frontend, history, matching, worker)
- Does NOT install databases — user provides persistence
- Example values files: `values.mysql.yaml`, `values.postgresql.yaml`, `values.cassandra.yaml`
- Published at `https://go.temporal.io/helm-charts/`

**Verdict**: Three-tier separation:
1. **In-repo**: dev dependencies only (docker-compose for DBs)
2. **Separate repo**: full docker-compose for quick-start users (now archived)
3. **Separate repo**: Helm chart for K8s production

## 3. Makefile (~726 lines, 80+ targets)

### Variable Definitions
- `COLOR := "\e[1;36m%s\e[0m\n"` — colored output
- Database connection params (MySQL, Postgres, Cassandra ports/addresses)
- Go build flags, test flags, coverage dirs
- Tool versions pinned (golangci-lint v2.9.0, buf v1.6.0, etc.)

### Target Categories

**Build (5 binaries)**:
- `temporal-server` — main server
- `temporal-cassandra-tool` — Cassandra schema management
- `temporal-sql-tool` — MySQL/Postgres schema management
- `temporal-elasticsearch-tool` — ES index management
- `tdbg` — debugger

**Proto compilation**: `proto`, `protoc`, `proto-codegen`, `lint-protos`, `lint-api`, `buf-breaking`

**Code quality**: `lint`, `lint-code` (golangci-lint), `lint-actions`, `lint-yaml`, `fmt`, `goimports`, `shell-check`, `workflowcheck`, `check`

**Testing** (3 tiers):
- `unit-test` — no external dependencies
- `integration-test` — requires DBs
- `functional-test` — full E2E, persistence options
- `functional-with-fault-injection-test`
- `mixed-brain-test` — version compatibility
- `test` — runs all three tiers

**Coverage**: `unit-test-coverage`, `integration-test-coverage`, `functional-test-coverage` (with retry logic)

**Schema installation**: `install-schema-cass-es`, `install-schema-mysql8`, `install-schema-postgresql12`, `install-schema-es`

**Server startup** (12 variants):
- `start` (SQLite default)
- `start-cass-es`, `start-mysql`, `start-mysql8`, `start-mysql-es`
- `start-postgres`, `start-postgres12`, `start-postgres-es`
- `start-sqlite`, `start-sqlite-file`
- `start-xdc-cluster-a/b/c`

**Dependencies**: `start-dependencies`, `stop-dependencies`, `gomodtidy`, `update-dependencies`

**Tools** (19 tools auto-installed via stamp files):
golangci-lint, gci, gotestsum, api-linter, buf, protogen, actionlint, workflowcheck, yamlfmt, goimports, gowrap, gomajor, errortype, mockgen, stringer, protoc-gen-go, protoc-gen-go-grpc, protoc-gen-go-helpers, protoc-gen-go-chasm

## 4. Helm Chart — Separate Repo

**Repo**: `temporalio/helm-charts`

Structure:
```
charts/temporal/          # The single Helm V3 chart
values/                   # Example value files per DB backend
  values.mysql.yaml
  values.postgresql.yaml
  values.cassandra.yaml
  values.elasticsearch.yaml
.github/                  # Test pipeline
README.md
UPGRADING.md
CONTRIBUTING.md
LICENSE
```

Deploys as separate K8s Deployments:
- Frontend (gRPC gateway)
- History service
- Matching service
- Worker service
- Admin-tools pod

Headless services for internal discovery. User provides all persistence.

## 5. CI Configuration (18 workflow files)

```
.github/workflows/
  run-tests.yml                    # Main test pipeline
  linters.yml                      # Code quality checks
  build-and-publish.yml            # Build + publish Docker images
  release.yml                      # Release automation
  features-integration.yml         # Feature integration tests
  flaky-tests-report.yml           # Flaky test tracking
  optimize-test-sharding.yml       # Test parallelization
  run-single-test.yml              # Run individual test (debugging)
  ci-success-report.yml            # CI status reporting
  stale.yml                        # Stale issue/PR management
  docker-build-manual.yml          # Manual Docker build trigger
  promote-docker-image.yml         # Promote Docker images
  promote-server-image.yml         # Promote server image
  promote-admin-tools-image.yml    # Promote admin tools image
  check-pr-placeholders.yml        # PR validation
  check-release-dependencies.yml   # Release dep verification
  auto-approve-cicd-release-pr.yml # Auto-approve CI/CD PRs
  trigger-version-info-service.yml # Version info updates
```

Also:
- `.github/.codecov.yml` — coverage reporting config
- `.github/.golangci.yml` — linter rules
- `.github/.yamlfmt` — YAML formatting rules
- `.github/actionlint-matcher.json` — GH Actions lint patterns

## 6. Developer Experience Files

### CONTRIBUTING.md
- CLA requirement (Temporal Contributor License Agreement)
- Build prereqs: Go, protoc, Temporal CLI
- Runtime prereqs: Docker (optional), SQLite default
- Three test tiers explained
- Server startup for each DB backend
- IDE debugging (GoLand config)
- API development workflow (cross-repo coordination)
- Commit message standards (Chris Beams guide)
- License header enforcement (`make copyright`)

### LICENSE
MIT License — Copyright Temporal Technologies Inc. (2025) and Uber Technologies Inc. (2020)

### Issue Templates
```
.github/ISSUE_TEMPLATE/
  bug_report.md       # Expected/Actual/Steps/Specs, label: potential-bug
  feature_request.md  # Problem/Solution/Alternatives/Context, label: enhancement
```

### PR Template
```
.github/PULL_REQUEST_TEMPLATE.md
  ## What changed?
  ## Why?
  ## How did you test it?
    - [ ] Built
    - [ ] Run locally and tested manually
    - [ ] Covered by existing tests
    - [ ] Added new unit test(s)
    - [ ] Added new functional test(s)
  ## Potential risks
```

### CODEOWNERS
Fine-grained ownership by team:
- `@temporalio/server`, `@temporalio/cgs`, `@temporalio/nexus` (defaults)
- `@temporalio/oss-foundations` (CHASM, archiver, history core)
- `@temporalio/oss-matching` (matching service, task queues)
- `@temporalio/act` (activities, scheduler, nexus operations)

### AI Agent Configs
- `AGENTS.md` — instructions for AI coding agents (convention adherence, lint/test commands, error handling, response brevity)
- `.claude/skills/review/` — Claude review skills
- `.cursor/rules/` — Cursor IDE rules
- `.github/copilot-instructions.md` — GitHub Copilot guidelines

### Release
- `.goreleaser.yml` — GoReleaser v2 config, builds 5 binaries for linux/darwin/windows x amd64/arm64
- Archives include binaries + `./config/` directory
- SHA256 checksums, no changelog generation

### Monitoring
- Git submodule for Grafana dashboards (`temporalio/dashboards`)
- Prometheus configs per OS in `develop/docker-compose/`

## Summary of Patterns Worth Noting

1. **Separation of concerns**: Main repo = source code + dev tooling. Docker-compose for users = separate repo. Helm chart = separate repo.
2. **Makefile as the single entry point**: Every action goes through `make`. No separate scripts directory cluttering root.
3. **Multi-DB support from day one**: Config files, schema dirs, Makefile targets, and docker-compose variants all per-database.
4. **Three-tier testing**: unit (fast, no deps) -> integration (needs DBs) -> functional (full E2E). Each has coverage variants.
5. **Tool pinning**: All dev tools version-pinned in Makefile with stamp files for caching.
6. **Minimal root files**: Only 12 files at root. Everything else in directories.
7. **Schema embedding**: `schema/embed.go` embeds DB schemas into the binary at compile time.
8. **AI-friendly**: AGENTS.md, .claude/, .cursor/, copilot-instructions.md — embracing AI-assisted development.
