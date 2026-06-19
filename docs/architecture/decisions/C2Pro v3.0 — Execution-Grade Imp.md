C2Pro v3.0 — Execution-Grade Implementation Plan

  SDD → Contract-First → TDD → Multi-Agent Execution · Plan date 2026-06-07 · Canon: ADR-013→021
  Scope guardrail: spine only (Time · Change · Health · Evidence · Action). Procurement & Stakeholder Intelligence = reserved seams only. No rewrite.

  ---
  1. Implementation Strategy

  Chosen approach: ADR-anchored → Spec-Driven (SDD) → Contract-First → Test-Driven (TDD), with BDD only at persona seams. Not one methodology — a layered
  pipeline where each layer feeds the next and each is owned by the agent best at it.

  ┌────────────────┬─────────────────────────────────────────────┬──────────────────────────────────────────────┬──────────────────────────────────┐
  │     Layer      │                   Purpose                   │            Why it's required here            │     Tooling already in repo      │
  ├────────────────┼─────────────────────────────────────────────┼──────────────────────────────────────────────┼──────────────────────────────────┤
  │ ADR (done)     │ The why/what at architecture altitude       │ Decided & ratified (013–021). Do not         │ docs/architecture/decisions/     │
  │                │                                             │ re-litigate.                                 │                                  │
  ├────────────────┼─────────────────────────────────────────────┼──────────────────────────────────────────────┼──────────────────────────────────┤
  │ SDD            │ Turn each ADR into a testable spec          │ The bridge from architecture to tests; the   │ openspec/, pnpm verify:openspec, │
  │                │ (requirements + acceptance scenarios)       │ shared artifact multiple agents read         │  sdd-* skills                    │
  ├────────────────┼─────────────────────────────────────────────┼──────────────────────────────────────────────┼──────────────────────────────────┤
  │                │ Freeze the interfaces (Pydantic models,     │ The #1 defect is untyped state + signature   │ Pydantic v2, make openapi,       │
  │ Contract-First │ NodeResult, repo Ports/Protocols, event     │ drift. Contracts are what let 4 agents work  │ Protocol ports                   │
  │                │ schemas, OpenAPI) before code               │ in parallel without merge chaos.             │                                  │
  ├────────────────┼─────────────────────────────────────────────┼──────────────────────────────────────────────┼──────────────────────────────────┤
  │                │                                             │ User mandate (80% coverage); tests are the   │                                  │
  │ TDD            │ Red→green→refactor against the contracts    │ executable spec; protects an AI-written      │ pytest, tests/, C2PRO_AI_MOCK=1  │
  │                │                                             │ codebase from AI blind spots                 │                                  │
  ├────────────────┼─────────────────────────────────────────────┼──────────────────────────────────────────────┼──────────────────────────────────┤
  │ BDD (seams     │ Gherkin acceptance for user-observable      │ Change-Impact Report, Health Vector, HITL    │ tests/golden/, tests/evals/,     │
  │ only)          │ behavior                                    │ review are persona-facing; their scenarios   │ golden-corpus CI                 │
  │                │                                             │ become golden/eval cases                     │                                  │
  └────────────────┴─────────────────────────────────────────────┴──────────────────────────────────────────────┴──────────────────────────────────┘

  The canonical loop per ADR (repeat for each phase):
  ADR → openspec change (SDD: requirements + scenarios)
      → contracts frozen (types/ports/events/OpenAPI) + contract tests RED
      → TDD: unit/integration tests RED → implement → GREEN → refactor
      → BDD acceptance (persona seams) → golden/eval case
      → feature-flag + canary 10→50→100% (ADR-009 pattern)
      → quality gates green → merge → integrator (Opus) reconciles

  Why this beats alternatives: pure TDD lacks architectural guardrails and a shared multi-agent spec; pure SDD/BDD under-specifies the typed contracts
  that are the actual gap; contract-first is non-negotiable because parallel agents must agree on interfaces first. ADR-driven is the spine that keeps
  all of it from drifting.

  Rule for multi-agent parallelism: contracts are frozen by a single owner (Claude Sonnet) before any implementer touches code. Agents may only
  parallelize behind frozen contracts. Changing a contract requires re-freeze + notify — never a silent edit.

  ---
  2. Delivery Phases

  ▎ Legend per phase: Obj · Tasks · Touches · Accept · Tests · Rollback · Deps. Phases 0–3 = Thin Spine (build now). Phases 4–6 = build now but
  ▎ 018-v1/semantic-L2 gated. Phases 7–8 = gated behind one real Contract-Manager using the Change-Impact loop weekly (per canon); planned at coarse
  ▎ grain, re-planned at the gate.

  Phase 0 — Repo Safety & Baseline (precondition; ~3 days)

  - Obj: make the repo safe to run a 4-agent loop against; establish the v3 branch, flags, and a green baseline.
  - Tasks: create feat/v3-spine integration branch + per-phase branches; root hygiene (move the 25 stray *.py and 15 *.txt at repo root into
  scripts/legacy/ or delete; remove nul, test.db, committed logs, the malformed C:Users…md filename); add CI secret-scan; confirm make lint typecheck
  test green at HEAD; register a feature_v3_* flag namespace in core/feature_flags/; snapshot baseline coverage numbers.
  - Touches: repo root, .gitignore, .github/workflows/ (add secret-scan), apps/api/src/core/feature_flags/.
  - Accept: clean git status except intended; CI green; secret-scan passing; feature_v3_spine flag exists (default off).
  - Tests: existing suite green; new secret-scan job green.
  - Rollback: branch-only; nothing in prod paths.
  - Deps: none.

  Phase 1 — ADR-013 Runtime Trust (Sprint 1; 2 weeks — detailed in §6)

  - Obj: typed material payloads, NodeResult, silent-failure ban, coherence signature fix, low_budget_mode default removal, CI graph-contract test,
  doc-health degradation signals. INV-1 honest-null discipline introduced.
  - Touches: analysis/adapters/graph/schema.py, nodes.py, nodes_extended.py (esp. :242), coherence/graph/graph.py (:263), analysis/domain/,
  tests/unit/analysis/graph/, tests/contract/, tests/ci/, .github/workflows/tests.yml.
  - Accept: zero except: return [] in material nodes; CI fails on node-signature drift; coherence path runs without low_budget_mode default and without
  kwarg mismatch; NodeResult{ok|degraded|failed|skipped} on extractor + synthesis nodes; degraded/failed surface as a documentation-health signal.
  - Tests: §5 gates — type, unit, graph-contract, no-silent-failure, evidence honest-null.
  - Rollback: typing is non-flaggable (covered by tests); behavioral changes (low_budget_mode removal) behind feature_v3_coherence_llm flag + canary.
  - Deps: Phase 0.

  Phase 2 — ADR-014 Project State Model (~3 weeks)

  - Obj: ProjectState aggregate + canonical entities + lifecycle_status + provenance + reserved future seams.
  - Tasks: define aggregate + entity Pydantic/domain models; repository Ports (Protocol) + SQLAlchemy adapters (no commit() in repos); Alembic migration;
  compatibility adapter mapping current per-document outputs → project entities; reserved nullable seams (procurement_refs, stakeholder fields, doc_type
  reserved enums) — no logic.
  - Touches: new apps/api/src/project_state/ (domain/application/ports/adapters), apps/api/alembic/versions/, shared_kernel/enums.py,
  tests/unit/project_state/, tests/integration/project_state/, tests/security/ (RLS).
  - Accept: Clause→WbsActivity→BudgetItem traversable within the aggregate; existing projects migrate behind adapter, no data loss; reserved seams
  persist nullable with no future-domain code.
  - Tests: unit (entities/lifecycle), integration (repo + migration up/down), RLS/tenant, no-commit()-in-repo static test.
  - Rollback: additive tables; migration downgrade() verified; aggregate read path behind feature_v3_project_state.
  - Deps: ADR-013.

  Phase 3 — ADR-015 Temporal Layer (~3 weeks; revisions first)

  - Obj: content-addressed DocumentRevision lineage → then ProjectEvent log + ProjectSnapshot + retention.
  - Tasks: promote reupload hash to durable DocumentRevision (R2 object + row, parent_revision_id, valid_from/to); append-only ProjectEvent (jsonb, RLS,
  reserved procurement.*/stakeholder.* namespaces); append-only ProjectSnapshot (INSERT-only); snapshot triggers (revision ingest, graph complete, HITL
  change, daily Celery, baseline change); retention/partition policy (daily 90d → weekly; monthly partitions).
  - Touches: documents/application/reupload_document_use_case.py, new temporal/ module, core/tasks/ (snapshot Celery job), Alembic,
  tests/integration/temporal/, tests/security/.
  - Accept: every upload → durable comparable revision; "what changed since revision N / last week" answerable from stored data; storage bounded by
  enforced retention.
  - Tests: integration (revision lineage, snapshot write/read), migration up/down, RLS, retention-policy test, append-only constraint test (UPDATE
  rejected).
  - Rollback: append-only ⇒ safe if unread; revision write behind feature_v3_temporal.
  - Deps: ADR-014.

  Phase 4 — ADR-016 Semantic Diff v0 (~3 weeks; L1 contracts, then gated L2)

  - Obj: L1 structural diff (contracts) → first Change-Impact Report; anchor-resolution with match_confidence.
  - Tasks: structural diff on extracted clause structures keyed on stable anchors (clause_id); ChangeSet/SemanticChange typed models; anchor resolver
  (deterministic → fuzzy fallback + confidence); evidence-gated report (INV-1). L2 semantic-LLM diff is built but flag-gated behind the pilot.
  - Touches: new change_intelligence/ module, documents/ clause extraction, tests/unit/change_intelligence/, tests/golden/ (diff fixtures of real
  revision pairs), tests/integration/.
  - Accept: a contract revision yields an evidence-cited ChangeSet naming specific clause changes + ≥1 cross-doc conflict; below-confidence anchors
  flagged needs_review, never asserted.
  - Tests: unit (diff/anchor), golden (real Rev C→D pairs), evidence-gate test, L1 zero-LLM-cost assertion.
  - Rollback: read-only artifact; behind feature_v3_change_impact.
  - Deps: ADR-014, ADR-015, INV-1.

  Phase 5 — ADR-017 ProjectGraph Skeleton (~3 weeks)

  - Obj: Tier-2 ProjectGraph, async (Celery-triggered), cross-doc coherence LLM-on + canaried.
  - Tasks: type Tier-1 DocumentArtifact contract; build Tier-2 ProjectGraph (small typed ProjectGraphState): load artifacts → align entities → cross-doc
  coherence (LLM-on) → diff impact (016 L3) → health (018) → snapshot delta → alert routing; async trigger on artifact change; Send() fan-out (serial
  first); cost governance (throttle/DLQ/per-tenant concurrency).
  - Touches: analysis/adapters/graph/ (Tier-1 typing), new analysis/adapters/graph/project_graph.py, core/tasks/, tests/unit/analysis/graph/,
  tests/integration/, tests/perf/.
  - Accept: cross-doc coherence runs always-on (LLM-on) per project change, async, within SLA; upload latency unaffected; canaried 10→50→100%.
  - Tests: graph-contract (Tier-1↔Tier-2), integration (async trigger), perf/cost (concurrency caps, DLQ on failure), canary metric gate.
  - Rollback: flag feature_v3_project_graph; disabling reverts to current per-document behavior, zero data loss (snapshots append-only).
  - Deps: ADR-013, ADR-014; consumes 016/018.

  Phase 6 — ADR-018 Health Engine v0 (~3 weeks; v0 dims now, v1 gated)

  - Obj: Health Vector v0 (Risk/Contract/Documentation/Governance), honest nulls, confidence separate from score, snapshot trends. Coherence demoted to
  Contract subscore.
  - Tasks: dimension scorers (v0); banded output + insufficient_data; trend from ProjectSnapshot; wire into ProjectGraph + dashboard contract (regenerate
  OpenAPI). Schedule/Cost/Deliverables = v1, deferred to ingestion.
  - Touches: new health/ module, coherence/ (subscore demotion), apps/web/ health view (contract only), docs/api/openapi.yaml (regen),
  tests/unit/health/, tests/golden/.
  - Accept: dashboard renders v0 vector with score+confidence+trend+insufficient_data; a green is impossible without evidence (INV-1).
  - Tests: unit (each dimension incl. honest-null branch), golden (health fixtures), evidence-gate, OpenAPI drift gate.
  - Rollback: behind feature_v3_health; coherence path unchanged if off.
  - Deps: ADR-014, ADR-015; coherence input from ADR-017.

  Phase 7 — ADR-019 / ADR-020 Action & Review Loop (GATED; ~5 weeks)

  - Obj: ActionItem correlation (2 rules) + Contract-Manager HITL queue + active-learning loop. Single persona, single queue.
  - Tasks: correlation engine (group-by-revision, group-by-shared-entity) + severity×confidence×impact ranking + dedupe/suppress; minimal org/role model;
  productize langgraph.interrupt → CM queue; policy-driven routing (replace hardcoded <0.5); dispute-grade audit trail; HITL correction → golden corpus
  → regression.
  - Touches: alerts/ (extend to ActionItem), modules/hitl/, ai_feedback/→golden/ wiring, apps/web/ review queue,
  tests/{unit,integration,golden,security}/.
  - Accept: one revision → one change-impact ActionItem (not 50); CM reviews/corrects/approves in <2 min; every correction → golden case in CI.
  - Tests: unit (correlation/dedupe), integration (queue+resume), golden (correction→eval), RLS, fallback-path alert test.
  - Rollback: behind feature_v3_action_review; alerts revert to current behavior.
  - Deps: ADR-016, ADR-018 (019); ADR-017, ADR-019 (020). Pilot gate.

  Phase 8 — ADR-021 Deferred Read Models (P3; coarse)

  - Obj: snapshot-projection layer + Morning Briefing delivery + portfolio rollup. Read-only; UI = separate PRD epic.
  - Tasks: projection over ProjectSnapshot deltas; digest delivery (email/Slack); portfolio R/A/G query; all figures evidence-backed.
  - Accept: briefing generated from snapshot deltas, zero new source-of-truth; every figure traces to evidence.
  - Tests: unit (projection), golden (briefing fixture), evidence-trace.
  - Rollback: read-only; behind feature_v3_briefing.
  - Deps: ADR-015/018/019. Build only after pilot traction.

  ---
  3. Task Breakdown (tickets)

  ▎ ID scheme V3-P{phase}-{ADR}-{nn}. Full detail for the actionable Thin Spine (P0–P3); P4–P8 listed at epic/ticket-stub grain (re-expanded when each
  ▎ phase opens). Every ticket inherits the global constraints (no rewrite, no procurement/stakeholder logic, no silent failures, no fake health, no
  ▎ evidence-free critical output, no commit() in repos).

  Phase 0

  - V3-P0-ENV-01 — Integration branch + flag namespace. Goal: feat/v3-spine + feature_v3_* registered. Out: any feature code. Files: core/feature_flags/.
  Tests: flag defaults-off unit. Done: flag togglable in tests.
  - V3-P0-HYG-02 — Root hygiene + secret scan. Goal: remove/relocate stray root files; add CI secret-scan. Scope: repo root, .gitignore,
  .github/workflows/secret-scan.yml. Out: src changes. Tests: secret-scan green. Done: clean git status, CI green.
  - V3-P0-BASE-03 — Baseline green + coverage snapshot. Goal: record baseline make test + coverage. Done: numbers recorded in PR description.

  Phase 1 — ADR-013 (see §6 for sprint detail)

  - V3-P1-013-01 — Contract: domain payload models. Goal: RiskItem, WbsActivity, BudgetItem, Citation, DocumentArtifact, CoherenceFinding (Pydantic v2).
  ADR-013. Scope: new analysis/domain/contracts.py. Out: changing node logic. Files: analysis/domain/contracts.py, tests/unit/analysis/contracts/. Tests:
  model validation unit (RED first). Done: models frozen + 100% validation coverage; published as the shared contract for other agents.
  - V3-P1-013-02 — Contract: NodeResult envelope + ErrorRecord. Goal: the status envelope for material nodes. Scope: analysis/domain/node_result.py. Out:
  applying it (that's -04). Tests: unit incl. degraded/failed serialization. Done: type frozen.
  - V3-P1-013-03 — Graph-contract CI test. Goal: a test that fails on graph-node signature/return drift; wire into tests.yml. Files:
  tests/contract/test_graph_node_contracts.py, .github/workflows/tests.yml. Tests: it must RED against current drift, GREEN after -05. Done: CI gate
  active.
  - V3-P1-013-04 — Apply NodeResult + ban silent failures (material nodes). Goal: replace except: return []/None with NodeResult(failed, error=…)
  persisted to errors/events; type channel values. Files: nodes.py, nodes_extended.py, schema.py. Out: trivial passthrough nodes. Tests:
  no-silent-failure test (inject extractor exception → assert failed + error recorded, not []). Done: zero silent fallbacks in material nodes.
  - V3-P1-013-05 — Fix coherence signature drift. Goal: reconcile N8 (nodes_extended.py:~238-250) passing seed_signals/seed_coverage with
  evaluate_coherence_async() (coherence/graph/graph.py:263) signature. ADR-013. Tests: graph-contract test (-03) green; unit on N8→subgraph call. Done:
  no kwarg mismatch; signature explicit.
  - V3-P1-013-06 — Remove low_budget_mode default (project path). Goal: drop the low_budget_mode=True default at nodes_extended.py:242; gate LLM by
  decision-value behind feature_v3_coherence_llm + canary. Tests: unit (default path now LLM-on under flag), canary metric stub. Done: headline path no
  longer degraded-by-default.
  - V3-P1-013-07 — Documentation-health degradation signal. Goal: route degraded/failed counts to a typed signal consumable by ADR-018. Files:
  analysis/domain/, emit into state. Tests: unit (failed node → signal increments). Done: signal emitted + asserted.
  - V3-P1-013-08 — INV-1 honest-null discipline (scaffold). Goal: EvidenceRef + tier enum + honest-null helper; assert no 0/100 substitution for missing
  evidence. Files: extend existing evidence layer (src/evidence/), analysis/domain/. Out: full gating in 016/018 (later). Tests: unit (missing evidence →
  null+reason). Done: helper + tier available to later phases.

  Phase 2 — ADR-014

  - V3-P2-014-01 Contract: aggregate + entity models + lifecycle_status. · -02 Repository Ports (Protocol) + no-commit() static test. · -03 SQLAlchemy
  adapters. · -04 Alembic migration (+downgrade). · -05 Compatibility adapter (per-doc output → entities). · -06 Reserved future seams (nullable; no
  logic). · -07 RLS policies + tenant tests.

  Phase 3 — ADR-015

  - V3-P3-015-01 DocumentRevision content-addressed lineage (R2 + row). · -02 Migrate reupload to revisions (no amnesiac reset). · -03 ProjectEvent
  append-only log + reserved namespaces. · -04 ProjectSnapshot append-only + INSERT-only constraint test. · -05 Snapshot triggers (incl. daily Celery). ·
  -06 Retention/partition policy + test.

  Phases 4–8 (epic stubs; expand at phase open)

  - P4/016: -01 ChangeSet/SemanticChange contracts · -02 L1 structural diff (contracts) · -03 anchor resolver + match_confidence · -04 evidence-gated
  Change-Impact Report · -05 (gated) L2 semantic-LLM diff.
  - P5/017: -01 Tier-1 DocumentArtifact contract · -02 Tier-2 ProjectGraphState · -03 async trigger · -04 cross-doc coherence node (LLM-on) · -05 cost
  governance + canary.
  - P6/018: -01 HealthVector contracts · -02..05 v0 dimension scorers · -06 coherence→Contract subscore · -07 trend from snapshots · -08 OpenAPI regen +
  dashboard.
  - P7/019-020: -01 ActionItem + correlation · -02 ranking/dedupe · -03 org/role minimal · -04 CM HITL queue · -05 policy routing · -06 audit trail · -07
  correction→golden loop.
  - P8/021: -01 snapshot projection · -02 briefing delivery · -03 portfolio rollup.

  ---
  4. Multi-Agent Plan

  Orchestrator (you/Opus): decompose, freeze sequencing, integrate branches, adjudicate gate failures, own the canary decisions. Never an interchangeable
  coder.

  ┌───────────┬─────────────────────────────────────────────────────────────────────────────────────────────────┬───────────────────────────────────┐
  │   Agent   │                                          Standing role                                          │            Must NOT do            │
  ├───────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ Claude    │ Spec & Contract owner + PR reviewer. Writes the openspec change per ADR; authors & freezes the  │ Implement features in parallel    │
  │ Sonnet    │ typed contracts (models, NodeResult, ports, event schemas, OpenAPI); reviews every PR for       │ with reviewing them.              │
  │           │ ADR-conformance + architecture consistency.                                                     │                                   │
  ├───────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │           │ Primary implementer. TDD red→green→refactor against frozen contracts; refactors; writes the     │ Change a frozen contract without  │
  │ Codex     │ bulk of unit/integration tests; migrations.                                                     │ re-freeze; touch reserved future  │
  │           │                                                                                                 │ domains.                          │
  ├───────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │           │ Long-context validator. Whole-repo consistency sweeps; edge cases; product/persona consistency; │                                   │
  │ Gemini    │  generates BDD/golden eval scenarios from real fixtures; cross-file drift detection (huge       │ Be the merge authority.           │
  │           │ context window).                                                                                │                                   │
  ├───────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────┤
  │ DeepSeek  │ Risk & simplification (the Challenger seat). Proposes alternative/simpler implementations;      │ Block delivery; it advises,       │
  │           │ migration-complexity & cost/latency risk analysis; flags over-engineering before merge.         │ Sonnet/Opus decide.               │
  └───────────┴─────────────────────────────────────────────────────────────────────────────────────────────────┴───────────────────────────────────┘

  Per-phase assignment:

  ┌───────────┬─────────────────────────────────┬─────────────────────────┬────────────────────────────────────┬───────────────────────────────────┐
  │   Phase   │             Sonnet              │          Codex          │               Gemini               │             DeepSeek              │
  ├───────────┼─────────────────────────────────┼─────────────────────────┼────────────────────────────────────┼───────────────────────────────────┤
  │ 0         │ branch/flag policy              │ hygiene + secret-scan   │ scan stray-file risk               │ rollback review                   │
  │           │                                 │ CI                      │                                    │                                   │
  ├───────────┼─────────────────────────────────┼─────────────────────────┼────────────────────────────────────┼───────────────────────────────────┤
  │ 1 (013)   │ freeze payload+NodeResult       │ implement -04/-05/-06 + │ no-silent-failure edge cases;      │ simpler envelope vs per-node;     │
  │           │ contracts; PR review            │  tests                  │ whole-graph drift sweep            │ coherence-fix risk                │
  ├───────────┼─────────────────────────────────┼─────────────────────────┼────────────────────────────────────┼───────────────────────────────────┤
  │ 2 (014)   │ aggregate contract + ports;     │ adapters + migration +  │ RLS edge cases; entity-model       │ migration-complexity risk; seam   │
  │           │ review                          │ compat                  │ consistency                        │ minimalism                        │
  ├───────────┼─────────────────────────────────┼─────────────────────────┼────────────────────────────────────┼───────────────────────────────────┤
  │ 3 (015)   │ event/snapshot schema; review   │ revision + event +      │ retention edge cases; append-only  │ ES-vs-hybrid simplification check │
  │           │                                 │ snapshot + Celery       │ sweep                              │                                   │
  ├───────────┼─────────────────────────────────┼─────────────────────────┼────────────────────────────────────┼───────────────────────────────────┤
  │ 4 (016)   │ ChangeSet contract; review      │ L1 diff + anchor        │ golden Rev-C→D fixtures; anchor    │ anchor-resolution risk            │
  │           │                                 │ resolver                │ edge cases                         │ (make-or-break)                   │
  ├───────────┼─────────────────────────────────┼─────────────────────────┼────────────────────────────────────┼───────────────────────────────────┤
  │ 5 (017)   │ Tier contracts; review          │ ProjectGraph async      │ concurrency/cost edge cases        │ cost/latency risk; serial-first   │
  │           │                                 │                         │                                    │ defense                           │
  ├───────────┼─────────────────────────────────┼─────────────────────────┼────────────────────────────────────┼───────────────────────────────────┤
  │ 6 (018)   │ HealthVector contract; review   │ dimension scorers       │ honest-null edge cases; persona    │ fake-precision risk; weight       │
  │           │                                 │                         │ consistency                        │ simplicity                        │
  ├───────────┼─────────────────────────────────┼─────────────────────────┼────────────────────────────────────┼───────────────────────────────────┤
  │ 7         │ ActionItem+HITL contracts;      │ engines + queue + loop  │ dedupe edge cases; UX flow         │ "4-products" scope-creep guard    │
  │ (019/020) │ review                          │                         │                                    │                                   │
  ├───────────┼─────────────────────────────────┼─────────────────────────┼────────────────────────────────────┼───────────────────────────────────┤
  │ 8 (021)   │ projection contract; review     │ projection + delivery   │ briefing content consistency       │ defer-vs-build call               │
  └───────────┴─────────────────────────────────┴─────────────────────────┴────────────────────────────────────┴───────────────────────────────────┘

  Hand-off protocol (CLI loop): Sonnet freezes contract + posts it → Codex implements behind flag (TDD) → Gemini + DeepSeek review the diff in parallel
  (edge/consistency vs risk/simplification) → Sonnet PR review (ADR-conformance) → Opus runs §5 gates + integrates. A contract change mid-flight = stop,
  re-freeze, re-broadcast.

  ---
  5. Quality Gates (mandatory, blocking)

  ┌─────────────────────────┬────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────┬────────┐
  │          Gate           │               Command / location               │                      Blocks merge when                      │ Owner  │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ Type checks             │ make typecheck (mypy + tsc)                    │ any new dict[str,Any] on material paths; type error         │ Codex  │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ Unit tests              │ make test-api / pytest tests/unit              │ <80% coverage on changed modules                            │ Codex  │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ Integration             │ pytest tests/integration                       │ repo/migration/use-case break                               │ Codex  │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ Migration up/down       │ pytest tests/integration migration tests       │ downgrade() fails or drifts                                 │ Codex  │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ Graph-contract          │ pytest                                         │ node signature/return drift                                 │ Sonnet │
  │                         │ tests/contract/test_graph_node_contracts.py    │                                                             │        │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ No-silent-failure       │ pytest tests/contract (inject-exception suite) │ a material node returns []/None on caught error             │ Gemini │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ Evidence/provenance     │ pytest tests/evals + golden                    │ a CRITICAL output lacks verified/weak evidence; any 0/100   │ Sonnet │
  │ (INV-1)                 │                                                │ substituted for missing evidence                            │        │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ Tenant/RLS              │ pytest tests/security                          │ cross-tenant leakage; RLS not fail-closed                   │ Gemini │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ No-commit()-in-repo     │ static test in tests/ci/                       │ a repository calls commit()                                 │ Sonnet │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ OpenAPI drift           │ make openapi + openapi-drift.yml               │ spec not regenerated after route change                     │ Codex  │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ Rollback/canary         │ flag-off smoke + canary metric gate (ADR-009)  │ flag-off path broken; canary metrics regress at 10/50%      │ Opus   │
  ├─────────────────────────┼────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼────────┤
  │ Golden/eval regression  │ golden-corpus-evals.yml                        │ eval scores regress                                         │ Gemini │
  └─────────────────────────┴────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────┴────────┘

  Definition of Done (every ticket): spec exists → contract frozen → tests written first (RED shown) → GREEN → refactor → all applicable gates green →
  behind flag (if behavioral) → PR reviewed by Sonnet → integrated by Opus.

  ---
  6. First Sprint Plan — ADR-013 (2 weeks)

  Sprint goal: the runtime is type-safe and failure-honest on material paths; the coherence headline path is correct and no longer degraded-by-default;
  CI enforces the graph contract. Behavioral changes flag-gated + canaried; typing changes covered by tests.

  Week 1 — Contracts & tests RED
  - D1 (Sonnet+Opus): openspec change for ADR-013; freeze contracts.py payload models (V3-P1-013-01) and NodeResult/ErrorRecord (‑02). Broadcast frozen
  contracts to Codex/Gemini/DeepSeek.
  - D2 (Codex): write RED tests — model validation, NodeResult serialization, no-silent-failure injection suite, graph-contract test (‑03, must RED
  against current drift). DeepSeek: review "universal envelope vs material-only" → confirm material-only (Challenger ruling).
  - D3 (Codex): type channel values in schema.py; begin applying NodeResult to extractor nodes in nodes.py/nodes_extended.py (‑04). Gemini: whole-graph
  sweep for every except…return []/None/silent fallback → checklist.
  - D4 (Codex): finish silent-failure ban on material nodes; doc-health degradation signal (‑07).
  - D5 (Codex+Sonnet): coherence signature fix (‑05) — reconcile N8 kwargs with evaluate_coherence_async (graph.py:263); graph-contract test goes GREEN.
  Mid-sprint review.

  Week 2 — Behavior, gate, harden
  - D6 (Codex): remove low_budget_mode=True default (nodes_extended.py:242); put LLM-on path behind feature_v3_coherence_llm (‑06). DeepSeek:
  cost/latency risk note on always-LLM coherence.
  - D7 (Codex): INV-1 scaffold — EvidenceRef + tier enum + honest-null helper (‑08); unit tests (missing evidence → null+reason, never 0/100).
  - D8 (Codex+Gemini): wire graph-contract + no-silent-failure into tests.yml; Gemini edge-case pass (partial extraction, empty doc, mock mode
  C2PRO_AI_MOCK=1).
  - D9 (all): canary harness for the coherence-LLM flag (10→50→100% metric gate, ADR-009 pattern); §5 gates run; DeepSeek simplification pass on the
  diff.
  - D10 (Sonnet+Opus): PR review (ADR-013 conformance), integrate to feat/v3-spine, retro.

  Sprint DoD: all §5 gates green; zero silent failures in material nodes (audited by injection suite); coherence path correct + flag-gated LLM-on; CI
  fails on signature drift; coverage ≥80% on changed modules; feature_v3_coherence_llm canary-ready.

  ---
  7. Prompt Pack (copy-paste ready)

  ▎ Each prompt assumes the agent is run in the repo at apps/api/. Replace <TICKET> as needed. All four share the Global Constraints block.

  GLOBAL CONSTRAINTS (prepend to every prompt):
  Project: C2Pro (apps/api, FastAPI+Pydantic v2, SQLAlchemy/Alembic, LangGraph). Hexagonal modules.
  Canon: ADR-013..021 in docs/architecture/decisions/. We are implementing ADR-013 (Runtime Trust).
  HARD CONSTRAINTS:
  - Do NOT rewrite the platform. Additive, surgical changes only.
  - Do NOT implement Procurement or Stakeholder Intelligence (reserved future domains).
  - No silent failures: never `except: return []/None`. Use NodeResult{ok|degraded|failed|skipped} + persisted ErrorRecord.
  - No fake health / no evidence-free critical outputs. Missing evidence => null + reason, never 0 or 100 (INV-1).
  - Repositories MUST NOT call commit() (locked invariant).
  - Behavioral changes go behind a feature flag (core/feature_flags) + ADR-009 canary. Typing changes need tests.
  - TDD: write failing tests first. Target ≥80% coverage on changed modules. Use C2PRO_AI_MOCK=1 to skip real AI.
  - Touch only material graph nodes for NodeResult (not trivial passthroughs).
  Key files: analysis/adapters/graph/{schema.py,nodes.py,nodes_extended.py}, coherence/graph/graph.py.
  Known defects to fix: low_budget_mode=True default at nodes_extended.py:242; coherence signature drift
  (N8 passes seed_signals/seed_coverage to evaluate_coherence_async() at coherence/graph/graph.py:263 which
  does not declare them).

  Codex — implementation prompt

  ROLE: Primary implementer. Implement <TICKET> for ADR-013 using strict TDD.
  [paste GLOBAL CONSTRAINTS]
  DO:
  1. Read the frozen contracts in analysis/domain/contracts.py and node_result.py (do NOT modify them; if a change is needed, STOP and report).
  2. Write failing tests first under tests/unit/ and tests/contract/. Show the RED run output.
  3. Implement the minimal change to pass. Show GREEN. Refactor.
  4. For V3-P1-013-04: replace every silent except-return in material nodes with NodeResult(failed, error=...) persisted to the errors/events table; type
  the channel values.
  5. For V3-P1-013-05: make the N8→evaluate_coherence_async call signature explicit and correct.
  6. For V3-P1-013-06: remove the low_budget_mode default; gate LLM-on behind feature_v3_coherence_llm.
  OUTPUT: unified diff per file + test files + the pytest output (RED then GREEN) + a 5-line summary of what changed and why. Do not commit.

  Claude Sonnet — review prompt

  ROLE: Spec/Contract owner & PR reviewer. Review the diff for ADR-013 conformance and architecture consistency.
  [paste GLOBAL CONSTRAINTS]
  REVIEW CHECKLIST — flag every violation with file:line:
  - Any dict[str,Any] left on a material path; any unfrozen contract change.
  - Any silent failure (except: return []/None) remaining in a material node.
  - NodeResult applied to material nodes only (not trivial passthroughs).
  - Coherence signature drift fully resolved (no undeclared kwargs).
  - low_budget_mode default removed; behavioral change behind flag + canary.
  - INV-1: no 0/100 substituted for missing evidence; honest nulls.
  - No commit() inside repositories.
  - Tests written first, ≥80% coverage on changed modules, no-silent-failure + graph-contract tests present and green.
  OUTPUT: APPROVE / REQUEST-CHANGES, a ranked list of blocking issues (CRITICAL/HIGH/MEDIUM) with file:line and a suggested fix for each. Do not write
  feature code.

  Gemini — risk/edge-case & long-context review prompt

  ROLE: Long-context validator. Sweep the WHOLE graph + coherence subsystem for the diff's blast radius.
  [paste GLOBAL CONSTRAINTS]
  DO:
  1. Enumerate EVERY `except`-that-returns-empty / silent fallback across analysis/adapters/graph/** and coherence/** (file:line) and confirm the diff
  covers the material ones.
  2. Identify edge cases for the changed nodes: empty document, partial extraction, C2PRO_AI_MOCK=1 mode, concurrent branch writes, missing tenant_id,
  missing project_id.
  3. Generate BDD/golden scenarios (Gherkin) for: "extractor crashes => degraded surfaced, not 0 findings" and "missing evidence => Pending, never
  0/100".
  4. Cross-file consistency: does removing low_budget_mode default affect any caller/test that assumed degraded behavior?
  OUTPUT: (a) silent-fallback inventory table, (b) edge-case list with severity, (c) Gherkin scenarios ready for tests/golden, (d) list of callers/tests
  impacted by the low_budget_mode change.

  DeepSeek — simplification & risk-analysis prompt

  ROLE: Risk & simplification (Challenger seat). Pressure-test the ADR-013 plan/diff for over-engineering and risk.
  [paste GLOBAL CONSTRAINTS]
  DO:
  1. Is NodeResult on all material nodes the simplest sufficient design, or is "ban silent failure + type DocumentGraph outputs only" enough? Recommend
  the minimal version.
  2. Coherence signature fix: identify the lowest-risk reconciliation (declare kwargs vs adapter) and the regression risk to existing coherence tests.
  3. low_budget_mode removal: quantify cost/latency risk of always-LLM coherence; propose the canary + cost-ceiling that contains it.
  4. Flag anything in the diff that expands scope beyond ADR-013 or toward reserved domains.
  OUTPUT: a ranked risk register (Likelihood×Impact) with concrete mitigations, and a "simplify-this" list with the minimal alternative for each.
  Advisory only — do not change code.

  ---
  Constraint compliance (self-check)

  No rewrite (additive modules + flags) ✓ · no Procurement/Stakeholder logic (reserved seams only, P2 ‑06) ✓ · no full PM / BIM / mobile / ERP ✓ ·
  existing architecture preserved (reuses LangGraph, Celery, feature_flags, golden CI) ✓ · ADR dependencies respected (critical path
  013→014→015→016→017→018) ✓ · flags/canary throughout ✓ · no silent failures / no fake health / no evidence-free critical outputs (gates §5) ✓ · no
  commit() in repos (static gate) ✓.

  ---
  This plan is execution-ready: Phase 0 + the §6 Sprint 1 can be dispatched to the four agents today using the §7 prompts, gated by §5. Backlog still
  untouched per your instruction — when you're ready, the natural next step is to materialize the Phase 0–1 tickets (V3-P0-* and V3-P1-013-*) into
  C2PRO_MASTER_BACKLOG.md, which I'll do as a separate dispatched markdown edit rather than inline.

  Want me to (a) generate the OpenSpec change scaffold for ADR-013 (openspec/ requirements + scenarios) so Sonnet's contract-freeze has a home, or (b)
  expand the Phase 2–3 tickets to the same depth as Phase 1 next?