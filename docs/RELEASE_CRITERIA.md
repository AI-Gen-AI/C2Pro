# C2Pro Release Criteria

> **Status:** ACTIVE  
> **Last Updated:** 2026-10-01  
> **Owner:** QA / DevOps / Release Authority  
> **Executable truth:** repository ruleset + current workflows

## 1. Purpose

Define release evidence and decision boundaries without duplicating the live CI configuration.

Workflow files and the active GitHub ruleset are executable truth. This document explains the policy around them.

## 2. Three distinct gates

### A. Merge gate

The active `main` ruleset currently requires:

- `CI Status`
- `gitleaks`
- `Install Drift Guard`

A PR must also satisfy the pull-request/ruleset constraints in GitHub.

Do not document retired workflows such as `tests.yml`, `frontend-ci.yml` or `e2e-security-tests.yml` as current required checks.

### B. Release certification gate

`.github/workflows/release.yml` certifies a tag by verifying:

1. the tagged commit is on `main`;
2. `CI Status` is successful (except the explicit legacy escape hatch);
3. a Gate 7 evidence bundle is validated when one exists for that release tag;
4. publication passes the protected `Production` environment.

Platform deployment and release publication are distinct: Railway/Vercel may auto-deploy from `main`; the release workflow creates the auditable release trail.

### C. Product production-qualification gate

Product lifecycle claims such as `PROD_VALIDATED` are **not** inferred from merge or release publication.

Where Product Control requires production qualification, evidence must satisfy:

- `validation/product/` schemas/validators;
- the qualification evidence contract;
- the relevant operator runbook;
- human-controlled Product Control reconciliation.

For #706/#715 specifically, use `docs/product/production-qualification-operator-runbook.md`.

## 3. CI Status contract

`.github/workflows/ci.yml` is the consolidated PR/push CI graph.

Its final `CI Status` job explicitly joins required lanes. Depending on changed paths, required lanes may succeed or be legitimately skipped.

Current required CI lanes include the relevant subset of:

- backend lint;
- backend typecheck ratchet;
- backend unit tests;
- Presidio NER gate;
- backend security;
- backend integration;
- backend core/coherence/modules suites;
- combined backend coverage ratchet;
- migration checks;
- backend Docker build;
- frontend lint/typecheck;
- frontend tests + API drift;
- frontend E2E smoke;
- frontend production build;
- P0b acceptance journey;
- detect-changes/join logic.

The exact workflow is authoritative if this list drifts.

## 4. Security / supply-chain gates

### Required merge checks

- `gitleaks` — working-tree secret scan.
- `Install Drift Guard` — exact reviewed install-command baseline.

### Additional security evidence

CodeQL, dependency review/audit, Product-Control Guard and domain-specific security gates provide additional evidence where triggered/applicable.

A green Sonar or CodeQL result must never be manufactured by mutating baselines, issue dispositions or quality policy merely to make a release pass.

## 5. Coverage

Coverage is enforced as a **ratchet/contract**, not by copying a stale global percentage into this document.

- backend coverage is merged/enforced by the `Backend Combined Coverage` lane;
- frontend tests enforce their current coverage ratchet;
- changed-code/Codecov signals are supporting evidence.

Never lower an existing enforced threshold merely to pass a release.

## 6. Release evidence bundle

Release evidence belongs under:

`evidence/releases/<release-id>/`

When present, it must be internally consistent and validate against the release commit.

Typical evidence may include:

- automated CI summary;
- manual QA/UAT where required;
- performance/capacity evidence;
- disaster-recovery/rollback evidence;
- waivers with explicit owner/risk/expiry;
- release signoff.

Historical evidence is immutable point-in-time proof. Do not edit an old bundle to represent a later run.

## 7. Product qualification evidence

Product qualification is separate from release evidence.

Use:

- `docs/product/qualification-evidence-contract-v1.md`;
- `evidence/product-qualification/`;
- `validation/product/validate_qualification_evidence.py`;
- current Product-Control parity/validation guards.

A validator PASS is necessary evidence but is not autonomous lifecycle promotion.

## 8. Release decision

Release approval requires no unexplained blocking defect in the applicable release scope.

Minimum questions:

- Is the exact commit on `main`?
- Did the required merge gates pass?
- Does `CI Status` represent all affected required lanes?
- Are security/supply-chain checks clean for the change?
- Are applicable release evidence bundles valid?
- Are migrations/runtime compatibility risks covered?
- Are open P0/P1 blockers explicitly resolved or dispositioned by the correct authority?
- If claiming production validation, is there actual production qualification evidence?

## 9. Waivers

A waiver must state:

- exact failed/advisory gate;
- risk level;
- rationale;
- mitigation;
- owner;
- approver;
- expiry;
- linked issue/evidence.

Waivers must not be used for tenant-isolation failure, secret exposure, fabricated evidence or an unresolved critical trust-boundary defect.

## 10. Historical note

Earlier versions of this document referenced `tests.yml`, `frontend-ci.yml`, `e2e-security-tests.yml` and a different release topology. Those references were superseded by consolidated `ci.yml`, dedicated secret/install guards and the tag-driven `release.yml` workflow.
