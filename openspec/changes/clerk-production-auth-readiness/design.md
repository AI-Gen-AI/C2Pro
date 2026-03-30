# Design: Clerk Production Authentication Readiness

## Technical Approach

Use a docs-first spec-driven change to define the operational contract for production Clerk authentication. The change does not alter application runtime behavior. It formalizes how operators move from development/test Clerk usage to production/live usage and how they prove completion for `TASK-1174` through `TASK-1179`.

The executable runbook will become the operator-facing implementation of this change. The OpenSpec artifacts provide the stable requirements, rationale, sequencing, and evidence model that the runbook must follow.

## Architecture Decisions

| Option | Tradeoff | Decision |
| ------ | -------- | -------- |
| Keep explanatory guide vs replace with executable runbook | Explanatory guide is easier to read but weak for closure evidence | Replace with executable runbook |
| Treat repo wiring as task completion vs require external evidence | Repo-only status is simpler but misleading for production auth | Require external evidence for Clerk, Vercel, and Railway |
| One aggregate task only vs explicit subtask closure matrix | Single task is shorter but hides blockers | Keep aggregate `TASK-1174` with explicit dependency checks `1175-1179` |

Rationale: The current guide correctly explains the difference between demo mode and Clerk environment, but it does not provide the operator contract needed to close the backlog tasks. A spec + runbook pairing removes ambiguity.

## Data Flow

```text
Operator -> Runbook preflight
           -> Clerk production configuration
           -> Vercel production environment configuration
           -> Railway production environment configuration
           -> Deploy backend
           -> Deploy frontend
           -> Execute smoke tests
           -> Capture evidence
           -> Mark TASK-1175..1179 done
           -> Mark TASK-1174 done
```

Sequence (cross-system flow):

```text
Operator        Runbook        Clerk Prod        Vercel Prod        Railway Prod        C2Pro Frontend/API
   |               |                |                 |                  |                    |
   | preflight     |                |                 |                  |                    |
   |-------------->| check matrix   |                 |                  |                    |
   | configure     |--------------->| live keys       |                  |                    |
   | set env vars  |--------------------------------->| publishable key  |                    |
   | set env vars  |---------------------------------------------------->| issuer/jwks/secret |
   | deploy back   |---------------------------------------------------->| deploy API         |
   | deploy front  |--------------------------------->| deploy web       |                    |
   | smoke tests   |--------------------------------------------------------------->| sign-in/up/reset |
   | evidence      | collect URLs, screenshots, logs, headers, health results      |                    |
```

## File Changes

| File | Action | Description |
| ---- | ------ | ----------- |
| `openspec/changes/clerk-production-auth-readiness/proposal.md` | Create | Intent, scope, risks, rollback, success criteria |
| `openspec/changes/clerk-production-auth-readiness/design.md` | Create | Operational flow, architecture decisions, evidence model |
| `openspec/changes/clerk-production-auth-readiness/tasks.md` | Create | Phased task checklist for runbook rewrite and verification |
| `openspec/changes/clerk-production-auth-readiness/specs/auth-production/spec.md` | Create | Requirements and scenarios for production auth readiness |
| `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` | Modify | Rewrite as executable runbook with validation and closure evidence |

## Interfaces / Contracts

Environment contract:

| System | Required Values |
| ------ | --------------- |
| Clerk | Production project, live publishable key, live secret key, production domain, verified sender |
| Vercel | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, production API routing vars, no demo mode in production |
| Railway | `CLERK_SECRET_KEY`, `CLERK_ISSUER`, `CLERK_JWKS_URL`, database and backend runtime vars |

Evidence contract:

| Task | Required Evidence |
| ---- | ----------------- |
| `TASK-1175` | Screenshot or operator note proving `pk_live_...` and `sk_live_...` are provisioned in secret stores |
| `TASK-1176` | Clerk dashboard screenshot or operator note showing production domain and redirect URLs |
| `TASK-1177` | Email screenshots proving non-`accounts.dev` sender and no `[Development]` subject |
| `TASK-1178` | Successful frontend production deploy and live `/sign-in` + `/sign-up` check |
| `TASK-1179` | Successful backend health check and authenticated frontend-to-backend request |
| `TASK-1174` | Consolidated checklist showing all dependent tasks complete |

## Testing Strategy

| Layer | What to Verify | Approach |
| ----- | -------------- | -------- |
| Static | Runbook contains complete task mapping, env matrix, and evidence | Manual review against spec requirements |
| Operational | Production sign-in/sign-up/reset and authenticated API request | Manual smoke tests against deployed systems |
| Traceability | Each backlog task maps to one or more explicit validation steps | Runbook checklist review |

## Migration / Rollout

No data migration is required.

Rollout steps:

1. Land OpenSpec artifacts for Clerk production auth readiness.
2. Rewrite `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` to match the new contract.
3. Use the runbook as the canonical execution guide for `TASK-1174` through `TASK-1179`.
4. Capture operator evidence when the production auth rollout is executed.

## Reviewer Usage Notes

Reviewer checklist:

1. Confirm `proposal.md`, `design.md`, `tasks.md`, and `specs/auth-production/spec.md` exist under `openspec/changes/clerk-production-auth-readiness/`.
2. Confirm the runbook has preflight checks, environment matrix, ordered task execution, smoke tests, closure evidence, and rollback guidance.
3. Confirm the runbook does not present repo wiring as proof of production completion.
4. Confirm secret-handling guidance explicitly forbids committing live credentials.

## Open Questions

- [ ] Should the runbook require a staging validation pass before production closure?
- [ ] Should production auth closure require a dedicated evidence file under `evidence/releases/`?
