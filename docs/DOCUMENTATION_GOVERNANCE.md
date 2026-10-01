# C2Pro Documentation Governance

**Status:** Canonical  
**Effective:** 2026-10-01  
**Owner:** Repository maintainers / Master Reconciler  
**Tracking:** #771

This document defines which repository artifacts may be treated as current authority. Its purpose is to prevent architecture, product status, agent execution state and historical evidence from silently contradicting one another.

## 1. Authority hierarchy

Different questions have different sources of truth.

| Question | Canonical authority | Notes |
| --- | --- | --- |
| What code is landed? | Git `main`, merged PRs and commit history | A plan/backlog never proves implementation. |
| Did a gate pass? | GitHub checks and retained evidence for the exact SHA | Historical green does not qualify a newer SHA. |
| What is the product lifecycle/status? | `validation/product/c2pro-master-product-control-v1.yaml` | Human projection: `docs/product/00-c2pro-master-product-control-v1.md`. |
| What work may execute now? | `.c2pro/control/` + assigned `.c2pro/work/` envelope | Single-Writer Control Plane. |
| What is the current platform architecture? | Current platform TDD + **Accepted** ADRs | ADRs own their specific decisions. |
| What is proposed but not yet accepted? | Specs/plans/issues explicitly marked Proposed/In-flight | Proposal is not architecture fact. |
| What happened historically? | Git history, archive, dated audits/evidence | History is not silently refreshed. |

## 2. Document classes

- **Canonical** — current authority for its declared concern.
- **Supporting** — explanation derived from canonical sources; cannot override them.
- **Proposed / In-flight** — design or plan not yet accepted/landed.
- **Snapshot** — point-in-time reconciliation; date and bound SHA matter.
- **Historical / Superseded** — retained for traceability, not current decisions.

If status is not obvious from location, state it near the top.

## 3. Architecture precedence

For architecture questions:

1. Accepted ADR covering the decision.
2. Current platform TDD for system-wide composition.
3. Current code/migrations/tests as implementation evidence.
4. Supporting diagrams/runbooks.

A code/ADR contradiction is **architecture drift**. Do not rewrite an ADR merely to make the contradiction disappear; reconcile the decision explicitly.

Current canonical platform design:
- `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md`
- `docs/architecture/decisions/README.md`

## 4. Product-control boundary

Git merge, CI success, deployment and production validation are separate states.

Never infer:
- merged ⇒ deployed;
- deployed ⇒ production-qualified;
- tests exist ⇒ acceptance passed;
- issue closed ⇒ lifecycle promoted.

Product status changes through Product Control reconciliation, not explanatory Markdown.

## 5. Development-control boundary

The repository operates a **dual-read / single-write-new-control** model:

- `.c2pro/control/` is authoritative development control;
- assigned `.c2pro/work/<work_id>.yaml` envelopes define worker scope;
- `C2PRO_MASTER_BACKLOG.md`, `backlogs/*.md` and `blackboard.json` are legacy/cold references for ordinary workers;
- workers return structured `c2pro-implementation-result-v1` evidence;
- the Planner/Master Reconciler is the single writer that reconciles accepted evidence into canonical control state.

Historical changelog entries describing the former backlog/blackboard model remain valid as history.

## 6. ADR policy

Use a new ADR when a durable technical decision changes system invariants, authority, trust boundaries, persistence/orchestration semantics or cross-cutting platform structure.

Lifecycle:
- **Proposed**
- **Accepted**
- **Superseded**
- **Rejected**

Implementation status and ADR status are different. An Accepted ADR may be partially realized; a detailed implementation plan is not automatically an Accepted ADR.

## 7. History and archive policy

- `docs/archive/`, dated audits and old completion reports remain historical evidence.
- Superseded canonical documents get a clear notice and remain in Git.
- Old diagrams may remain when explicitly labelled non-canonical.
- Git history is the final record of what a document said at a point in time.

## 8. Change discipline

Material documentation changes should:

1. use a branch/PR;
2. identify the authority they derive from;
3. avoid lifecycle promotion unless the corresponding control process authorizes it;
4. update indexes when canonical paths change;
5. add/supersede an ADR when a durable architecture decision changes;
6. preserve exact issue/PR/SHA/gate references where material;
7. record unresolved contradictions as residuals instead of inventing resolutions.

## 9. Known legal-metadata residual

As of this reconciliation, the repository is public, `package.json` declares `ISC`, no standalone `LICENSE` file exists, and historical README text used different licensing language.

This pass does **not** decide licensing. No documentation should infer redistribution rights until maintainers publish canonical license terms.
