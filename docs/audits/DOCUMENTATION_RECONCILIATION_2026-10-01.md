# Documentation Reconciliation Audit — 2026-10-01

**Repository:** AI-Gen-AI/C2Pro  
**Baseline main SHA:** `33650a28a930d82a7bd65d98b50981145b3fd1d1`  
**Scope:** canonical documentation, architecture decisions, product/development status pointers, runtime/deployment documentation and root navigation

## Executive finding

The repository contained strong technical evidence but material documentation drift. The main risk was **not missing prose**; it was multiple older documents still presenting themselves as current while the implementation and governance model had evolved substantially.

### Highest-impact inconsistencies found

1. Root `README.md` still described “Sprint S2 65%”, Next.js 14/React 18-era architecture and Supabase Auth while the current frontend uses Next.js 16.3.6, React 19.2.7 and Clerk.
2. `docs/ARCHITECTURE_INDEX.md` was last updated in March and elevated older v4.1/v4.0 TDDs without the later ADR-013→025 product-intelligence spine.
3. `docs/DECISION_LOG.md` maintained a second ADR numbering/catalogue independent from `docs/architecture/decisions/`, creating authority ambiguity.
4. Product Control was still reconciled against 2026-09-27-era `main` and described #714/#715 as incomplete/unimplemented even though their implementation PRs have since merged. Importantly, that does **not** mean #715 production qualification has passed.
5. #714/#758 introduced durable trust/concurrency architecture that was implemented but not yet represented as dedicated ADRs.
6. Production is composite (Railway API/Worker/Scheduler + Vercel frontend), while older status language still encouraged a singleton-runtime mental model.
7. The CI/CD runbook correctly documented the 2026-10-01 Vercel gating change but still contained an obsolete “currently unprotected” branch-protection instruction.
8. The repository contains hundreds of useful historical Markdown artifacts. Without an authority policy, search results can surface snapshots as if they were live canon.

## Reconciliation actions

### Authority

- Added `docs/DOCUMENTATION_AUTHORITY.md`.
- Deprecated `docs/DECISION_LOG.md` as an independent ADR source and redirected it to the canonical ADR directory.
- Rebuilt architecture/documentation indexes around explicit authority order.

### Architecture

- Added `docs/architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md`.
- Added ADR-026: Trusted-State Commit Boundary.
- Added ADR-027: Processing Authority and Checkpoint-Lineage Fencing.
- Added ADR-028: Production Qualification / Composite Runtime Identity.
- Preserved earlier TDDs as supporting historical design documents rather than deleting them.

### Product status

- Reconciled Product Control baseline to current `main` without promoting any capability to `PROD_VALIDATED`.
- Recorded that #714 implementation and #715 harness implementation are merged.
- Preserved the decisive non-claim: #706, #715 and #690 remain open; #712/#713 remain fix-forward workstreams.

### Operations

- Corrected current branch-protection documentation.
- Preserved Vercel automatic deployment allowlist and preview policy as an operational policy, not an architecture ADR.

### Repository navigation

- Rewrote root README status/stack/navigation to point readers to canonical control planes instead of a stale sprint percentage.
- Updated documentation and architecture indexes.

## Decisions deliberately not taken

- Did not declare #706 complete.
- Did not mark the production synthetic journey as passed merely because the harness is merged.
- Did not collapse frontend/backend production identity into one SHA.
- Did not rewrite every historical report; archival provenance is valuable.
- Did not convert operational Vercel quota/gating work into an ADR.
- Did not promote P0b/P0c/P0d lifecycle state without accepted production evidence.

## Residual documentation debt

The repository still contains a large historical surface. The following are lower priority and should be handled incrementally:

- old wireframe implementation reports;
- dated audit/planning snapshots that can be moved deeper into archive;
- component-level README files whose version examples may drift;
- duplicated “architecture plan” materials already classified as legacy;
- old backlog category files retained for historical compatibility.

These should be cleaned only when there is a clear duplicate/authority problem. Bulk deletion would reduce traceability and is not recommended.

## Acceptance criteria for this reconciliation

- one explicit product-status authority;
- one explicit ADR catalogue;
- one current architecture baseline;
- root README no longer makes stale sprint/stack claims;
- current product non-claims preserved;
- implementation-era trust/fencing/qualification decisions are documented;
- CI/documentation gates pass on the reconciliation PR.


## Adversarial review findings

A second pass treated the reconciliation PR as an external architecture/governance review rather than a formatting exercise.

### P2 findings from independent Codex review

1. **Live agent-instruction contradiction:** `.claude/rules/DOCUMENTATION_STRUCTURE.md` had been modernized while `CLAUDE.md` still instructed workers to treat legacy backlogs as the task source of truth.
   - **Disposition:** fixed. `CLAUDE.md`, `agents.md`, the documentation agent and the C2Pro patterns skill now route current execution through the single-writer `.c2pro/` control plane.

2. **Historical snapshot mutation:** the 2026-09-27 Product-Control reconciliation conclusion had been overwritten with 2026-10-01 facts.
   - **Disposition:** fixed. The 2026-09-27 block is restored as immutable historical truth; later facts live only in `reconciliation_delta_2026_10_01`.

3. **Unregistered ADR lifecycle:** ADR-026..028 existed in the human catalogue but were absent from Product Control and parity enforcement.
   - **Disposition:** fixed. Machine lifecycle rows, Markdown projection, parity extraction and negative drift tests now cover ADR-026, ADR-027 and ADR-028.

### Additional adversarial findings

- **Stale authorized sequence:** Product Control still told operators to complete #711/#714 before #715 even though those workstreams had already closed.
  - Fixed to route current work through #690 + open #712/#713, then execute #715.

- **Historical material still presenting itself as current:** v4.0/v4.1 TDDs, the planning index and the legacy orchestration guide retained current/canonical language.
  - Reclassified explicitly; current authority now points to the dated technical baseline, ADR catalogue and owning control planes.

- **Legacy decision-log traceability:** replacing the duplicate decision log with a pointer removed authority but made historical content less discoverable.
  - The original log is now preserved under `docs/archive/architecture/decisions/` and linked from the compatibility pointer.

- **Storage proof overstatement:** repository code proves a configured R2-compatible storage path and shared HTTP/worker storage factory, but this documentation reconciliation did not independently observe the current production storage provider.
  - Current baseline wording now distinguishes implemented/configured object storage from runtime provider qualification.

- **WBS design vs realization:** “one project → one canonical WBS” is a binding architecture invariant, while complete one-root enforcement remains PARTIAL.
  - Current baseline/README now state both facts together.

- **Retrospective ADR provenance:** ADR-026..028 codify decisions already accepted through issue/PR contracts.
  - Each ADR now states that it is retrospective codification and creates no new runtime authority.

- **Aggregate status ambiguity:** associating ADR-027/028 directly with a Product-WBS row already marked DEPLOYED could be read as a deployment claim.
  - Removed that aggregate implication; per-ADR lifecycle rows remain authoritative.

### Second adversarial round

A later Codex pass on the expanded reconciliation found five additional material points:

1. **P1 — trust guarantee was too broad.** Runtime policy can auto-approve a non-gated high-confidence LOW/MEDIUM-impact item and persist it as trusted without human action.
   - Fixed by scoping ADR-026 and the technical baseline to **HITL-gated candidates**.
   - Product Control now records the remaining ADR-020 policy-realization gap: current routing is confidence/impact based and does not yet encode all named consequential decision classes from the ADR.

2. **P1 — residual legacy writes in `agents.md`.** A later completion section still told workers to update the legacy master backlog.
   - Fixed. Suite/task completion now returns structured evidence to the single-writer control plane; legacy tracking mutation instructions were removed.

3. **P2 — design status was not parity-guarded.**
   - Fixed for ADR-018, ADR-024, ADR-025 and ADR-026..028. The canonical block now includes design + realization + deployment + production-validation state; negative drift tests cover design status.

4. **P2 — architecture precedence mixed product status with design authority.**
   - Fixed. Accepted ADRs govern architecture/design questions; Product Control governs lifecycle/readiness questions; `.c2pro` governs execution.

5. **P2 — the v4.0 historical snapshot had been rewritten instead of merely superseded.**
   - Fixed. The March document content is restored verbatim beneath a 2026-10-01 historical/supersession banner.

The requested final automated Codex re-review could not run because the repository's Codex review quota was exhausted. This is recorded explicitly; it is **not** treated as an implicit PASS. Final acceptance therefore requires exact-head automated guards plus manual reconciliation of every raised thread.

## Review conclusion

The reconciliation is acceptable only if the **exact final head** passes Product-Control parity/tests, CI, secret/install/dependency/security gates and the final adversarial review has no unresolved material finding. Earlier green heads are not sufficient evidence for later documentation commits.


### Third adversarial round — moving-base reconciliation

During final review, `main` advanced after the original documentation baseline. PR #781 merged backend support for Clerk v2 organization claims, moving `main` from `a025982e...` to `33650a28a930d82a7bd65d98b50981145b3fd1d1`.

**Disposition:** the documentation branch was merged forward to the new `main`, the architecture/product-control baseline was rebound to the new SHA, and the auth baseline now records the supported Clerk v2 organization-claim path. This prevents #780 from merging with a baseline that was already stale.
