# C2Pro Documentation Authority and Lifecycle

**Status:** Canonical documentation-governance policy  
**Effective:** 2026-10-01

C2Pro has accumulated design documents, execution plans, audit reports and historical snapshots across multiple development eras. Professional documentation requires that readers can tell **what is authoritative now**, **what is historical**, and **what proves implementation**.

## 1. Source-of-truth hierarchy

When two artifacts disagree, interpret them in this order.

### Product programme state

1. `validation/product/c2pro-master-product-control-v1.yaml` — machine source of truth.
2. `docs/product/00-c2pro-master-product-control-v1.md` — human projection guarded for parity.

### Architecture

1. Accepted ADRs in `docs/architecture/decisions/`.
2. `docs/architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md` — current-state architecture synthesis.
3. Focused current specifications/runbooks.
4. Older platform TDDs as supporting/historical design context.

### Development execution

1. `.c2pro/control/current.yaml`
2. `.c2pro/control/work-queue.yaml`
3. work envelopes under `.c2pro/work/`
4. `validation/development/` machine controls
5. human development-control documentation

### Implementation evidence

1. merged code and migrations;
2. exact-head CI/security/test evidence;
3. deployment-provider observation;
4. explicit production qualification evidence.

Implementation evidence proves **realization**. It does not silently amend an ADR or promote Product Control.

## 2. Lifecycle labels

Every durable architecture/status document should be understandable as one of:

- **Canonical** — current authority for its subject.
- **Supporting** — useful detail subordinate to a canonical source.
- **Snapshot** — accurate for a stated date/SHA but not live authority.
- **Historical** — retained for traceability; must not drive current decisions.
- **Deprecated pointer** — kept only because older links still reference it.

Avoid the word **Current** without a date, SHA or authority pointer.

## 3. ADR policy

An ADR records a durable architectural decision, not every implementation change.

Create or amend an ADR when a change alters:

- aggregate/state authority;
- trust/approval boundaries;
- concurrency/consistency guarantees;
- cross-module ownership;
- persistent data semantics;
- deployment/qualification authority;
- non-trivial security invariants.

Do **not** create ADRs for ordinary dependency upgrades, localized refactors, CI tuning or operational fixes unless they establish a durable architectural policy.

If implementation intentionally contradicts an accepted ADR, the ADR must be amended, deprecated or superseded explicitly.

## 4. Status-document policy

Do not maintain multiple live status registers.

- Product status belongs in Product Control.
- Development execution belongs in the `.c2pro` control plane.
- GitHub issues/PRs contain work evidence, not the canonical product state by themselves.
- Dated reports belong under audits/archive when they cease to drive decisions.

## 5. Historical plans and TDDs

A historical plan may describe technology or sequencing that no longer exists. It remains valuable as decision history, but readers must not infer current implementation from it.

Current indexes must label older TDDs/roadmaps as supporting or historical if they have been superseded.

## 6. Documentation change discipline

A material code change should answer:

1. Did this change alter an accepted architecture decision?
2. Did it change the current runtime topology?
3. Did it change a security/trust boundary?
4. Did it change production qualification/deployment semantics?
5. Did it change the Product Control state?

If yes, update the corresponding canonical artifact in the same workstream or create a bounded follow-up.

## 7. No self-certification

Documentation may summarize evidence, but it cannot upgrade an unvalidated capability to `PROD_VALIDATED`.

A claim such as “production ready”, “complete”, “operational”, “deployed” or “validated” must use the vocabulary and evidence contract of the owning control plane.

## 8. Review cadence

Review canonical indexes and architecture status:

- after a major architecture/workstream closure;
- before a release candidate;
- after a production-qualification milestone;
- whenever a canonical source is found to contradict `main`.

This reconciliation policy exists to prevent documentation drift from becoming architecture drift.
