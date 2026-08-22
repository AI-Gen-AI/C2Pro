# ADR-024: Single-Document Activation — Intake → Category Coverage → Gap Alerts

**Status:** Accepted (VP product decision, 2026-08-22)
**Date:** 2026-08-22
**Deciders:** Jesús Camacho (VP Engineering / Strategic Procurement Director)
**Related:** ADR-018 (Health Vector — the surface this populates; promoted P0-now same date), ADR-009 (Coherence Score — demoted to the relational Contract-health input, same date), ADR-022 (Contract-clarity findings — same findings channel), ADR-013 (`FindingSignal` typed source), ADR-016 (Change-Impact — the *relational* wedge, sequenced after activation).

## Context

A new user creates a company, uploads **one real contract**, and gets: a 422 storm (the onboarding `start_sample_project` is a stub returning a fake non-UUID id `proj_sample_001`) and — where extraction works — a wall of ~67 clauses stuck at "Pending Review 65%", **0 alerts, no per-category view, no guidance**. The product delivers no value from the first document.

Root of it: the headline we built is the **Coherence Score** (ADR-009), which is **relational** — it measures whether the contract, schedule, and budget *agree with each other*. With one document there is nothing to reconcile, so the score is null/meaningless. The activation moment — one document, one user, minute one — is exactly where a relational score has nothing to say.

## Decision

**Invert the model for activation: a single uploaded document is decomposed into the six categories, and the product reports per-category *coverage + coherence-of-what's-present + gaps*, driving the Health Vector (ADR-018) — not the relational Coherence Score.**

Concretely, uploading one document produces:

1. **Category decomposition.** Extracted clauses are classified into the 6 categories (SCOPE, BUDGET, TIME, TECHNICAL, LEGAL, QUALITY) — reuse the existing clause classifier.
2. **Per-category state**, each returning `{state, findings, missing_data}`:
   - **Present + coherent** — the category is substantively covered by this document.
   - **Present + issues** — intrinsic findings (clause-clarity per ADR-022, internal contradictions per the cross-clause floor/LLM depth) — actionable now, from one doc.
   - **Absent / `insufficient_evidence`** — the document does not cover this category → an **honest-null gap** (ADR-018 discipline: never fabricate a green).
3. **Gap alerts = the primary output.** Every absent/insufficient category emits an actionable alert: *"No schedule detected — upload the cronograma to assess TIME"*, *"No technical specs — upload the pliego técnico"*, *"No budget/BoQ — upload it to reconcile against the contract price."* This is the guidance that makes one document immediately useful **and** tells the user exactly what to upload to unlock the relational Coherence Score.
4. **Coherence Score appears only when ≥2 reconcilable documents exist** — as the Contract-health `coherence_subscore` (ADR-009 demoted), never as the single-document headline.

**Onboarding must be real.** `start_sample_project` creates (or idempotently reuses) a genuine seeded project with a real UUID and a real sample document for the caller's tenant, so a new user lands on a working project that already shows the decomposition + gaps. No stub ids, no non-UUID routes.

## Why this is right (not a rebuild)

The infrastructure exists: pgvector embeddings, RAG retrieval, working extraction, the category classifier, the honest-null discipline (ADR-009/018), and the findings channel (ADR-022). This ADR **re-orients** them — coverage-and-gaps-first from one document — rather than building anything from scratch. It also closes concrete gaps already noted in canon: ADR-022's `coherence_subscore = None` hard-coding and the un-wired Health snapshot source.

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| Single-document → coverage + gaps (Health) | **Chosen** | Value from doc #1; honest about what's missing; drives the surface ADR-018 already made primary. |
| Keep the relational Coherence Score as the headline | **Rejected** | Structurally silent on a single document — the activation moment gets nothing (the observed failure). |
| Fabricate a category score from one document | **Rejected** | Violates INV-1 honest-null (ADR-018) — a fabricated green in EPC is unrecoverable. |

## Scope

Single-document intake pipeline → category decomposition → per-category `{state, findings, missing_data}` → gap alerts; a **real** seeded sample project on onboarding; wiring the Health Vector's Contract/Documentation dimensions from this output (closes the `coherence_subscore = None` gap). Fix the `/api/api/` dashboard prefix and the new-user retry storm (422/429) as part of making the flow real.

## Out of scope

The relational Coherence Score algorithm itself (unchanged; stays the Contract `coherence_subscore`). The Change-Impact Report (ADR-016) — the *relational* wedge, sequenced after single-document activation works. Weighting `missing_data`/findings into a composite number (deferred per ADR-018/022 honest-null discipline until pilot data confirms it).

## Success criteria

- A brand-new user/company can onboard, land on a **real** project (real UUID, zero 422/429), and upload one document.
- That upload yields a **per-category view**: covered categories with findings, absent categories as explicit gaps with a concrete "upload X" alert.
- No fabricated category green exists without supporting evidence (INV-1).
- The Coherence Score is shown only once ≥2 reconcilable documents are present, as the Contract subscore — never as the single-document headline.
