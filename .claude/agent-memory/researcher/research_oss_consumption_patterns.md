---
name: OSS Consumption Patterns — How Companies Use Their Own Extracted Open-Source
description: 5 patterns for how a parent product consumes an extracted OSS component, with real examples (Docker/Moby, GitLab CE/EE, Grafana, Red Hat, Meta/React, E2B, Terraform), and recommendation for Vexa/Runtime API extraction
type: project
---

# How Companies Consume Their Own Extracted Open-Source Components (March 2026)

**Why:** Vexa is extracting Runtime API as a generic CaaS open-source project. We need to decide the dependency direction: how does Vexa (the product) consume the extracted component?

**How to apply:** Choose a consumption pattern before starting extraction. The wrong choice creates maintenance hell; the right choice reduces it. This research ranks 5 patterns by fit for our specific situation (Python monorepo, small team, CaaS extraction).

---

## Pattern 1: Import as Library/Dependency

**How it works:** The OSS component is published as a package (npm, PyPI, crate). The parent product adds it as a dependency in requirements.txt/package.json.

**Real examples:**
- **E2B:** Published as `e2b` on PyPI and `e2b` on npm. The hosted E2B Cloud platform consumes these same SDKs internally. The `e2b-dev/infra` repo (Terraform-deployed backend) is separate from the SDK repo. The Code Interpreter SDK (`@e2b/code-interpreter`) extends the base Sandbox SDK (`e2b`). Dependency direction: SDK -> Cloud API (unidirectional). Users install SDK, authenticate with API key, SDK calls hosted REST API. Self-hosters deploy the infra repo separately.
- **Testcontainers:** Library consumed via Maven/pip by the parent company's own test suites.
- **Most small utility extractions:** lodash, axios, etc. Company extracts, publishes, imports.

**Pros:**
- Cleanest dependency direction
- Version pinning gives stability
- OSS improvements automatically available via upgrade
- Community contributions directly benefit parent

**Cons:**
- Breaking changes in OSS package require parent product updates
- Parent product's needs may diverge from community direction
- Publishing/versioning overhead for small teams

**Fit for Vexa/Runtime API:** MODERATE. Runtime API is currently a FastAPI service, not a library. Extracting it as a pip-installable library would require significant restructuring. More natural if the extraction is the Python client SDK for the Runtime API service.

---

## Pattern 2: Run as Sidecar/Microservice

**How it works:** The OSS component runs as a separate service. The parent product calls its API. The OSS project ships as a container image or binary; the parent deploys it alongside other services.

**Real examples:**
- **Steel Browser (open-source) / Steel.dev (hosted):** Steel Browser is an open-source Docker container providing browser automation API. Steel.dev's hosted platform deploys the same container at scale. Users can self-host the same Docker image or use the managed cloud.
- **Browserless:** Open-source headless browser service. Companies (including Browserbase competitors) deploy it as a sidecar.
- **Selenium Grid 4:** Open-source browser grid. Companies deploy it as infrastructure. Grid provides generic browser sessions; consuming products add domain-specific logic on top.
- **Grafana:** Deployed as a service. Grafana Labs' own Grafana Cloud runs the same open-source Grafana binary, plus enterprise plugins.
- **MinIO:** Open-source S3-compatible object store. Companies deploy it as a service alongside their products.

**Pros:**
- Natural for service-oriented architectures (which Vexa already is)
- OSS project has clear API contract
- Parent product and OSS project can be versioned/deployed independently
- Community can self-host the exact same service
- No code coupling — only API coupling

**Cons:**
- Network hop between parent and OSS service
- Must maintain API backward compatibility
- Operational overhead of another service to deploy/monitor

**Fit for Vexa/Runtime API:** HIGH. Runtime API is already a FastAPI microservice with REST endpoints. It already has a clear API contract (`POST /containers`, `GET /containers/{name}`, etc.). The extraction would literally be: move the service to its own repo, publish a Docker image, and Vexa deploys that image in its docker-compose/Helm alongside other services. Minimal code changes needed.

---

## Pattern 3: Fork and Extend (Internal Fork with Proprietary Extensions)

**How it works:** Company maintains a private fork of the OSS repo. Proprietary features are added in the fork. Periodic merges from upstream OSS into the fork.

**Real examples:**
- **Meta/React:** React is developed on GitHub, then manually synced to Facebook's internal monorepo ("fbsource") for extensive testing. Feature flags control which features are on internally vs. in OSS npm releases. A sync bot copies code between fbsource and the GitHub repo, with blacklists for FB-specific directories. FB engineers use the exact same React Native code as GitHub, with separate feature flag files for internal vs. OSS builds.
- **Google's internal forks:** Many Google projects (gRPC, Protobuf, Abseil) are developed internally first, then synced to open-source with Copybara. Internal versions may have Google-specific extensions.
- **Android OEMs:** Samsung, Xiaomi etc. maintain forks of AOSP with proprietary UI layers.

**Pros:**
- Maximum flexibility — can add anything proprietary
- Internal needs never blocked by OSS review process
- Can move fast internally

**Cons:**
- Merge hell — keeping fork in sync with upstream is expensive
- Community divergence — internal version drifts from OSS
- Requires dedicated sync tooling (Copybara, sync bots)
- Only viable for very large engineering teams (Meta, Google scale)

**Fit for Vexa/Runtime API:** LOW. Small team. Maintaining a fork is pure overhead. The whole point of extraction is to reduce coupling, not create a merge treadmill.

---

## Pattern 4: Plugin/Extension Model (Open Core)

**How it works:** OSS core provides extension points (plugins, hooks, modules). Proprietary features are implemented as plugins that the parent product ships alongside the core.

**Real examples:**
- **Grafana:** OSS core (Apache 2.0) + enterprise plugins (proprietary). Enterprise data source plugins (Splunk, Dynatrace, Databricks) are only available in Grafana Enterprise and Grafana Cloud. Core provides plugin framework; enterprise adds >20 proprietary data source plugins plus features like team sync, data source permissions, caching, reporting. Goal: "create a great Enterprise product without undermining open source."
- **Terraform:** Core (BSL) + provider plugins. Core handles state management, planning, applying. Providers handle resource-specific CRUD via RPC. Plugin framework is the SDK; anyone can write custom providers. Companies write internal providers for proprietary clouds.
- **GitLab (current):** Single codebase with EE modules. Proprietary code lives in `ee/` directory. Ruby module injection pattern: EE modules are injected into CE classes. For the FOSS mirror (`gitlab-foss`), a "Merge Train" tool automatically strips all `ee/` code. Moved from separate repos to single repo because separate repos caused 150+ MRs for a single security release. Migration: 55 engineers, 600+ MRs, 1.5M lines changed.
- **PostHog:** Same pattern as GitLab — `ee/` directory in same repo.
- **Kubernetes CRDs:** OSS core provides Custom Resource Definitions as extension mechanism. Companies add proprietary operators/controllers as CRDs.

**Pros:**
- Clean separation of concerns
- OSS core is genuinely useful standalone
- Enterprise features don't pollute OSS codebase
- Community can build their own plugins

**Cons:**
- Requires designing plugin architecture upfront
- Plugin API becomes a contract you must maintain
- GitLab lesson: separate repos created merge hell, so they moved to single repo with directory separation + automated stripping

**Fit for Vexa/Runtime API:** MODERATE-HIGH. The profile system is already a natural extension point. Meeting-specific profiles ("meeting", "agent", "browser") are essentially plugins that define container behavior. Could design Runtime API with a profile plugin system where Vexa provides meeting-specific profiles and the OSS core provides the engine. However, the plugin complexity may be premature for a small project.

---

## Pattern 5: Upstream-First

**How it works:** ALL changes go to the OSS project first. The parent product is just a downstream consumer — it builds on top of OSS releases, never maintains a separate version.

**Real examples:**
- **Red Hat / Linux Kernel / Fedora:** All fixes and enhancements are submitted upstream first. Patches must be accepted by upstream maintainers before inclusion in RHEL. Red Hat spent ~$2B since 2000 acquiring OSS companies (Ansible, 3Scale) and made them available to the community. RHEL is built from upstream Fedora packages + stability patches. "Making the software available, getting collaboration, getting eyes on code makes better software for everyone."
- **Docker / Moby:** Docker committed to using Moby as upstream for the Docker product. Components extracted from Docker into independent projects: containerd, runc, SwarmKit, InfraKit, HyperKit, VPNKit, libnetwork. Docker CE code spread across dozens of repos. Goal: moby/moby eventually only includes tooling to assemble Docker CE from components. "Changes made to Moby will show up when you install Docker." Other projects (Mirantis, etc.) also use Moby as upstream.
- **Sentry:** FSL-licensed, but all development happens in the open repo. Sentry Cloud runs the same code as self-hosted.

**Pros:**
- Zero fork maintenance
- Maximum community benefit
- Credibility ("we eat our own dog food")
- Simplest operational model

**Cons:**
- Cannot keep any proprietary features in the OSS component
- All competitive advantages must come from layers above the OSS component
- OSS community may push back on features that only serve parent product

**Fit for Vexa/Runtime API:** HIGH. Runtime API is designed to be domain-agnostic — it already knows nothing about meetings. All Vexa-specific logic lives in Meeting API, Agent API, etc. (layers above). The OSS Runtime API would be the upstream, and Vexa would consume it as-is. Vexa's competitive advantage comes from meeting domain logic, not container orchestration.

---

## Recommendation for Vexa

### Primary: Pattern 2 (Microservice) + Pattern 5 (Upstream-First)

**The combined pattern:**

1. **Extract Runtime API to its own repo** as an open-source CaaS microservice
2. **Publish Docker images** (`ghcr.io/vexa-ai/runtime-api:latest`)
3. **Vexa's docker-compose/Helm references the published image** — no fork, no vendoring
4. **All Runtime API changes go upstream first** — Vexa never maintains a private patch
5. **Meeting-specific profiles are configuration, not code** — they live in Vexa's repo as profile YAML/JSON, passed to Runtime API at startup
6. **Vexa's competitive moat is the Meeting API, Agent API, and domain logic** — not the container orchestration layer

**Why this combination:**
- Runtime API is already a microservice with REST API — zero restructuring needed
- Runtime API already knows nothing about meetings — upstream-first is natural
- Profile system is already configuration-driven — meeting profiles are just config
- Small team — cannot afford fork maintenance overhead
- Community value is clear — generic CaaS is useful beyond meetings

### Concrete dependency direction:

```
vexa-product-repo/
  docker-compose.yml:
    runtime-api:
      image: ghcr.io/vexa-ai/runtime-api:v1.2.3  # <-- pinned version
      volumes:
        - ./config/profiles.yaml:/app/profiles.yaml  # <-- Vexa-specific profiles
      environment:
        - ORCHESTRATOR_BACKEND=kubernetes
    meeting-api:
      image: vexa-meeting-api:latest
      environment:
        - RUNTIME_API_URL=http://runtime-api:8080

runtime-api-oss-repo/   (separate repo, open source)
  Dockerfile
  src/
    main.py
    backends/
      docker.py
      kubernetes.py
      process.py
    profiles.py         # loads profiles from config file
    lifecycle.py        # callbacks, idle management
    api.py              # REST endpoints
  profiles.example.yaml # example profiles (not meeting-specific)
```

### Why NOT the alternatives:

| Pattern | Why Not |
|---------|---------|
| Library import | Runtime API is a service, not a library. Would require major restructuring. |
| Fork and extend | Small team, fork maintenance is expensive, no need for proprietary container features. |
| Plugin model (sole) | Premature complexity. Profile YAML achieves the same extensibility without plugin infrastructure. Could adopt later if needed. |

### Secondary consideration: Light Plugin System (Pattern 4 lite)

If profiles alone aren't enough (e.g., need custom lifecycle hooks per profile), add a minimal plugin system later:

```python
# In profiles.yaml
meeting:
  image: vexa-bot:latest
  hooks:
    on_exit: "http://meeting-api:8080/internal/callback"
    on_start: "http://meeting-api:8080/internal/callback"
  # No code plugins, just webhook hooks
```

This is effectively Pattern 4 but using webhooks as the extension mechanism instead of code plugins. Already partially designed in the architecture plan (callback_url).

---

## E2B as the Closest Analogy

E2B's architecture is the most relevant comparison:

| Aspect | E2B | Vexa/Runtime API |
|--------|-----|-----------------|
| OSS component | Sandbox SDK (e2b on PyPI/npm) + infra repo | Runtime API (container lifecycle service) |
| Hosted product | E2B Cloud | Vexa platform |
| Extension | Code Interpreter SDK extends base SDK | Meeting API consumes Runtime API |
| Self-hosting | Deploy infra repo via Terraform | Deploy Runtime API via docker-compose/Helm |
| Dependency direction | SDK -> Cloud API (unidirectional) | Meeting API -> Runtime API (unidirectional) |
| What's proprietary | Cloud control plane, billing, scaling | Meeting domain logic, transcription, voice agent |

Key difference: E2B's OSS is a client SDK; Vexa's OSS would be a server-side service. E2B users need E2B Cloud (or self-host infra) to use the SDK. Vexa's Runtime API would be fully self-contained — no cloud dependency.

---

## Docker/Moby as the Architectural Precedent

Docker's Moby extraction is the closest architectural precedent:

1. Docker extracted containerd, runc, SwarmKit, etc. as independent OSS projects
2. Docker committed to using Moby (the assembly framework) as upstream
3. Docker CE is assembled from these components
4. Docker's proprietary value: Docker Desktop UX, Docker Hub, enterprise features

Vexa parallel:
1. Vexa extracts Runtime API as an independent OSS project
2. Vexa commits to using Runtime API as upstream (no internal fork)
3. Vexa's platform is assembled from Runtime API + domain services
4. Vexa's proprietary value: Meeting domain, transcription, voice agent, hosted platform

---

## Sources

### GitLab
- Single codebase blog: https://about.gitlab.com/blog/a-single-codebase-for-gitlab-community-and-enterprise-edition/
- Migration used 55 engineers, 600+ MRs, 1.5M lines
- FOSS mirror uses "Merge Train" to auto-strip ee/ code
- Module injection pattern: EE modules injected into CE classes, auto-disabled in CE builds

### Meta/React
- Sync process gist: https://gist.github.com/bvaughn/91583b158a207c72d63954452101b5d6
- Manual sync from GitHub to fbsource, extensive internal testing
- Feature flags control internal-only features
- Sync bot blacklists FB-specific directories
- React Foundation announced 2025 for governance transition

### Red Hat
- Upstream-first explainer: https://opensource.com/article/16/12/why-red-hat-takes-upstream-first-approach
- All patches submitted upstream before inclusion in RHEL
- $2B in acquisitions since 2000, all made available to community

### Docker/Moby
- Moby announcement: https://www.docker.com/blog/introducing-the-moby-project/
- Components: containerd (CNCF), runc (OCI), SwarmKit, HyperKit, VPNKit, libnetwork
- Docker committed to using Moby as upstream
- Goal: moby/moby becomes assembly-only, not monolith

### E2B
- Architecture: deepwiki.com/e2b-dev/E2B
- Monorepo: packages/js-sdk, packages/python-sdk, packages/cli, apps/web
- Infra repo: github.com/e2b-dev/infra (Terraform-deployed backend)
- Dual-protocol: REST (control plane) + gRPC (data plane)
- $21M Series A (July 2025), aiming for open standard

### Grafana
- Enterprise differentiation: https://grafana.com/blog/how-we-differentiate-grafana-enterprise-from-open-source-grafana/
- Plugin architecture: data source, panel, app plugins via RPC
- 20+ enterprise data source plugins (Splunk, Dynatrace, Databricks)

### Terraform
- Plugin framework: https://developer.hashicorp.com/terraform/plugin/framework
- Core/plugin split via RPC
- Custom providers for proprietary infrastructure

### Kubernetes
- CRD extensibility: https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/
- Operator pattern: CRD + custom controller

### Steel/Browserbase
- Steel: open-source browser API (Docker, self-hosted)
- Browserbase: managed cloud browser automation
- Agent-infrastructure split pattern: AI reasoning separate from browser execution
