---
name: Standalone Infra Repo Structures (Traefik, MinIO, Loki)
description: Deep dive on root-level files, Makefile targets, Helm chart placement, CI systems, directory layout, and local-vs-prod deploy for 3 Go infra projects
type: project
---

# Standalone Infrastructure Repository Structures

Research date: 2026-03-26. All three are Go-based, single-binary infrastructure projects.

## 1. Traefik (traefik/traefik) -- Reverse Proxy

### Root-level files
```
.dockerignore, .gitattributes, .gitignore
.go-version, .golangci.yml, .goreleaser.yml.tmpl
CHANGELOG.md, CODE_OF_CONDUCT.md, CONTRIBUTING.md
Dockerfile, LICENSE.md (MIT), Makefile
README.md, SECURITY.md
flake.nix, flake.lock
generate.go, go.mod, go.sum
traefik.sample.toml, traefik.sample.yml
```

NO docker-compose.yml at root.

### Directory structure
```
cmd/           -- CLI entrypoints
pkg/           -- public Go packages
internal/      -- private Go packages
integration/   -- integration tests (40+ test files, fixtures, testdata)
docs/          -- documentation
webui/         -- built-in dashboard UI
contrib/       -- grafana dashboards, systemd unit files
script/        -- CI/build scripts (crossbinary, deploy, validate)
.github/       -- GitHub Actions workflows
```

### Makefile targets (key ones)
build-related: `binary`, `crossbinary-default`, `build-image`, `build-image-dirty`, `dist`
test: `test`, `test-unit`, `test-integration`, `test-gateway-api-conformance`, `test-knative-conformance`, `test-ui-unit`
quality: `lint`, `validate`, `validate-files`, `fmt`
UI: `build-webui-image`, `clean-webui`, `generate-webui`
docs: `docs`, `docs-serve`
codegen: `generate`, `generate-crd`, `generate-genconf`
misc: `pull-images`, `multi-arch-image-%`, `help`

### Helm charts
**Separate repo**: github.com/traefik/traefik-helm-chart
Not in the main repo at all.

### CI system
GitHub Actions -- 13 workflows:
build.yaml, release.yaml, test-unit.yaml, test-integration.yaml, test-gateway-api-conformance.yaml, test-knative-conformance.yaml, validate.yaml, check_doc.yaml, documentation.yaml, experimental.yaml, sync-docker-images.yaml, template-webui.yaml, codeql.yml

### Local dev vs production
- Local dev: `make binary` compiles Go binary, run directly. `make test-unit`. Nix flake available.
- Dockerfile is packaging-only (12 lines): copies pre-built binary from dist/ into alpine:3.23. Does NOT build inside container.
- No docker-compose for Traefik itself. Integration tests use Go test framework with real Docker/Consul/Redis/etc containers.
- GoReleaser for releases (.goreleaser.yml.tmpl).
- Sample configs: traefik.sample.toml, traefik.sample.yml at root.

---

## 2. MinIO (minio/minio) -- Object Storage

### Root-level files
```
.dockerignore, .gitignore, .golangci.yml, .mailmap, .typos.toml
CNAME, COMPLIANCE.md, CONTRIBUTING.md, CREDITS
LICENSE (AGPLv3), Makefile, NOTICE
PULL_REQUESTS_ETIQUETTE.md, README.md
SECURITY.md, VULNERABILITY_REPORT.md
_config.yml, code_of_conduct.md
docker-buildx.sh, go.mod, go.sum
helm-reindex.sh, index.yaml, main.go
update-credits.sh
Dockerfile, Dockerfile.cicd, Dockerfile.hotfix
Dockerfile.release, Dockerfile.release.old_cpu, Dockerfile.scratch
```

NO docker-compose.yml at root. SIX Dockerfiles for different build scenarios.

### Directory structure
```
cmd/            -- CLI entrypoints
internal/       -- private Go packages
docs/           -- documentation
buildscripts/   -- CI/build shell scripts
dockerscripts/  -- Docker entrypoint + static curl download
helm/minio/     -- Helm chart (in-repo)
helm-releases/  -- Helm release artifacts
.github/        -- GitHub Actions workflows
```

### Makefile targets (key ones)
build: `build`, `build-debugging`, `install`, `install-race`, `crosscompile`, `hotfix`, `hotfix-push`, `docker`, `docker-hotfix`, `docker-hotfix-push`
test (granular): `test`, `test-race`, `test-root-disable`, `test-ilm`, `test-ilm-transition`, `test-pbac`, `test-decom`, `test-versioning`, `test-configfile`, `test-upgrade`, `test-iam`, `test-replication`, `test-replication-2site`, `test-replication-3site`, `test-delete-replication`, `test-delete-marker-proxying`, `test-site-replication-ldap`, `test-site-replication-oidc`, `test-site-replication-minio`, `test-multipart`, `test-timeout`, `test-resiliency`, `test-iam-ldap-upgrade-import`, `test-iam-import-with-missing-entities`, `test-iam-import-with-openid`, `test-sio-error`
quality: `checks`, `lint`, `lint-fix`, `verify`, `verify-healing`, `verify-healing-with-root-disks`, `verify-healing-with-rewrite`, `verify-healing-inconsistent-versions`, `getdeps`, `check-gen`
misc: `all`, `clean`, `help`

Notable: extremely granular test targets -- each failure mode (replication, IAM, healing, ILM) gets its own target.

### Helm charts
**In-repo**: `helm/minio/` with Chart.yaml, values.yaml, templates/, .helmignore, README.md.
Also `helm-releases/` for packaged charts and `helm-reindex.sh` + `index.yaml` at root (self-hosted Helm repo).
Community-maintained; MinIO officially recommends their separate Operator chart for production.

### CI system
GitHub Actions -- 17+ workflows:
go.yml (primary), go-cross.yml, go-healing.yml, go-lint.yml, go-resiliency.yml, helm-lint.yml, iam-integrations.yaml, replication.yaml, root-disable.yml, mint.yml, upgrade-ci-cd.yaml, vulncheck.yml, shfmt.yml, typos.yml, depsreview.yaml, issues.yaml, lock.yml
Plus subdirectories: mint/, multipart/

### Local dev vs production
- Local dev: `go install -v` or `make build`. Run binary directly. No containers needed.
- Dockerfile copies pre-built binary (not built in container). Uses `minio/minio:latest` as base.
- 6 Dockerfiles for different scenarios: standard, CICD, hotfix, release, old_cpu, scratch.
- docker-buildx.sh for multi-arch builds.
- No docker-compose. MinIO is a single binary; just run `minio server /data`.
- Now source-only distribution (compile from source with Go 1.24+).

---

## 3. Grafana Loki (grafana/loki) -- Log Aggregation

### Root-level files
```
.dockerignore, .gitattributes, .gitignore, .gitmodules
.golangci.yml, .lychee.toml, .release-please-manifest.json
ADOPTERS.md, AGENTS.md, CHANGELOG.md, CODEOWNERS
CODE_OF_CONDUCT.md, CONTRIBUTING.md, LICENSE (AGPLv3), LICENSING.md
MAINTAINERS.md, Makefile, README.md
codecov.yml, flake.lock, flake.nix
go.mod, go.sum, mkdocs.yml, relyance.yaml
```

NO docker-compose.yml at root (it's in production/ subdirectory).

### Directory structure
```
cmd/                -- CLI entrypoints (loki, logcli, etc.)
pkg/                -- public Go packages
clients/            -- client libraries (promtail, etc.)
tools/              -- development tools
docs/               -- documentation (mkdocs)
examples/           -- getting-started examples
integration/        -- integration tests
production/         -- all deployment configs
  docker/           -- docker-compose.yaml + configs for local dev
  helm/             -- Helm charts (loki, loki-stack, fluent-bit, meta-monitoring)
  ksonnet/          -- Jsonnet-based production configs
  nomad/            -- HashiCorp Nomad jobs
  terraform/modules/s3/ -- AWS S3 Terraform module
operator/           -- Loki Operator (Kubernetes)
loki-build-image/   -- CI build image definition
vendor/             -- vendored Go dependencies
nix/                -- Nix build configs
debug/              -- debugging utilities
.claude/            -- Claude AI config
.cursor/            -- Cursor IDE config
.devcontainer/      -- VS Code Dev Container config
.github/            -- GitHub Actions (41 workflows)
.vscode/            -- VS Code settings
```

### Makefile targets (key ones)
build: `loki`, `loki-debug`, `logcli`, `logcli-debug`, `loki-canary`, `loki-canary-boringcrypto`, `loki-querytee`, `lokitool`, `migrate`, `dist`, `packages`, `fluent-bit-plugin`, `fluentd-plugin`
images: `images`, `loki-image`, `loki-debug-image`, `loki-local-image`, `loki-canary-image`, `loki-canary-boringcrypto-image`, `logcli-image`, `helm-test-image`, `loki-querytee-image`, `migrate-image`, `logql-analyzer-image`, `build-image`, `build-image-push`, `loki-operator-image`, `fluent-bit-image`, `fluentd-image`, `logstash-image`
test: `test`, `test-integration`, `test-fuzz`, `compare-coverage`, `benchmark-store`
helm: `helm-test`, `helm-lint`, `helm-docs`, `helm-test-push`
quality: `lint`, `lint-jsonnet`, `lint-scripts`, `lint-markdown`, `format`, `check-format`, `check-mod`, `check-generated-files`
docs: `doc`, `docs`, `check-doc`, `generate-example-config-doc`, `check-example-config-doc`, `documentation-helm-reference-check`
deploy: `dev-k3d-loki`, `dev-k3d-enterprise-logs`, `dev-k3d-down`
codegen: `protos`, `yacc`, `ragel`, `fmt-jsonnet`, `fmt-proto`
security: `trivy`, `snyk`, `scan-vulnerabilities`
release: `publish`, `release-workflows`, `release-workflows-check`, `update-loki-release-sha`
logging pipeline: `docker-driver`, `docker-driver-push`, `docker-driver-enable`, `docker-driver-clean`, `fluentd-plugin-push`, `logstash-push-test-logs`
misc: `all`, `clean`, `clean-protos`, `validate-example-configs`, `validate-dev-cluster-config`, `flake-update`, `binfmt`, `help`

### Helm charts
**In-repo**: `production/helm/` containing:
- `loki/` -- core Loki chart
- `loki-stack/` -- full stack chart (Loki + Promtail + Grafana)
- `fluent-bit/` -- log shipping
- `meta-monitoring/` -- monitoring Loki itself
Plus `cr.yaml` and `ct.yaml` for chart-releaser and chart-testing configs.
Helm CI/release is automated via 5 dedicated GitHub Actions workflows.

### CI system
GitHub Actions -- 41 workflows (most complex of the three):
Core: check.yml, build-loki-binary.yml, images.yml
Release: release.yml, minor-release-pr.yml, patch-release-pr.yml, backport.yml
Helm: helm-ci.yml, helm-diff-ci.yml, helm-release.yaml, helm-tagged-release-pr.yaml, helm-weekly-release-pr.yaml
Operator: 11 operator-specific workflows
Quality: lint-jsonnet.yml, conventional-commits.yml, labeler.yml
Security: secret-scanning.yml, snyk.yml, syft-sbom-ci.yml
Special: claude-code-review.yml, claude.yml, nix-ci.yaml, deploy-pr-preview.yml, logql-*.yml

### Local dev vs production
- Local dev: `make loki` compiles binary. Go workspaces (go work init). Nix flake + devcontainer available.
- Docker local dev: `production/docker/docker-compose.yaml` -- full stack with 3 Loki replicas (read/write/backend), nginx gateway, MinIO for S3 storage, Prometheus, Grafana, Promtail, Alertmanager, log-generator. Supports Delve debugger attachment.
- Simple local: `production/docker-compose.yaml` -- minimal 3-service setup (Loki + Promtail + Grafana).
- K3d dev: `make dev-k3d-loki` / `make dev-k3d-down` for local Kubernetes.
- Production: Helm charts, Ksonnet, Nomad, Terraform modules -- all in production/ directory.

---

## Cross-cutting Patterns

| Aspect | Traefik | MinIO | Loki |
|--------|---------|-------|------|
| Root docker-compose | No | No | No (in production/) |
| Dockerfile at root | Yes (1, packaging-only) | Yes (6 variants) | No (in loki-build-image/) |
| Makefile | Yes (26 targets) | Yes (50+ targets) | Yes (90+ targets) |
| Helm charts | Separate repo | In-repo (helm/) | In-repo (production/helm/) |
| CI | GH Actions (13 workflows) | GH Actions (17+ workflows) | GH Actions (41 workflows) |
| Nix | Yes (flake.nix) | No | Yes (flake.nix) |
| Vendor dir | No | No | Yes |
| Dev container | No | No | Yes (.devcontainer/) |
| Sample configs | Root (*.sample.toml/yml) | No | production/ + examples/ |
| GoReleaser | Yes (.goreleaser.yml.tmpl) | No | No (release-please) |
| Build in Docker | No (pre-built binary copied) | No (pre-built binary copied) | Build image separate |
| Local dev | make binary + run | go install + run | make loki + run OR docker-compose |
| Test granularity | Unit/integration/conformance | Per-subsystem (30+ test targets) | Unit/integration/fuzz/benchmark |

### Key takeaways for repo structure design:
1. **No project puts docker-compose at root** -- it's either absent or nested in production/examples dirs
2. **Dockerfile at root is common** but only for packaging pre-built binaries, never for building
3. **Helm charts**: small projects use separate repos (Traefik), larger ones keep in-repo (MinIO, Loki)
4. **All use GitHub Actions** with 13-41 workflows depending on complexity
5. **cmd/ + pkg/ + internal/** is the standard Go project layout used by all three
6. **integration/ as top-level dir** is common (Traefik, Loki)
7. **Makefile is the universal build interface** -- even with Go's native tooling, `make` wraps everything
8. **Sample configs at root** (Traefik) or in dedicated dirs (Loki) help onboarding
9. **contrib/ or production/** directories separate deployment concerns from source code
10. **All build the binary outside Docker** -- Dockerfiles just package the result
