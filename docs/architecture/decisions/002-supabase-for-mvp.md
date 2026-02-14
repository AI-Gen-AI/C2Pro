# ADR 002: Supabase for MVP

## Status
Accepted

## Context
The MVP requires managed PostgreSQL, authentication primitives, and operational simplicity with low setup overhead for the team.

## Decision
Adopt Supabase as the managed Postgres platform for development and staging, including RLS-first multi-tenant controls.

## Consequences
- Positive: Accelerated setup, integrated Postgres tooling, and improved delivery speed.
- Tradeoff: Platform coupling to Supabase conventions.
- Mitigation: Keep data access behind module ports and SQLAlchemy repositories.

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added initial ADR scaffold and documented the Supabase MVP decision.
