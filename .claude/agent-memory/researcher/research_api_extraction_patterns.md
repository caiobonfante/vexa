---
name: API Extraction Patterns Research
description: How successful open-source projects (Docker, Temporal, Terraform, K8s, FastAPI/Starlette, Fly Machines) designed API surfaces when extracting from internal tools. Patterns for making hardcoded profiles user-definable.
type: project
---

# API Surface Design: Extraction from Internal Tools (2026-03-26)

Research into how successful open-source projects balanced the tension between "too generic = useless" and "too specific = no adoption" when extracting public APIs from internal tools.

## 1. Docker: Extraction from dotCloud PaaS

**Source:** Jpetazzo (Docker engineer) retrospective

### What Was Stripped

dotCloud was a PaaS with these internal assumptions that Docker removed:
- Stateful container management (MySQL, MongoDB running as containers)
- Complex in-place build system (code updated while containers ran)
- Distributed scheduling system (Redis-locked broadcast across nodes)
- SSH servers in every container for remote execution
- Mercurial-based image storage (slow, cumbersome)
- Multiple on-disk services sharing container metadata with fragile locking

### What Was Kept

Docker kept exactly one thing: **the container primitive itself** (AuFS + namespaces + cgroups wrapped in a simple API).

### Key Design Decision: "Batteries Included, But Swappable"

Docker's philosophy became its defining characteristic:
- **Ship with sensible defaults** (built-in bridge networking, local storage driver)
- **But make every subsystem replaceable** via driver/plugin interfaces
- Extension points: network drivers, volume drivers, logging drivers, authorization plugins
- Plugins are independent processes communicating over RPC (not compiled in)

### Lesson for Vexa

The genius was NOT making Docker generic -- it was making Docker **opinionated about the right layer**. Docker is opinionated about container lifecycle (create, start, stop, remove) but unopinionated about everything above it (scheduling, networking, storage). The orchestration assumptions from dotCloud (naive scheduler, hardcoded networking) were explicitly removed.

**Applied to Runtime API:** The profile system should be opinionated about container CRUD lifecycle but unopinionated about what runs inside the container. Currently, `profiles.py` mixes lifecycle concerns (idle_timeout, auto_remove) with domain knowledge (BOT_MODE, BOT_CONFIG, claude credentials). The domain knowledge should move out.

---

## 2. Temporal: Extraction from Uber's Cadence

**Source:** Temporal blog, SE Daily interview, temporal.io comparison docs

### What Changed from Cadence to Temporal

| Cadence (internal) | Temporal (extracted) | Why |
|---|---|---|
| Mandatory timeouts for everything | Mostly discretionary timeouts | Reduced required config surface |
| Thrift structures | Protobuf + gRPC | Better security, broader language support |
| TChannel protocol | gRPC only | Simpler interprocess communication |
| Membership seed config required | Auto-registration from DB | Removed operational complexity |
| Binary blob payloads (no metadata) | Metadata per payload | Extensibility for codecs, encryption |
| Rigid signal/query handlers | Dynamic handler registration | More flexible extension |

### Core Abstraction: Workflow as Unit of Scalability

Temporal chose to keep workflow instances bounded ("every workflow should be limited in size") but infinitely scalable horizontally ("we can infinitely scale out the number of workflows"). This is the key design choice: **pick the right unit of abstraction and make it scale**.

### Extension Model

- Activities execute OUTSIDE the core cluster (user's code, user's infrastructure)
- Multiple language SDKs implement the same semantics
- System workflows use standard abstractions
- No plugin system per se -- extensibility is through the programming model itself

### Lesson for Vexa

Temporal's extraction lesson: **remove every configuration knob that isn't load-bearing**. Cadence required users to configure timeouts, membership seeds, and protocol details. Temporal made most of these either optional or automatic. The profile system should have good defaults and require minimum configuration for the common case.

---

## 3. Terraform: Provider Plugin Architecture

**Source:** HashiCorp provider design principles documentation

### Core Design Principles

1. **Providers map 1:1 to APIs or problem domains** -- not cross-cutting concerns
2. **Resources represent a single API object** with CRUD operations
3. **Schema closely matches the underlying API** -- don't re-imagine it
4. **Resources must be importable** -- bridge manual and automated provisioning
5. **Functions are pure and offline** -- no side effects, no network calls
6. **Abstractions of multiple components go in Modules, not providers**

### The Critical Boundary: Core vs Provider

| In Terraform Core | In Provider | In Modules (user-defined) |
|---|---|---|
| State management | CRUD for single API objects | Compositions of resources |
| Diff computation | Schema definition | Abstractions, patterns |
| Plan/Apply lifecycle | Authentication | Environment-specific config |
| Resource graph | Single-resource validation | Multi-resource validation |
| Import/export | Type conversions | Business logic |

### Key Insight: "Simplification Lives in Modules, Not Providers"

Terraform explicitly forbids providers from being opinionated about HOW resources combine. A provider does CRUD on individual resources; a module composes them. This separation prevents the provider from becoming a bottleneck for adoption.

### Lesson for Vexa

The profile system maps to Terraform's "module" concept, not its "provider" concept. The Runtime API should be the "provider" -- it does CRUD on containers. Profiles should be user-definable compositions (like Terraform modules) that specify image + resources + env + ports + lifecycle settings. The current hardcoded `profiles.py` dict should become a configuration file users can extend.

---

## 4. Kubernetes: API Conventions

**Source:** kubernetes/community api-conventions.md (the canonical document)

### Spec/Status Pattern

Every K8s resource has:
- **spec**: Desired state (user writes)
- **status**: Observed state (controller writes)
- Different authorization scopes: users write spec, controllers write status
- The system operates level-based (most recent spec), not edge-based

### Declarative Over Imperative

Fields describe intended outcomes, not actions. Name things by what you want, not what you do. The system reconciles continuously -- there is no "apply once" semantic.

### Extensibility Through CRDs

CRDs are the killer feature for extensibility:
- Users define new resource types with OpenAPI v3 schemas
- K8s treats them identically to built-in resources (CRUD, watch, quota, RBAC)
- Operator pattern: CRD + Controller = user-defined reconciliation loop
- Dynamic registration: CRDs appear/disappear at runtime

### Conditions (not State Machines)

Rather than rigid state enums, K8s uses a list of Conditions:
- Each has: type, status (True/False/Unknown), reason, message
- Multiple conditions can be true simultaneously
- Higher-level controllers can summarize without understanding specifics

### Key Insight: Uniform Metadata Enables Generic Tooling

Every K8s object has the same metadata structure (kind, apiVersion, name, namespace, uid, labels, annotations). This uniformity means quota systems, garbage collection, autoscalers, and RBAC all work across ANY resource type -- even user-defined CRDs.

### Lesson for Vexa

The container state model should follow K8s patterns:
- **Separate desired state (profile config) from observed state (container status)**
- Use **labels** for classification and querying (already doing this with vexa.managed, vexa.profile, vexa.user_id)
- Consider **Conditions** instead of a single status string (e.g., a container could be "Running" but also "IdleWarning" or "HealthCheckFailing")
- **Profile definitions should be declarative data**, not Python code -- analogous to CRDs being YAML, not Go code

---

## 5. FastAPI/Starlette: Layered Primitives

**Source:** Starlette docs, FastAPI architecture analysis

### The Layering Model

```
FastAPI (developer-friendly abstractions)
  |
  |  class FastAPI(Starlette):  # direct inheritance
  |
Starlette (ASGI primitives)
  |
  |  Request, Response, Routing, Middleware, Mount
  |
Uvicorn (ASGI server)
```

### How FastAPI Adds Value Without Modifying Starlette

- **Wraps**, never replaces: Pydantic models wrap Starlette's Request parsing
- **Composes**: Starlette's JSONResponse is used internally when you return a dict
- **Same interface**: `app.add_middleware()` in FastAPI passes through to Starlette
- Every ASGI middleware works unchanged in FastAPI

### Key Insight: Every Component is an ASGI App

Starlette's genius: Request, Route, Mount, Middleware are all ASGI apps. They compose because they share a single interface: `async def __call__(scope, receive, send)`. This means `Router -> Mount -> Router -> Mount -> Route` chains work naturally.

### Lesson for Vexa

For the Runtime API to be extensible:
- **Define a minimal interface** that profiles must conform to (image, resources, ports, idle_timeout, auto_remove)
- **Let higher-level services compose** on top (Meeting API adds bot_config, Agent API adds claude mounts)
- Domain-specific knowledge (BOT_CONFIG construction, credential mounting) should happen in the calling service, not in the Runtime API. Runtime API receives a fully-specified container spec.

---

## 6. Fly Machines: CaaS API Design

**Source:** Fly.io blog, Machines API docs

### Core Design Decisions

1. **Separate expensive (create) from fast (start)**: Machines are created ahead of time, started in ~150ms
2. **Hardware pinning**: Machines are pinned to specific hardware (trades resilience for speed)
3. **No profiles/templates at API level**: Config is specified fully at creation time
4. **Orchestration is the caller's responsibility**: Fly provides primitives, user builds patterns

### API Surface

```
POST /apps/{app_name}/machines    # Create machine (slow: image pull, resource allocation)
POST /machines/{id}/start         # Start machine (fast: ~150ms)
POST /machines/{id}/stop          # Stop machine
DELETE /machines/{id}             # Destroy machine
GET /machines/{id}                # Inspect
GET /machines/{id}/wait           # Long-poll for state change
POST /machines/{id}/exec          # Execute command inside
```

### Key Insight: No Template System is a Template System

Fly deliberately does NOT have profiles/templates in the API. Instead:
- Config is specified at creation time as a JSON blob
- Users build their own template layer on top
- This prevents the API from becoming opinionated about use cases

---

## 7. Selenoid/Selenium Grid: Profile System Design

**Source:** Selenoid browsers.json, Selenium Grid TOML stereotypes

### Selenoid's browsers.json (Best Profile Pattern Found)

```json
{
  "chrome": {
    "default": "128.0",
    "versions": {
      "128.0": {
        "image": "selenoid/vnc:chrome_128.0",
        "port": "4444",
        "tmpfs": {"/tmp": "size=512m"},
        "env": ["VAR=value"],
        "shmSize": 268435456,
        "cpu": "1.0",
        "mem": "512m"
      }
    }
  }
}
```

- Hot-reloadable via SIGHUP
- Pure data (JSON), not code
- Each profile maps to: image + port + resources + env + storage

### Selenium Grid 4 TOML Stereotypes

```toml
[node]
detect-drivers = false

[[node.driver-configuration]]
display-name = "Chrome"
stereotype = '{"browserName": "chrome", "browserVersion": "128.0"}'
max-sessions = 2
```

- Capability-based matching: incoming request specifies what it needs, Grid finds matching node
- Dynamic Grid (K8s): creates a pod matching the stereotype on demand

---

## 8. E2B: User-Defined Templates

**Source:** E2B documentation, API reference

### Template Model

1. User writes an `e2b.Dockerfile`
2. E2B builds it, extracts filesystem, does provisioning
3. Snapshots the result as a "template" with a template ID
4. User spawns sandboxes from the template ID
5. Multiple isolated instances from one template

### Key Insight: Dockerfile IS the Template

No custom DSL, no profile schema. The universally-known Dockerfile format IS the template definition. This is brilliant for adoption because users already know Dockerfiles.

---

## Synthesis: Design Recommendations for Vexa Runtime API

### The Spectrum

```
Too Generic (useless)          Sweet Spot              Too Specific (no adoption)
     |                            |                            |
  Fly Machines              Terraform/K8s               Current Vexa
  (raw VM API,              (strong primitives,         (hardcoded agent/browser/
   zero opinions)            user-defined               meeting profiles with
                             compositions)               domain logic in Runtime)
```

### Recommended Architecture: Three-Layer Profile System

**Layer 1: Runtime API Core (the "provider")**
- Container CRUD: create, start, stop, remove, inspect, list, exec
- State management: Redis-backed status, reconciliation loop
- Idle management: configurable timeouts per container
- Backend abstraction: Docker, K8s, Process
- Callbacks: POST to caller-provided URL on state change
- NO domain knowledge. NO profile-specific code paths.

**Layer 2: Profile Definitions (the "CRD/Module")**
- JSON or YAML files (like Selenoid's browsers.json)
- User-definable, hot-reloadable
- Specify: image, resources (cpu, memory, shm), ports, idle_timeout, auto_remove, default env, default mounts, labels
- Ship with built-in profiles (agent, browser, meeting, worker) but users can add their own
- The profile is a TEMPLATE -- callers can override fields at creation time

**Layer 3: Domain Services (the "operator")**
- Meeting API, Agent API, etc.
- Compose profiles with domain-specific config at creation time
- Add env vars, mounts, callbacks that the Runtime API doesn't understand
- Handle lifecycle events (meeting end, agent idle, etc.)

### Concrete Changes Needed

**Current `profiles.py` (hardcoded Python dict):**
```python
profiles = {
    "agent": {"image": config.AGENT_IMAGE, ...},
    "browser": {"image": config.BROWSER_IMAGE, ...},
    "meeting": {"image": config.MEETING_IMAGE, ...},
}
```

**Target `profiles.json` (data-driven, extensible):**
```json
{
  "profiles": {
    "agent": {
      "image": "${AGENT_IMAGE:-vexa-agent:dev}",
      "resources": {"memory": "512m"},
      "idle_timeout": 900,
      "auto_remove": false,
      "one_per_user": true,
      "ports": {}
    },
    "browser": {
      "image": "${BROWSER_IMAGE:-vexa-bot:dev}",
      "resources": {"memory": "2g", "shm_size": "2g"},
      "idle_timeout": 600,
      "auto_remove": false,
      "ports": {"6080/tcp": "vnc", "9223/tcp": "cdp", "22/tcp": "ssh"}
    }
  }
}
```

**Key principle:** Domain services (Meeting API, Agent API) pass a fully-constructed container spec to Runtime API. They reference a profile for defaults but overlay their domain-specific config. The Runtime API never has an `if profile == "meeting":` branch.

### What to Remove from Runtime API

| Currently in Runtime API | Should Move To |
|---|---|
| `BOT_MODE` env construction | Meeting API / Agent API |
| `BOT_CONFIG` JSON building | Meeting API |
| Claude credential mount logic | Agent API |
| MinIO/S3 config for browser profiles | Meeting API or Agent API |
| `VEXA_AGENT_API` env injection | Agent API |
| `BOT_API_TOKEN` env injection | Agent API |
| CDP URL construction (`http://{name}:9223`) | Caller or profile metadata |

### What to Keep in Runtime API

| Concern | Why It Belongs Here |
|---|---|
| Container CRUD | Core primitive |
| Redis state management | Infrastructure concern |
| Reconciliation loop | Infrastructure reliability |
| Idle timeout management | Lifecycle management |
| Port allocation and mapping | Infrastructure concern |
| Label management (vexa.managed, etc.) | Classification/querying |
| Health endpoint | Operational |

### Adoption Pattern: Selenoid-Style Hot Reload

Following Selenoid's proven pattern:
1. Profiles live in a JSON file mounted into the Runtime API container
2. Users edit the file to add new profiles
3. Send SIGHUP or POST /admin/reload to hot-reload profiles
4. No restart required
5. Built-in profiles ship as defaults, user profiles override or extend

### The Docker Lesson Applied

Docker succeeded by being opinionated about exactly one thing: the container lifecycle API (create, start, stop, remove). Everything else (networking, storage, scheduling, orchestration) was deliberately left to plugins and higher-level tools.

Runtime API should be opinionated about exactly one thing: **container lifecycle management with idle timeouts and state tracking**. Everything else (what runs in the container, how it gets configured, what happens when it exits) should be delegated to callers.

---

## Sources

- [From dotCloud to Docker](https://jpetazzo.github.io/2017/02/24/from-dotcloud-to-docker/)
- [Temporal: Workflow Engine Design Principles](https://temporal.io/blog/workflow-engine-principles)
- [Temporal vs Cadence](https://temporal.io/temporal-versus/cadence)
- [Terraform Provider Design Principles](https://developer.hashicorp.com/terraform/plugin/best-practices/hashicorp-provider-design-principles)
- [Kubernetes API Conventions](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
- [Fly Machines API](https://fly.io/blog/fly-machines/)
- [Docker Networking Design Philosophy](https://www.docker.com/blog/docker-networking-design-philosophy/)
- [Selenoid browsers.json](https://github.com/aerokube/selenoid/blob/master/docs/browsers-configuration-file.adoc)
- [E2B Sandbox Templates](https://e2b.dev/docs/sandbox-template)
- [FastAPI/Starlette Architecture](https://leapcell.io/blog/understanding-the-pillars-of-fastapi-through-starlette)
- [Nomad Task Driver Plugins](https://developer.hashicorp.com/nomad/plugins/drivers)
