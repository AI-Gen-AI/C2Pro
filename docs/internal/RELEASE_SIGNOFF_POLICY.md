# Release Signoff Policy

**Version:** 2.0.0  
**Effective:** 2026-10-01  
**Status:** ACTIVE

## Purpose

Define who may claim that a C2Pro release is certified, published or production-qualified.

These are separate claims.

## 1. Merge-ready

A change is merge-ready only when the live `main` ruleset is satisfied.

At this revision the required status checks are:

- `CI Status`
- `gitleaks`
- `Install Drift Guard`

The repository ruleset is authoritative if this list changes.

## 2. Release-certified

A release tag is certified by `.github/workflows/release.yml` when:

- the tag points to a commit on `main`;
- the exact commit has successful `CI Status`;
- Gate 7 release evidence is validated when present.

The explicit `allow_missing_ci` input is a legacy escape hatch and requires conscious operator use; it must not become routine release policy.

## 3. Release-published

Publication occurs only after the protected `Production` environment allows the `publish` job.

GitHub Release publication is not proof that every product capability is production-validated.

## 4. Product production-qualified

A capability may be marked production-qualified only through its Product Control evidence contract.

For controlled product qualification:

- bind the actual observed runtime;
- validate the evidence bundle;
- preserve failed evidence;
- perform human Product Control reconciliation;
- keep merge/deploy/qualification statuses separate.

For #715 see `docs/product/production-qualification-operator-runbook.md`.

## 5. Signoff roles

Where a release requires manual signoff, record:

- Product;
- Security;
- Operations;
- Release Authority.

A person approving release publication does not implicitly approve a separate Product Control lifecycle promotion unless that authority/action is explicit.

## 6. Blocking classes

No waiver should silently bypass:

- cross-tenant isolation failure;
- secret leakage;
- invalid/missing exact identity binding for a qualification that requires it;
- fabricated evidence;
- failed required merge gate;
- known critical data-integrity/trust-boundary defect in release scope.

Other advisory failures require documented risk acceptance.

## 7. Evidence integrity

Evidence must be:

- bound to the exact commit/runtime it claims;
- non-secret;
- immutable as historical proof;
- reproducible/inspectable where practical;
- honest about failure, skipped lanes and unverified state.

Never rewrite failed historical evidence into PASS.

## 8. CI and release topology

Current topology:

- consolidated PR CI: `.github/workflows/ci.yml`;
- secret gate: `.github/workflows/secret-scan.yml`;
- install/supply-chain drift gate: `.github/workflows/install-drift-guard.yml`;
- release certification/publication: `.github/workflows/release.yml`;
- Product Control integrity: `.github/workflows/c2pro-product-control-guard.yml`;
- production qualification harness: `.github/workflows/prod-synthetic-acceptance.yml`.

Retired workflow names must not be used as current signoff requirements.

## 9. Revision history

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-10-01 | Reconciled consolidated CI, active ruleset, tag-driven release, Product Control and production qualification boundaries. |
| 1.0.0 | 2026-03-26 | Initial release-signoff policy. |
