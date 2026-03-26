---
name: Alembic Multi-Directory Migration Patterns
description: How Alembic handles multiple migration directories for the same database — version_locations, branches, stamping, ordering, separate version tables
type: reference
---

# Alembic Multi-Directory Migration Patterns

Research completed 2026-03-27. Covers: version_locations, branch_labels, multiple bases, stamping transitions, ordering, and real-world patterns from Neutron/Invenio/Django-style modular apps.

## Two Fundamental Approaches

1. **Shared alembic_version table** — multiple branches coexist in one version table (Alembic's native "multiple bases")
2. **Separate version tables** — each service gets its own `alembic_version_<service>` table via `version_table` param

## Key Sources
- Alembic branches docs: https://alembic.sqlalchemy.org/en/latest/branches.html
- GitHub Discussion #1522 (maintainer CaselIT): separate version tables for shared DB
- GitHub Issue #777 (maintainer Michael Bayer): modular app pattern, include_object filtering
- Neutron expand/contract: https://docs.openstack.org/neutron/latest/contributor/alembic_migrations.html
- Monorepo multi-service pattern: https://dev.to/fadi-bck articles
- Modular apps pattern: https://medium.com/@karuhanga articles
