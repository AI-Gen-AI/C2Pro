# Security Backlog: Tenant Isolation Audit (TASK-REV-SECURITY-001)

**Status**: ✅ All named vulnerabilities fixed (SEC-009..011)
**Last Updated**: 2026-05-08

---

## Status View

**Pending Tasks**: 0 named tasks

All three critical vulnerabilities (SEC-009, SEC-010, SEC-011) are fixed.
Completed work archived in [COMPLETED.md](COMPLETED.md).

---

## Remaining Work (No Formal Task IDs)

These items were identified during the audit but have not been assigned task IDs:

### Database Migrations Required

1. **Enable RLS on tables**: `clause_embeddings`, `analysis`, `alerts`, `audit_logs`
2. **Add `tenant_id` column to `clause_embeddings` table**: Migration script needed

### High Priority Code Quality

3. **`SQLAlchemyAuditRepository` broken**: Matches a non-existent version of `AuditLogORM`. Synchronize models and repositories.

---

## Architecture Criterion Pending

- `[ ]` All tables have `tenant_id` and RLS enabled (RLS migration not yet created)

---

## Completed Vulnerabilities Reference

| ID | Location | Status |
|----|----------|--------|
| SEC-009 | `PgvectorEmbeddingRepository` / `clause_embeddings` | ✅ Fixed 2026-04-07 |
| SEC-010 | `SqlAlchemyCoherenceRepository._load_project` | ✅ Fixed 2026-04-07 |
| SEC-011 | `SqlAlchemyStakeholderRepository`, `SqlAlchemyAnalysisRepository` | ✅ Fixed 2026-04-07 |
