# C2Pro Planner Report - Increments I1-I14

## Executive Summary
This document is the professional execution baseline for core AI increments `I1` through `I14`, aligned with strict TDD, Hexagonal Architecture, and mandatory governance controls.

This revision upgrades the initial handoff with:
1. Readiness gates before implementation.
2. Sprint calendar with explicit sequencing.
3. Agent-level responsibilities and evidence requirements.
4. Risk register with mitigations and owners.
5. Standard acceptance criteria for technical and compliance quality.

## Strategic Objective
Deliver an end-to-end, review-gated, evidence-grounded AI decision pipeline where:
1. Every critical output is traceable to sources.
2. Confidence and impact gates are enforced before release.
3. Governance hardening (`I14`) prevents unsafe publication in all channels.

## Architectural Invariants
1. `clauses` remains source of truth for contractual traceability.
2. Every repository query must filter by `tenant_id`.
3. Domain layers remain framework-free and infra-free.
4. Cross-module communication occurs only via ports/events.
5. No scoring logic inside pure coherence rule classes.
6. No final decision package without explicit sign-off when required.

## Scope Coverage
Covered increments:
1. `I1` Canonical Ingestion Contract
2. `I2` OCR + Table Parsing Reliability
3. `I3` Clause Extraction + Normalization
4. `I4` Hybrid RAG Retrieval Correctness
5. `I5` Graph Schema + Relationship Integrity
6. `I6` Coherence Rule Engine
7. `I7` Risk Scoring + Coherence Aggregation
8. `I8` WBS/BOM Generation
9. `I9` Procurement Planning Intelligence
10. `I10` Stakeholder Resolution + RACI Inference
11. `I11` Human-in-the-Loop Enforcement
12. `I12` LangSmith Observability + Evaluation Harness
13. `I13` End-to-End Decision Intelligence Flow
14. `I14` Governance & Safety Hardening (Mandatory)

## Mandatory Pre-Execution Corrections
1. Replace imports `apps.api.src...` with `src...`.
2. Remove all `@pytest.mark.skip` in in-scope suites.
3. Remove SUT implementations embedded in test files.
4. Add Suite IDs in test and implementation docstrings.
5. Repair truncated or invalid skeletons before RED execution.
6. Normalize LangSmith interface usage (`start_span`/`end_span` or `start_run`/`end_run`) to one consistent contract per module.

## Delivery Governance
### Definition of Ready
1. Test file imports resolve.
2. Suite IDs present in docstrings.
3. No skipped tests for targeted increment.
4. Scope and dependencies recorded in backlog row.

### Definition of Done
1. RED committed and proven failing before implementation.
2. GREEN implementation passes suite without skip.
3. REFACTOR preserves green status and architecture boundaries.
4. Observability checks pass for required spans/events.
5. HITL gates pass for required high-impact or low-confidence scenarios.
6. `context/C2PRO_TDD_BACKLOG_v1.0.md` and `context/PLAN_ARQUITECTURA_v2.1.md` updated with completion marker.

## Agent Operating Model
| Agent | Responsibility | Required Evidence |
|---|---|---|
| `@qa-agent` | RED authoring and failure integrity | failing test output, no skip markers |
| `@backend-tdd` | GREEN implementation and refactor | passing suite output, architecture-safe code |
| `@security-agent` | gate bypass prevention, trace safety | security assertions and negative-path tests |
| `@docs-agent` | progress and architecture documentation | updated backlog and architecture statuses |

## Increment Dependency Graph
1. `I1 -> I2 -> I3 -> I4`
2. `I4 -> I5 -> I6 -> I7`
3. `I3 + I4 -> I8 -> I9`
4. `I3 -> I10`
5. `I6 + I7 + I10 -> I11`
6. `I4..I11 -> I12`
7. `I1..I12 -> I13`
8. `I13 -> I14`

## Sprint Plan (Starting 2026-02-16)
| Sprint | Date Window | Scope | Exit Gate |
|---|---|---|---|
| S1 | 2026-02-16 to 2026-02-27 | `I1`, `I2` | ingestion and OCR reliability green |
| S2 | 2026-03-02 to 2026-03-13 | `I3`, `I4` | extraction + hybrid retrieval green |
| S3 | 2026-03-16 to 2026-03-27 | `I5`, `I6` | graph integrity + pure rule engine green |
| S4 | 2026-03-30 to 2026-04-10 | `I7`, `I8` | deterministic scoring + evidence-constrained generation green |
| S5 | 2026-04-13 to 2026-04-24 | `I9`, `I10` | procurement intelligence + RACI integrity green |
| S6 | 2026-04-27 to 2026-05-08 | `I11`, `I12` | HITL enforcement + observability/eval harness green |
| S7 | 2026-05-11 to 2026-05-22 | `I13` | E2E orchestration with mandatory gates green |
| S8 | 2026-05-25 to 2026-06-05 | `I14` | governance hardening active in output layer |

## Increment-Level Acceptance Focus
| Increment | Core Acceptance Evidence |
|---|---|
| `I1` | chunk contract validation, typed ingestion errors, ingestion trace metadata |
| `I2` | OCR fallback trigger, table row/column preservation, low-confidence review flags |
| `I3` | normalized clause schema, actor preservation, ambiguity/manual validation flags |
| `I4` | intent router correctness, deterministic rerank, evidence threshold reviewer gate |
| `I5` | duplicate-edge semantics explicit, referential validation before edge persistence |
| `I6` | standardized alerts, neutral behavior on missing required data, per-rule observability |
| `I7` | deterministic score outputs, profile isolation by tenant/project, risk acknowledgment flags |
| `I8` | no evidence-free generation, unit normalization, low-confidence auto-accept blocked |
| `I9` | explicit lead-time tolerances, fallback warnings visible, lead approval flags |
| `I10` | canonical party resolution, single-accountable rule enforcement, ambiguity escalation |
| `I11` | confidence gate routing, SLA escalation, release requires reviewer identity and timestamp |
| `I12` | complete trace envelope in async paths, parent-child run correlation, drift alarm enforcement |
| `I13` | end-to-end gated finalization, citations required, reviewer approval unlocks package |
| `I14` | policy reason-code blocking, override by compliance only, legal disclaimer always injected |

## Risk Register
| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| Residual skipped tests | false green | fail CI if `@pytest.mark.skip` detected in scoped suites | `@qa-agent` |
| Import path drift | broken test runtime | enforce `src...` import rule in lint/check step | `@backend-tdd` |
| Trace inconsistency | missing observability lineage | standardize LangSmith adapter contract | `@backend-tdd` |
| Gate bypass in finalization | unsafe release | add negative-path E2E tests for all blockers | `@security-agent` |
| Cross-tenant config leakage | compliance breach | tenant-isolation tests for scoring/retrieval/governance | `@security-agent` |
| Documentation lag | execution ambiguity | update docs at sprint closure checkpoint | `@docs-agent` |

## Professional Delivery Controls
1. Each increment has one RED PR and one GREEN/REFACTOR PR.
2. Every PR includes explicit dependency statement.
3. Every sprint ends with a gate report: tests, coverage trend, unresolved risks.
4. Critical increments (`I11`, `I13`, `I14`) require security sign-off before close.
5. No policy override path without compliance approval evidence.

## Immediate Priority Queue
1. Complete `I13` state-gating correctness and E2E blocking assertions.
2. Complete `I14` policy engine, output guard service, and disclaimer middleware.
3. Close cross-cutting cleanup items listed under Mandatory Pre-Execution Corrections.

---

Last Updated: 2026-02-14

Changelog:
- 2026-02-14: Created initial consolidated planner report for increments I1-I14.
- 2026-02-14: Expanded into professional execution blueprint with governance, risk, sprint calendar, and acceptance controls.
