# C2Pro Product Qualification Evidence Contract v1

**Status:** CONTROL CONTRACT / NON-AUTHORITATIVE EVIDENCE  
**Owner plane:** Product Control  
**Machine schema:** `validation/product/qualification-evidence.schema.yaml`  
**Validator:** `validation/product/validate_qualification_evidence.py`

## 1. Boundary

A qualification evidence bundle answers:

> Did this exact capability produce its required user outcome on this exact observed composite production runtime?

It does **not** answer:

- whether the repository branch should merge;
- whether a full release is signed off;
- whether Product Control has already promoted lifecycle;
- whether a provider/deployment mutation is authorized.

The canonical lifecycle remains in:

`validation/product/c2pro-master-product-control-v1.yaml`

A validated evidence bundle is an input to a later Product-Control reconciliation. It cannot set `prod_validation_status`, `deployment_status`, `realization_status` or work status.

## 2. Required bindings

Every bundle binds to:

- an exact immutable `control_commit_sha` from canonical `main` history that contains the Product Control state used for qualification;
- the exact `production_position.reconciled_against_main_sha` recorded by Product Control at that commit;
- an exact composite runtime binding for the production planes exercised by the user journey:
  - backend: Railway deployment ID/evidence + exact Git commit SHA + terminal `SUCCESS`;
  - frontend: Vercel deployment ID/evidence + exact Git commit SHA + terminal `READY`;
- each runtime Git SHA must be reachable from canonical `main` history; a syntactically valid 40-hex value alone is insufficient;
- capability: `P0b | P0c | P0d`;
- concrete production scenario identifiers;
- observed timestamp;
- capability-specific assertions;
- typed evidence references;
- validator verdict.

The validator loads Product Control from `control_commit_sha` using repository Git history, verifies that commit is an ancestor of canonical `main`, and compares the recorded control baseline against that immutable historical control state.

Runtime identity is deliberately **plane-specific**. Backend and frontend SHAs may be equal or different because a backend-only change need not redeploy the frontend and vice versa. A bundle is valid only when both required plane bindings are exact, provider-correct and backed by typed `deployment` evidence.

The legacy singleton `production_position.deployed_runtime_sha` is not used by this Phase-A evidence validator to collapse the two planes. Product-Control promotion integration of the composite runtime belongs to #681. That split prevents a non-authoritative evidence file from inventing lifecycle/runtime authority.

This versioned binding preserves retained failed runs and earlier successful evidence after Product Control or either deployed runtime plane later advances. Historical bundles are never rebound to today's singleton control file.

A branch SHA, merge SHA, preview deployment or CI green is not a substitute for observed production deployment identities.

## 3. Minimum evidence floor

A PASS requires at least:

- two typed `deployment` references: one for backend/Railway and one for frontend/Vercel;
- each deployment evidence locator is provider-namespaced (`railway:<artifact-locator>` / `vercel:<artifact-locator>`), must contain a non-empty bounded locator after the namespace, and the two locators must identify distinct deployment artifacts rather than aliases of the same receipt;
- one `persisted_entity` reference;
- evidence for every required assertion;
- every evidence record to be immutable or content-addressed by SHA-256;
- a timezone-aware RFC3339 / ISO-8601 observation timestamp; this evidence profile deliberately rejects second `60` rather than accepting unverifiable leap-second timestamps.

Additional typed evidence kinds:

- `api_capture`;
- `ui_report`;
- `runtime_log`;
- `test_report`;
- `review`;
- `release_bundle`.

There is deliberately no generic `other` kind in a PASS contract. Extend the schema explicitly when a new evidence class becomes legitimate.

A release bundle may be referenced, but does not become lifecycle authority.

## 4. P0b — Single-document Health

Scenario:

`single_document_health`

Required identifiers:

- project;
- document;
- source revision.

Required proof:

1. all six canonical categories are represented truthfully, including Unknown where unsupported;
2. findings are evidence-traceable;
3. missing-data semantics survive persistence/read;
4. actionable gap alerts are visible;
5. API and user-visible UI/report have the same Health semantics;
6. Unknown never becomes 0 or green;
7. relational Coherence headline remains null while fewer than two reconcilable documents exist;
8. HITL/retry/recovery does not strand the document.

Recommended evidence:

- Railway backend deployment receipt + exact commit SHA;
- Vercel frontend production deployment receipt + exact commit SHA;
- persisted project/document/revision IDs;
- bounded API capture;
- user-visible Health report/screenshot artifact;
- bounded worker/runtime log only when needed for recovery proof.

## 5. P0c — What Changed

Scenario:

`what_changed_two_revisions`

Required identifiers:

- project;
- document;
- from revision;
- to revision.

The two revision IDs must differ.

Required proof:

1. durable revision-bound events exist;
2. timeline is queryable;
3. semantic change is source/revision traceable;
4. API and user-visible projection agree;
5. absent evidence does not create an invented change.

Use two revisions of the same real production document/project. Do not satisfy the gate with synthetic branch fixtures alone.

## 6. P0d — Current State

Scenario:

`current_state_report`

Required identifiers:

- project;
- authoritative state/snapshot reference.

Required proof:

1. report derives from authoritative domain sources;
2. six-category Health semantics match P0b;
3. honest null survives API, UI and export/report surfaces;
4. identical authoritative state produces reproducible output.

## 7. Collection procedure

Before any production interaction:

1. verify current Product Control baseline SHA;
2. independently observe the current backend Railway production deployment and frontend Vercel production deployment;
3. record exact commit SHA + terminal deployment state + typed deployment evidence for each plane; do **not** require artificial SHA equality;
4. record the exact canonical-main commit containing the Product Control baseline used for the run as `control_commit_sha`;
5. confirm the planned scenario is within existing production authority;
6. avoid any consequential mutation not already part of the approved user journey;
7. freeze the target project/document/revision identifiers.

During the run:

1. execute the real user journey;
2. collect only bounded evidence;
3. avoid raw secrets, broad environment dumps or unrelated tenant data;
4. use durable references/hashes where available;
5. record failures honestly.

After the run:

1. create the evidence YAML under the fixed repository directory `evidence/product-qualification/`;
2. run:

```bash
python validation/product/validate_qualification_evidence.py
```

The CLI intentionally accepts **no arbitrary filesystem path**. It scans only committed `*.yaml` bundles in that fixed directory and always binds them against the canonical Product Control YAML at `validation/product/c2pro-master-product-control-v1.yaml`.

3. the validator binds each bundle to the versioned canonical Product Control snapshot named by `control_commit_sha`, not merely to SHA syntax or today's singleton control state;
4. independently review the bundle;
5. retain failed and superseded bundles unchanged; later control/runtime advances do not rewrite their historical binding;
6. only then open a separate Product-Control reconciliation that references the validated evidence.

## 8. Promotion rule

`validator_verdict=PASS` is necessary but not sufficient for lifecycle promotion.

Promotion still requires:

- Product-Control YAML edit first;
- guarded Markdown projection update;
- lifecycle/parity guard;
- evidence reference/digest;
- exact composite production runtime binding, reconciled into Product Control by the Phase-B promotion guard (#681);
- human-controlled merge.

No automation should infer `PROD_VALIDATED` merely because an evidence file exists.

## 9. Failure semantics

A failed qualification is useful evidence.

Keep `validator_verdict=FAIL` and the failed assertions/evidence. Do not rewrite a failed run into PASS.

A rerun must create new evidence bound to its own observed time, backend/frontend deployment identities and scenario as appropriate.

## 10. Composite runtime example

A valid bundle may intentionally record different repository SHAs for the two planes:

```yaml
runtime_bindings:
  - plane: backend
    provider: railway
    commit_sha: d2189da1d1f580d97bad417a42db849822483895
    terminal_state: SUCCESS
    deployment_evidence_ref: deploy-backend
  - plane: frontend
    provider: vercel
    commit_sha: 670a71524f82071c1f609055d332b883538691a7
    terminal_state: READY
    deployment_evidence_ref: deploy-frontend
```

That is truthful when the backend changed after the last frontend-relevant deploy. Product qualification must prove the actual UI+API combination exercised, not manufacture a same-SHA invariant that the deployment topology does not provide.
