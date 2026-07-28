# ADR-022: Contract Clarity Findings — Health v0, Findings-Only

**Status:** Accepted — P2 · C2Pro v3.0 canon · extends ADR-018
**Date:** 2026-07-28
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Resolves TASK-V3-P1-SCOPE-11 (backlog decision point, logged 2026-06-29).
**Related:** ADR-018 (Project Health Engine — hosts this dimension's findings), ADR-009 (Coherence Score v2 — the surface this decision keeps clean), ADR-013 (typed graph contracts — `FindingSignal` source type).

## Context

TASK-V3-P1-SCOPE-11 asked a product/design question left open by ADR-018: the qualitative clause-clarity rules (`R-SCOPE-CLARITY-01`, `R-PAYMENT-CLARITY-01`, `R-SCHEDULE-CLARITY-01`, `R-TECHNICAL-SPEC-CLARITY-01`, `R-RESPONSIBILITY-01` — defined in `coherence/qualitative_rules.yaml`) evaluate a **single clause in isolation** ("is this clause's language ambiguous/undefined?"). This is structurally different from the Coherence Score™'s core thesis, which is **relational**: "do two or more documents/clauses agree with each other?" (budget reconciliation, cross-document RESPONSIBILITY evidence, schedule-vs-contract dates, etc.).

Today these rules run inside the coherence engine's LLM semantic layer and emit `FindingSignal`s like every other coherence rule. Left there, they are an intrinsic (single-clause) signal masquerading as a relational (cross-document) one — see "Options considered" below for why that is a problem, not just an inconsistency.

Three options were on the table (backlog entry, 2026-06-29):
- **(A)** Fold them into Coherence v1 as a `CONTRACT_QUALITY` sub-dimension.
- **(B)** Hoist them into Health v0 as `contract_clarity_findings`.
- **(C)** Keep them in the LLM semantic layer as an optional, separate `contract_quality_score`.

## Decision

**Option (B).** Clause-clarity findings are hoisted into **Health v0** as `contract_clarity_findings` — a **findings-only** list attached to the `HealthVector`, structurally independent of every scored `HealthSignal` dimension (including `HealthDimension.CONTRACT`, per ADR-018 §Contract).

**HARD CONSTRAINT — v0 emits findings, not a score:**
- Each `ContractClarityFinding` carries `severity` (categorical: critical/high/medium/low/info) and evidence (`clause_id`, `rule_id`, `summary`, `quote`). It carries **no numeric score, confidence, or weight field** — nothing an aggregator could sum or average.
- `contract_clarity_findings` is **not** included in `assemble_health_vector`'s `signals` weighted rollup and **does not** contribute to `HealthVector.composite_score`. There is no `contract_clarity` health dimension, band, or aggregate number in v0.
- Clause-clarity findings are **not** folded into the Coherence Score (rejects option A) and **not** exposed as a second, competing score alongside it (rejects option C).

Why not (A) — folding into Coherence Score: the Coherence Score's whole sales thesis is *relational* incoherence between documents. An intrinsic, single-clause signal (this sentence is vague) does not test agreement between anything. Mixing intrinsic and relational signals into one number means the score can move for a reason that has nothing to do with document disagreement, which **poisons score comparability under score versioning** (ADR-009 `score_version`) — a score delta between two versions would become unexplainable without knowing whether clause language changed vs. whether documents started disagreeing.

Why not (C) — a second competing score: a second "quality score" sitting next to the Coherence Score dilutes the one number the product sells and re-introduces the same premature-precision risk ADR-018 already rejected for a single composite Health number ("hides the dimensional truth... one wrong green destroys trust").

Why (B) is right: Health v0 already exists as the home for "is my project on track" signals distinct from Coherence's "do the documents agree" question (ADR-018 §Context). Clause clarity is exactly that kind of contract-quality signal — informative to a Contract Manager, not comparable across score versions, and not required to move a single number to be useful. Surfacing it as evidence (findings) rather than a score keeps it honest: there is no invented weighting formula for "how much does one vague clause matter," and none is needed for v0 to be useful.

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| (B) Findings-only hoist into Health v0 | **Chosen** | Matches ADR-018's existing intrinsic/relational split; no fabricated weighting; zero risk to Coherence Score comparability. |
| (A) Fold into Coherence v1 as `CONTRACT_QUALITY` | **Rejected** | Backward-compatible on the surface but semantically wrong — intrinsic signal mixed into a relational score poisons comparability under score versioning (ADR-009). |
| (C) Separate `contract_quality_score` | **Rejected** | A second competing number dilutes the one score C2Pro sells; repeats the premature-single-number mistake ADR-018 already rejected for Health. |
| Weighted `contract_clarity` Health dimension now | **Rejected (deferred)** | No real user has confirmed clause ambiguity needs to move a number yet — inventing a weighting formula pre-emptively is exactly the fabricated-precision risk ADR-018's honest-null discipline exists to prevent. |

## Consequences

**Positive:** clause-level ambiguity becomes visible to Contract Managers without touching the Coherence Score's comparability guarantees; zero new fabricated-precision surface; the finding shape (severity + evidence, no score) is trivially cheap to extend later if scoring is confirmed to matter.
**Negative:** contract-clarity findings do not (yet) move any single number — a Contract Manager who wants "one score to worry about" for clause quality does not get one in v0. This is deliberate: fabricating that number before real usage data exists would be premature precision (same failure mode ADR-018's honest-null discipline exists to prevent).

## Scope
`ContractClarityFinding` domain model (`health/domain/contract_clarity.py`) — `rule_id`, `clause_id`, `severity`, `summary`, `quote`, no numeric fields. A pure, read-only extraction function (`health/application/contract_clarity_findings.py`) that filters coherence `FindingSignal`s by `CONTRACT_CLARITY_RULE_IDS` (the 4 `R-*-CLARITY` rules + `R-RESPONSIBILITY-01`) and projects them into that shape. `HealthVector.contract_clarity_findings: list[ContractClarityFinding]` as an additive field, independent of `dimensions`/`composite_score`.

## Out of scope
Weighting or scoring `contract_clarity_findings` into any composite number (this ADR, any dimension, or the Coherence Score) — deferred until **≥2 of Julio/Rafael/Francisco** (pilot Contract Managers) confirm clause ambiguity is a scored need, not just a visible-findings need. Live wiring of the extraction function into `SnapshotWriter`'s coherence-signal source is deferred — `SnapshotWriter.write_snapshot` does not yet have a live `FindingSignal` source available (`coherence_subscore` is itself still hardcoded `None` there, a pre-existing gap this ADR does not close). Any change to the Coherence scorer itself (`coherence/graph/`, `coherence/rules_engine/`) — this hoist is a pure downstream projection of coherence's existing `FindingSignal` output; it reads, never writes, coherence internals.

## Dependencies
ADR-018 (hosts the `HealthVector` this field is attached to); ADR-013 (`FindingSignal` as the typed source of clause-clarity rule results); ADR-009 (the score-versioning comparability this decision protects).

## Success criteria
- `contract_clarity_findings` is queryable per-project as a findings list (severity + evidence), independent of `HealthVector.composite_score`.
- No code path sums, averages, or otherwise aggregates `ContractClarityFinding.severity` into a number.
- The Coherence Score's rule set and scoring logic are unchanged by this decision (verified: `coherence/graph/`, `coherence/rules_engine/` untouched by the implementing change).

## Implementation note
v0 scaffold only: domain model + pure extraction function + additive `HealthVector` field, unit-tested in isolation. Live wiring into the snapshot-writing pipeline and any future weighting decision are explicitly deferred per "Out of scope" above.
