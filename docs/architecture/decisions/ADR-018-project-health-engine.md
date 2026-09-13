# ADR-018: Project Health Engine

**Status:** Accepted — **PROMOTED 2026-08-22 to P0-NOW (the primary product surface)** · build-gate lifted · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict.
**Related:** ADR-009 (honest nulls — reused); ADR-014 (entities), ADR-015 (snapshots/trends), ADR-017 (coherence input), ADR-025 (canonical WBS Project Controls backbone). Hosts INV-1 honest-null discipline.

## 2026-09-13 Amendment — Six-dimension project surface, Coherence Score and Alerts separation (GOVERNING)

**Status:** Accepted product decision, 2026-09-13. This amendment clarifies the user-facing Project Controls model without erasing the historical v0 Health design below.

### Canonical six project dimensions

The user-facing project intelligence taxonomy is shared across Health/coverage, Coherence decomposition and Alerts:

- `SCOPE`
- `BUDGET`
- `TIME`
- `TECHNICAL`
- `LEGAL`
- `QUALITY`

The earlier Contract / Risk / Documentation / Governance v0 dimensions below remain historical/internal Health inputs where useful; they are **not** a competing user-facing taxonomy.

### Health, Coherence and Alerts answer different questions

They are related but MUST NOT be collapsed into one concept:

1. **Health / evidence coverage — “Do we have enough evidence to assess this dimension?”**
   - `PRESENT` / evidence-backed values where supported.
   - `INSUFFICIENT_EVIDENCE` / `Unknown` where evidence is missing.
   - `Unknown` is never converted to `0` merely to complete a chart or aggregate.

2. **Coherence Score — “Given the available evidence, how consistent is the project state?”**
   - It is a visual project-control signal with dimensional breakdown over the six canonical dimensions where evidence is reconcilable.
   - Relational Coherence remains unavailable as a valid single-document headline; the project surface must disclose the evidence/coverage basis of any overall score.
   - A high Coherence Score does **not** imply the project is healthy in the business sense. Example: all sources may consistently show a seven-day delay (high coherence) while a `TIME` alert is `CRITICAL`.
   - Overall/project roll-up must expose coverage and exclude unsupported dimensions rather than silently scoring them as zero.

3. **Alerts — “What concrete situation requires attention?”**
   - Alerts use the same six canonical dimensions as their **category**.
   - Their **trigger** is a separate concept (`missing_evidence`, `deadline`, `deviation`, `contradiction`, `material_change`, etc.).
   - Alerts compare an expected state with an observed state and retain evidence for both when available.

### WBS drill-down

Project-level Health/Coherence/Alerts may drill down through the **single canonical hierarchical WBS** defined by ADR-025. Discipline branches are not separate WBS structures.

Where evidence supports it, a user may navigate conceptually:

`Project -> WBS branch -> Work Package -> six-dimension state -> alert/change -> source evidence`.

No WBS-level or project-level score may use a blind arithmetic average or convert unknown children to zero. Future roll-up rules must explicitly account for evidence coverage/materiality/criticality.

## 2026-08-22 Amendment — PROMOTED to P0-now; this is the product surface (GOVERNING)

**Status:** Accepted (VP product decision, 2026-08-22). A new user uploaded one real contract and hit only 422s + a wall of un-actionable "Pending Review 65%" clauses — because we built the *Coherence Score* (the dimension this ADR explicitly demotes) and left **this** engine — the Health Vector, the actual "is my project on track?" surface — as an un-wired v0 scaffold. Corrections, effective now:

1. **Build-gate lifted.** The prior gate ("no Health wiring until a Contract Manager uses Change-Impact weekly") is void — it starved the surface that *creates* the first user. Health v0 (Contract / Risk / Documentation / Governance) is wired **now**.
2. **Single-document first (see ADR-024).** The Health Vector must produce value from **one** uploaded document: dimensions populate from what that document supports; every unsupported dimension returns **honest-null `missing_data`** — surfaced as *"missing: upload the schedule / budget / technical pliego."* This gap-alerting is the onboarding product, not a footnote.
3. **Coherence Score is one input here (ADR-009 demoted).** It feeds the **Contract** dimension's `coherence_subscore`; it is not the headline. The `coherence_subscore = None` hard-coding noted in ADR-022 is the concrete gap to close.
4. **`missing_data` / `insufficient_evidence` is the primary signal, not an edge case.** For a single-doc project most dimensions are legitimately Unknown; saying so honestly + telling the user what to upload IS the value.

The v0 dimension design below is unchanged and correct — it is now the top build priority, wired live and driven by single-document intake.

## Context

**Coherence ≠ Health.** Coherence answers "do the documents agree?"; buyers ask "is my project on track?" — a different question. There is **no `project_health` concept in the codebase**. Coherence is being overloaded to carry a question it cannot answer.

## Decision

A **multi-dimensional, confidence-weighted Health Vector** with honest nulls. **Coherence is demoted to one input of Contract health.**

| Dimension | Inputs | v0/v1 | Confidence driver |
|---|---|---|---|
| Contract | obligations, clauses, **coherence subscore**, LDs, COs | **v0** | clause coverage |
| Risk | risk items, severity, mitigation, aging | **v0** | extraction quality |
| Documentation | ingestion coverage, parse success, `degraded`/`failed` node count (ADR-013) | **v0** | meta-signal |
| Governance | HITL approvals, alert SLA breaches, audit completeness | **v0** | workflow coverage |
| Schedule | activities, dates, %complete, baseline | **v1** (needs schedule ingest) | dated-activity coverage |
| Cost | budget, committed, actuals, COs | **v1** | actuals presence |
| Deliverables | WBS/scope vs progress | **v1** | scope completeness |

- **Score and confidence are separate axes.** Every dimension returns `{score|null, confidence, evidence[], trend, missing_data}`.
- **Bands, not false precision:** Healthy 80–100 · Watch 60–79 · At-Risk 40–59 · Critical 0–39 · **Unknown = insufficient evidence**.
- **Honest nulls (INV-1 / ADR-009):** distinguish `budget_exhausted` from `insufficient_evidence`; **never fabricate a green.**
- **Composite** = confidence-weighted roll-up over *available* dimensions; thresholds **adaptive by project profile**, weights configurable (defaults equal within available dimensions). "Invariant by formula, adaptive by profile."

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| Phased v0 (4 dims) → v1 (7 dims) | **Chosen** | v0 dims are buildable from data already extracted (30–90 days); v1 waits on ingestion — avoids fake precision. |
| Ship all 7 dimensions in v0 | **Rejected** | Schedule/Cost without baselines produce fabricated or perpetually-"unknown" scores that do not sell (Challenger Risk #2). |
| Single composite number | **Rejected** | Hides the dimensional truth executives need; one wrong green destroys trust. |

## Consequences

**Positive:** the first real executive value; the number every persona asks for; trend-based early warning emerges from snapshots (ADR-015).
**Negative:** trust is fragile — a wrong green is unrecoverable in EPC; the honest-null discipline is non-negotiable. Weight calibration requires real data (log queries to calibrate over time).

## Scope
Health Vector; **v0 dimensions Risk / Contract / Documentation / Governance** with honest nulls, confidence, trend; coherence demoted to Contract subscore; snapshot-backed trends.

## Out of scope
Schedule / Cost / Deliverables scoring before baseline ingestion (ADR-018 v1, gated on P6/MSP/Excel ingestion); a single composite score without dimensional breakdown.

## Dependencies
ADR-014, ADR-015; coherence input from ADR-017; ADR-025 for the canonical WBS backbone.

## Success criteria
- Dashboard renders the v0 vector with per-dimension score, confidence, trend arrow, and explicit `insufficient_data`.
- A "green" is structurally impossible without supporting evidence (INV-1).
- Health trend over the last *N* snapshots is queryable.
- User-facing project intelligence preserves the six canonical dimensions (`SCOPE/BUDGET/TIME/TECHNICAL/LEGAL/QUALITY`) across Health/Coherence/Alerts.
- Coherence Score, when available, discloses the evaluated coverage and never turns unknown dimensions into zero.

## Implementation note
Thin-Spine, **Month 3** (v0 dimensions on existing data). v1 dimensions gated behind the pilot and schedule/cost ingestion (Month 6).