# Security Backlog: Tenant Isolation Audit (TASK-REV-SECURITY-001)

**Status**: 🔶 5 hardening tasks open (post-audit 2026-05-08)
**Last Updated**: 2026-05-09

---

## Status View

**Pending Tasks**: 5 (TASK-SEC-012..016) — post-audit hardening

- P1: TASK-SEC-012 (missing SQL RLS test), TASK-SEC-013 (cookie consent auth), TASK-SEC-014 (disclaimer persistence), TASK-SEC-015 (SecretStr)
- P2: TASK-SEC-016 (VaultKv guard)
- Completed 2026-05-09: TASK-SEC-017 (tenant_id + RLS migration), TASK-SEC-018 (AuditLogORM sync)

Prior vulnerabilities SEC-009..011 fixed. Completed work in [COMPLETED.md](COMPLETED.md).

---

## Active Tasks (Post-Audit Hardening — 2026-05-08)

| Status | Priority | Task ID | Description | Source |
|--------|----------|---------|-------------|--------|
| [x] | P1 | `TASK-SEC-012` | Add SQL RLS test `supabase/tests/09_clause_embeddings_rls.sql` — cross-tenant isolation + fail-closed | Audit finding (CRITICAL) | ✅ Done 2026-08-07 (PR #467): pgTAP RLS suite for clause_embeddings cross-tenant isolation. |
| [x] | P1 | `TASK-SEC-013` | Add auth guard to cookie consent endpoints (`POST/GET/PATCH /compliance/cookies/consent`) — currently unauthenticated | Audit finding (HIGH) | ✅ Done 2026-08-07 (PR #467): Auth guard on cookie consent endpoints. |
| [x] | P1 | `TASK-SEC-014` | Persist disclaimer acceptance to DB (currently in-process memory — breaks multi-pod) | Audit finding (HIGH) | ✅ Done 2026-08-07 (PR #467): DisclaimerAcceptanceORM + DB-backed table with RLS. |
| [x] | P1 | `TASK-SEC-015` | Use `SecretStr` for `secret_channel_token` + `secret_channel_vault_token` in `config.py` | Audit finding (HIGH) | ✅ Done 2026-08-07 (PR #467): SecretStr for channel tokens. |
| [x] | P2 | `TASK-SEC-016` | Guard `VaultKvBundleProvider.load_bundle` against malformed `bundle_ref` (no `:`) — currently raises unhandled `ValueError` | Audit finding (HIGH) | ✅ Done 2026-08-07 (PR #467): ValueError guard on malformed bundle_ref. |
| [x] | P2 | `TASK-SEC-017` | Add RLS migration: `tenant_id` on `clause_embeddings`, `analysis`, `alert`, `coherence_results` + Alembic migration | ✅ 2026-05-09 PR#112 |
| [x] | P2 | `TASK-SEC-018` | Fix `SQLAlchemyAuditRepository` — AuditLogORM tagged with `rls_policy` metadata | ✅ 2026-05-09 PR#112 |

---

## Remaining Work (Pre-existing, No Formal Task IDs)

### Database Migrations Required

1. **Enable RLS on tables**: `analysis`, `alerts`, `audit_logs` (beyond clause_embeddings covered by TASK-SEC-017)

---

## Architecture Criterion Pending

- `[x]` All tables have `tenant_id` and RLS enabled (✅ 2026-08-07 PR #467)

---

## Completed Vulnerabilities Reference

| ID | Location | Status |
|----|----------|--------|
| SEC-009 | `PgvectorEmbeddingRepository` / `clause_embeddings` | ✅ Fixed 2026-04-07 |
| SEC-010 | `SqlAlchemyCoherenceRepository._load_project` | ✅ Fixed 2026-04-07 |
| SEC-011 | `SqlAlchemyStakeholderRepository`, `SqlAlchemyAnalysisRepository` | ✅ Fixed 2026-04-07 |
