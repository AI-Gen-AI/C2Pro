# ADR-013: Typed Graph Contract & Runtime Correctness Baseline

**Status:** Accepted — P0 (Foundation) · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict (`docs/audits/`).
**Related:** ADR-009 (honest scoring — discipline reused); ADR-014 (Project State Model); ADR-017 (ProjectGraph). Hosts cross-cutting invariant **INV-1**.

> **Numbering note.** The v3.0 canon (ADR-013 → ADR-021) starts at 013 to avoid collision with the in-flight evidence-layer ADRs ADR-010 (Evidence Maturity), ADR-011 (Evidence Intelligence), ADR-012 (deferred), which are referenced in `CHANGELOG.md` / `CLAUDE.md` but not yet filed in `decisions/`. When those are filed, the evidence layer they describe is the substrate INV-1 extends.

## Context

The live LangGraph state (`apps/api/src/analysis/adapters/graph/schema.py`) is a flat `TypedDict` whose domain values are all `dict[str, Any]` (`Risk = dict[str, Any]`, `Task`, `Citation`, …). Three runtime defects compound on top of this and were named by every audit:

1. **Silent failure swallowing.** Pervasive `except Exception: return []` / `return None` in nodes (N6, N8, N10, stakeholder/KG extractors) makes a *crashed extractor* indistinguishable from a *clean "0 findings"* result. For an intelligence product this manufactures false confidence.
2. **Mixed mutation contract.** Sequential nodes mutate `state` in place and return it; parallel nodes return dict patches. The inconsistency is a latent concurrency footgun.
3. **Degraded-by-default headline feature.** N8 calls the coherence subgraph with `low_budget_mode=True` (LLM/RAG skipped) and a signature drift on `seed_signals`/`seed_coverage`. The differentiator runs degraded in the default path.

Building project-level synthesis (ADR-014 → ADR-020) on this substrate would compound the fragility irreversibly. This ADR is the precondition for the entire canon.

## Decision

1. **Type material channel values with Pydantic v2** — `RiskItem`, `WbsActivity`, `BudgetItem`, `Citation`, `DocumentArtifact`, `CoherenceFinding`. Keep the LangGraph `TypedDict` channels; type the *values*.
2. **Mandate a uniform return type on material nodes** (extractors and synthesis nodes — not trivial passthroughs):
   ```python
   class NodeResult(BaseModel):
       status: Literal["ok", "degraded", "failed", "skipped"]
       data: BaseModel | list[BaseModel] | None = None
       error: ErrorRecord | None = None        # persisted to the errors/events table — never swallowed
       confidence: float | None = None
       degradation_reason: str | None = None
   ```
   `degraded` / `failed` propagate as a **Documentation-health signal** (consumed by ADR-018), never as a silent empty.
3. **Ban silent fallbacks globally.** No node may return `[] / None / {}` as a substitute for a caught failure. Errors are recorded; failure is visible.
4. **Fix the coherence node signature drift** and add a **CI contract test** that fails the build on any graph-node signature mismatch.
5. **Remove `low_budget_mode` as the project-path default.** It survives only as an explicit per-call cost ceiling, gated by decision-value (a project re-score is worth an LLM call) — see ADR-017.

### Cross-cutting invariant INV-1 — Evidence & Provenance (tiered)

> Every material output carries an `EvidenceRef(document_revision_id, source_location, extraction_method, model/rule_version, confidence)` and a tier ∈ `{verified, weak, inferred, unverified}`.
>
> **Hard gate (CRITICAL outputs only):** an output with no `verified`/`weak` evidence may **not** appear as a critical alert, an executive claim, or a scored health dimension — it surfaces as `needs_review` instead.
>
> **Honest nulls (reuse ADR-009):** absence of evidence yields `null` + reason, never `0` or `100`.

INV-1 **extends the existing evidence layer (ADR-010/011); it is deliberately *not* a new ADR.** The absolute "no evidence → no output anywhere" veto proposed by some blueprints is **rejected** (it makes bad-OCR / partial-integration projects produce nothing); the tiered gate above is adopted instead.

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| Universal `NodeResult` envelope on **every** node | **Rejected** | Ceremony + LangGraph-integration friction on trivial passthroughs (Challenger Risk #3). Envelope is required only on material nodes; silent-failure ban is universal. |
| Defer typing until after the spine is built | **Rejected** | Compounds fragility at the exact layer 17+ nodes share; unsafe to build synthesis on it. |
| A separate "Evidence & Provenance" ADR | **Rejected** | Duplicates in-flight ADR-010/011 (Claude + Challenger). Captured as INV-1 here. |
| Absolute evidence veto ("no evidence → no contribution") | **Rejected** | Renders real-world partial documents useless (Challenger Risk #5). Tiered gate adopted. |

## Consequences

**Positive:** eliminates false-confidence "0 findings"; gives the UI a `clean` vs `degraded` distinction; unblocks safe refactoring; data-quality becomes a first-class health input.
**Negative:** one-time migration of node return sites; a transient *spike in surfaced failures* — these were always present, merely hidden. This must be communicated as a feature, not a regression.

## Scope
Typed material payloads; `NodeResult` on material nodes; global silent-failure ban; coherence signature fix + CI gate; removal of `low_budget_mode` default; INV-1 definition.

## Out of scope
Envelope on trivial passthrough nodes; the Project State redesign (ADR-014); repository hygiene / secret-scan (parallel chore, tracked separately).

## Dependencies
None. **This is the first ADR; everything else depends on it.**

## Success criteria
- Zero silent failures in extraction nodes (audited).
- CI fails on graph-node signature/type drift.
- The coherence path runs without the `low_budget_mode` default; no signature mismatch.
- UI and downstream nodes can distinguish `ok` / `degraded` / `failed`.

## Implementation note
Thin-Spine, **Weeks 1–2**. Honors the locked invariant *no `commit()` inside repositories*. Ships behind the existing test suite + the new CI signature gate (this is the one non-flaggable change in the canon).
