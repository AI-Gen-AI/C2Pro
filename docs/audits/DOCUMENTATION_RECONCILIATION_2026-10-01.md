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


### Third-round live-guidance defects

The moving-base review also re-read live agent instructions instead of only the new architecture documents and found additional contradictions:

- **Live agent-governance residue:** `agents.md` still described legacy blackboard/backlog post-execution enforcement after declaring those files cold/read-only.
  - Fixed by scoping blackboard/backlog mutation/enforcement to the genuine legacy supervisor path and making `.c2pro` + structured results authoritative for modern work.
- **Unsafe direct-main pattern:** `CLAUDE.md` and `docs/skills/c2pro-patterns.md` still documented `ALLOW_PUSH_MAIN=1 git push origin main` as a normal procedure.
  - Fixed. Current guidance requires PR-based integration; the local Husky escape is explicitly not repository authority.
- **Retired CI workflow map:** the patterns skill still listed retired `tests.yml`, `frontend-ci.yml`, `deploy-staging.yml` and `deploy-production.yml` as current workflows.
  - Fixed against the current CI/runbook model.
- **Overstated result-block enforcement:** the Claude rule claimed every CI/CD path parses worker result blocks automatically.
  - Fixed. Schemas/parser/reconciler and control-plane validators are real; exact CI enforcement must be discovered per active workflow.
- **Malformed evidence example:** the worker-result YAML example had nested code fences.
  - Fixed.
- **Documentation-agent metadata drift:** its `Last Updated` marker still read 2026-02-13 despite authority changes.
  - Fixed to 2026-10-01.

Relative-link checks over the primary modified navigation/baseline documents found no broken repository links.


### Fourth adversarial round — exact-head semantic reconciliation

A later Line B review re-checked the exact PR head against both the live runtime and the authority rules introduced by this reconciliation. Three material defects were found and corrected:

1. **P1 — historical Product-Control snapshot regression.** A post-2026-09-27 fact (#781 Clerk v2 organization-claim support) had been inserted into `reconciliation_delta_2026_09_27.material_main_advances`, re-contaminating the historical snapshot.
   - **Disposition:** fixed. The 2026-09-27 block is again immutable; #781 now appears only in the 2026-10-01 reconciliation, whose `current_main_sha` is rebound to `33650a28a930d82a7bd65d98b50981145b3fd1d1`.

2. **P1 — checkpoint exactness was overstated.** ADR-026/ADR-027 and the technical baseline said HITL always resumes an exact persisted checkpoint tuple. The runtime deliberately captures `checkpoint_id` best-effort; if capture is unavailable, resume can fall back to the latest checkpoint on the same authority-scoped thread.
   - **Disposition:** fixed in documentation rather than changing runtime inside this reconciliation PR. The documented invariant is now: exact checkpoint binding when a checkpoint ID exists; otherwise thread-only fallback is confined to the same processing-attempt lineage and cannot cross an authority boundary.

3. **P2 — live CI remediation still pointed at a legacy backlog.** The CI runbook routed current advisory-suite and paused-E2E remediation into `backlogs/DEV_DEVOPS.md`, contradicting the new single-writer control-plane policy.
   - **Disposition:** fixed. The backlog is explicitly historical context; current remediation must be tracked through `.c2pro` plus the corresponding GitHub issue/PR.

The prior automated Codex reviews were anchored to earlier heads and therefore do not constitute review of the remediated exact head. Final acceptance still requires exact-head CI plus a fresh independent review after these corrections.


### Fifth adversarial round — 2026-10-03 moving-base revalidation

Before final merge, Line B re-checked the documentation branch against current `main` rather than treating the 2026-10-01 baseline as indefinitely current. `main` had advanced by 38 commits from `33650a28a930d82a7bd65d98b50981145b3fd1d1` to `314fc39b0b4c25c8c0ca99977314ba1bb9083208`.

The intervening changes were material to the documented trust/qualification surfaces:

- **#782-#787 / #715** hardened production identity observation, tenant-RLS verifier context, bounded Clerk production-preflight waits, session-first canonical-origin authentication and production sign-out selectors.
- **#790 / #789** moved SSE bearer handling behind the same-origin server proxy and rejected bearer tokens in query strings.
- **#793 / #792** fixed a trust-boundary defect: an explicit `human_approval_required=True` state now forces HIGH impact before confidence routing, so confidence cannot auto-approve a state that already requires human review.

**Disposition:**

- current `main` was merged into the documentation branch without altering historical 2026-09-27 or 2026-10-01 reconciliation deltas;
- Product Control now adds a distinct `reconciliation_delta_2026_10_03` and updates only its current reconciliation pointer;
- the human Product-Control projection is rebound to the same current SHA;
- ADR-026 and the technical baseline now record the #793 explicit-human-boundary hardening while preserving the still-valid non-gated LOW/MEDIUM policy path;
- the technical baseline remains the dated 2026-10-01 artifact but is explicitly marked revalidated on 2026-10-03 rather than silently rewriting its provenance;
- #706, #715, #690, #712 and #713 remain open; #792 is also still open pending acceptance/closure;
- no P0b/P0c/P0d lifecycle state was promoted.

This round converts the prior exact-head acceptance evidence into historical evidence only. The new exact head must independently pass Product-Control parity/guards and the repository CI/security checks before merge.


### Sixth adversarial round — exact-head Codex review after 2026-10-03 revalidation

Codex successfully reviewed exact head `ee777ea91f9c66a28dd3dc01876461d0b7467089` and raised two P2 documentation defects.

1. **Mixed architecture/lifecycle precedence in the canonical architecture index.**
   - `docs/ARCHITECTURE_INDEX.md` still placed machine Product Control first under a single “Architecture decisions” ordering, contradicting `docs/DOCUMENTATION_AUTHORITY.md` and the technical baseline.
   - **Disposition:** fixed. The index now separates architecture/design, product lifecycle/readiness and development-execution authority. Accepted ADRs lead architecture/design; Product Control leads lifecycle/readiness.

2. **Obsolete advisory-job classification in the CI runbook.**
   - `docs/runbooks/ci-cd-setup.md` still labelled `backend-lint`, `backend-typecheck` and `backend-integration` advisory even though active `.github/workflows/ci.yml` includes all three in `REQUIRED_JOBS` and defines `ADVISORY_JOBS=()`.
   - **Disposition:** fixed. Pipeline labels and the gate-classification section now match active CI; the runbook explicitly states that there are currently no advisory jobs.

These fixes are documentation-only and do not promote product lifecycle state. Because they changed the PR head, both CI and independent review must be evaluated again on the new exact head before merge.
