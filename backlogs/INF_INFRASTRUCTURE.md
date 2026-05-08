# Infrastructure Tasks & Knowledge Base

**Category**: Infrastructure (INF)
**Owner Role**: infra
**Last Updated**: 2026-05-08

**Quick Links**:
- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_infra.md)

---

## 0. Status View

**Pending Tasks**: 6

- Phase 2 deferred: `TASK-INF-008`..`TASK-INF-011`
- Data-gated deferred: `TASK-INF-014` ([~] — needs 4-6 weeks of LangSmith production data)
- Blocked (external): `TASK-INF-055` (Sentry DSN + backend auth instrumentation required)

**Completed Tasks**: 53 — see COMPLETED.md

**Usage Note**:

- Check this split first before reading the specifications below.
- The detailed sections remain the source for implementation detail on pending tasks.

## 1. Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
|--------|----------|---------|------------|-------------|--------|
| [ ] | P2 | `TASK-INF-008` | None | [PHASE 2 DEFERRED] Multi-language prompt templates in English and Spanish | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P2 | `TASK-INF-009` | Planned | [PHASE 2 DEFERRED] Implement Procurement Plan flow with LangChain | Planning |
| [ ] | P2 | `TASK-INF-010` | Planned | [PHASE 2 DEFERRED] Implement RACI flow with LangChain | Planning |
| [ ] | P2 | `TASK-INF-011` | Planned | [PHASE 2 DEFERRED] Implement Stakeholder Resolution flow with LangChain | Planning |
| [~] | P3 | `TASK-INF-014` | None | Prompt optimization suggestions from usage metrics `[~ DEFERRED] @2026-05-08 — Requires LangSmith production data (4-6 weeks). Revisit once traces accumulate.` | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P3 | `TASK-INF-055` | DevOps | Monitor auth failures in Sentry `[-] Blocked @2026-04-20 - Requires backend/security changes plus external Sentry DSN and alert destination setup.` | `docs/archive/plans/Clerk/IMPLEMENTATION_GUIDE.md` |

**Statistics**:
- Total: 59 tasks
- Active: 6 (10.2%)
- Completed: 53 (89.8%)
- Blocked: 1 (TASK-INF-055)

---

## 2. Specifications

### Multi-Language Prompt Templates (TASK-INF-008)

**Task**: `TASK-INF-008`
**Priority**: P2 (Phase 2 deferred)

```python
# apps/api/src/core/ai/templates/i18n_loader.py
class I18nPromptLoader:
    """Loads prompt templates with i18n support (English + Spanish)."""

    def load_template(self, template_name: str, language: str = "en") -> str:
        # Load from: templates/procurement_plan_v1.en.jinja2
        #        or: templates/procurement_plan_v1.es.jinja2
```

**Directory Structure**:
```
apps/api/src/core/ai/templates/
├── procurement_plan_v1.en.jinja2
├── procurement_plan_v1.es.jinja2
├── raci_assignment_v1.en.jinja2
├── raci_assignment_v1.es.jinja2
├── stakeholder_resolution_v1.en.jinja2
└── stakeholder_resolution_v1.es.jinja2
```

**Estimated Hours**: 12
**Depends on**: TASK-INF-009..011 workflows (all Phase 2 together)

---

### Monitoring & Observability (TASK-INF-055)

**Initiative**: Production monitoring for auth failures

**Status**: TASK-INF-055 blocked (external Sentry DSN + backend auth-failure tagging required)

**Auth Monitoring Specification** (TASK-INF-055):

```python
# apps/api/src/core/middleware/tenant_isolation.py
from sentry_sdk import capture_exception, set_tag

async def extract_tenant_id(request: Request) -> str:
    try:
        # Verify token
        # Extract tenant_id
    except Exception as e:
        set_tag("auth_failure_type", type(e).__name__)
        set_tag("auth_endpoint", request.url.path)
        capture_exception(e)
        raise

# Sentry Alerts:
# - Condition: >10 auth failures in 1 hour
# - Action: Email + Slack notification
```

**Blocker (2026-04-20)**:

- `role_infra` cannot complete the application instrumentation because `apps/api/src/**/*.py` and tests are protected for this role.
- The repo already has baseline Sentry lifecycle wiring in `apps/api/src/main.py`, `src.config` settings, and `apps/api/tests/core/test_mcp_startup.py`.
- Completion requires:
  - Backend/security owner to add auth-failure tagging/capture at the auth or tenant-isolation boundary.
  - Ops owner to provide a real `SENTRY_DSN` and alert destination for the target environment.
  - Infra/devops owner to validate that the runtime secret is configured in staging/production after those inputs exist.

```python
# Target metrics
- clerk_token_validation_failures
- tenant_isolation_bypasses
- invalid_jwt_signatures
- expired_tokens

# Alerts:
- Trigger: >10 auth failures/minute
- Severity: High
- Notify: #security-alerts Slack channel
```

---

## 3. Lessons Learned

_Lessons learned will be documented here_

---

## 4. Architectural Decisions

_ADRs for this category will be documented here_

---

## 5. Technical Debt

| Debt ID | Description | Impact | Effort | Created |
|---------|-------------|--------|--------|---------|

---

## 6. Metrics

- **Total Tasks**: 59
- **Completed**: 53 (89.8%)
- **Active/Blocked**: 6 (10.2%)
- **Test Coverage**: TBD

---

## 7. Audit Reports

### Alembic Migration Chain Audit (TASK-REV-INFRA-001)
**Date**: 2026-04-07
**Status**: ✅ RESOLVED

#### Findings (historical):
1. **Migration Chain Divergence**: The chain branched at `20260406_0004`.
2. **Broken Dependency**: `20260406_0001_add_wbs_nodes_table.py` had a hardcoded string dependency.
3. **RLS Policy Coverage**: ✅ 100% coverage on all tables created via migrations.

#### Resolution:
- `down_revision` in `20260406_0001_add_wbs_nodes_table.py` updated to `"20260407_0002"`. Single linear chain confirmed.

---
