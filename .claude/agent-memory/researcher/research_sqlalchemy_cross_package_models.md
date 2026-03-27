---
name: SQLAlchemy Cross-Package Model Sharing
description: How SQLAlchemy handles models split across packages — ForeignKey vs relationship resolution, shared Base/MetaData/registry, patterns and gotchas
type: project
---

## Core Finding

ForeignKey and relationship() use DIFFERENT resolution mechanisms:
- **ForeignKey("table.column")** resolves against **MetaData** (table namespace). It uses TABLE names, not class names.
- **relationship("ClassName")** resolves against the **registry** (class namespace). It uses CLASS names, not table names.

Both require sharing the same MetaData/registry, which means sharing the same `Base` (or at least the same `registry` object).

## Key Rule

Two packages CAN define models that hit the same database, but:
1. String ForeignKey references (`ForeignKey("users.id")`) only work if both models share the same `MetaData` object
2. String relationship references (`relationship("User")`) only work if both models share the same `registry` object
3. Since `DeclarativeBase` / `declarative_base()` bundles both MetaData and registry, sharing the same Base is the simplest path

## Vexa Current State

- `libs/shared-models/shared_models/models.py` defines `Base = declarative_base()` and all models (User, Meeting, etc.)
- `services/calendar-service/app/models.py` just re-exports from shared_models — no separate Base
- Only one `declarative_base()` call in the entire codebase

**Why:** ForeignKey is Core-level (table-to-table), relationship is ORM-level (class-to-class). Different layers, different lookup namespaces.

**How to apply:** If runtime-api needs its own models that reference shared-models tables, it MUST import the same Base. If it only needs ForeignKey (no ORM relationships back), it could theoretically use a separate Base with the same MetaData — but this is fragile and not recommended.
