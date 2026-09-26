# C2Pro Product Qualification Evidence Contract v1

**Status:** CONTROL CONTRACT / NON-AUTHORITATIVE EVIDENCE  
**Owner plane:** Product Control  
**Machine schema:** `validation/product/qualification-evidence.schema.yaml`  
**Validator:** `validation/product/validate_qualification_evidence.py`

## 1. Boundary

A qualification evidence bundle answers:

> Did this exact capability produce its required user outcome on this exact deployed production runtime?

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

- exact Product Control baseline commit SHA;
- exact observed production runtime SHA;
- capability: `P0b | P0c | P0d`;
- concrete production scenario identifiers;
- observed timestamp;
- capability-specific assertions;
- typed evidence references;
- validator verdict.

A branch SHA, merge SHA, preview deployment or CI green is not a substitute for an observed production runtime SHA.

## 3. Minimum evidence floor

A PASS requires at least:

- one `deployment` reference;
- one `persisted_entity` reference;
- evidence for every required assertion.

Additional useful evidence kinds:

- `api_capture`;
- `ui_report`;
- `runtime_log`;
- `test_report`;
- `release_bundle`.

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

- deployment receipt/runtime SHA;
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
2. verify current deployed runtime SHA through deployment/runtime evidence;
3. confirm the planned scenario is within existing production authority;
4. avoid any consequential mutation not already part of the approved user journey;
5. freeze the target project/document/revision identifiers.

During the run:

1. execute the real user journey;
2. collect only bounded evidence;
3. avoid raw secrets, broad environment dumps or unrelated tenant data;
4. use durable references/hashes where available;
5. record failures honestly.

After the run:

1. create the evidence YAML;
2. run:

```bash
python validation/product/validate_qualification_evidence.py <bundle.yaml>
```

3. independently review the bundle;
4. only then open a separate Product-Control reconciliation that references the validated evidence.

## 8. Promotion rule

`validator_verdict=PASS` is necessary but not sufficient for lifecycle promotion.

Promotion still requires:

- Product-Control YAML edit first;
- guarded Markdown projection update;
- lifecycle/parity guard;
- evidence reference/digest;
- exact production runtime binding;
- human-controlled merge.

No automation should infer `PROD_VALIDATED` merely because an evidence file exists.

## 9. Failure semantics

A failed qualification is useful evidence.

Keep `validator_verdict=FAIL` and the failed assertions/evidence. Do not rewrite a failed run into PASS.

A rerun must create new evidence bound to its own observed time/runtime/scenario as appropriate.
