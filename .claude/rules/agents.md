# Agent Orchestration — Claude Adapter

> **Status:** ACTIVE adapter  
> **Canonical development authority:** `.c2pro/control/` + assigned `.c2pro/work/` envelope  
> **Last reconciled:** 2026-10-01

This file contains Claude-facing guidance only. It must not define an independent roster, backlog, routing table or merge policy.

## Canonical sources

Read the applicable machine control before dispatching development work:

- `.c2pro/control/current.yaml`
- `.c2pro/control/routing.yaml`
- `.c2pro/control/review-policy.yaml`
- `.c2pro/control/workspace-policy.yaml`
- assigned `.c2pro/work/<work_id>.yaml`

Legacy `C2PRO_MASTER_BACKLOG.md`, `backlogs/*.md` and `blackboard.json` are read-only/cold reconciliation sources and are not normal bootstrap context.

## Role / worker separation

The canonical routing policy currently distinguishes:

- **role** — required function for the work;
- **worker** — execution identity;
- **surface/harness** — how the worker is invoked;
- **model/provider** — replaceable route/runtime identity.

Do not hard-code a model as permanent owner of a role in this file.

Current routing policy, not this prose, determines eligible workers and preferences.

## Review independence

Follow `.c2pro/control/review-policy.yaml`.

Key invariants:

- material self-approval is forbidden;
- when independent principal review is required, implementation worker and reviewer differ;
- subordinate results cannot satisfy a required principal-review gate;
- architecture/security/high-blast-radius work requires the stronger review policy defined in machine control;
- unresolved material disagreement escalates according to control policy.

## Workspace safety

Follow `.c2pro/control/workspace-policy.yaml`.

Workers may validate the assigned workspace but must not independently create, remove, reset, clean or repurpose controlled workspaces unless the canonical policy/work envelope grants that authority.

On mismatch: fail closed with the configured workspace-guard behavior.

## Execution lifecycle

1. Validate work ID, base SHA, branch/workspace and effective authority.
2. Load only the context needed by the bounded work envelope.
3. Execute the assigned role inside scope/out-of-scope boundaries.
4. Run required tests/checks.
5. Return structured `c2pro-implementation-result-v1` evidence.
6. Obtain the independent review/challenger required by risk class.
7. Let the Planner/Master reconciler update canonical development state only after required evidence/CI/merge.

## Parallel execution

Parallelize only work that:

- has independent write surfaces/workspaces;
- does not violate dependency ordering;
- does not create conflicting ownership of the same canonical file/contract;
- preserves independent review requirements.

Do not parallelize merely to maximize model count.

## Documentation

Follow `DOCUMENTATION_STRUCTURE.md`.

- Durable architecture decision → ADR.
- Platform-wide design change → current TDD.
- Operator procedure → runbook.
- Product lifecycle → Product Control YAML-first flow.
- Development task/control state → `.c2pro`.
- Temporary analysis → non-canonical working context/PR discussion.

Never create a second task/status authority in Claude-specific files.

## Historical agent files

Other role/agent definitions may remain for compatibility/tool integration. They are subordinate to the canonical `.c2pro` routing/review/workspace policies whenever they disagree.
