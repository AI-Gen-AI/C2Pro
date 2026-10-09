# C2PRO-DEV-14 — Task-first traceability and execution authority (SDD v1)

**Date:** 2026-10-09
**State:** owner-approved design objective; implementation/CI gate NOT YET ACTIVE.
**Tracking issue:** #991 (DEV-14; created without a duplicate Product Task).
**Canonical parent:** C2PRO-DEV-14, the existing Product work-envelope extension in .c2pro/control/work-queue.yaml and the VPS Development Control Plan, section 12. Product programme reference: PQ-HITL #936 and its 28 atomic subpackages, owned by validation/product/c2pro-master-product-control-v1.yaml. This SDD does not add a Product WBS or create a second source of task status.

## 1. Observable goal and authority

The question is WHICH PRODUCT CAPABILITY is delivered with WHAT acceptance evidence, not how many pull requests merged. A pull request is a receipt, never the authority to start work, declare a task ACCEPTED, perform HITL review or promote PROD_VALIDATED.

Ownership is strict: Product machine MASTER owns task ID, priority, dependency, parent issue, acceptance and Product lifecycle; .c2pro current/queue/envelopes owns principal worker execution and workspace; SDD owns behavior/tests; PR/CI is implementation evidence; owner/independent Product Control reconciles final acceptance. The role is separate from model identity.

**Identity:** Product Task examples PQ-HITL-09.1 (issue #945), PQ-HITL-04.6 (issue #940); the existing execution debt C2PRO-DEV-14 is an independent DEV namespace, not a substitute Product Task. Defect DEF-PQ-006 belongs to PQ-HITL-04.6 and is never the only primary Task. Future Product WORK IDs must have collision-free IDs in a revised machine-valid .c2pro schema; the current schema only accepts C2PRO-DEV-NN.

**Cardinality:** 1 Task → N bounded PRs valid; 1 PR → N Tasks only exceptionally, with separable scope and evidence; no PR without a canonical primary Task; merge ≠ ACCEPTED ≠ DEPLOYED ≠ PROD_VALIDATED. Product issues #937–#946 remain parents; avoid opening 28 duplicative issues just to force a one-to-one relationship.

## 2. Proposed pull-request trace contract

Every new governed PR must declare a machine-readable metadata section, with exactly one primary Task, and optionally related Tasks only when acceptance is independently demonstrated:

~~~yaml
c2pro_trace:
  schema: c2pro-pr-task-trace-v1
  primary_task: PQ-HITL-09.1
  related_tasks: []
  parent_issue: 945
  sdd_path: docs/product/pq-hitl-09-1-golden-fixtures-sdd-v1.md
  acceptance_ids:
    - TS-PQ-HITL-09-GOLDEN-001
  execution_work_id: "<REAL_ASSIGNED_WORK_ID>"
  work_envelope_path: "<EXISTING_VALID_WORK_ENVELOPE>"
  workspace_evidence_ref: "<VALIDATED_WORKSPACE_RECEIPT>"
  defects: []
  effect_claim: IMPLEMENTATION_ONLY
~~~

This is an illustrative schema, NOT a valid authority receipt or evidence of a Product WORK envelope for 09.1. Do not copy placeholders as real values. Allowed effect claims: SPEC_ONLY, IMPLEMENTATION_ONLY, PRODUCT_ACCEPTANCE_PROPOSED. PROD_VALIDATED, TRUSTED and production actions are not permitted claims. Runtime implementation additionally requires the authentic .c2pro work envelope, appropriate principal/role, allowed scope, branch and base SHA, registered workspace guard and security authorization; issue/PR metadata alone is never enough.

**Effect claims are never self-authorizing.** The read-only trace validator MUST derive changed paths from the immutable PR base/head diff and compare them to a trusted, versioned effect-class policy loaded from the approved base, never from authority fields added by the PR under review. SPEC_ONLY is default-deny and may touch only documentation paths explicitly allowed by that prior policy. Newly created SDD files may qualify **only if their exact destination and canonical DEV task are registered in independently approved pre-PR authority**; a PR cannot add that allowance for itself. Edits to Python/TypeScript, executable tests, GitHub workflows, schemas, Product MASTER YAML, machine-control state, permissions, runtime or secrets always fail SPEC_ONLY. Unknown, unapproved new/renamed paths and symlinks fail closed after safe normalization. Missing WORK receipts never permit implementation or execution claims. **DEV-14.1 bootstrap:** this design-only PR predates deployment of the proposed trace check, so it is assessed under existing checks and independent review, not falsely marked trace-PASS; it must contain only the proposed SDD plus already existing development-plan documentation. Any Product MASTER change requires its own independently authorized Product Control scope.

Human PR body must succinctly state WHAT user outcome changed, acceptance criterion, WHAT RED test failed then GREEN proof, affected paths, unresolved defects, exact-head CI and independent review, non-goals and next Task. Missing evidence is marked PENDING, never invented.

**Acceptance-ID source of truth (prerequisite to DEV-14.3 ENFORCE):** Current Product MASTER acceptance descriptions are free-form text; a sample `TS-*` fixture name is not a canonical acceptance identifier. DEV-14.2 must specify a versioned, Product-Control-approved acceptance registry or immutable SDD acceptance mapping keyed by canonical Task ID, with exact source path, content hash/revision and criteria. The validator must resolve every claimed ID from that approved base and reject unknown/unversioned claims; never derive authority from an implementation fixture, arbitrary PR body string or SDD newly introduced by the same PR. Until an independently accepted registry exists, `acceptance_ids` is a proposal/diagnostic field only and mandatory-ID enforcement remains disabled. The example above is schematic and MUST NOT be treated as an enrolled Product acceptance ID.

## 3. Validator and GitHub CI architecture

**DEV-14.1 — specify:** this SDD, staged gate design, review. Documentation only.

**DEV-14.2 — extend work namespace:** integrate Product WORK identity into existing .c2pro schemas, queue validator, assignment and workspace authorization without reusing C2PRO-DEV IDs. Must have RED negative tests for unknown Product IDs, wrong parent/campaign, branch/base mismatch, no active WORK, role mismatch and forbidden paths. No fake hot-state activation.

**DEV-14.3 — deterministic PR validator:** parse one bounded YAML metadata section without code execution; prohibit duplicate YAML keys/blocks, unknown keys, unrelated IDs, oversized bodies and injection; validate primary task in machine MASTER (or canonical development queue for development-only tasks), parent issue, SDD existence, acceptance IDs, status and dependencies. A BLOCKED task can support explicitly authorized discovery/spec ONLY, not implementation. For execution require actual assigned WORK and exact workspace/branch/base. Changed-file scope must fit envelope; a PR with two tasks must pass both mappings separately. A merged PR cannot directly set ACCEPTED and no CI job can set PROD_VALIDATED.

**DEV-14.4 — roll out:** pinned, read-only GitHub Action using pull_request event and contents/pull-requests read permission, independent negative tests, no pull_request_target with untrusted checkout, no shell interpolation of PR text, no credentials, and explicit phased AUDIT → ENFORCE policy. Audit existing PRs without blocking unrelated historical work. ENFORCE new PRs only AFTER a real Product WORK assignment route and migration path are verified; avoid adding an unconditionally required job before this capability exists. No weakening of existing CI, security, Product Control guards or human merge policy.

**Bootstrap constraint:** Before the *new PR traceability check* exists, a tightly identified DEV-14 implementation PR may be exempt **only from that not-yet-deployed check** and only after the owner and orchestrator record the exact exemption and expiration. This is NOT an exception to any existing .c2pro WORK/envelope, registered workspace, branch/base-SHA guard, security policy, TDD, CI, independent review, human merge, Product Control or production boundary. If those existing preconditions are absent, execution stays EXECUTION_BLOCKED_WORK_ENVELOPE and no bootstrap implementation may begin. The new check cannot validate its own authorization from changes within its own PR; validate against the effective approved base.

## 4. SDD acceptance scenarios

| ID | Given / When | Then |
|---|---|---|
| TRACE-01 | Valid Product task, issue, SDD, acceptance ID and assigned WORK | Trace PASS, NOT automatically task ACCEPTED |
| TRACE-02 | Unknown or forged PQ-HITL-99.9 | REJECT unknown Task |
| TRACE-03 | Valid Task ID but incorrect parent issue | REJECT issue mismatch |
| TRACE-04 | DEF-PQ-006 alone as primary Task | REJECT; require parent PQ-HITL-04.6 |
| TRACE-05 | One Task delivered through 3 bounded PRs | Each independently traceable; task still open until aggregate acceptance |
| TRACE-06 | One PR claims two Tasks | Require separate acceptance ID and real authority for both |
| TRACE-07 | Task/issue present but no valid WORK or no workspace evidence | EXECUTION_BLOCKED_WORK_ENVELOPE, no false PASS |
| TRACE-08 | Implementation while prerequisite Task not ACCEPTED | REJECT dependency violation |
| TRACE-09 | Forbidden path, wrong branch or stale base SHA | WORKSPACE_GUARD_FAILURE / REJECT |
| TRACE-10 | Duplicate keys, second trace block, arbitrary code in PR metadata | REJECT safely without executing text |
| TRACE-11 | PR merged, Task still has missing acceptance | Keep MERGED_UNACCEPTED, not ACCEPTED |
| TRACE-12 | Task ACCEPTED but product not qualified in production | Never claim PROD_VALIDATED |
| TRACE-13 | Missing independent review or reviewer implemented same material change | Block promotion even if CI green |
| TRACE-14 | Head SHA changed after verification | Rerun exact-head gates |
| TRACE-15 | Spec-only PR with missing work receipt | May document an execution BLOCKER, never claim it executed Product WORK |
| TRACE-16 | Existing merged PR lacking trace metadata during AUDIT mode | Diagnostic only; no rewrite of history |
| TRACE-17 | SPEC_ONLY claim with a code, test, workflow, schema or non-allowlisted changed path | REJECT despite declared effect and absent work receipt |
| TRACE-18 | PR modifies its own Task/SDD/WORK authority to satisfy its guard | REJECT against approved pre-PR authority; separate governance approval required |
| TRACE-19 | Bootstrap exemption claimed to skip existing WORK, branch, CI or review guards | REJECT; only not-yet-existing trace check may be exempt |

**Test-first:** failing negative tests before new CI code; focused Python pytest with pinned PyYAML, existing .c2pro control validator and Product-Control Guard remain green, then independent principal review. Separate high-blast-radius/security review if the trace changes authority or bypass semantics.

## 5. Entry and exit

**Entry:** authorized programme objective; Product tasks exist in MASTER; DEV-14 registered; but current.yaml is reconciled_idle and no Product WORK capability is active. A ready queue entry without assigned principal + validated workspace is not permission to start execution.

**Exit:** actual DEV-14.2–.4 implementation tested and independently reviewed on exact-head CI; real Product WORK envelope schema validated with registered workspace and explicit worker selection; per-PR trace check deployed and enabled under approved branch protection; receipt linkage demonstrably works for a subsequent Product Task; Product MASTER status reconciled separately. Do not mark exit from writing a template or SDD.

**Non-goals:** no new ninth Product WBS, no rewriting old PRs, no deployment, no production review B, no changes to HITL trust, database roles, tenant permissions, credential access or release authority. Never modify legacy blackboard or backlogs. All work must preserve the canonical .c2pro control plane.
