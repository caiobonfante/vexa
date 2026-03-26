---
name: Open Source Extraction Checklist Research
description: Comprehensive research on what to strip/make-pluggable when extracting internal Python/FastAPI CaaS tool as open source — patterns, checklists, architecture decisions
type: project
---

## Research: Open-Sourcing Internal Tools — Extraction Checklist

**Why:** Vexa Runtime API is being prepared for open source release. Need to identify what must be stripped, abstracted, or made pluggable.
**How to apply:** Use as the master checklist when planning the extraction work.

### Key Sources Consulted

1. CFPB Open Source Checklist (github.com/cfpb/open-source-project-template)
2. Spectral: 7 Tips to Securely Open-Source Internal Software
3. E2B infra architecture (github.com/e2b-dev/infra CLAUDE.md)
4. Coolify architecture (coolify.io)
5. Microsoft Azure Strangler Fig Pattern documentation
6. Airflow executor pluggable backend pattern
7. Python ABC vs Protocol comparison for pluggable interfaces
8. Repository Pattern for FastAPI with pluggable backends
9. podman-py / docker-py compatibility research

### 1. WHAT TO STRIP (must remove before public)

- **Secrets in git history**: Use gitleaks/trufflehog to scan ALL commits, not just HEAD
- **Internal service URLs**: hardcoded hostnames like `bot-manager:8080`, `redis:6379`
- **Internal auth tokens**: BOT_API_TOKEN, specific API keys
- **PII in code/comments**: user emails, internal user IDs
- **Internal business logic in profiles**: meeting-specific BOT_CONFIG, platform-specific env vars
- **Internal webhook URLs**: POST_MEETING_HOOKS, callback URLs to internal services
- **Internal observability endpoints**: any logging tied to internal infrastructure
- **Claude/Anthropic credentials**: CLAUDE_CREDENTIALS_PATH, CLAUDE_JSON_PATH

### 2. WHAT TO MAKE PLUGGABLE (interface-based)

#### Auth (HIGH priority)
Current: SQLAlchemy query against User/APIToken tables + token_scope check
Pattern: Python Protocol class defining `authenticate(token) -> User | None`
Default impl: API key header check
Users provide: JWT, OAuth2, OIDC, custom
Reference: fastapi-auth-middleware, Airflow's BaseExecutor pattern

#### Container Runtime (MEDIUM priority)
Current: Direct Docker socket via requests_unixsocket
Pattern: Backend interface (already planned in architecture-refactoring-plan.md)
Implementations: Docker (default), K8s, Process
Note: podman-py is NOT a drop-in for docker-py, BUT docker-py works against Podman socket
Recommendation: Keep docker-py, document Podman socket compatibility

#### Container Profiles (HIGH priority)
Current: Hardcoded agent/browser/meeting in profiles.py
Pattern: JSON/YAML file loaded at startup, hot-reloadable (SIGHUP pattern from Selenoid)
Users define: their own profiles with custom images, resources, ports, timeouts

#### Lifecycle Callbacks (MEDIUM priority)
Current: Internal webhook to bot-manager
Pattern: Generic callback_url at container creation (already in refactoring plan)
Additional: Webhook signing for external callbacks

### 3. WHAT TO KEEP AS-IS

#### Redis (keep as required dependency)
- Redis is standard enough. E2B uses Redis. Coolify uses Redis. Airflow uses Redis.
- Adding pluggable state stores (SQLite, Postgres, in-memory) adds complexity without clear benefit
- FakeRedis exists for testing without a Redis server
- Valkey is a drop-in Redis replacement (no code changes needed)
- **Recommendation: Redis as required, document Valkey/DragonflyDB compatibility**

#### Docker as default runtime
- Docker is the standard. Podman works via Docker-compatible socket.
- containerd is lower-level; users needing it are on K8s anyway
- **Recommendation: Docker default, document Podman socket, K8s backend for production**

### 4. STRANGLER FIG PATTERN (how to extract incrementally)

From Microsoft Azure Architecture Center:
1. Introduce facade (proxy) between clients and both old/new systems
2. Facade routes requests — initially all to legacy, incrementally to new
3. Each iteration moves more functionality to new system
4. After full migration, remove facade

Applied to our extraction:
- Phase 1: Abstract internal auth behind Protocol interface (facade = auth dependency)
- Phase 2: Extract profiles to config file (facade = get_profile function stays same)
- Phase 3: Replace internal webhooks with generic callbacks (facade = callback mechanism)
- Phase 4: Remove Vexa-specific env vars, replace with generic config

Key consideration from Microsoft docs:
> "Consider how to handle services and data stores that both the new system and the legacy system might use."
Redis state store is shared — both internal and open-source versions use it identically.

### 5. E2B ARCHITECTURE (reference for what's pluggable vs hardcoded)

E2B infra (github.com/e2b-dev/infra):
- **Hardcoded**: Firecracker as runtime (not pluggable), GCP as cloud provider
- **Pluggable**: Templates (user-defined container images)
- **Auth**: JWT via Supabase (hardcoded to their stack)
- **State**: PostgreSQL (primary), Redis (caching), ClickHouse (analytics)
- **Observability**: OpenTelemetry with Grafana stack (hardcoded)
- **Lesson**: E2B does NOT make infrastructure pluggable. They commit to specific tech choices. The pluggability is at the user-facing layer (templates, SDK).

### 6. COOLIFY ARCHITECTURE (reference for self-hosted open source)

Coolify (github.com/coollabsio/coolify):
- **Docker**: Required, not abstracted. K8s "coming soon" but not available.
- **Auth**: Built-in, self-contained (no external auth dependency)
- **State**: SQLite (self-contained, no Redis/Postgres required)
- **Lesson**: Coolify keeps infrastructure simple — fewer dependencies = easier self-hosting. They don't over-abstract.

### 7. AIRFLOW PATTERN (reference for pluggable backends in Python)

Airflow executors (airflow.apache.org):
- BaseExecutor abstract class with `queue_command()`, `heartbeat()`, `sync()`
- Implementations: LocalExecutor, CeleryExecutor, KubernetesExecutor
- Selected by config: `executor = LocalExecutor` in airflow.cfg
- **Pattern**: Abstract base class, config-driven selection, implementations in separate modules
- **This is exactly what Runtime API needs for container backends**

### 8. PYTHON PROTOCOL vs ABC FOR INTERFACES

From jellis18.github.io comparison:
- **ABC**: Requires explicit subclassing (nominal typing). Good for internal code, enforces contract at class creation.
- **Protocol**: Structural typing (duck typing). Good for external/plugin interfaces, no inheritance needed.
- **Recommendation for open source**: Use Protocol for auth interface (external users shouldn't need to subclass our classes). Use ABC for container backend (internal implementations, want enforcement).

### 9. SPECIFIC VEXA RUNTIME API EXTRACTION PLAN

Based on code review of actual files:

| File | What to change | Priority |
|------|---------------|----------|
| auth.py | Replace SQLAlchemy User/APIToken lookup with Protocol interface | HIGH |
| config.py | Remove CLAUDE_*, BOT_API_TOKEN. Keep REDIS_URL, DOCKER_HOST. Add PROFILE_PATH. | HIGH |
| profiles.py | Load from JSON/YAML file instead of hardcoded dict. Keep defaults for agent/browser. | HIGH |
| state.py | Keep as-is. Redis is the right choice. Clean, minimal, 60 lines. | LOW |
| docker_ops.py | Already clean abstraction. Wrap in backend Protocol. | MEDIUM |
| main.py | Remove Vexa-specific env injection (lines 140-190). Make generic. | HIGH |
| main.py | Remove shared_models dependency (move to optional). | MEDIUM |

### 10. CHECKLIST BEFORE PUBLIC RELEASE

Pre-release:
- [ ] Run gitleaks/trufflehog on full git history
- [ ] Remove/replace all internal service hostnames
- [ ] Extract auth to Protocol interface with default API-key impl
- [ ] Extract profiles to config file (JSON/YAML)
- [ ] Remove Claude-specific credential mounting
- [ ] Remove Vexa-specific env var injection from container creation
- [ ] Make shared_models optional (inline minimal User model)
- [ ] Add .env.example with documented variables
- [ ] Add LICENSE file
- [ ] Add CONTRIBUTING.md
- [ ] Add CHANGELOG.md
- [ ] Test clean install on fresh machine
- [ ] Write README with quickstart (docker-compose up → create container)
- [ ] Document Podman compatibility
- [ ] Document Valkey/DragonflyDB Redis alternatives

Post-release:
- [ ] Set up GitHub Actions CI
- [ ] Add OpenAPI docs (FastAPI auto-generates)
- [ ] Create example profiles (generic worker, browser, jupyter)
- [ ] Write integration tests using FakeRedis
