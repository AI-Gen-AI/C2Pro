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
  - an item whose target node fingerprints changed is in CONFLICT.
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
- **Persistence is still to come.** Persistence for runs, items and decisions (PC-2b.2) and for import sources (PC-2b.3) needs new tenant-scoped tables with RLS. PC-2b.1 adds none.
- **Cost of the design.** Applying proposals is explicit work for the user. This is deliberate: a rerun can never overwrite human edits.

## Alternatives rejected

- **AI writes the DRAFT candidate directly (model A).** Rejected because it:
  - violates human-only authoring;
  - lets reruns overwrite human edits;
  - loses rejected suggestions.
- **A persisted proposed candidate plus a manifest (model C).** Rejected because it creates a second candidate tree. The comparison it offers is delivered as a simulated read model.
- **A single composite WBS quality score.** Not defensible without calibration, and it hides NOT_EVALUATED dimensions.
- **Profiles as Skills, plugins or database records.** Rejected because they are not declarative or digestable, or are runtime-mutable, or would need an admin CMS before there is a need.
