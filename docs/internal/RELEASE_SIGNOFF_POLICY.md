# Release Signoff Policy

**Version**: 1.0.0
**Effective Date**: 2026-03-26
**Last Updated**: 2026-03-26

## Governance Note

This document defines release policy and evidence requirements. It does not own task status.

Any open release work, blockers, or follow-up actions derived from this policy must be tracked in `C2PRO_MASTER_BACKLOG.md`.

## Purpose

This document defines the minimum automated test suite requirements for release signoff. A release candidate MUST pass all required suites before promotion to production.

## Suite Categories

### 1. BLOCKING Suites (Must Pass)

These suites MUST pass with zero failures for release approval.

| Suite | Workflow | Threshold | Blocking |
|-------|----------|-----------|----------|
| Secrets Scan | `tests.yml` (secrets-scan) | 0 leaks | **YES** |
| Unit Tests | `tests.yml` (unit-tests) | 100% pass, 70% coverage | **YES** |
| Frontend Typecheck | `frontend-ci.yml` (typecheck) | 0 errors | **YES** |
| Frontend Lint | `frontend-ci.yml` (lint) | 0 errors | **YES** |
| Security E2E | `e2e-security-tests.yml` | 100% pass, 60% coverage | **YES** |

### 2. QUALITY Suites (Should Pass)

These suites should pass. Failures require documented waivers with mitigation plans.

| Suite | Workflow | Threshold | Waiver Allowed |
|-------|----------|-----------|----------------|
| Integration Tests | `tests.yml` (integration-tests) | 95% pass | Yes, with mitigation |
| S5 Core AI Gates | `tests.yml` (s5-core-ai-gates) | 100% pass | No |
| Frontend E2E | `frontend-ci.yml` (tests) | 90% pass | Yes, for flaky tests |
| API Drift Check | `frontend-ci.yml` (api-generation-drift) | 0 drift | No |

### 3. EVALUATION Suites (Regression Guard)

These suites guard against AI model regression. Must meet minimum thresholds.

| Suite | Workflow | Metric | Minimum |
|-------|----------|--------|---------|
| Coherence Engine | `evaluation-regression.yml` | coherence_score_accuracy | 75% |
| Document Extraction | `evaluation-regression.yml` | entity_f1 | 75% |
| Hybrid Retrieval | `evaluation-regression.yml` | mrr_at_10 | 65% |
| Golden Dataset | `evaluation-regression.yml` | overall_pass_rate | 90% |

### 4. RELIABILITY Suites (Release Evidence)

These suites provide reliability evidence. Required for GA releases.

| Suite | Workflow | Requirement |
|-------|----------|-------------|
| I13 Real E2E | `i13-real-e2e-scheduled.yml` | 100% pass on release commit |

## Pass Criteria Summary

### Minimum Viable Release (MVR)

For hotfixes and urgent patches:

```
REQUIRED:
- [ ] Secrets Scan: PASS
- [ ] Unit Tests: PASS (70% coverage)
- [ ] Security E2E: PASS (60% coverage)
- [ ] S5 Core AI Gates: PASS
```

### Standard Release

For regular releases:

```
REQUIRED (all of MVR plus):
- [ ] Frontend Typecheck: PASS
- [ ] Frontend Lint: PASS
- [ ] Frontend E2E: 90%+ pass
- [ ] Integration Tests: 95%+ pass
- [ ] API Drift Check: PASS
- [ ] Evaluation Suites: All above minimum thresholds
```

### GA Release

For general availability releases:

```
REQUIRED (all of Standard plus):
- [ ] I13 Real E2E: PASS on exact release commit
- [ ] Swagger Workbook: 100% verified
- [ ] Performance Baseline: Met
- [ ] Manual Signoffs: Product, Security, Operations
```

## Waiver Process

When a QUALITY suite fails and a release is critical:

1. **Document the failure** in `evidence/releases/<release-id>/waivers/`
2. **Include**:
   - Suite name and failure details
   - Risk assessment (LOW/MEDIUM/HIGH/CRITICAL)
   - Mitigation plan
   - Owner and expiration date
   - Approval from release authority
3. **Add to manifest.yaml** under `waivers[]`

### Waiver Template

```yaml
- suite: <suite-name>
  failure: <description>
  risk_level: <LOW|MEDIUM|HIGH|CRITICAL>
  mitigation: <mitigation-plan>
  owner: <github-username>
  approved_by: <approver-username>
  expires: <YYYY-MM-DD>
  ticket: <JIRA/GitHub issue link>
```

## Coverage Requirements

| Area | Minimum Coverage | Measured By |
|------|-----------------|-------------|
| Backend Unit Tests | 70% | pytest-cov |
| Security E2E (auth/middleware/tenants) | 60% | pytest-cov |
| Frontend | N/A (E2E coverage via Playwright) | - |

## Workflow Evidence Matrix

Each release MUST have evidence artifacts from:

| Workflow | Artifact | Required |
|----------|----------|----------|
| `tests.yml` | `backend-release-summary` | YES |
| `frontend-ci.yml` | `frontend-release-summary` | YES |
| `e2e-security-tests.yml` | `security-release-summary` | YES |
| `evaluation-regression.yml` | `evaluation-release-summary` | YES |
| `i13-real-e2e-scheduled.yml` | `i13-release-summary` | GA only |

## Manifest.yaml Required Fields

```yaml
release_id: <YYYY-MM-DD-rc#>
commit_sha: <exact-40-char-sha>
promotion_workflow: .github/workflows/deploy-production.yml

required_suites:
  backend:
    workflow: .github/workflows/tests.yml
    status: <pass|failure>
    artifact: <artifact-reference>
    coverage: <percentage>

  frontend:
    workflow: .github/workflows/frontend-ci.yml
    status: <pass|failure>
    artifact: <artifact-reference>

  security:
    workflow: .github/workflows/e2e-security-tests.yml
    status: <pass|failure>
    artifact: <artifact-reference>
    coverage: <percentage>

  evaluation:
    workflow: .github/workflows/evaluation-regression.yml
    status: <pass|failure>
    artifact: <artifact-reference>
    metrics:
      coherence_accuracy: <value>
      extraction_f1: <value>
      retrieval_mrr: <value>
      golden_pass_rate: <value>

  reliability:
    workflow: .github/workflows/i13-real-e2e-scheduled.yml
    status: <pass|failure|not_required>
    artifact: <artifact-reference>

thresholds:
  unit_coverage_min: 70
  security_coverage_min: 60
  integration_pass_rate_min: 95
  frontend_e2e_pass_rate_min: 90
  golden_pass_rate_min: 90
  coherence_accuracy_min: 75
  extraction_f1_min: 75
  retrieval_mrr_min: 65

manual_signoff:
  product: <pending|approved|waived>
  security: <pending|approved|waived>
  operations: <pending|approved|waived>
  release_authority: <pending|approved>

waivers: []
```

## Release Gate Decision Tree

```
START
  │
  ├─ Secrets Scan passed? ─NO──> BLOCK
  │    YES
  │
  ├─ Unit Tests passed (70% cov)? ─NO──> BLOCK
  │    YES
  │
  ├─ Security E2E passed (60% cov)? ─NO──> BLOCK
  │    YES
  │
  ├─ S5 Core AI Gates passed? ─NO──> BLOCK
  │    YES
  │
  ├─ [Standard+] Frontend checks passed? ─NO──> BLOCK (unless MVR)
  │    YES
  │
  ├─ [Standard+] Integration 95%+? ─NO──> Waiver required
  │    YES
  │
  ├─ [Standard+] Evaluation thresholds met? ─NO──> BLOCK
  │    YES
  │
  ├─ [GA] I13 Real E2E passed? ─NO──> Cannot GA (defer or downgrade)
  │    YES
  │
  └─ RELEASE APPROVED
```

## Enforcement

1. **CI Checks**: All BLOCKING suites are enforced as GitHub required status checks
2. **Gate 7 Validator**: Validates manifest.yaml against this policy before deploy
3. **Deploy Workflow**: Reads manifest.yaml and blocks if `status: failure` on required suites

Open execution work related to this policy is currently tracked in:

- `REL-RC1-01`
- `REL-RC1-02`

## Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-03-26 | Initial policy definition | G7-02 |
