# Production Qualification Operator Runbook

> **Scope:** #715 / #706 synthetic production qualification  
> **Status:** Active operator contract  
> **Last reconciled:** 2026-10-01  
> **Implementation:** `.github/workflows/prod-synthetic-acceptance.yml`

## Purpose

Prove the real deployed C2Pro user journey in a dedicated synthetic production tenant without using customer data, mocks, hidden repair or operator-supplied evidence that can self-satisfy the identity gate.

Landing the harness is not qualification. Qualification exists only when an authorized run executes against the intended production runtime and its evidence is reviewed.

## Preconditions

Before a full journey:

1. required remediation/dependencies for #706 are merged and deployed;
2. dedicated synthetic Clerk user + Organization exists through the supported operator path;
3. the mapped C2Pro tenant is positively marked synthetic;
4. operator has the protected production-qualification permissions/secrets required by the workflow;
5. exact expected deployment identifiers/SHAs are known for comparison;
6. there are no unreviewed staged production configuration changes that would make the observed runtime ambiguous;
7. the committed fixture hash is unchanged.

Do not use customer/CI identities as substitutes.

## Execution modes

### identity-preflight

Use first.

It may verify:

- canonical production origin;
- provider-observed Railway API/Worker/Scheduler identity;
- provider-observed Vercel production identity;
- tenant/org binding;
- real Clerk login;
- synthetic-tenant marker;
- read-only database preflight.

It must not create the project/upload mutation sequence.

### full-journey

Use only after identity-preflight and external gates are satisfied.

Canonical journey:

`AUTH → PROJECT CREATE → UPLOAD → PARSE/EXTRACT → ANALYSIS → EVIDENCE → HEALTH → HITL (when required) → REFRESH/RELOGIN → supported retry/recovery`

## Fail-closed identity rules

- production credentials are entered only after canonical HTTPS production origin validation;
- explicit alternate ports/non-production hosts are rejected;
- Railway observations are scoped to pinned project/environment/service identities;
- Vercel deployment must belong to the pinned production project;
- operator-provided expected identifiers are comparisons, not evidence sources;
- wrong tenant/org/synthetic marker aborts before mutation;
- fixture SHA mismatch aborts before upload.

## Evidence rules

Allowed evidence is bounded, normalized and non-secret.

Never persist/upload:

- provider API raw responses when unnecessary;
- passwords/tokens;
- database DSNs;
- environment dumps;
- customer row contents;
- browser traces/screenshots/video that could capture credentials in this qualification mode.

Evidence must bind the actual composite runtime observed.

Different backend/frontend SHAs may be truthful if the deployment topology actually contains that combination; never manufacture same-SHA equality.

## Durable verification

Where needed, the verifier is read-only and tenant/project scoped.

Verification may assert existence/state of:

- project/document;
- parsed/extracted durable records;
- analysis/artifact;
- evidence;
- ProjectGraph/event/snapshot/Health;
- HITL result when exercised.

It should report identifiers/check states, not broad row contents.

## Qualification bundle

Bundle construction/validation must:

- require canonical full Git SHAs where the contract requires SHAs;
- hash referenced evidence artifacts with SHA-256;
- use canonical/fixed evidence roots;
- reject arbitrary output paths/path traversal;
- preserve failed evidence honestly.

Run the committed validation tools from `validation/product/` as defined by the workflow/control contract.

## Interpretation

A successful workflow run is evidence, not autonomous lifecycle promotion.

Promotion still requires:

- Product Control reconciliation;
- parity/validation guard;
- evidence review;
- human-controlled merge/promotion authority.

A failed run is retained as failed evidence; do not rewrite it into PASS.

## Related sources

- `docs/superpowers/specs/2026-09-27-issue-706-production-journey-remediation-design.md`
- `docs/superpowers/plans/2026-09-27-715-production-synthetic-acceptance.md`
- `docs/product/qualification-evidence-contract-v1.md`
- `.github/workflows/prod-synthetic-acceptance.yml`
- `validation/product/test_prod_synthetic_workflow_contract.py`
- `apps/api/scripts/verify_prod_synthetic_journey.py`
