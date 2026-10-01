# C2Pro Release Criteria

**Status:** Current policy  
**Updated:** 2026-10-01  
**Product lifecycle authority:** Product Control  
**Execution authority:** `.c2pro/control/`

## 1. Principle

A release decision is evidence-bound to an **exact commit/deployment identity**. Historical pass counts, screenshots or a previous green branch do not qualify a newer release candidate.

This document defines evidence classes. It does not own task status and does not replace the protected-branch ruleset or Product Control.

## 2. Merge gates vs release gates

### Merge gates

Required merge checks are defined by the repository ruleset and current GitHub workflows. At the 2026-10-01 reconciliation the protected-main ruleset includes required contexts such as:

- `CI Status`;
- `gitleaks`;
- `Install Drift Guard`.

The ruleset is authoritative if this list changes.

### Release gates

A release can require more evidence than a merge:

- primary CI suites for the exact SHA;
- dependency/code/security scans;
- Product-Control/document contract gates where applicable;
- evaluation/golden/real-document gates for AI-affecting changes;
- deployment identity evidence;
- production synthetic journey / acceptance evidence when the product-control phase requires it;
- manual Product/Security/Operations signoff where the release policy requires it.

## 3. Current workflow map

| Evidence class | Workflow/surface |
| --- | --- |
| Primary product/code CI | `.github/workflows/ci.yml` |
| Secrets | `.github/workflows/secret-scan.yml` |
| Install drift | `.github/workflows/install-drift-guard.yml` |
| Dependency change | `.github/workflows/dependency-review.yml` |
| Dependency audit | `.github/workflows/dependency-audit.yml` |
| Static code security | `.github/workflows/codeql.yml` |
| Product control | `.github/workflows/c2pro-product-control-guard.yml` |
| Evaluation regression | `.github/workflows/evaluation-regression.yml` |
| Golden corpus | `.github/workflows/golden-corpus-evals.yml` |
| Real-document operability | `.github/workflows/real-document-operability.yml` |
| Scheduled real E2E | `.github/workflows/i13-real-e2e-scheduled.yml` |
| Release orchestration | `.github/workflows/release.yml` |

Trigger/required status must be read from the workflow/ruleset itself; this table is an index.

## 4. Blocking principles

A release candidate is blocked when:

1. a required ruleset check is not successful;
2. an applicable security/secret/dependency gate reports an unresolved blocking finding;
3. exact deployment identity cannot be bound to the qualified commit;
4. required production-journey evidence is absent/failed;
5. Product Control still marks the required capability/gate as unqualified;
6. evidence belongs to another SHA/deployment/environment;
7. a required manual signoff is missing.

External/advisory provider statuses may be non-blocking only when the repository ruleset/release contract says so and their failure is classified with evidence.

## 5. Coverage and quality

Use the coverage ratchets enforced by the **current CI**. Do not hard-code a historical global percentage into release signoff when CI has moved to module/combined/patch ratchets.

For every release, record:
- exact SHA;
- exact workflow run/check URLs or artifact identifiers;
- required suites and conclusions;
- residual warnings/advisories;
- waivers (if the governing policy permits them);
- deployment identities;
- manual signoffs.

## 6. Release evidence

Store durable release evidence under the repository-approved release evidence path when the release workflow/policy calls for it. Evidence must be bounded and must not contain credentials, raw secrets or unrestricted provider responses.

Suggested manifest fields:

```yaml
release_id: <release-id>
commit_sha: <40-char-sha>
environment: <staging|production>
required_checks:
  - name: CI Status
    conclusion: success
    evidence: <run/check ref>
deployments:
  frontend: <provider-observed id>
  api: <provider-observed id>
product_control:
  status: <canonical control state/ref>
manual_signoff:
  product: <pending|approved|not-required>
  security: <pending|approved|not-required>
  operations: <pending|approved|not-required>
waivers: []
```

## 7. Waivers

A waiver must be explicit, bounded, owned, expiring and permitted by the relevant gate policy. A waiver does not turn a failed test into a pass and must not be used to bypass tenant isolation, secret exposure, identity, trusted-state or other non-waivable safety boundaries.

## 8. Historical results

Past release counts/percentages belong in dated evidence/audits, not in this current policy. Do not use old statements such as “334 tests passed” as current release proof.
