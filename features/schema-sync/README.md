# Schema Sync

<!-- DESIGN: what we want. Can be ahead of code. Updated before implementation. -->

## Why

This is an open-source project with many users. We don't know what state their database is in — fresh install, old main-branch schema, partially started services, or current feature branch. Alembic migrations assume a known starting point, which we don't have. Rewriting migrations in-place (as we did with `transcription_jobs`) breaks the version chain for anyone who already ran the original.

We need a single mechanism that converges any database to the correct schema — safely, idempotently, without data loss.

## What

A startup schema sync that:

1. **Creates missing tables** in correct FK order (admin tables before meeting tables)
2. **Adds missing columns** to existing tables (e.g., `segment_id` on `transcriptions`)
3. **Creates missing indexes** (e.g., partial unique index on `segment_id`)
4. **Never drops** tables, columns, or data — orphaned tables like `transcription_jobs` are left alone
5. **Is idempotent** — safe to run on every startup, multiple times, in any order

### The Problem with Multiple Bases

We have two model packages, each with its own `declarative_base()`:

| Package | Base | Tables |
|---|---|---|
| `admin-models` | `admin_models.models.Base` | `users`, `api_tokens` |
| `meeting-api` | `meeting_api.models.Base` | `meetings`, `transcriptions`, `meeting_sessions`, `recordings`, `media_files`, + future tables |

Both write to the **same Postgres database, same `public` schema**. `create_all(checkfirst=True)` handles new tables but:

- Won't add new columns to existing tables
- Won't add new indexes to existing tables
- FK ordering depends on which service starts first

### The 4 Database States

| State | Description | What needs to happen |
|---|---|---|
| Empty | Fresh install | Create all tables in FK order |
| Main-branch | Upgrading from main | Add missing columns/indexes, create new tables. Leave `transcription_jobs` |
| Current branch | Already up to date | No-op |
| Partial | One service started, other didn't | Complete the missing tables without FK errors |

## How

### ensure_schema()

A single async function that both `admin-models` and `meeting-api` can call from their `init_db()`. It uses SQLAlchemy `inspect()` to check actual DB state before acting.

```python
async def ensure_schema(engine, base, prerequisites=None):
    """
    Converge database to match models defined in `base.metadata`.

    1. If prerequisites given, create those tables first (e.g., admin Base)
    2. create_all(checkfirst=True) for the main base
    3. Inspect existing tables, add any missing columns
    4. Add any missing indexes
    """
```

### Where it lives

In a shared location importable by both packages. Options:

- **A)** Standalone `schema_sync` package under `libs/` — cleanest separation
- **B)** Inside `admin-models` since it's the dependency root — both packages already depend on it or can
- **C)** Duplicated helper in each package — avoids cross-dependency but drifts

Preferred: **A** — a small `libs/schema-sync/` package with one module.

### Integration

Each service's `init_db()` calls `ensure_schema()` instead of raw `create_all()`:

```python
# admin-api startup
from schema_sync import ensure_schema
from admin_models.models import Base as AdminBase

await ensure_schema(engine, AdminBase)

# meeting-api startup
from schema_sync import ensure_schema
from admin_models.models import Base as AdminBase
from meeting_api.models import Base as MeetingBase

await ensure_schema(engine, MeetingBase, prerequisites=AdminBase)
```

### Column sync logic

```python
inspector = inspect(engine)
for table in base.metadata.tables.values():
    if table.name in inspector.get_table_names():
        existing_cols = {c['name'] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name not in existing_cols:
                # ADD COLUMN — nullable, no default constraint issues
                execute(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type} ...")
```

### Index sync logic

```python
existing_indexes = {idx['name'] for idx in inspector.get_indexes(table.name)}
for index in table.indexes:
    if index.name not in existing_indexes:
        index.create(bind=engine)
```

## Verification

Test script (`features/schema-sync/tests/test_schema_sync.py`) that:

1. Starts with empty DB → ensure_schema → all tables/columns/indexes present
2. Starts with main-branch schema → ensure_schema → new columns added, old tables untouched
3. Starts with current schema → ensure_schema → no-op, no errors
4. Starts with partial schema (users only) → ensure_schema → completes
5. Runs ensure_schema twice → idempotent, no errors

## Scope Boundaries

- **In scope**: Table creation, column addition, index creation, FK ordering
- **Out of scope**: Column type changes, column renames, data migrations, dropping anything
- **Future**: If we ever need destructive changes, that's a manual migration with a version bump — not this feature

## First consumer: auth-and-limits

The `api_tokens` schema change (adding scopes TEXT[], name, last_used_at, expires_at) is the first feature that depends on ensure_schema() for safe column addition. See `features/auth-and-limits/README.md` and `conductor/missions/auth-and-limits.md`.

---

<!-- STATE: what we got. Updated after validation only. -->

## Current State

**Implemented and verified (2026-03-29).** `libs/schema-sync/` package with `ensure_schema()` wired into admin-api and meeting-api startup.

### Verified

1. `ensure_schema()` creates all tables in FK order on empty DB ✓
2. Adds missing columns to existing tables (api_tokens gained 4 columns via ALTER TABLE) ✓
3. Idempotent — safe to run on every startup, multiple times ✓
4. Service startup order doesn't matter — prerequisites handle FK ordering ✓
5. First consumer: auth-and-limits token schema change — verified on agentic stack ✓

### Remaining Gaps

1. Not tested against main-branch DB state (has `transcription_jobs`, lacks `segment_id`) — needs E2E test
2. Index sync not yet exercised in production (column sync is)
3. `libs/shared-models/` deleted — Alembic migrations in `alembic/versions/` are orphaned (not breaking, just unused)
