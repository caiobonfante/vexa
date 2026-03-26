# Shared Models

## Why

All Python services share the same database schema and validation logic. Without a shared package, schema drift between services causes silent data corruption — a field renamed in one service but not another, an enum value added without updating validation. This package is the **single source of truth** for models, schemas, migrations, token scoping, webhook delivery, and storage.

## What

### Data Model

```
User ─────┬── APIToken (many, scoped via vxa_ prefix)
          │
          └── Meeting ─── MeetingSession (many, one per bot join attempt)
                     │
                     ├── Transcription (many, one per segment batch)
                     │
                     └── Recording ─── MediaFile (many: audio, video, screen)
```

### Meeting Status Machine

```
                              needs_human_help
                              ↑       │
requested → joining → awaiting_admission → active → stopping → completed
    │          │              │              │          │
    └──────────┴──────────────┴──────────────┴──────────┘
                              ↓
                           failed
```

Terminal states: `completed`, `failed` (no outbound transitions).

### Token Scoping

Tokens use prefix-based scoping: `vxa_<scope>_<random>`.

| Prefix | Scope | Access |
|--------|-------|--------|
| `vxa_bot_` | Bot management | Join/stop bots, voice agent |
| `vxa_tx_` | Transcription | Read transcripts, meetings |
| `vxa_user_` | Dashboard | Full user access |
| `vxa_admin_` | Admin | User/token CRUD, settings |

Legacy tokens (no `vxa_` prefix) get full access for backward compatibility.

### Webhook Delivery

```
Event occurs → build_envelope() → sign_payload() → deliver()
                                                      │
                                              success? ┤
                                              yes → done
                                              no  → Redis retry queue
                                                      │
                                              webhook_retry_worker
                                              (exponential backoff)
```

Envelope format: `{event_id, event_type, api_version, created_at, data}`
Signature: `X-Webhook-Signature: sha256=<HMAC-SHA256 of timestamp.payload>`

### Modules

| Module | Description |
|--------|-------------|
| `models.py` | SQLAlchemy ORM — User, APIToken, Meeting, MeetingSession, Transcription, Recording, MediaFile |
| `schemas.py` | Pydantic request/response schemas, Platform/Status enums, transition validation |
| `token_scope.py` | Prefix-based API token scoping (`vxa_bot_`, `vxa_tx_`, `vxa_user_`, `vxa_admin_`) |
| `webhook_delivery.py` | HMAC-signed webhook delivery with Redis-backed retry queue |
| `webhook_retry_worker.py` | Background retry worker with exponential backoff (30s → 1m → 5m → 30m → 2h) |
| `storage.py` | S3/MinIO/local filesystem abstraction for recordings |
| `database.py` | SQLAlchemy async session factory |
| `scheduler.py` | Redis sorted-set job scheduler |
| `security_headers.py` | Standard security response headers |

### Documentation
- [Webhooks](../../docs/webhooks.mdx)
- [Token Scoping](../../docs/token-scoping.mdx)

## How

```bash
# Install
pip install -e packages/shared-models/

# Run migrations
alembic upgrade head

# Run all tests
pytest packages/shared-models/tests/ packages/shared-models/shared_models/test_*.py -v

# Check migration status
alembic current
alembic heads
```
