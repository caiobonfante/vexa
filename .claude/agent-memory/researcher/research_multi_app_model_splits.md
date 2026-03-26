---
name: research_multi_app_model_splits
description: How Django, Rails, SQLAlchemy/Alembic handle multi-app model splits with cross-app foreign keys sharing one database — patterns for splitting shared-models
type: project
---

# Multi-App Model Splits with Cross-App Foreign Keys (Shared Database)

Research conducted 2026-03-27 for the shared-models split described in `docs/architecture-proposed.md` Step 6.

## 1. Django's Approach

### app_label + db_table

Every Django model has a `Meta.app_label` that determines which app "owns" the model. The `db_table` defaults to `<app_label>_<model_name>` but can be overridden.

Since Django 1.7+ (ticket #14007, fixed July 2013), models in a `models/` package directory **automatically** get the correct `app_label` without explicit `Meta` declaration. The system resolves it by looking one level up from a package or module named `models`:
- `myapp/models/user.py` -> app_label = `myapp`
- `geo/models/places.py` -> app_label = `geo`

### Cross-App ForeignKey References

Django uses **string references** to avoid circular imports:
```python
# In app "orders"
class Order(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
```

This is the canonical Django way. The string `'accounts.User'` is resolved lazily from the app registry. No import of the User model is needed.

### Migration Independence and Cross-App Dependencies

Each Django app has its own `migrations/` directory with its own numbered migration files. `makemigrations` can target a single app (`makemigrations orders`) but Django auto-detects cross-app dependencies.

When `orders.Order` has a FK to `accounts.User`, the generated migration contains:
```python
class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),  # auto-detected from FK
    ]
    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('user', models.ForeignKey(to='accounts.User', ...)),
            ],
        ),
    ]
```

**Key behavior**: "Restricting to a single app (either in makemigrations or migrate) is a best-efforts promise, not a guarantee; any other apps that need to be used to get dependencies correct will be."

**Circular dependencies**: Django splits them automatically by breaking one FK into a separate migration within the same app, creating a two-step creation (table first, then alter to add FK).

### Splitting models.py into a Package

The official cookbook pattern:
```
myapp/
  models/
    __init__.py     # from .user import User; from .order import Order
    user.py
    order.py
```

In modern Django (1.7+), you do NOT need `app_label` in Meta for models inside the package -- just ensure they're imported in `__init__.py`. Sentry uses this pattern at massive scale (122+ model files + 5 subdirectories in `src/sentry/models/`).

**Sentry's __init__.py**: Uses `from .module import *  # NOQA` for every submodule, creating a barrel export of all models.

## 2. Rails Approach

### Engines Sharing a Database

Rails engines are packaged gems that can contain models, controllers, and migrations. For shared databases:

- Models are namespaced: `Analytics::LogStat` in engine, `User` in host app
- Cross-engine references use `class_name`:
  ```ruby
  belongs_to :author, class_name: 'OtherEngine::Author'
  ```
- Configurable references via initializers:
  ```ruby
  belongs_to :author, class_name: Blorgh.user_class
  ```

### Migration Ordering

Two approaches:
1. **Copy to host** (Rails default): `install_migrations` copies engine migrations into host's `db/migrate/` with a timestamp comment showing origin. Risk: shared DB + multiple apps = duplicate migration execution.
2. **Keep in engine** (recommended for shared DB): Append engine migration path to app's migration paths. Custom rake tasks manage engine-specific migrations independently.

### Shared Database Gotchas

- The engine can create records without the host app's knowledge
- Test setup requires explicit database creation and migration runs
- Factory definitions need explicit class references for namespaced models
- Separate schema files (e.g., `analytics_schema.rb`) to avoid conflicts

## 3. SQLAlchemy/Alembic (Directly Relevant to This Repo)

### Cross-Module ForeignKey (No Model Import Needed)

SQLAlchemy ForeignKey accepts **table name strings**, not model classes:
```python
# In meeting-api/models.py
class Meeting(Base):
    __tablename__ = "meetings"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # No import of User needed! "users.id" refers to the TABLE name.
```

This is EXACTLY how `shared_models/models.py` already works -- `ForeignKey("users.id")` is a string referencing the table, not the model class.

### Relationships vs ForeignKeys

- `ForeignKey("users.id")` -- works without importing anything. References the DB table.
- `relationship("User", ...)` -- requires the model class to be registered in the same metadata/registry. This is the constraint that creates coupling.

**The split strategy**: Keep ForeignKey columns (DB-level integrity), drop relationship() objects across package boundaries. Each package only defines relationships to its own models.

### Alembic Multi-Package Migrations

Alembic supports **multiple version locations** with **independent named branches**:

```ini
# alembic.ini
version_locations =
    packages/meeting-api/migrations
    packages/agent-api/migrations
    packages/admin-api/migrations
```

Create independent branches:
```bash
alembic revision -m "create meeting tables" \
  --head=base \
  --branch-label=meeting \
  --version-path=packages/meeting-api/migrations
```

**Cross-branch dependencies** (e.g., meetings table FK to users table):
```bash
alembic revision -m "add meetings table" \
  --head=meeting@head \
  --depends-on=<admin_initial_revision_id>
```

This creates a logical ordering dependency without merging branches.

**Alembic maintainer recommendation** (GitHub discussion #1522): If two services share both schema and tables, "rethink your schema." If they share a schema but have separate tables, configure Alembic to look only at relevant tables per service. Use separate `version_table` names if running truly independent migration histories.

### Filtering Tables Per Package

In `env.py`, use `include_object` to scope autogenerate to specific tables:
```python
def include_object(obj, name, object_type, reflected, compare_to):
    if object_type == "table":
        return name in OWNED_TABLES  # e.g., {"meetings", "transcriptions", "recordings"}
    return True

context.configure(
    target_metadata=metadata,
    include_object=include_object,
)
```

## 4. Real-World Examples

### Sentry (Django, 122+ Model Files)

- Single Django app (`sentry`) with `models/` package containing 122+ files and 5 subdirectories
- All models re-exported via `from .module import *` in `__init__.py`
- NOT multi-app -- Sentry keeps everything in one app with file-level organization
- `getsentry` (proprietary) imports the `sentry` app, adds routes/models, and re-exports it
- Extension via Django signals, swappable backends, and feature flags

### SQLModel (FastAPI Ecosystem)

Recommended pattern for split models:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .team_model import Team

class Hero(SQLModel, table=True):
    team_id: int = Field(foreign_key="team.id")
    team: Optional["Team"] = Relationship(back_populates="heroes")
```

This is for models within the same package that need relationships. For cross-package (no relationship), just use the FK string.

## 5. Synthesis: Recommendation for This Repo's Split

### What the Proposed Architecture Wants

From `docs/architecture-proposed.md`:
- `admin-api` owns: users, api_tokens
- `meeting-api` owns: meetings, meeting_sessions, transcriptions, recordings, media_files
- `agent-api` owns: agent_sessions, workspaces
- Cross-references are integers: `meetings.user_id = 5`
- FK exists at DB level. Code never does `from admin_api.models import User`

### How to Implement (Django-Inspired, Alembic-Native)

1. **Each package gets its own `models.py`** with its own `Base = declarative_base()` (or shared metadata)
2. **ForeignKeys use string table references** (already the case): `ForeignKey("users.id")`
3. **No `relationship()` across packages** -- meeting-api's Meeting model has `user_id` column but no `user = relationship("User")`. If you need user data, query by ID or read from X-User-ID header.
4. **Alembic uses `version_locations`** with branch labels per package
5. **Cross-branch `depends_on`** ensures meeting tables are created after users table
6. **Single `alembic_version` table** tracks all branches (Alembic handles multiple heads natively)

### The Key Insight from Django

Django's secret sauce is that ForeignKey('app.Model') is a **lazy string reference** resolved at migration time, not import time. SQLAlchemy already does this naturally -- `ForeignKey("users.id")` is a string referencing the table, resolved at `CREATE TABLE` time. No model import graph needed.

### Dead Ends to Avoid

- **Separate databases per package**: Alembic maintainer says this over-complicates things if tables share FK relationships. One database, separate migration branches.
- **Shared Base with all models imported**: This recreates the monolithic coupling. Each package should have its own metadata/Base.
- **Separate `version_table` per package**: Only needed if packages run migrations truly independently (different deploy cycles). For a monorepo deployed together, single version table with branches is simpler.
