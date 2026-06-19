# MASTER AUDIT CONSOLIDATION — C2Pro Strategic Synthesis

**Scope limitation:** this is **not a new repo audit**. It synthesizes the four uploaded audits as expert testimony. Where the audits make code-level claims, I treat them as claims unless multiple audits converge or the claim is very specific and internally consistent.

The strongest consolidated conclusion is blunt: **C2Pro has a serious technical foundation, but the product reality is still closer to document / contract intelligence than true project intelligence.** All four audits converge on that core point. Codex says C2Pro is “closer to a contract/document intelligence platform” than a living project system; DeepSeek calls it a “document intelligence engine with a dashboard”; Gemini says it is engineered like SaaS but functions as a static document parser; Claude calls it a high-quality document-analysis platform “wearing the costume” of a project-intelligence platform.    

---

## PHASE 1 — Audit Cross-Comparison Matrix

Legend: **S = supports**, **P = partially supports**, **C = contradicts**, **I = ignored / no material position**

| Finding                                                                | Claude | Codex | DeepSeek | Gemini | Confidence      |
| ---------------------------------------------------------------------- | -----: | ----: | -------: | -----: | --------------- |
| Strong engineering foundation: Hexagonal/DDD, RLS, LangGraph, CI/tests |      S |     S |        S |      S | **HIGH**        |
| Product is not yet true project intelligence                           |      S |     S |        S |      S | **HIGH**        |
| Current core is document / contract intelligence                       |      S |     S |        S |      S | **HIGH**        |
| Coherence ≠ project health                                             |      S |     S |        S |      S | **HIGH**        |
| Missing project health engine                                          |      S |     S |        S |      S | **HIGH**        |
| Missing temporal / versioning / semantic diff core                     |      S |     S |        S |      S | **HIGH**        |
| Current workflow is too document-centric for daily PM use              |      S |     S |        S |      S | **HIGH**        |
| LangGraph is useful but not optimally used for project intelligence    |      S |     S |        S |      S | **HIGH**        |
| Main orchestration is too single-document oriented                     |      S |     P |        S |      P | **HIGH**        |
| Current alerting is reactive, not predictive / correlated              |      S |     S |        S |      S | **HIGH**        |
| HITL exists technically but is not yet a mature product workflow       |      S |     S |        S |      S | **HIGH**        |
| Need persona-based review queues                                       |      S |     S |        P |      S | **HIGH**        |
| Need integration with existing PM systems rather than replacement      |      S |     S |        S |      S | **HIGH**        |
| Contract Manager is the best beachhead persona                         |      S |     P |        P |      P | **MEDIUM-HIGH** |
| Runtime bug in coherence bridge / `seed_signals` drift                 |    I/P |     S |        S |      I | **MEDIUM-HIGH** |
| Coherence hot path is degraded / not true cross-doc coherence          |      S |     P |      I/P |    I/P | **MEDIUM-HIGH** |
| Need ProjectGraph / two-tier map-reduce project synthesis              |      S |     P |        P |      S | **HIGH**        |
| Need Pydantic / typed graph state and better failure semantics         |      S |     P |        P |    I/P | **MEDIUM-HIGH** |
| Excel parser fragility is a critical issue                             |    I/P |   I/P |        S |      I | **MEDIUM**      |
| No BIM/IFC support is a major gap                                      |      I |     P |        S |      I | **LOW-MEDIUM**  |
| Mobile field interface is essential soon                               |      I |     P |        S |      I | **LOW-MEDIUM**  |
| True graph database Neo4j/Memgraph is needed                           |      I |   I/P |      I/P |      S | **LOW**         |
| C2Pro should become full “project operating system”                    |    C/P |   C/P |        S |    C/P | **LOW-MEDIUM**  |

---

## PHASE 2 — Consensus Extraction

### Architecture

**Consensus finding:** the modular-monolith / hexagonal / multi-tenant foundation is directionally correct.
**Evidence:** all audits cite strong architecture: DDD/hexagonal boundaries, RLS, Clerk, FastAPI, Postgres/pgvector, Celery, LangGraph, LangSmith, CI/test discipline. Claude and DeepSeek give especially specific evidence around LangGraph, tests, migrations, RLS and CI.  
**Strategic impact:** C2Pro does not need a platform rewrite. It needs a **product-state redesign** on top of a solid base.
**Urgency:** **Critical**, but not because the architecture is bad; because the current architecture is pointed at the wrong unit of work.

### Product

**Consensus finding:** C2Pro is not yet a daily-use PM / EPC platform.
**Evidence:** Codex says it lacks real workflows for PMs, construction managers, executives and PMO teams; DeepSeek lists missing workflows such as change orders, RFIs, progress reporting, meetings, inspections, invoice verification and risk register management; Gemini says real PMs do not want another tool just to upload documents and get a score.   
**Strategic impact:** product-market fit risk is higher than technical risk.
**Urgency:** **Critical**.

### AI / LangGraph

**Consensus finding:** LangGraph is valuable but currently used more as a document pipeline than a project intelligence system.
**Evidence:** Codex says the graph is mostly a pipeline DAG; DeepSeek says LangGraph is used as a workflow pipeline builder rather than an agentic state machine; Gemini says it is partially effective but mostly a DAG; Claude says it is near-optimal for single-document processing but wrong for project intelligence.    
**Strategic impact:** do not remove LangGraph; change its granularity.
**Urgency:** **Critical** for v3.0.

### User Experience

**Consensus finding:** the UI is a dashboard, not yet a workbench.
**Evidence:** Codex calls for a shift from dashboard to workbench, AI output to decisions, alerts to accountable actions, and single-project analysis to portfolio intelligence; DeepSeek lists missing PM workflows and visualizations; Gemini says the current UX is not daily-use ready.   
**Strategic impact:** more charts alone will not fix adoption. The product needs a daily action loop.
**Urgency:** **Important to Critical**, depending on whether you are building demo or production adoption.

### Project Intelligence

**Consensus finding:** the missing layer is continuous project state: revisions, snapshots, deltas, health, alerts, decisions.
**Evidence:** Codex proposes project event store, health snapshots and role-specific queues; Claude proposes a two-tier DocumentGraph + ProjectGraph; Gemini calls for semantic temporal tracking; DeepSeek calls for project health, schedule/cost metrics and workflows.    
**Strategic impact:** this is the central architectural missing piece.
**Urgency:** **Critical**.

### Scalability

**Consensus finding:** infrastructure has scalable ingredients, but the current intelligence flow is not scalable as project-level reasoning.
**Evidence:** Claude flags single-document framing, singleton graph/checkpointer concerns and no temporal dimension; DeepSeek flags single-document and sequential pipeline limits; Codex flags broad shared state and hidden failures.   
**Strategic impact:** technical scale will not matter if the semantic unit remains “one document” instead of “project state change.”
**Urgency:** **Important**, becoming **Critical** before enterprise pilots.

### Enterprise Readiness

**Consensus finding:** enterprise foundations exist, but trust, auditability, RBAC/SSO, evidence and workflow maturity are incomplete.
**Evidence:** Claude scores Enterprise Readiness 5.5 despite RLS/HITL/audit foundations; DeepSeek scores it 5/10 due to missing SSO, complete audit logging, certifications and support model; Gemini scores higher but still notes SSO and audit gaps.   
**Strategic impact:** enterprise buyers may be interested but will not trust opaque or non-auditable AI outputs.
**Urgency:** **Important**, with provenance as **Critical**.

### Technical Debt

**Consensus finding:** the most dangerous technical debt is not cosmetic; it is semantic and runtime-contract debt.
**Evidence:** Codex flags runtime/design split, signature drift, metadata-only reupload and provenance gaps; Claude flags untyped graph state, mixed mutation contracts, silent degradation, duplicate coherence paths and repo hygiene; DeepSeek flags dual module structure, broken bridge, Excel parser fragility and evidence gaps.   
**Strategic impact:** these issues undermine trust in the core scoring proposition.
**Urgency:** **Critical** for runtime correctness and provenance; **Important** for cleanup.

---

## PHASE 3 — Contradictions & Disagreements

| Topic                    | Position A                                                 | Position B                                                            | Most Likely Reality                                                                                                                                | Confidence      |
| ------------------------ | ---------------------------------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| LangGraph quality        | Claude: good / near-optimal for single-document processing | DeepSeek/Gemini/Codex: underused, pipeline-like, not truly agentic    | Both are true. LangGraph is technically sound for document workflows but strategically wrong as the main project intelligence unit.                | **HIGH**        |
| Target product identity  | DeepSeek leans toward “project operating system”           | Codex/Claude/Gemini lean toward overlay on existing PM systems        | C2Pro should **not** try to become Primavera/Procore. It should become an AI project intelligence overlay first.                                   | **HIGH**        |
| Product maturity score   | Claude gives Product 5/10                                  | Codex/DeepSeek/Gemini give ~3–3.5/10                                  | Product maturity is probably closer to **3.5–4.5/10**. Claude gives credit for surfaces and philosophy; others weight daily workflow more heavily. | **MEDIUM-HIGH** |
| AI readiness score       | Gemini 9/10                                                | DeepSeek 6/10, Codex 6.5/10, Claude 7.5/10                            | Likely **7/10**. Strong AI infra exists, but the most valuable AI path is not fully wired into product reality.                                    | **MEDIUM-HIGH** |
| Scalability score        | Gemini 8/10                                                | Codex/DeepSeek 5/10, Claude 6/10                                      | Likely **5.5–6/10**. Infra scales better than product intelligence flow.                                                                           | **HIGH**        |
| Need for BIM/mobile soon | DeepSeek stresses BIM/mobile/field workflows               | Claude/Codex/Gemini mostly defer or ignore                            | BIM/mobile are future expansion items, not v3.0 core. Premature now.                                                                               | **MEDIUM**      |
| Need true graph database | Gemini suggests Neo4j/Memgraph                             | Others emphasize knowledge graph concept but not necessarily graph DB | Graph reasoning may be useful later, but a dedicated graph DB is not currently proven necessary.                                                   | **MEDIUM-HIGH** |
| Gantt/workbench priority | DeepSeek prioritizes interactive Gantt early               | Claude/Codex prioritize ProjectGraph, diff, coherence, health         | Read-only schedule import/baseline is important; full interactive scheduling risks competing with P6/MS Project too early.                         | **HIGH**        |

---

## PHASE 4 — False Positives & Overstatements

| Claim                                                    | Source Audit | Why It May Be Incorrect / Overstated                                                                                                                                                                                                 | Confidence      |
| -------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------- |
| “No competitor does cross-document consistency analysis” | DeepSeek     | Too broad. Some enterprise tools, legal AI tools or document-control products may offer partial comparison / consistency features. Safer: C2Pro can differentiate through **evidence-backed EPC-specific cross-document coherence**. | **HIGH**        |
| “Nobody in construction tech is doing this well”         | DeepSeek     | Market claim not evidenced by the audits. It may be directionally true, but cannot be accepted as fact from repo evidence.                                                                                                           | **HIGH**        |
| “Mobile field interface is a top-11 priority”            | DeepSeek     | Valid for construction platforms, but C2Pro’s wedge is not yet field execution. Premature before temporal diff, health, coherence and alerts.                                                                                        | **MEDIUM-HIGH** |
| “BIM/IFC is table-stakes in 2026”                        | DeepSeek     | Important in construction tech, but not table-stakes for an AI contract/coherence wedge. Could distract from core.                                                                                                                   | **MEDIUM-HIGH** |
| “True Knowledge Graph Database is required”              | Gemini       | The need is for entity relationships and evidence graph; that does not automatically require Neo4j/Memgraph. Postgres + pgvector + relational edges may suffice initially.                                                           | **HIGH**        |
| “Project Health Vector is low complexity”                | Gemini       | Underestimates complexity. Health is easy to mock, hard to make trustworthy with real baselines, schedule logic, cost actuals and confidence.                                                                                        | **HIGH**        |
| “Project operating system” direction                     | DeepSeek     | Strategically risky. Competing with Primavera, Procore, Aconex or Unifier before owning the intelligence wedge would dilute focus.                                                                                                   | **HIGH**        |
| “AI Readiness 9/10”                                      | Gemini       | Too generous because the AI capability is not fully connected to the highest-value live product path.                                                                                                                                | **MEDIUM-HIGH** |
| “Scalability 8/10”                                       | Gemini       | Overweights backend statelessness/checkpointing and underweights single-document reasoning, state bloat and project synthesis gaps.                                                                                                  | **HIGH**        |

---

## PHASE 5 — Root Cause Analysis

### 1. Wrong primary unit of intelligence

**Explanation:** C2Pro reasons primarily around documents, not evolving project state.
**Consequences:** coherence is computed too locally; revision changes are not first-class; health, trend and early warning are structurally blocked.
**Affected subsystems:** LangGraph orchestration, coherence, alerts, document versioning, UX, reporting.

### 2. Coherence and health are conflated

**Explanation:** Coherence answers “do documents agree?” Health answers “is the project on track?” These are related but not equivalent. Claude makes this distinction most sharply, and all audits converge on it. 
**Consequences:** the main product score risks answering a question executives do not actually ask.
**Affected subsystems:** scoring, dashboards, executive reporting, alerts, product positioning.

### 3. No temporal model

**Explanation:** Version counters and reprocessing are not enough. The product needs revisions, snapshots, deltas, timelines and valid-from/valid-to semantics.
**Consequences:** no change-impact report, no trend alerts, no “what changed since yesterday?”, no serious early warning.
**Affected subsystems:** documents, RAG, knowledge graph, project state, alerts, reporting.

### 4. Orchestration granularity is too low-level

**Explanation:** the existing graph is valuable but centered on per-document analysis. The missing layer is a ProjectGraph / synthesis graph that operates on all current artifacts and deltas.
**Consequences:** cross-document coherence, health, alert correlation and executive reporting are bolted on rather than native.
**Affected subsystems:** LangGraph, Celery, persistence, coherence, health, HITL.

### 5. Findings are not yet converted into accountable workflows

**Explanation:** AI outputs are not consistently turned into owner/action/due-date/escalation/review objects.
**Consequences:** PMs and executives will see information, not operational leverage.
**Affected subsystems:** UX, alerts, HITL, notifications, PMO reporting.

---

## PHASE 6 — Strategic Project Identity

### What is C2Pro today?

**Choice: Document Analysis Platform**, more specifically an **AI contract/document intelligence platform with project scaffolding**.

It is not yet a Project Intelligence Platform because it lacks temporal project state, health engine, robust cross-document live coherence, project workflows and daily operating loops.

### What should C2Pro become?

**AI-native Project Intelligence Overlay.**

Not a full system of record. Not a Primavera replacement. Not a Procore replacement. The best defensible position is:

> C2Pro continuously reads project documents and execution records, detects changes, conflicts, risks and health deterioration, and turns them into evidence-backed decisions and review workflows.

### Expected market position

Initial wedge: **AI Cross-Document Coherence & Change-Impact Auditor for EPC / contract-heavy projects.**

Expansion path: **Project Health & Early Warning Layer** for PMO, owners, contractors and contract managers.

### Competitive advantage

The defensible advantage is not generic chat over documents. It is:

1. cross-document coherence,
2. semantic revision diff,
3. evidence-backed change-impact,
4. HITL validation,
5. health scoring with honest confidence,
6. integrations into existing project systems.

### Long-term defensibility

The moat is not the LLM. The moat is the **domain-specific evidence graph + human-validated project intelligence history**.

---

## PHASE 7 — Architectural Consensus

| Statement                                                   | Verdict             | Justification                                                                                              |
| ----------------------------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------- |
| LangGraph architecture is fundamentally sound               | **Partially Agree** | The tooling and foundations are sound, but current graph granularity is wrong for project intelligence.    |
| Current orchestration is a primary bottleneck               | **Agree**           | Not because LangGraph is bad, but because the hot path is document-centric and not a ProjectGraph.         |
| Project-state modeling is missing                           | **Agree**           | Strong consensus. This is the deepest missing abstraction.                                                 |
| Temporal intelligence is missing                            | **Agree**           | Strong consensus across all audits.                                                                        |
| Project health engine is missing                            | **Agree**           | All audits converge.                                                                                       |
| Alerting system is insufficient                             | **Agree**           | Plumbing exists, but correlation, impact, temporal triggers and ownership are incomplete.                  |
| HITL is strategically important                             | **Agree**           | It is a real differentiator, but must become persona-based workflow, not just approval interruption.       |
| Document intelligence is currently the strongest capability | **Agree**           | It is the strongest current product asset, but also the area where versioning/diff gaps are most damaging. |

---

## PHASE 8 — Unified Prioritization Matrix

| Recommendation                                                         | Category      | Impact | Complexity | Strategic Importance | Recommended Timing                                  |
| ---------------------------------------------------------------------- | ------------- | -----: | ---------: | -------------------: | --------------------------------------------------- |
| Fix coherence runtime/signature drift and broken hot path              | **Critical**  |      9 |          3 |                   10 | Next 30 days                                        |
| Create immutable document revisions with binary/version lineage        | **Critical**  |     10 |          7 |                   10 | Next 30–90 days                                     |
| Build semantic diff / Change-Impact Report v0                          | **Critical**  |     10 |          8 |                   10 | Next 90 days                                        |
| Introduce ProjectGraph / project synthesis layer                       | **Critical**  |     10 |          8 |                   10 | Next 90 days                                        |
| Make true cross-document coherence live, not side endpoint only        | **Critical**  |     10 |          6 |                   10 | Next 90 days                                        |
| Add project snapshots / temporal store                                 | **Critical**  |      9 |          7 |                   10 | Next 90 days                                        |
| Build Project Health Engine v0 with honest nulls                       | **Critical**  |     10 |          7 |                   10 | Next 90 days                                        |
| Add evidence-grade provenance: doc_rev/page/span/hash/confidence       | **Critical**  |      9 |          6 |                   10 | Next 90 days                                        |
| Replace silent failures with typed NodeResult/degraded-state reporting | **Critical**  |      9 |          5 |                    9 | Next 30–90 days                                     |
| Type graph state with Pydantic models                                  | **Important** |      8 |          6 |                    8 | Next 90 days                                        |
| Alert correlation, dedupe, severity × confidence × impact ranking      | **Important** |      8 |          5 |                    9 | Next 90 days                                        |
| Persona HITL queues and approval chains                                | **Important** |      8 |          6 |                    8 | Next 90 days                                        |
| Contract Manager workbench / beachhead workflow                        | **Important** |      9 |          6 |                    9 | Next 90 days                                        |
| Schedule/cost baseline import                                          | **Important** |      9 |          7 |                    9 | 3–6 months                                          |
| P6/MS Project/SharePoint/Procore/Aconex connectors                     | **Important** |      9 |          8 |                    9 | 3–6 months                                          |
| RFI / Change Order lifecycle                                           | **Important** |      8 |          6 |                    8 | 3–6 months                                          |
| Active learning from HITL into eval corpus                             | **Important** |      8 |          7 |                    8 | 3–6 months                                          |
| Morning Briefing / daily digest                                        | **Important** |      7 |          4 |                    8 | 3–6 months                                          |
| Portfolio PMO dashboard                                                | **Future**    |      8 |          6 |                    7 | 6–12 months                                         |
| Predictive forecasting                                                 | **Future**    |      8 |          9 |                    8 | 6–12 months                                         |
| BIM/IFC/4D/5D ingestion                                                | **Future**    |      6 |          9 |                    6 | 12 months+                                          |
| Mobile field reporting                                                 | **Future**    |      6 |          8 |                    5 | 12 months+                                          |
| Natural language rules engine                                          | **Future**    |      6 |          9 |                    6 | 12 months+                                          |
| Dedicated graph database                                               | **Future**    |      5 |          8 |                    5 | Only if relational graph model becomes insufficient |

---

## PHASE 9 — Master Consolidated Roadmap

### Next 30 Days — Stop trust leakage

1. Fix coherence runtime/signature drift.
2. Audit the live coherence path: confirm whether it is single-doc, low-budget, LLM/RAG-disabled, or API-only cross-doc.
3. Define canonical project-state objects: DocumentRevision, DocumentArtifact, Clause, Obligation, WBSItem, BudgetItem, Risk, ChangeSet, ProjectSnapshot.
4. Define NodeResult / degraded execution semantics.
5. Freeze scope expansion until the core intelligence loop is clarified.
6. Clean repository hygiene and secret/log/test-db risks.
7. Produce one target demo flow: **new revision → semantic diff → cross-doc conflict → impact → alert → HITL → health update**.

### Next 90 Days — Make the differentiator real

1. Implement immutable document revisions and semantic diff v0.
2. Implement ProjectGraph as synthesis layer above DocumentGraph.
3. Make cross-document coherence run on real project artifacts.
4. Add temporal project snapshots.
5. Build Project Health v0 with dimensions that current data can support: contract, documentation, risk, governance; schedule/cost can start as partial/confidence-limited.
6. Convert alerts into accountable actions: owner, due date, evidence, impact, confidence, status.
7. Build persona HITL queues, starting with Contract Manager.
8. Add evidence-grade provenance to all findings.

### Next 6 Months — Move from audit to operating workflow

1. Add Change Order and RFI workflows.
2. Add schedule/cost baseline import, at least from robust Excel and one standard format.
3. Add alert correlation, dedupe and digest.
4. Integrate HITL corrections into evaluation/golden corpus.
5. Add Contract Obligation Matrix.
6. Add executive health report with confidence and evidence.
7. Prototype connectors: SharePoint/OneDrive first, then P6/MS Project/Procore/Aconex depending on target customers.
8. Build morning briefing as daily adoption hook.

### Next 12 Months — Enterprise intelligence layer

1. Portfolio health dashboard.
2. Enterprise RBAC/SSO/audit/export hardening.
3. Predictive early-warning models based on project snapshots.
4. Cross-project benchmarking.
5. Integration platform / connector ecosystem.
6. Optional BIM/IFC/field/mobile expansion only after the contract/project intelligence wedge is proven.

---

## PHASE 10 — Final Verdict

### Consolidated Scores

| Dimension               |                                    Score | Rationale                                                                                                                                 |
| ----------------------- | ---------------------------------------: | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Technical Maturity      |                             **6.8 / 10** | Strong architecture, tests, CI, RLS, LangGraph, AI infra; weakened by runtime drift, untyped state, silent failures and duplicated paths. |
| Product Maturity        |                             **3.8 / 10** | Good foundations and surfaces, but not yet mapped to daily PM/EPC workflows.                                                              |
| Architecture Quality    |                             **7.0 / 10** | Good modular foundation; missing project-state and temporal architecture.                                                                 |
| AI Readiness            |                             **7.0 / 10** | Strong AI tooling, routing, LangSmith, RAG and HITL; but highest-value AI path is not fully live/productized.                             |
| Enterprise Readiness    |                             **5.5 / 10** | RLS/HITL/audit foundations exist; SSO/RBAC/compliance/provenance/workflow maturity incomplete.                                            |
| Scalability             |                             **5.8 / 10** | Infra is promising; current intelligence model is still too single-document and pipeline-bound.                                           |
| User Adoption Potential | **4.0 / 10 today; 8.0+ if repositioned** | Current dashboard/coherence score is insufficient; change-impact + early-warning workflow could be highly compelling.                     |
| Long-Term Potential     |                             **8.5 / 10** | Large opportunity if focus replaces scope sprawl.                                                                                         |

### 1. Single most important misunderstanding

The team appears to be treating **project intelligence as advanced document analysis**.

That is the wrong abstraction. Project intelligence requires **state over time**: revisions, baselines, deltas, obligations, progress, cost, risk, decisions and human validation.

### 2. Biggest risk if current trajectory continues

C2Pro becomes an impressive demo that sophisticated buyers abandon after testing, because the headline promise — live project intelligence / cross-document health / early warning — does not exist deeply enough in the daily workflow.

### 3. Biggest opportunity

Own the wedge of:

> **Evidence-backed Change-Impact and Cross-Document Coherence for EPC / contract-heavy projects.**

That is narrower than “AI project management,” but much more defensible.

### 4. Primary focus of C2Pro v3.0

**C2Pro v3.0 should be the ProjectGraph + Temporal Diff release.**

The core v3.0 loop should be:

**Document revision uploaded → semantic diff → cross-document coherence → project snapshot delta → impact estimate → alert/action → HITL review → health update.**

### 5. First 10 actions if I became CTO tomorrow

1. Freeze new feature expansion for 2–3 sprints.
2. Validate the live coherence path and fix runtime/signature drift.
3. Define the canonical project-state model.
4. Implement immutable DocumentRevision and ProjectSnapshot.
5. Build semantic diff v0 for clauses and key project objects.
6. Introduce ProjectGraph as the project-level synthesis layer.
7. Replace silent failure patterns with NodeResult/degraded-state propagation.
8. Make evidence/provenance mandatory for every finding.
9. Build one Contract Manager workbench around change-impact review.
10. Reposition the product externally as an AI project intelligence overlay, not a project management replacement.

**Final consolidated verdict:** C2Pro is not weak. It is prematurely broad. The foundation is good enough to build something serious, but only if the next phase narrows the product to the missing core: **temporal project intelligence with evidence-backed change impact.**
