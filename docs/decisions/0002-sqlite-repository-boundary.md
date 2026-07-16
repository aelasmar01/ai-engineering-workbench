# ADR 0002: SQLite Persistence Behind Repository Classes

## Status

Accepted

## Context

The workbench needs durable local operational state without a cloud backend.
Later CLI, API, and dashboard features will need to read and mutate the same
project and task state.

## Decision

Use SQLite through SQLAlchemy ORM mappings and expose persistence through
repository classes. Interface code should depend on repositories and domain
models rather than direct table access.

Schema initialization is handled by application code in Milestone 1. A migration
tool may be introduced later when schema evolution requires ordered migrations.

## Consequences

- Data remains local by default.
- Tests can use temporary SQLite databases.
- Domain validation and status rules remain outside UI code.
- Future API and CLI work can share persistence logic without duplicating SQL.
