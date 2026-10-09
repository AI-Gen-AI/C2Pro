# ADR-030: WBS Intelligence — Immutable Proposals, Dimension-Level Qualification, Domain Profiles

**Status:** Accepted
**Date:** 2026-10-07
**Decision class:** Product + AI architecture (AI authority boundary, evidence semantics, advisory profiles)
**Conforms to:** ADR-029 §7 (entry modes), §9 (Domain Profiles) and §10 (alignment is not authority). ADR-029 remains the WBS governance authority; this ADR adds nothing to it and supersedes nothing in it.
**Related:** ADR-010/011 (Evidence layers), ADR-013 (Runtime trust), ADR-014 (Project state model), ADR-020 (HITL), ADR-026 (Trusted-state commit boundary)
**Planning lineage:** #688 (umbrella), PC-2b slices #920 (this ADR) → #921 → #922 → #923 → #924; core follow-ups #925 (prompt-cache tenant scope) and #926 (retrieval scope)

## Context

PC-2a made the canonical WBS governed. The governance path is the only way a baseline is created:

- change sets;
- a typed edit-command algebra;
- a human-only author and decider;
- a signed change-set digest;
- approve = apply;
- STALE and rebase.

PC-2b adds WBS intelligence on top of that governance:

- **Generate:** propose a WBS when none exists.
- **Import + Review:** review a customer's WBS against project evidence.
- **Review / Optimize:** improve an approved baseline.

AI can be wrong, can be steered by document content, and is not deterministic. It must therefore never become a second path to authority.

## Decision

### 1. No AI authority

AI never:
- authors, edits or submits a change set;
- approves anything;
- pins a profile;
- mutates the live WBS;
- bypasses governance.

Origin `ai` never confers authority. Every path still ends in the unchanged ADR-029 flow:

> DRAFT → human edit → SUBMIT → human APPROVE = APPLY.

### 2. Three output types, never collapsed

| Type | What it is | PC-2b |
|---|---|---|
| A. Structural proposal | One governed edit command against an exact target | yes |
| B. Qualification finding | A dimension-level judgement with evidence | yes |
| C. Mapping / alignment observation | e.g. obligation or procurement not mapped | later engines; reported as NOT_EVALUATED |

A finding never becomes a mutation. It may reference proposals, and a human may close it with "no change".

### 3. Immutable proposals, applied by a human

AI produces immutable proposal and finding items: model B of the PC-2b architecture review.

- **Applying an item.** A human applies selected items through the existing governed commands, on a DRAFT that the human may author:
  - C2Pro mints real node ids only at that moment; the model only ever names new nodes by short local labels;
  - node provenance records the run and the item;
  - the change-set digest covers only the submitted candidate, never the discarded suggestions.
- **Selection.** Selections must be dependency-safe:
  - the prerequisite closure must be selected explicitly (shown, never auto-accepted);
  - a rejected prerequisite makes its dependants non-applicable;
  - application is atomic and all-or-nothing.
- **Reruns.** A rerun is a new run; the candidate changes only by explicit human application.
- **Freshness.** Freshness is derived, never stored:
  - a baseline that moved, or a change set that is not a DRAFT, makes a run STALE;
  - an item whose target node fingerprints changed is in CONFLICT. A SPLIT or MERGE also
    fingerprints the children it takes over and each source's child set, so a child edited or added
    under a source after the run is a CONFLICT too. Like PC-2a, a minted node is never split or merged.
- **Comparison.** The "AI proposed tree" view is a simulated read model; no second candidate tree is persisted.

### 4. Qualification is dimension-level; no composite score (deferred)

`wbs-qualification/v1` reports **every** dimension exactly once. Each result has:
- a status: SUPPORTED, GAP, WARNING, NOT_EVALUATED or AMBIGUOUS;
- a reason code;
- a method: DETERMINISTIC, AI or PROFILE_HEURISTIC;
- evidence.

Rules:
- A dimension without inputs, or without downstream authority, is NOT_EVALUATED with an honest reason. It is never SUPPORTED by absence, and never a fake deficiency: "Governed Schedule evidence unavailable", not "schedule alignment poor".
- The availability matrix is enforced by the server. A model cannot move a dimension off NOT_EVALUATED.
- A composite "WBS quality score" is deferred until golden human judgements can calibrate it.

### 5. Trusted inputs and source-specific authority

Every input enters a run through a tenant- and project-scoped evidence manifest, with one of these classes:
- trusted project evidence (#714 TRUSTED);
- proposed evidence (human-included only);
- advisory evidence (schedule hierarchy, BC3, legacy structure);
- a human-provided import (the target, not proof of itself);
- the current approved WBS (the target);
- user context.

Authority comes from the manifest, never from the model. Proposed, advisory or import evidence alone can never support SUPPORTED or GAP. A profile heuristic is never documentary fact.

The canonical source location and the model-visible text are separate:
- **Canonical source:** document, revision, blob or artifact identity, and page, section, row or offsets. It is selected from the original revision before anything is anonymised.
- **Model-visible text:** the anonymised text the model reads. Model quotes are verified against this text only. Anonymised offsets are never presented as source locations, and no PII is stored to make citation easier.

### 6. Domain Profiles

`wbs-domain-profile/v1` profiles are:
- versioned;
- declarative;
- advisory;
- composable;
- digested;
- read-only at runtime.

**Storage:** reviewed YAML in the repository, with a JSON Schema export. `profiles.lock` freezes each published version's digest. There is no database CMS, no executable profile code and no industry enums.

**What profiles may do:**
- suggest and warn;
- supply terminology and decomposition patterns;
- supply heuristics from a closed predicate set, at most WARNING;
- supply bounded prompt guidance, linted against governance overrides.

**What profiles may never do:**
- create nodes;
- author, submit or approve;
- override governance or digest rules.

**Pins:** pins carry `(profile_id, profile_version, profile_digest)`. A bundle pins its constituents by digest, so its identity binds them transitively.

**Composition** fails closed on namespace collisions, version clashes and declared conflicts. Contradictory heuristics are AMBIGUOUS, never GAP.

**Selection** order: explicit user choice, then project configuration, then an AI suggestion, which counts only after human confirmation.

**Submit rule:** a non-core `decomposition_kind` must belong to a profile pinned on the change set, and the term must be declared by that exact version.

### 7. Untrusted-content isolation (layered; it does not prevent injection alone)

Project, import and user content is data. The defence is layered:
1. PII anonymisation.
2. A data-only system instruction.
3. Per-call unguessable boundaries, with forged or closing boundaries neutralised.
4. No model tools.
5. Output schemas with no governance fields.
6. Strict parsing.
7. Deterministic server validation.
8. Evidence restricted to the manifest.
9. Human-only governance.

### 8. Deterministic validation before storage

LLM output is never trusted because it is valid JSON. Every response is checked before storage for:
- strict schemas;
- references limited to snapshot ids or local labels (an invented canonical id rejects the item);
- allowed operations (no ADOPT_LEGACY);
- pinned namespaces and declared terms, plus dictionary v1;
- verified evidence;
- an acyclic dependency graph;
- a simulated application that keeps the tree structurally valid.

A rejected item takes its dependants with it. An invalid envelope, or too many rejections, fails the run.

### 9. Bounded orchestration, provenance, idempotency

**Orchestration:** generation and review use a bounded pipeline, not autonomous agents:
1. inventory and sufficiency gate;
2. manifest-restricted, tenant- and project-scoped retrieval;
3. map;
4. reduce;
5. validate.

It runs with call, token and cost caps, cancellation, and no tools or recursion.

**Model provenance:** recorded through the shared `core/ai` contract:
- provider, requested model and served model;
- routing tier and integer sampling configuration;
- prompt-template identities;
- profile pins;
- contract versions;
- telemetry references.

**Idempotency:** a tenant-scoped key binds everything that determines a result and nothing volatile. Runs bypass the shared prompt cache until #925 is resolved.

### 10. Evaluation philosophy

Quality is measured by deterministic scorers over synthetic or licensed golden fixtures, replayed from recorded responses. LLM-as-judge is never a gate on its own.

Hard gates from day one:
- hierarchy validity 100%;
- invented canonical ids 0;
- injection effects 0;
- NOT_EVALUATED correctness 100%;
- insufficient-evidence abstention 100%.

## Consequences

- **AI becomes useful without becoming an authority.** Every structural change is still a human-authored, digest-signed, human-approved governed change.
- **Qualification is honest.** Missing inputs and missing downstream authorities read as NOT_EVALUATED; they are never presented as fitness or as a defect.
- **Profiles are cheap to review and reproducible.** Changing one means publishing a new version, so old proposals stay auditable.
- **Persistence.** Runs, items and decisions are persisted by PC-2b.2 (amendment below). Import sources (PC-2b.3) still need their own tenant-scoped tables with RLS.
- **Cost of the design.** Applying proposals is explicit work for the user. This is deliberate: a rerun can never overwrite human edits.

## Amendment 1 — PC-2b.2 store and human decision loop (#921)

Conforms to §1–§4 and §9. It persists intelligence; it adds no authority.

- **Store.** Three tenant- and project-scoped tables, linked by composite (tenant, project, …) foreign keys, with RLS ENABLED + FORCED and fail-closed policies:
  - `wbs_intelligence_runs`: the exact input identity of a run and its complete `wbs-qualification/v1` report (one coherent result, never spread over findings);
  - `wbs_intelligence_items`: FINDING or PROPOSAL, insert-only, recorded only while the run is RUNNING;
  - `wbs_intelligence_decisions`: append-only, one per item.
- **Run lifecycle.** Status (REQUESTED / RUNNING / COMPLETED / FAILED / CANCELLED) is separate from the outcome vocabulary. A terminal run is frozen. Execution is DETERMINISTIC (no model provenance, never fabricated) or AI (model provenance required). PC-2b.2 only executes deterministic runs.
- **Idempotency.** A partial unique index on `(tenant_id, idempotency_key)` covers REQUESTED, RUNNING and COMPLETED runs only. A FAILED or CANCELLED run never blocks or answers a retry, and concurrent identical requests serialize on the index.
- **Decisions are choices, not approvals.**
  - Proposal decisions are `APPLY_AS_PROPOSED`, `APPLY_WITH_HUMAN_EDIT` or `REJECT`; finding decisions are `ACKNOWLEDGE`, `DISMISS` or `NO_CHANGE`.
  - Only an active human `user` or `admin` decides (database-checked); never `api`, AI or a service.
  - Applying needs an existing DRAFT (never created by the decision API) and runs through the PC-2a governed commands as the human, under the expected revision.
  - A human edit is recorded on the decision (exact governed commands and their digest) beside the untouched original proposal digest.
  - Baseline approval stays the unchanged ADR-029 submit + human admin approve = apply.
- **Atomicity.** For one selected batch, freshness, fingerprints, dependency closure, the simulation of the final batch, the governed commands, the decision rows and their `wbs.intelligence.item_decided` events form one transaction. One invalid item and nothing is applied, decided or emitted.
- **Freshness stays derived.** STALE is run-level: the baseline moved, or the candidate is no longer a DRAFT on the current base. CONFLICT is per item (fingerprints). Ordinary edits to a valid DRAFT never stale the run, so untouched items still apply.
- **Provenance.** The candidate node `provenance` records `{intelligence_run_id, intelligence_item_id, decision_id, application_mode}`. It never enters a digest, and decisions never touch `evidence_refs`.

## Amendment 2 — PC-2b.3 external WBS import + review (#922)

Conforms to §1, §3, §5 and §9 and to ADR-029's IMPORT_REVIEW entry mode. **Imported source ≠ DRAFT candidate ≠ approved WBS**: an import is input and confers no authority.

- **Source document.** `document_type = 'wbs'` is an external WBS source file (`.xlsx`, `.csv` or strict `wbs-import/v1` JSON; these formats are granted to the `wbs` type only). It never enters ingestion, RAG chunking, the N1–N17 graph, clause/entity extraction, reprocess or recovery. It is parsed only by the deterministic WBS importer, which leaves it `parsed` (never analysis-pending).
- **Import source.** `wbs_import_sources` stores one immutable, deterministic parse of ONE document revision with ONE parser identity (`wbs-xlsx/v1`, `wbs-csv/v1`, `wbs-json/v1`) and ONE normalized configuration:
  - the exact blob hash (database-checked against the revision);
  - the `wbs-import-snapshot/v1` snapshot and its digest (stable diagnostic codes included, wording excluded);
  - diagnostics and the parse status (READY / READY_WITH_WARNINGS / INVALID — no workflow authority).
  It is INSERT-ONLY and leaves only with its project. Its key binds tenant, project, document, revision, blob, parser identity and configuration digest. A re-parse reuses the stored import only after reproducing its digest; a different digest fails closed as parser nondeterminism. A new revision is a new import; old imports stay auditable.
- **No silent repair.** Hierarchy comes from every method present (`parent_code`, `parent_id`, outline `level`), and they must agree. A cycle, self-parent, unresolved or ambiguous parent, impossible level jump, conflicting methods, duplicate source identity or missing name is BLOCKING (the import is INVALID; no candidate). A WBS code is not identity: an invalid or duplicated code becomes NULL with a WARNING (the raw value stays in provenance), unless a parent reference depends on it. Source rows are identified by their immutable location (`sheet:<s>/row:<n>`, `row:<n>`, `/nodes/<i>`). Identifiers inside the file are source identifiers only and never become canonical ids. Formulas are never evaluated (BLOCKING in mapped columns); macros, external links and oversized or deeply nested input are refused.
- **Schedule and cost are not WBS.** Schedule columns (dates, durations, predecessors, …) and cost columns are never mapped into WBS semantics: ignored with a WARNING in tabular files, rejected in the strict JSON contract. A schedule activity or budget line is never imported as a WBS node by this path.
- **Explicit human candidate.** Parsing creates no DRAFT. Only an explicit human action (`POST …/wbs-imports/{id}/candidates`; never `api`, AI or a service) creates an IMPORT_REVIEW change set. It is linked by the immutable `wbs_change_sets.source_import_id`, where `entry_mode = IMPORT_REVIEW` holds if and only if the link is set, with `origin = import` and no base baseline. It is populated only through the PC-2a governed ADD_NODE commands, with server-minted ids, as ONE revision, all or nothing. v1: an import establishes Baseline #1 only, so with an approved baseline it is refused (use CHANGE_BASELINE or the Reviewer/Optimizer flow). Legacy live rows are never matched, adopted or retired by the import; the submit-time legacy disposition is unchanged.
- **Provenance.** Each imported candidate node records `provenance.import = {origin, import_source_id, document_id, revision_id, snapshot_digest, source_ref, raw_code, external_id, parser_id, parser_version}`. Neither this nor the source link enters any digest, and neither touches the WBS Dictionary. Human edits change the candidate only; the snapshot never changes.
- **Retention.** The import → revision foreign key is NO ACTION: an individual source document that was imported cannot be deleted (409), so no IMPORT_REVIEW change set or baseline loses its provenance. Project or tenant deletion cascades as before.
- **Comparison.** IMPORTED vs CANDIDATE is a pure read. Rows correspond by the import `source_ref` recorded in node provenance, never by code or name. Every governed field is compared: name, code, `control_level`, `decomposition_kind`, the WBS Dictionary in its canonical `wbs-dictionary/v1` form (the tree digest's semantics), parent, and sibling-relative order among the imported siblings still under the same parent. A row that cannot be compared reliably is `NOT_COMPARABLE` with an explicit limitation, never `UNCHANGED`. Nodes added in the candidate are reported as `ADDED`. PROPOSED is `NOT_AVAILABLE` unless a run with proposals is named, in which case it is DERIVED through the PC-2b.2 preview and never persisted.
- **Qualification.** The imported DRAFT is qualified only by an explicit deterministic run (PC-2b.2); an import never starts a run. No model call exists in this slice.

## Amendment 3 — PC-2b.4 AI Reviewer / Optimizer, offline (#923)

Conforms to §1, §5, §7, §8 and §9. **Live model execution is BLOCKED.** This amendment covers the offline implementation only (`PC2B4_OFFLINE_ONLY`).

- **Model boundary.** `WBSReviewerModelPort` is the Reviewer's only way to a model.
  - **A request carries only:** the validated task identity (tenant, project, run, call, attempt, cluster); versioned prompt references (task, version, SHA-256 of the exact template text); the declared model fingerprint; explicit per-call input/output limits; and already-isolated, PII-anonymised text.
  - **It never carries:** a database session, a credential, a retrieval interface, a WBS mutation service, an approval action or tools.
  - **Blocked until authorized:** `LIVE_MODEL_EXECUTION_AUTHORIZED = False`, and anything but the synthetic adapter itself is refused before anything else runs. An adapter's own `is_synthetic` claim is not trusted: the class must be exactly `FakeReviewerModelAdapter` with its `complete` unreplaced. Provenance and usage derive `synthetic` from that check, never from a constant. Only `FakeReviewerModelAdapter` (in memory, scripted) exists. A production adapter needs a separate integration authorization, and only after these gates pass: Wave 3.11 default-off tracing and privacy-safe export; #925 cache read/write bypass and tenant isolation; no extraction-cache use on the WBS path; usage attribution; and PII/provider-boundary tests.
- **Targets.**
  - `IMPORT_REVIEW` is a human-created candidate from an immutable import.
  - `DRAFT` is any governed DRAFT.
  - `REVIEW_OPTIMIZE` is the current Baseline #N.

  A review binds tenant, project, target kind and id, the exact tree digest, the candidate revision and its base, the profile pins and the evidence-manifest digest. It never creates or edits a change set, never submits, approves or applies anything, and never creates a baseline.
- **Evidence.** Each document's current revision is classified by the C3a trusted-current rule over #714 `document_artifacts`:
  - A TRUSTED revision is `TRUSTED_PROJECT_EVIDENCE`; a schedule or budget is only ever `ADVISORY_EVIDENCE`.
  - An untrusted revision enters only when the human includes it, as `PROPOSED_EVIDENCE`.
  - A WBS source is never evidence; the import under an `IMPORT_REVIEW` is `HUMAN_PROVIDED_IMPORT` (the structure under review, not proof of itself).
  - A requested document or revision outside this set is refused before any call.

  Retrieval reads only `document_chunks` stamped with an admitted (document, revision) pair, matched as exact pairs, with `tenant_id AND project_id` in the SQL. The result is bounded inside the SQL (per document and in total) in a deterministic order: well-formed chunk index, then creation time and id, with documents taking turns in evidence-class priority. A malformed or oversized chunk index never fails the read. It uses no embedding, no generic retrieval port and no wider fallback, and it fails closed without scope. RLS is the second wall, proven under a NOBYPASSRLS role.
- **Excerpts.** The canonical locator is captured from the original chunk BEFORE anonymisation. Offsets are kept only when the chunk carries exact original coordinates. The model sees only anonymised text, whose length never becomes an offset. A citation names a manifest excerpt id and is verified deterministically.
- **Privacy boundary.** Isolation markers are not anonymisation. Text is anonymised BEFORE it is truncated, so an identifier straddling a cut never survives as a fragment; a cut excerpt keeps no exact offsets. Besides the shared anonymiser, the Reviewer applies its own deterministic floor that never depends on the NER tier: checksum-validated IBAN (mod 97), NIE and DNI (control letter, dotted or not), e-mail addresses, and phone numbers in their real groupings (international with a non-zero country code, Spanish mobile and landline; a trailing full stop ends the number; amounts followed by a currency are kept). Each excerpt's transform label names the boundary that actually ran (`pii-anonymizer/v1+ner`, `pii-anonymizer/v1+regex-floor`, or `custom-unverified`); a live adapter is refused in code, by the service and by every pipeline run, unless the default boundary runs with its NER tier (`require_live_privacy`). The NER tier currently ships a Spanish model only; NER quality for other languages remains a live-integration gate. Every model-visible text passes the same anonymiser before any model-port call: evidence excerpts, the imported structure, user context, the target's node names and codes (in MAP and REDUCE), and MAP summaries forwarded into REDUCE. Canonical node ids and structural references are never anonymised, so deterministic validation resolves the original nodes. Stored targets and import snapshots are never mutated.
- **Sufficiency gate.** Without trusted scope evidence (a trusted contract or specification) or with an empty target, the run completes `INSUFFICIENT_EVIDENCE` with ZERO model calls and honest NOT_EVALUATED reasons. Without a trusted contract, `MISSING_CONTRACT_SCOPE` stays `NOT_EVALUATED(NO_TRUSTED_CONTRACT)`.
- **Bounded pipeline (§9).** The steps are:
  1. deterministic qualification;
  2. clusters (top-level branches packed or windowed by `max_cluster_nodes`);
  3. one MAP call per cluster, for findings and proposals of that cluster only;
  4. a deterministic merge and de-duplicate;
  5. one REDUCE call for the 19-dimension qualification;
  6. the PC-2b.1 validator on the assembled envelope, with nothing repaired.

  Reconciliation never lets AI soften a deterministic result or move an unavailable dimension off NOT_EVALUATED; AI may only add severity backed by validated evidence.
  - **Limits (v1):** at most 24 calls (retries included), at most 2 transient retries per call, per-call input/output caps, a total token cap, a cost cap and an elapsed-time cap.
  - **Admission:** each call is admitted by the budget and the cancellation check BEFORE it starts, and an over-limit response (reported usage, or a raw response longer than the output limit) is discarded. The REDUCE call's worst-case tokens and cost stay reserved while MAP calls are admitted. A failed or timed-out call is charged its admitted worst case. Each call is bounded by the remaining time budget. Token, cost and time caps have hard ceilings, and estimation rates are positive.
  - **Per-call size:** evidence (at most 45% of a call's input budget, the same budget that bounds the manifest), the target outline (25%, free text capped, omitted nodes counted) and REDUCE's MAP summaries (15%) are bounded, so every call fits by construction. Nothing is cut silently: a MAP cluster whose outline was cut is listed uncovered, excerpts never shown or MAP summaries cut make the run PARTIAL, and when the whole tree does not fit one REDUCE outline the tree-level qualification is not run (its AI dimensions stay NOT_EVALUATED) instead of qualifying part of the tree. A REDUCE that cannot run leaves the run PARTIAL, never FAILED. Citations and availability use only the excerpts actually shown. Within trusted evidence, documents take turns (round-robin) with the contract and scope documents first, so no document crowds out the contract.
  - **Robustness:** malformed or oversized model output fails its call, never the process. A ref repeated within one MAP response costs that item, not the run. Items refused before validation count toward the rejection-ratio gate. Persisted failure reasons never carry model text.
  - **Citations:** SUPPORTED or GAP needs a TRUSTED excerpt whose quote was VERIFIED; a quote verifies only when it is at least 8 characters and located on word boundaries.
  - **Availability:** contract and scope availability come from the TRUSTED excerpts the model actually sees, not from the document inventory.
  - **Execution configuration:** every limit is result-affecting. The limits have a canonical, versioned digest (`wbs-reviewer-execution-config/v1`) that binds the run's idempotency key and is recorded in provenance. Different limits make a new run; the same inputs and limits reuse it. FAILED and CANCELLED runs are still never reused, and a deterministic (PC-2b.2) run key is unchanged.
  - **Partial runs:** a run cut short is `PARTIAL_PROPOSAL` with the uncovered clusters listed. If no MAP call produces a valid response, or the REDUCE fails, the run is FAILED.
- **Persistence.** Runs reuse the PC-2b.2 store (`execution_type = AI`, terminal runs frozen, items immutable); there is no second store and no schema change.
  - **Transactions:** the RUNNING run is committed before any model call, so another session can see and cancel it and no lock or open transaction is held while the model works. Finalization re-reads the run under lock and keeps a state already set elsewhere. A RUNNING run whose worker was lost is reused only within its lease (time cap plus 60 s); afterwards it is failed and a new run opens. An unexpected pipeline error is persisted as FAILED with a static reason and its usage; so is a run whose finalization fails (rolled back first, never left RUNNING, with the usage of the calls already made). Every transaction after a commit binds `app.current_tenant` again, so the RLS second wall holds for status reads, finalization, items and events.
  - **Provenance:** `model_provenance` is immutable and marks offline runs `synthetic: true` and `production_invocation: false`.
  - **Usage:** it is attributed to tenant, project and run in an append-only `wbs.intelligence.run_usage` project event, holding counts only (calls, retries, tokens, cost, elapsed time, stop reason, per-call status). Evidence, prompts and model output are never logged or exported.
  - **Exposure:** no API route exposes the Reviewer, and the production Reviewer stays disabled.

## Alternatives rejected

- **AI writes the DRAFT candidate directly (model A).** Rejected because it:
  - violates human-only authoring;
  - lets reruns overwrite human edits;
  - loses rejected suggestions.
- **A persisted proposed candidate plus a manifest (model C).** Rejected because it creates a second candidate tree. The comparison it offers is delivered as a simulated read model.
- **A single composite WBS quality score.** Not defensible without calibration, and it hides NOT_EVALUATED dimensions.
- **Profiles as Skills, plugins or database records.** Rejected because they are not declarative or digestable, or are runtime-mutable, or would need an admin CMS before there is a need.
