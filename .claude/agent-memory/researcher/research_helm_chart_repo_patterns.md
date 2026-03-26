---
name: Helm chart repository patterns (in-repo vs separate)
description: Comprehensive survey of where CNCF/infra projects keep Helm charts, OCI registry adoption, versioning, and pragmatic recommendations for new small projects
type: project
---

# Helm Chart Repository Patterns: In-Repo vs Separate

## 1. Projects with Helm Charts IN the Same Repo

| Project | Location | Published To | Version Coupling |
|---------|----------|-------------|-----------------|
| **cert-manager** | `deploy/charts/cert-manager/` | OCI: `quay.io/jetstack` + legacy `charts.jetstack.io` | chart version != app version; both bumped on release |
| **MinIO** | `helm/minio/` in minio/minio | `helm.min.io` | chart version tracks app loosely |
| **Linkerd** | `charts/linkerd-control-plane/`, `charts/linkerd2-cni/` etc. in linkerd/linkerd2 | `helm.linkerd.io/edge` and `/stable` | discussed decoupling in issue #7405 |

**Why in-repo works for these:** Single team owns both app and chart. Chart changes are tightly coupled to code changes (new flag = new template variable). PRs that change both app and chart are atomic.

## 2. Projects with SEPARATE Chart Repos

| Project | App Repo | Chart Repo | Why Separate |
|---------|----------|-----------|-------------|
| **Traefik** | `traefik/traefik` | `traefik/traefik-helm-chart` | Multiple charts (proxy, enterprise, hub, mesh); different release cadences |
| **ArgoCD** | `argoproj/argo-cd` | `argoproj/argo-helm` (contains argo-cd, argo-workflows, etc.) | Multi-project umbrella; community maintains charts independently |
| **Grafana** | `grafana/grafana` | `grafana/helm-charts` (now splitting to `grafana-community/helm-charts` as of Jan 2026) | Many products in one chart repo; community governance |
| **Prometheus** | `prometheus/prometheus` | `prometheus-community/helm-charts` | Community-maintained; 20+ charts for different exporters/tools |
| **Temporal** | `temporalio/temporal` | `temporalio/helm-charts` at `charts/temporal/` | Chart has complex dependencies (Cassandra/ES/Postgres); different maintainers |
| **Bitnami** | N/A (packaging vendor) | `bitnami/charts` monorepo | 200+ third-party app charts; no relationship to upstream repos |
| **Cilium** | `cilium/cilium` | `cilium/charts` | Separate release process |

**Why separate works for these:** Different teams/communities maintain charts vs app. Multiple apps share one chart repo. Chart release cadence differs from app release cadence.

## 3. Modern Consensus (2024-2026)

### Helm documentation recommendation
- Official Helm docs now recommend OCI registries over traditional chart repositories
- Quote: "When considering creating a chart repository, you may want to consider using an OCI registry instead"
- `helm repo add` / `helm repo update` overhead eliminated with OCI

### OCI registry adoption
- **Mainstream as of 2024.** Bitnami defaulted to OCI in November 2024 -- the single largest chart provider.
- Traefik publishes to `oci://ghcr.io/traefik/helm/traefik`
- ArgoCD publishes to `oci://ghcr.io/argoproj/argo-helm/argo-cd`
- cert-manager publishes to `oci://quay.io/jetstack/charts`
- Azure deprecated legacy Helm CLI commands (Sep 2025)
- Harbor dropped non-OCI Helm support
- All major registries support it: GHCR, ECR, ACR, GCR, Quay, Docker Hub

### Trend direction
**In-repo is winning for single-product projects.** The "separate chart repo" pattern is legacy from the helm/charts monorepo era (deprecated 2020). New projects almost universally keep charts in-repo. Separate repos persist only for multi-product orgs or community-maintained chart collections.

### Versioning best practice
- `version` (chart version): bump on ANY chart change (template, values, new app version)
- `appVersion`: bump only when default app image version changes
- They are independent. Many projects sync them; many don't. Both are valid.
- For single-product in-repo charts: syncing them is simpler and common

## 4. Pragmatic Choice for a New Small Project

### Recommendation: In-repo at `deploy/helm/charts/<name>/`
- This is exactly what Vexa already does (`deploy/helm/charts/vexa/` and `deploy/helm/charts/vexa-lite/`)
- Matches cert-manager and MinIO patterns
- Atomic PRs: app code + chart change in one commit
- No sync headaches

### Publish via OCI to GHCR
- Use `helm push` to `oci://ghcr.io/<org>/charts/<name>`
- 15-line GitHub Actions workflow (see below)
- No GitHub Pages needed, no index.yaml maintenance
- Users install with: `helm install vexa oci://ghcr.io/vexa-ai/charts/vexa --version 0.1.0`

### Minimum viable GitHub Actions workflow
```yaml
name: Publish Helm Chart
on:
  push:
    branches: [main]
    paths: ['deploy/helm/charts/**']
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - name: Extract version
        id: version
        run: echo "VERSION=$(yq -r .version deploy/helm/charts/vexa/Chart.yaml)" >> "$GITHUB_OUTPUT"
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ github.token }}
      - name: Package and push
        run: |
          helm package deploy/helm/charts/vexa --version ${{ steps.version.outputs.VERSION }}
          helm push vexa-${{ steps.version.outputs.VERSION }}.tgz oci://ghcr.io/${{ github.repository_owner }}/charts
```

### Kustomize vs Helm
- **Kustomize** is simpler for first-party apps with few config knobs (plain YAML + overlays)
- **Helm** is better when you want users to customize extensively via `values.yaml`
- **For an OSS infra project shipping to external users: Helm is the right choice**
  - Users expect `helm install` -- it's 75% adoption among K8s users (CNCF 2025)
  - `values.yaml` is the standard configuration surface
  - Kustomize is for internal teams customizing their own deploys
- **You CAN do both**: ship Helm chart, tell advanced users they can `helm template` + pipe to kustomize
- Helm 4 (Nov 2025) added native server-side apply and better Kustomize interop

### Minimum K8s deploy story for a GitHub infra project
1. **docker-compose.yml** at repo root -- for local dev and simple self-hosting (day 1)
2. **Helm chart** at `deploy/helm/charts/<name>/` -- for K8s users (week 1)
3. **Published to GHCR OCI** via GitHub Actions -- for `helm install` from anywhere (week 2)
4. **values.yaml** with good defaults -- so it works out of the box
5. Optional: kustomize overlays for internal staging/prod environments

## 5. Supabase Self-Hosting Pattern

### Official (Supabase-maintained)
- `docker/` directory in main repo (`supabase/supabase`): contains `docker-compose.yml` + `.env` templates
- Docker Compose is the **primary** self-hosting method
- No Kubernetes configs in the main repo

### Community (separate repo)
- `supabase-community/supabase-kubernetes` -- Helm chart at `charts/supabase/`
- Community-maintained, NOT officially supported by Supabase
- Apache 2.0 licensed
- Contains a single umbrella chart deploying all Supabase services

### Takeaway
Supabase follows a **docker-compose-first** strategy with community-driven K8s support. This is common for projects that prioritize simplicity of self-hosting over enterprise K8s deployment.

## 6. E2B Infrastructure Pattern
- Uses **Terraform** as primary IaC (not Helm, not docker-compose)
- Infrastructure in `iac/` directory
- Cloud-specific: GCP (full), AWS (beta)
- No Helm charts -- they target cloud VMs with Firecracker, not K8s

## Summary: What Pattern Should Vexa Follow

Vexa's current structure (`deploy/helm/charts/vexa/` and `deploy/helm/charts/vexa-lite/`) matches the modern best practice for a single-product project. The recommended next steps are:

1. Keep charts in-repo (already done)
2. Add OCI publishing to GHCR via GitHub Actions
3. Maintain docker-compose for simple self-hosting (already have at `deploy/compose/`)
4. Keep `version` and `appVersion` in Chart.yaml -- bump chart version on any chart change
5. Document installation: `helm install vexa oci://ghcr.io/vexa-ai/charts/vexa`
