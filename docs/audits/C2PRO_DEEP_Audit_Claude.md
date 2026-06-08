 C2Pro — Deep Audit & Product Evolution Review

  Principal Architect / Product / EPC-Domain / LangGraph / AI-Systems consulting report
  Date: 2026-06-07 · Repo: AI-Gen-AI/C2Pro (analyzed at local main, HEAD 1585de51)

  ---
  Executive Summary

  C2Pro is far more mature than a typical AI side-project and far less coherent than its own vision claims. This is the central tension you must resolve.

  The engineering substrate is genuinely strong: a real two-level LangGraph orchestration (a 17-node project graph wrapping a 7-node coherence subgraph),
  hexagonal module boundaries, Celery async workers with a dead-letter queue, multi-tenant Postgres RLS, Clerk auth, ~814 test files, 51 Alembic
  migrations, and 15 CI workflows including golden-corpus AI evals and regression harnesses. The recent coherence work (ADR-009, ECOA v2 shadow mode,
  "honest scoring" that refuses to fabricate 100/0 numbers) shows product-engineering taste that most teams never reach. If I scored only "is this
  well-built software," it would land near 7/10.

  But the product does not yet do the one thing its name and pitch promise. The "tridimensional Coherence Score™ (Contract + Schedule + Budget)" is the
  differentiator — and in the live ingestion pipeline it is computed one document at a time, against itself, with the LLM/RAG layer cost-gated off.
  Cross-document scoring exists only in a separate API endpoint (POST /coherence/evaluate with a project_id that re-fetches clauses from RAG). So you
  have two divergent coherence engines, and the headline feature runs on the weaker one by default.

  Worse for the stated long-term vision ("a living digital project companion"): there is no temporal model, no semantic version-diff, and no
  project-health engine. Document re-upload (reupload_document_use_case.py) is a SHA-256 compare + integer counter + full reprocess — it cannot answer
  "what changed between Rev C and Rev D of the contract," which is the entire job of EPC document control. A grep for project_health / health_score
  returns nothing. Coherence is the only project-level number, and coherence is not health.

  Verdict in one line: C2Pro is a high-quality document-analysis platform wearing the costume of a project-intelligence platform. The bones to become the
  real thing are present and unusually good. But three foundational subsystems — a temporal/versioning core, a true cross-document coherence path, and a
  multi-dimensional health engine — are missing, and no amount of polish on the existing surfaces substitutes for them.

  ┌────────────────────┬────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │     Dimension      │ Score  │                                               One-line justification                                               │
  ├────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Technical Maturity │ 6.5/10 │ Excellent patterns + tests + CI, undercut by single-doc architecture, dict[str,Any] state, silent failure          │
  │                    │        │ swallowing, repo squalor.                                                                                          │
  ├────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Product Maturity   │ 5.0/10 │ Real surfaces and a defensible coherence philosophy, but no health engine, no evolution tracking, unresolved       │
  │                    │        │ product identity.                                                                                                  │
  ├────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Scalability        │ 6.0/10 │ Async/Celery/RLS/stateless services are right; singleton graph, full-doc reprocessing, no portfolio layer cap it.  │
  ├────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ User Adoption      │ 4.5/10 │ Rich UI exists; no daily-use loop, no continuous monitoring, document-centric not PM-centric.                      │
  ├────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ AI Readiness       │ 7.5/10 │ Model routing, prompt cache, cost control, PII gate, golden evals, honest scoring — best-in-class for the stage.   │
  ├────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Enterprise         │ 5.5/10 │ RLS + HITL + audit + observability + DLQ are real; SSO/RBAC depth, compliance evidence, and hygiene are not.       │
  │ Readiness          │        │                                                                                                                    │
  ├────────────────────┼────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Long-Term          │ 8.0/10 │ The foundation quality is rare; the gaps are addressable; the market is large and underserved by AI-native         │
  │ Potential          │        │ tooling.                                                                                                           │
  └────────────────────┴────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  Phase 1 — Architecture Review

  What C2Pro actually is today (maturity reality check)

  Not a prototype. Concretely present and working:
  - Backend (apps/api, ~90k LOC Python): FastAPI + Pydantic v2, SQLAlchemy/Alembic (51 migrations), domain-oriented + hexagonal modules.
  - Orchestration: LangGraph StateGraph N1–N17 (analysis/adapters/graph/workflow.py) + a nested 7-node coherence subgraph (coherence/graph/graph.py).
  - Async: Celery (core/tasks/celery_app.py, ingestion_tasks.py, scheduled budget_alerts.py) + dead-letter queue (core/events/dead_letter_queue.py) +
  LangGraph Postgres checkpointer.
  - Frontend (apps/web): Next.js 16 / React 19, per-project sub-surfaces
  (projects/[id]/{coherence,budget,wbs,alerts,analysis,documents,evidence,review,stakeholders,settings}), each with co-located tests.
  - AI infra (core/ai/): model router (Haiku/Sonnet/Opus by cost), prompt cache, usage analytics, tool registry, anthropic wrapper, cost controller.
  - Doc parsers: PDF, Excel, and BC3 (bc3_file_parser.py — the FIEBDC Spanish/LATAM construction-budget standard; a serious domain signal) + RAG
  (documents/adapters/rag/).
  - Quality bar: ~538 backend + ~276 frontend test files; CI includes golden-corpus-evals, evaluation-regression, qa-swarm, real-document-operability,
  openapi-drift, e2e-security-tests.

  Architecture diagram (text)

                           ┌────────────────────────── apps/web (Next.js 16 / React 19) ──────────────────────────┐
                           │  (app)/projects/[id]/{coherence,budget,wbs,alerts,analysis,documents,evidence,review} │
                           │  Clerk auth · MSW mocks · Orval-generated client from openapi.json                    │
                           └───────────────────────────────────────┬──────────────────────────────────────────────┘
                                                                    │  HTTPS (JWT)
  ┌─────────────────────────────────────────────────────────────  apps/api (FastAPI)  ───────────────────────────────────────────┐
  │  Middleware: TenantIsolation · RateLimit · APIContract · RequestLogging · clerk_auth (PEP562 lazy)                              │
  │  Routers (~25): projects, documents, alerts, coherence(+dashboard), hitl, wbs, raci, stakeholders, procurement,                │
  │                 decision_intelligence, ai_analytics, observability, dlq_admin, bulk_operations, mcp, analysis                   │
  │                                                                                                                                │
  │  Upload ─► create_and_queue_document ─► Celery worker ─► run_orchestration(thread_id)                                          │
  │                                                                                                                                │
  │   LangGraph PROJECT graph (analysis/adapters/graph/workflow.py)        ── checkpointer: AsyncPostgresSaver (PgBouncer-safe) ── │
  │   N1 ingest ─► N2 PII ─► N3 router ─►[N4 risk | N5 wbs | N9 budget]─► N12 critique ──┬─ retry ──┐                              │
  │                                                                                      ├─ N13/14 HITL (langgraph interrupt())    │
  │                                                                                      └─ enrichment_dispatch (fan-out)          │
  │                         ┌───────────────────────────────┬───────────────────────────┘                                        │
  │                         ▼                               ▼                            ▼                                         │
  │                   N6 stakeholder ─► N7 RACI      N8 coherence_scorer          N15 citation_validator                          │
  │                         └────────────────┬───────────┴────────────────────────────┘                                          │
  │                                  N10 knowledge_graph (list-edge fan-in barrier) ─► N17 save ─► N11 decision ─► N16 final ─►END │
  │                                                              │                                                                 │
  │                            N8 delegates ─► COHERENCE subgraph (coherence/graph/graph.py):                                     │
  │                            prepare_context ─► deterministic ─► llm_semantic ─► rag_similarity ─► cross_clause ─► arbiter ─►fmt │
  │                            (sequential; llm+rag SKIPPED when low_budget_mode=True — which N8 sets)                            │
  │                                                                                                                                │
  │  Persistence: Supabase Postgres (RLS, pgvector centroids/embeddings) · Redis (Upstash) cache · Cloudflare R2 blobs            │
  │  External: Claude API (Sonnet/Haiku/Opus) · OpenAI text-embedding-3-small · (optional Neo4j client present)                   │
  └────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Strengths

  1. Real, idiomatic LangGraph with a correct static fan-out/fan-in (list-valued edge into N10 as a true join, disjoint branch keys, add_messages reducer
  for the one shared channel). This is textbook-correct — see the state-safety contract in workflow.py:134-156.
  2. Hexagonal discipline in the newer modules (alerts/, coherence/, documents/, modules/hitl/): domain / application / ports / adapters cleanly
  separated; nodes are thin adapters delegating to use cases.
  3. Production-grade async: queue-on-upload, Celery workers, DLQ, Postgres checkpointer with explicit PgBouncer/Railway compatibility
  (prepare_threshold=None).
  4. Eval-driven AI: golden corpus, regression workflow, "honest scoring" guardrails, openapi-drift gate. This is the rarest thing here and the strongest
  competitive moat-in-the-making.
  5. Cost-aware AI by construction: model router + prompt cache + per-tenant usage analytics + CoherenceLlmGate.

  Weaknesses / technical debt

  1. The state object is untyped. ProjectState (schema.py) is a flat TypedDict of ~40 fields where every domain alias is dict[str, Any] (Risk = dict[str,
  Any], Task, Citation, …). You get none of the Pydantic v2 validation you use everywhere else, at the exact layer where 17 nodes read/write shared
  mutable state. This is the highest-leverage debt in the system.
  2. Mixed mutation contract. Sequential nodes mutate state in place and return it (nodes.py); parallel nodes return dict patches (nodes_extended.py).
  Both work in LangGraph, but the inconsistency is a latent concurrency footgun and violates your own immutability rule.
  3. Silent degradation everywhere. Pervasive except Exception: … return [] / None (N6, N8, N10, stakeholders, KG). A crashed extractor is
  indistinguishable from "nothing found." For an intelligence product this is dangerous: it manufactures false confidence ("0 risks") out of failures.
  4. Two core/, two ai/, two coherence engines, two migration systems. Documented in CLAUDE.md as "gotchas," but gotchas are debt with good PR. The
  duplicate coherence path (N8 vs API) is the one that actually misleads users.
  5. Repository squalor. 25 stray *.py scripts and 15 *.txt brain-dumps at repo root (definitive_fix_v2/v3/v4.py, absolute_refine_backlog.py, "stablish
  only 5 as much as possible.txt"), a literal C:Usersesus_Documents…C2PRO_MASTER_BACKLOG.md path-as-filename, a nul artifact, committed test.db, *.log,
  task1429-*.out. This is a credibility tax on every enterprise code review and a security-leak surface.

  Architectural risks

  - Single-document framing is load-bearing and wrong for the vision. ProjectState is keyed on one document_id/document_text. Every "project" insight is
  actually a per-document insight stitched together at persistence time. The data model fights the product mission.
  - Singleton compiled graph (_graph_app global) + module-global checkpointer pool: fine at one replica, a coordination problem at horizontal scale.
  - No temporal dimension anywhere in the schema — the system stores latest snapshots, not project history.

  ---
  Phase 2 — LangGraph & Agent Orchestration Review

  Is LangGraph used optimally? For single-document processing — yes, near-optimally. For project intelligence — no, because the graph's unit of work is
  the wrong noun.

  Anti-patterns / bottlenecks found

  1. Wrong granularity of the graph. The graph orchestrates "analyze one document." There is no graph (or Send-API map-reduce) that orchestrates
  "analyze/relate the N documents of a project." Cross-document reasoning is therefore impossible inside the main graph; it's been pushed to an HTTP
  endpoint that re-derives context from RAG.
  2. The differentiator runs degraded in the hot path. N8 (coherence_scorer_node) calls evaluate_coherence_async(... low_budget_mode=True ...) with a
  single synthetic clause built from the current doc (_build_coherence_clauses returns a 1-element list). The subgraph (coherence/graph/graph.py) skips
  the LLM-semantic and RAG nodes in low_budget_mode. So the live per-upload "Coherence Score" is essentially deterministic-rules + a risk-signal bridge —
  not the AI cross-document analysis the brand promises. (PR #143 "Re-enable LLM Semantic Layer … cost-gated" shows you're already fighting this
  tension.)
  3. Coherence's "cross_clause_eval" has nothing to cross. With one clause in, the cross-clause and RAG-similarity nodes are no-ops in the embedded path.
  The capability exists; the wiring starves it.
  4. _missing_audit_dimensions encodes the conceptual error. It marks "schedule"/"budget" as missing if this one document lacks them — i.e., it penalizes
  a contract for not being a schedule, instead of comparing the contract against the project's actual schedule and budget documents.
  5. Critique retry loop is shallow. retry_count routes back to the same extractor with no changed strategy/prompt/model — a retry that re-runs the
  identical computation is mostly a latency tax unless the prompt is mutated on retry.
  6. Observability is log-shaped, not trace-shaped at the domain level. LangSmith tracing is wired (run_orchestration tags/metadata — good), but
  node-level explainability (why a score, which evidence) is structlog strings in messages, not a structured, queryable evidence ledger.

  Recommended orchestration redesign

  Move from "document graph" to a two-tier graph: per-document extraction (map) + per-project synthesis (reduce), with a temporal spine.

  TIER 1 — DocumentGraph (per doc, your current N1–N9 + N15, lightly trimmed)
      ingest → PII → classify → extract(risk|wbs|budget|dates|obligations) → critique → cite
      OUTPUT: typed DocumentArtifact (Pydantic) → persisted, versioned, embedded

  TIER 2 — ProjectGraph (per project, runs on any artifact change; this is the missing graph)
      load_all_current_artifacts(project)              # contract + schedule + budget + RFIs + COs
        → align_entities (cross-doc resolution: WBS↔BOQ↔activities↔clauses)
        → CROSS-DOC COHERENCE (the real one: 6 categories over multiple docs)
        → HEALTH ENGINE (schedule/cost/risk/contract/deliverables/docs/governance)
        → DELTA vs previous project snapshot (what changed, why score moved)
        → alert synthesis + HITL routing
        → executive report assembly
      Use LangGraph Send() to fan Tier-1 across all changed docs, then reduce in Tier-2.

  Concrete moves:
  - Replace ProjectState dict[str,Any] aliases with Pydantic models (Risk, WbsActivity, BomItem, Citation, DocumentArtifact, CoherenceFinding). Keep the
  TypedDict graph channels but make the values validated models.
  - Introduce ProjectGraph invoked by the artifact-changed event (Celery already gives you the trigger). This is where cross-document coherence and
  health actually belong.
  - Kill low_budget_mode defaulting in the project path; gate LLM by value of the decision (a project re-score is worth a Sonnet call) not by a per-node
  default.
  - Replace except Exception: return [] with a NodeResult{status, data, error} so downstream nodes and the UI can distinguish "clean: 0 findings" from
  "degraded: extractor failed." Surface degradation as a documentation-health signal.
  - Make retries adaptive: on retry, escalate model tier or switch prompt strategy, else cap at 0 retries.

  ---
  Phase 3 — Document Intelligence Review

  This is simultaneously your strongest foundation and your most dangerous gap.

  Strong: multi-format parsing (PDF/Excel/BC3), clause + subclause entities, date-entity extraction, RAG ingestion with pgvector, source locator,
  citation validator, entity extraction. The bones of real document understanding are here.

  Dangerous gap — there is no version intelligence. ReuploadDocumentUseCase:
  - hashes the new bytes, compares to file_hash;
  - if different → version += 1, reset status, full re-process;
  - there is no diff, no clause-level change set, no semantic comparison, no "Rev C → Rev D" report.

  For EPC/construction this is disqualifying for the core workflow. Contract revisions, scope changes, schedule updates, RFIs, change orders, technical
  clarifications, progress reports — the value is entirely in the delta, and the delta does not exist as a first-class object. "Version" is a counter,
  not a history.

  There is also no temporal store: no project_snapshot table, no time-series of scores/risks/quantities, so "evolution analysis," "historical tracking,"
  and "early warning trends" (Phases 1/3/5) have no substrate.

  World-class document-intelligence architecture (target)

  1. Immutable document revisions with content-addressed blobs (you already hash) → DocumentRevision(rev_no, parent_rev, blob_hash, parsed_at).
  2. Clause-anchored diff engine: structural + semantic diff between revisions (clause added/removed/modified, quantity changed, date moved), producing a
  typed ChangeSet with severity and category. This is the feature.
  3. Cross-document entity resolution layer: a canonical ProjectGraph of entities (WBS nodes, BOQ items, schedule activities, obligations, stakeholders)
  with edges that link the three dimensions — the thing your N10 knowledge graph gestures at but only builds per-doc.
  4. Provenance everywhere: every score, alert, and number carries (document_revision, clause_id, char_span) — you already have source_locator and
  citation validation; promote provenance to a hard invariant.
  5. Project timeline / snapshot store: append-only project_snapshot(score, health, open_risks, totals, ts) to power trends, deltas, and "is it getting
  worse."
  6. Change-order & RFI as domain objects, not generic documents — with lifecycle, cost/time impact, and links to the clauses/activities they affect.

  ---
  Phase 4 — Project Health & Scoring System

  Can the platform answer "is this project healthy?" today? No. It can answer "is this document internally coherent, mostly via rules." There is no
  ProjectHealth concept in the codebase (verified by grep). Coherence Score is being asked to carry a load it was never designed for.

  You must separate two ideas you've conflated:
  - Coherence = "do the project's documents agree with each other?" (a consistency metric).
  - Health = "is the project on track to succeed?" (a performance/risk metric).

  A healthy project can be incoherent (good execution, sloppy docs) and a coherent project can be unhealthy (perfect paperwork, blown schedule). You need
  both, as siblings.

  Proposed Project Health Engine (multi-dimensional)

  ┌────────────────┬──────────────────────────────────┬─────────────────────────────────────────────────┬─────────────────┬────────────────────────┐
  │   Dimension    │          Primary inputs          │        Calculation logic (v1 pragmatic)         │   Confidence    │       Threshold        │
  │                │                                  │                                                 │     driver      │   (green/amber/red)    │
  ├────────────────┼──────────────────────────────────┼─────────────────────────────────────────────────┼─────────────────┼────────────────────────┤
  │ Schedule       │ Schedule doc activities, dates,  │ SPI proxy = earned duration / planned duration; │ coverage of     │ ≥0.95 / 0.85–0.95 /    │
  │ health         │ % complete, baseline             │  slip days vs baseline; critical-path slack     │ dated           │ <0.85                  │
  │                │                                  │ (needs activity network)                        │ activities      │                        │
  ├────────────────┼──────────────────────────────────┼─────────────────────────────────────────────────┼─────────────────┼────────────────────────┤
  │ Cost health    │ Budget/BOQ, committed, actuals,  │ CPI proxy = EV/AC; budget burn vs % complete;   │ presence of     │ ≥0.95 / 0.9 / <0.9     │
  │                │ change orders                    │ CO exposure % of contract                       │ actuals         │                        │
  ├────────────────┼──────────────────────────────────┼─────────────────────────────────────────────────┼─────────────────┼────────────────────────┤
  │ Risk health    │ N4 risks, severity, mitigation   │ weighted open-risk index; trend over snapshots; │ extraction      │ <0.2 / 0.2–0.4 / >0.4  │
  │                │ status, aging                    │  unmitigated high-severity count                │ quality         │ index                  │
  ├────────────────┼──────────────────────────────────┼─────────────────────────────────────────────────┼─────────────────┼────────────────────────┤
  │ Contract       │ Obligations, clauses, compliance │ obligations-met %, unresolved incoherence       │ clause coverage │ ≥0.9 / 0.8 / <0.8      │
  │ health         │  flags, coherence-LEGAL          │ count, expiring deadlines                       │                 │                        │
  ├────────────────┼──────────────────────────────────┼─────────────────────────────────────────────────┼─────────────────┼────────────────────────┤
  │ Deliverables   │ WBS/scope vs progress reports    │ committed-vs-delivered ratio; overdue           │ scope           │ ≥0.9 / 0.8 / <0.8      │
  │ health         │                                  │ deliverables                                    │ completeness    │                        │
  ├────────────────┼──────────────────────────────────┼─────────────────────────────────────────────────┼─────────────────┼────────────────────────┤
  │ Resource       │ RACI gaps, stakeholder coverage  │ unassigned-responsibility count;                │ RACI            │ 0 gaps / few / many    │
  │ health         │                                  │ single-point-of-failure roles                   │ completeness    │                        │
  ├────────────────┼──────────────────────────────────┼─────────────────────────────────────────────────┼─────────────────┼────────────────────────┤
  │                │ Ingestion coverage,              │ % docs parsed cleanly; missing                  │                 │                        │
  │ Documentation  │ parse/extraction success,        │ contract/schedule/budget; failed-node count     │ n/a (it is the  │ all present / 1        │
  │ health         │ degradation events, missing      │ (from the NodeResult change above)              │ meta-signal)    │ missing / core missing │
  │                │ dimensions                       │                                                 │                 │                        │
  ├────────────────┼──────────────────────────────────┼─────────────────────────────────────────────────┼─────────────────┼────────────────────────┤
  │ Governance     │ HITL approvals, audit            │ overdue approvals; unactioned critical alerts;  │ n/a             │ 0 / few / breaches     │
  │ health         │ completeness, alert SLA breaches │ SLA breach rate (you have sla_calculator)       │                 │                        │
  └────────────────┴──────────────────────────────────┴─────────────────────────────────────────────────┴─────────────────┴────────────────────────┘

  Composite Project Health = confidence-weighted roll-up with explicit "insufficient data" states (reuse your honest-scoring discipline from ADR-009 —
  never fabricate a green). Every dimension returns {score|null, confidence, contributing_evidence[], trend}. The dimensions you can ship now with
  existing data: Risk, Contract, Documentation, Governance. The ones that need the missing schedule/cost network: Schedule, Cost, Deliverables — which is
  exactly why Phase-4 work depends on Phase-3 (versioning) and a schedule model.

  ---
  Phase 5 — Alerting & Early Warning System

  Today: a solid alert-management layer (alerts/ hexagonal: create/list/resolve/review/bulk use cases, SlaCalculator, workspace settings) plus alerts
  generated from coherence findings (coherence/alert_generator.py) and a scheduled budget_alerts.py Celery task. So you have alert plumbing and one
  proactive source.

  What's missing is the "early warning" half. Alerts are reactive to a document analysis, not derived from project state changes over time. With no
  snapshot/timeline store, you cannot detect: scope creep (Δ scope across revisions), schedule slippage (Δ dates), budget-burn trend, deliverable
  lateness, "incoherence introduced by the new revision," or stakeholder/governance drift. These are precisely the alerts an EPC PM wants at 7am.

  Target alert framework

  - Categories: Critical / High / Medium / Low / Informational (you have severity enums — keep).
  - Required fields per alert (extend alerts/domain/models.py): severity, confidence (you preach honest scoring — alerts must too), impact_estimate (₂
  cost/days where derivable), recommended_action, evidence[] (doc_rev + clause + span), escalation_path (role chain), requires_human_validation (bool),
  source_signal (which detector/delta fired), trend (new/worsening/stable).
  - Detector taxonomy: (a) intra-document (current coherence) → (b) cross-document (the real coherence path, project graph) → (c) temporal (snapshot
  deltas) → (d) threshold/SLA (health crosses amber/red) → (e) deadline (obligations/milestones approaching).
  - Noise control: dedupe by (signal, evidence), suppress unchanged alerts across re-runs, and rank by severity × confidence × impact. Information
  overload is the #1 killer of monitoring-tool adoption — design the digest, not just the firehose.

  ---
  Phase 6 — Human-in-the-Loop Review

  Best-realized differentiator after the AI infra. HITL is a real langgraph.types.interrupt() gate (N13/14, human_interrupt_node) with a service-routed
  auto-approve path (route_for_review can return APPROVED and resume without interrupting), confidence/impact-driven routing (ImpactLevel.HIGH when
  confidence < 0.5), a review_queue_repository port, a /review UI surface per project, and notification settings. The checkpointer makes interrupts
  genuinely resumable. This is correct architecture.

  Gaps vs an ideal HITL framework:
  1. Routing thresholds are hardcoded (confidence < 0.5) rather than per-tenant/per-doc-type policy. Enterprise buyers will demand configurable gates.
  2. No multi-step approval chains / delegation / escalation timers. SlaCalculator exists for alerts; HITL needs the same (auto-escalate an unactioned
  review).
  3. Feedback is not a learning loop. Human approvals/rejections/edits are recorded but there's no evidence they feed back into prompts, few-shot
  examples, or the golden corpus. You have ai_feedback/ and a golden harness — connect them: every human correction should be a candidate eval case. This
  is the flywheel that compounds the AI moat.
  4. except Exception → interrupt() fallback in N13 means an infra blip routes everything to humans — safe, but will silently bury reviewers; needs
  alerting on the fallback path.

  ---
  Phase 7 — UX Review (by persona)

  The surface is more complete than expected: per-project tabs for coherence, budget, WBS, RACI, alerts, analysis, documents, evidence, review,
  stakeholders — all test-covered. But surface ≠ workflow. Would a real project team use this daily? Not yet — and the reason is structural, not
  cosmetic.

  - Project Director / Executive Sponsor: wants a single "is my portfolio okay?" glance. There is no portfolio/program view and no health number — only
  per-project coherence. They will not log in daily for a consistency score. Adoption: low.
  - Project Manager: wants "what changed, what's late, what needs me today." No change-feed, no timeline, no "today" queue spanning schedule/cost/risk.
  The HITL /review queue is the closest thing. Adoption: occasional.
  - Construction Manager: wants schedule/field reality. No schedule network, no progress tracking, no field input. Adoption: very low — this persona has
  the least here.
  - Contract Manager: best fit. Clause extraction, obligations, coherence-LEGAL, citations, RFIs/COs (if modeled) map well. Make this the beachhead
  persona. Adoption: promising.
  - PMO Lead: wants cross-project standards, rollups, governance. No portfolio layer, no template/standard enforcement. Adoption: low until portfolio
  exists.

  Cross-cutting UX risks: (1) information overload if alerts/coherence breakdowns ship without a digest; (2) trust cliff — the honest-scoring "—/Pending"
  work is excellent and protects trust, keep that discipline ruthlessly; one fabricated green destroys an EPC relationship; (3) no daily hook — there's
  no email/Slack "morning project briefing," which is the single highest-ROI adoption mechanic for this category.

  ---
  Phase 8 — Product Strategy Review

  Current identity (honest read): an AI contract/document-coherence analyzer with project scaffolding. The marketing identity ("living project
  intelligence platform across EPC/PMO/capital programs") is ~12–18 months ahead of the code.

  Positioning vs the field:
  - Primavera P6 / MS Project / Oracle Unifier: schedule/cost systems of record. C2Pro does not compete here and shouldn't — it has no CPM/Gantt engine.
  It should integrate (ingest P6 XER/XML, MSP) and audit them. Right now it can't read their native formats.
  - Procore / Autodesk Construction Cloud / Aconex: document/field systems of record with huge incumbency. C2Pro does not replace them — it should sit on
  top as the AI audit/coherence layer and ingest from them.
  - Monday/ClickUp/Notion AI: generic work mgmt + generic AI. C2Pro's domain depth (BC3, clauses, coherence, HITL) is a real differentiator if it
  delivers the cross-document audit they can't.
  - Copilot-style assistants: chat over docs. C2Pro's structured, evidence-cited, HITL-gated scoring is more defensible than chat — if the scoring is the
  real cross-document one.

  Differentiation that is real and defensible: (1) tridimensional cross-document coherence as a number with evidence and honest nulls; (2) HITL-gated AI
  with audit trail; (3) eval-driven AI quality. Differentiation that is currently vapor: "living," "continuous," "lifecycle," "evolution," "early
  warning," "multi-industry PMO."

  Strategic recommendation: Stop selling the platform. Win the wedge. Be the AI Cross-Document Coherence & Change-Impact Auditor for contract/EPC teams —
  the tool that, when a new contract revision or change order lands, tells you in minutes what changed, what it conflicts with across schedule/budget,
  what it'll cost, and routes the risky calls to a human. Nail that loop, then expand to health/portfolio. The generalized "project intelligence
  platform" is the destination, not the go-to-market.

  ---
  AI Review (cross-cutting)

  The best part of the system. Present and good: model routing by cost (model_router.py + model_routing.yaml), prompt caching, per-tenant usage/cost
  analytics, cost controller + CoherenceLlmGate, PII anonymization before Claude (N2, enforced), tool registry (@register_tool), deterministic fallbacks,
  golden-corpus + regression CI, "honest scoring."

  Weaknesses: (1) LLM is cost-gated off the hot coherence path, so users may rarely see the real AI value; gate by decision-value, not by default. (2) No
  confidence calibration surfaced — confidence scores exist but I see no calibration/Brier tracking against golden truth. (3) Human feedback not wired
  to evals (the flywheel gap from Phase 6). (4) Prompts: confirm they're English (your memory note says they must be) and that the v1/v1_1 prompt
  variants are A/B-tracked, not just accreting. (5) Hallucination control is good directionally (citation validator, provenance) — make provenance a hard
  gate: no evidence span → finding is unverified, never shown as fact.

  ---
  Top Risks (ranked)

  1. Differentiator–reality gap. The headline feature runs degraded/single-doc by default. If a sophisticated buyer tests it, the cross-document magic
  isn't there in the hot path. Existential.
  2. No temporal/versioning core. Blocks "living," evolution, early-warning, change-order workflows — i.e., most of the roadmap. Foundational.
  3. No health engine. The question every executive asks has no answer. Adoption-blocking.
  4. Silent failure swallowing. Manufactured false confidence in an intelligence product is a trust and liability risk. High.
  5. Repo hygiene / secret-leak surface. 40+ stray root files incl. logs and a test.db; raises real questions for due diligence and security. Medium-High
  (reputational/security).
  6. Scope sprawl vs focus. 25 modules, multiple half-built subsystems; thin in many, deep in few. Spreading further before consolidating risks a
  permanently "demo-quality everywhere, production-quality nowhere" plateau. High.
  7. Schedule blindness. Can't parse P6/MSP or model a CPM network — yet "schedule health" is a third of the pitch. Medium (addressable via integration).

  Top Opportunities (ranked)

  1. Promote cross-document coherence to the live path + make it the demo. The capability already exists (cross_clause, RAG) — you mostly need wiring + a
  ProjectGraph.
  2. Ship the Change-Impact Report (revision diff → cross-doc conflict → cost/time impact). Nothing in the incumbent stack does this with AI; it's a
  wedge nobody owns.
  3. Project Health dashboard from data you already extract (Risk/Contract/Docs/Governance now; Schedule/Cost after integration).
  4. Human-feedback → eval flywheel. Turn HITL corrections into golden cases. Compounding quality moat.
  5. Morning Briefing (email/Slack digest) as the daily-adoption hook.
  6. Connectors (P6 XER/XML, MSP, Procore/Aconex export) to become the audit layer on top of systems of record rather than a competitor to them.

  ---
  Phase 9 — Roadmap

  90-Day (consolidate the wedge, make the differentiator real)

  - [Critical] ProjectGraph (Tier-2): cross-document coherence on the live path, multi-clause, LLM-on for project re-score. Retire low_budget_mode
  default for project scoring. Makes the headline feature true.
  - [Critical] Typed graph state: replace dict[str,Any] aliases with Pydantic models; introduce NodeResult{status,error} to end silent degradation.
  Foundation for everything.
  - [Critical] Repo hygiene + secret sweep: purge root scripts/logs/test.db/nul, add .gitignore guards and a CI secret-scan. One day, big credibility
  return.
  - [Important] Document revision + clause-level diff v1 → first Change-Impact Report.
  - [Important] Wire HITL corrections into the golden corpus.
  - [Nice] Resolve product identity in copy: lead with "Cross-Document Coherence & Change-Impact Auditor."

  6-Month (become a daily tool)

  - [Critical] Project Health Engine v1 (Risk/Contract/Docs/Governance dimensions) with honest nulls + trends; project_snapshot timeline store.
  - [Critical] Temporal early-warning detectors (snapshot deltas → scope creep, new incoherence, deadline risk).
  - [Important] Schedule ingestion: P6 XER/XML + MSP parsers → activity model → Schedule/Deliverables health.
  - [Important] Morning Briefing digest (email/Slack) + alert dedupe/ranking.
  - [Important] Configurable HITL policies + escalation timers.
  - [Nice] Confidence calibration tracking vs golden truth.

  12-Month (toward the platform / PMO)

  - [Critical] Portfolio/Program layer: cross-project health rollup, the Executive/PMO view.
  - [Important] Cost actuals + EVM (CPI/SPI) once schedule + cost integrations exist.
  - [Important] Connectors to Procore/Aconex/ACC as the audit layer.
  - [Important] Multi-industry abstraction (generalize "doc types" + coherence categories via config — your category_registry/centroid work is the seam
  for this).
  - [Nice] Closure/operations phase modules; benchmarking across projects.

  ---
  Phase 10 — Final Verdict

  Scores (repeated with rationale in the Executive Summary table): Technical 6.5 · Product 5.0 · Scalability 6.0 · Adoption 4.5 · AI Readiness 7.5 ·
  Enterprise 5.5 · Long-Term Potential 8.0.

  1. Can C2Pro become a category-leading platform? Yes — conditionally. The AI foundation, eval discipline, HITL, and coherence philosophy are genuinely
  top-decile for the stage. But only if you (a) make cross-document coherence real in the hot path, (b) build the temporal/versioning core, and (c) add a
  health engine. Without those three, it plateaus as a competent document analyzer. The probability is good if focus replaces sprawl.

  2. Biggest risks: differentiator–reality gap; no temporal core; scope sprawl diluting the few deep features; silent-failure-induced false trust;
  schedule blindness.

  3. Biggest opportunities: Change-Impact Report (unowned wedge); live cross-doc coherence; health dashboard from existing data; HITL→eval flywheel;
  morning-briefing adoption hook; audit-layer connectors.

  4. What to build next (the single most important thing): the ProjectGraph + revision-diff pairing that produces an evidence-cited Change-Impact /
  Cross-Document Coherence report on every new document revision. That one loop converts the platform from "scores a document" to "watches a project."

  5. If I were CTO — top 10 priorities (in order):
  1. Make cross-document coherence the live, LLM-on path (ProjectGraph).
  2. Type the graph state (Pydantic) and replace silent except: return [] with NodeResult.
  3. Ship document revisions + clause-level semantic diff → Change-Impact Report.
  4. Build project_snapshot temporal store (unlocks trends/early-warning/health).
  5. Project Health Engine v1 (dimensions buildable from current data) with honest nulls.
  6. Repo hygiene + CI secret-scan + DLQ/degradation alerting.
  7. HITL corrections → golden corpus flywheel + confidence calibration.
  8. Temporal early-warning detectors + alert dedupe/ranking + Morning Briefing.
  9. Schedule ingestion (P6/MSP) to light up Schedule/Cost/Deliverables health.
  10. Consolidate the 25 modules: kill or finish half-built ones before adding new scope; pick the Contract-Manager beachhead and make it flawless.

  ---
  Missing Capabilities Required to Reach World-Class Status

  Ranked. BI = Business Impact, TC = Technical Complexity, SI = Strategic Importance, Priority = implementation order (P0 = now).

  ┌─────┬────────────────────────────────────────────────────────────────────────────────────┬──────────┬────────┬────────────────────────┬──────────┐
  │  #  │                                 Missing capability                                 │    BI    │   TC   │           SI           │ Priority │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 1   │ Temporal/versioning core (revisions, snapshots, project timeline)                  │ Critical │ High   │ Critical               │ P0       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 2   │ Live cross-document coherence in the hot path (real ProjectGraph, multi-clause,    │ Critical │ Medium │ Critical               │ P0       │
  │     │ LLM-on)                                                                            │          │        │                        │          │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 3   │ Clause-level semantic diff + Change-Impact Report                                  │ Critical │ High   │ Critical               │ P0       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 4   │ Typed graph state + no-silent-failure (NodeResult)                                 │ High     │ Medium │ High                   │ P0       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 5   │ Project Health Engine (multi-dimensional, honest nulls, trends)                    │ Critical │ High   │ Critical               │ P1       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 6   │ Temporal early-warning detectors (deltas → scope creep/slip/new incoherence)       │ Critical │ Medium │ Critical               │ P1       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 7   │ HITL → eval flywheel + confidence calibration                                      │ High     │ Medium │ High                   │ P1       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 8   │ Daily adoption hook (Morning Briefing digest, alert ranking/dedupe)                │ High     │ Low    │ High                   │ P1       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 9   │ Schedule model + P6/MSP ingestion (CPM, SPI)                                       │ High     │ High   │ High                   │ P2       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 10  │ Cost actuals + EVM (CPI/EV/AC)                                                     │ High     │ High   │ Medium                 │ P2       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 11  │ Change Order / RFI as first-class domain objects                                   │ High     │ Medium │ High                   │ P2       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 12  │ Portfolio / Program (PMO) layer                                                    │ High     │ High   │ Critical (for vision)  │ P2       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 13  │ Connectors (Procore/Aconex/ACC ingest; export to BI)                               │ Medium   │ Medium │ High                   │ P3       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 14  │ Configurable HITL policies + escalation timers + RBAC depth                        │ Medium   │ Medium │ High (enterprise)      │ P3       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 15  │ Multi-industry config abstraction (doc-types/categories as config)                 │ Medium   │ Medium │ High (TAM)             │ P3       │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 16  │ Compliance posture (SOC2 evidence, audit export, data residency)                   │ Medium   │ Medium │ High (enterprise       │ P3       │
  │     │                                                                                    │          │        │ sales)                 │          │
  ├─────┼────────────────────────────────────────────────────────────────────────────────────┼──────────┼────────┼────────────────────────┼──────────┤
  │ 17  │ Closure/Operations lifecycle modules                                               │ Low      │ Medium │ Medium                 │ P4       │
  └─────┴────────────────────────────────────────────────────────────────────────────────────┴──────────┴────────┴────────────────────────┴──────────┘

  ---
  Bottom line

  You have built the hard, unglamorous 60% — the AI plumbing, the orchestration, the evals, the HITL, the honest-scoring conscience — that most teams
  skip and never recover from. What's missing is the product spine: time, change, and health. Build those three, ruthlessly resist adding a 26th module
  until you do, and C2Pro has a credible path to category leadership. Keep shipping surfaces over that hollow spine, and it stays an impressive demo.

  ---
  Want me to go one level deeper on any single phase (e.g., a concrete ProjectGraph + Pydantic-state design with file-by-file changes, or a clause-diff
  engine spec)? I kept each phase at decision-altitude here; I can turn any of them into an implementable design. I'll also save the core architectural
  findings to project memory so the next session starts from this baseline.