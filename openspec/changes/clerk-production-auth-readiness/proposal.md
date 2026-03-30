# Proposal: Clerk Production Authentication Readiness

## Intent

Define a spec-driven, evidence-backed workflow for closing `TASK-1174` and its dependent production-auth tasks (`TASK-1175` through `TASK-1179`). The change turns the existing guidance into an executable runbook with clear environment contracts, validation steps, and closure evidence.

## Scope

### In Scope

- Define production Clerk authentication readiness requirements for C2Pro.
- Specify the environment-variable contract across Clerk, Vercel, and Railway.
- Define the exact verification evidence required to close `TASK-1174` through `TASK-1179`.
- Rewrite `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` as an executable production runbook.

### Out of Scope

- Creating or modifying live Clerk dashboard settings.
- Writing production deployment automation code beyond existing workflows.
- Rotating or removing already exposed secrets from repository history.

## Approach

Add a dedicated OpenSpec change for production Clerk readiness and use it to drive a runbook rewrite. The runbook will shift from explanatory guidance to an operator procedure with preflight checks, environment matrices, ordered execution steps, smoke tests, evidence capture, and rollback guidance.

## Affected Areas

| Area | Impact | Description |
| ---- | ------ | ----------- |
| `openspec/changes/clerk-production-auth-readiness/proposal.md` | New | Defines scope, success criteria, and rollback boundaries |
| `openspec/changes/clerk-production-auth-readiness/design.md` | New | Describes operational flow, decisions, and evidence model |
| `openspec/changes/clerk-production-auth-readiness/tasks.md` | New | Phased implementation and verification checklist |
| `openspec/changes/clerk-production-auth-readiness/specs/auth-production/spec.md` | New | Codifies production auth readiness requirements and scenarios |
| `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` | Modify | Rewritten as executable runbook for `TASK-1174` to `TASK-1179` completion |

## Risks

| Risk | Likelihood | Mitigation |
| ---- | ---------- | ---------- |
| Operators treat explanation as completion evidence | Med | Make evidence capture and exit criteria explicit for each task |
| Production env drift across Clerk, Vercel, Railway | High | Define one canonical environment matrix and one execution order |
| Sensitive values get committed while following guide | Med | Add explicit security guardrails and secret-handling requirements |

## Rollback Plan

If the executable runbook proves inaccurate or too rigid, revert the runbook rewrite and this OpenSpec change, then restore the prior guide while keeping the audit findings as an implementation reference.

## Dependencies

- `C2PRO_MASTER_BACKLOG.md` task definitions for `TASK-1174` through `TASK-1179`
- Existing Clerk integration in `apps/web` and `apps/api`
- Existing production deployment workflows for Vercel and Railway

## Success Criteria

- [ ] A spec defines the exact requirements to close `TASK-1174` through `TASK-1179`.
- [ ] The runbook contains ordered execution steps, validation commands, and closure evidence.
- [ ] The runbook distinguishes repository readiness from external-system completion.
- [ ] The runbook states secret-handling rules and prohibits committing live credentials.
