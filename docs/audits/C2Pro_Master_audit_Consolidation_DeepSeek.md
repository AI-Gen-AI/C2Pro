# MASTER AUDIT CONSOLIDATION — C2Pro Strategic Synthesis

**Date:** 2026-06-07  
**Role:** Independent Chief Architect / Principal Product Strategist  
**Method:** Meta‑analysis of four independent expert audits (Claude, Codex, DeepSeek, Gemini)  
**Status:** Consolidated findings – not a new repository audit

---

## PHASE 1 — AUDIT CROSS‑COMPARISON MATRIX

| Finding | Claude | Codex | DeepSeek | Gemini | Confidence |
|--------|--------|-------|----------|--------|------------|
| **Missing temporal/versioning core** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Cross‑document coherence not in hot path / degraded** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Project health engine missing** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **No semantic document diffing (V1 vs V2)** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Coherence score ≠ project health** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **LangGraph orchestration – partially optimal, partially bottleneck** | ✅ (near‑optimal for single doc) | ❌ (not yet optimal) | ❌ (glorified pipeline) | ❌ (rigid DAG) | **MEDIUM** (disagreement) |
| **Typed graph state missing / dict[str,Any] debt** | ✅ | ❌ (not mentioned) | ❌ (not mentioned) | ❌ (not mentioned) | **LOW** (only Claude) |
| **Silent failure swallowing (except Exception → [])** | ✅ | ✅ | ✅ | ❌ | **HIGH** (3/4) |
| **HITL is technically sound but product‑incomplete** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Alerting exists but lacks correlation / early warning** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Repo hygiene / root clutter** | ✅ | ❌ | ✅ | ❌ | **MEDIUM** (2/4) |
| **Document intelligence is strongest capability** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **LangGraph Postgres checkpointer is a strength** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Multi‑tenancy (RLS) is production‑grade** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Test culture / CI is mature** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **AI readiness (evals, honest scoring, routing) is best‑in‑class** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Product identity confusion (document vs project intelligence)** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Dual module structure / duplicate coherence engines** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Schedule / cost intelligence missing (P6, MSP, EVM)** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **No BIM / field / mobile workflows** | ❌ | ✅ | ✅ | ✅ | **HIGH** (3/4) |
| **No portfolio / PMO layer** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Coherence scorer node may have runtime bug (param mismatch)** | ❌ | ❌ | ✅ | ❌ | **LOW** (only DeepSeek) |
| **Low_budget_mode degrades coherence in hot path** | ✅ | ✅ | ❌ | ❌ | **MEDIUM** (2/4) |
| **Knowledge graph is rudimentary** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Excel parser fragility** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Scalability limited by single‑doc sequential processing** | ✅ | ✅ | ✅ | ✅ | **HIGH** |
| **Enterprise readiness needs SSO/RBAC depth, compliance** | ✅ | ✅ | ✅ | ✅ | **HIGH** |

---

## PHASE 2 — CONSENSUS EXTRACTION

### Architecture
- **Hexagonal / DDD discipline** is widely praised.  
  *Supporting evidence*: Claude, Codex, DeepSeek, Gemini all note strict domain isolation, ports/adapters, and clean module boundaries in newer modules.
- **Multi‑tenancy via Postgres RLS** is production‑grade and fail‑closed.  
  *Strategic impact*: Enables enterprise SaaS without re‑architecture.
- **LangGraph with Postgres checkpointer** is the right foundation for stateful AI workflows.  
  *Implementation urgency*: Medium – keep, but evolve from pipeline to event‑driven mesh.

### Product
- **No project health engine** – coherence score is not health.  
  *Supporting evidence*: All four audits state this explicitly.  
  *Strategic impact*: **Existential** – product cannot answer core user question.  
  *Urgency*: **Critical** (P0).
- **No temporal/versioning core** – document versions are counters, not history.  
  *Strategic impact*: Blocks “living project,” evolution tracking, early warning, change orders.  
  *Urgency*: **Critical** (P0).
- **Cross‑document coherence is not on the live hot path** – the headline feature runs degraded (low_budget_mode, single synthetic clause).  
  *Strategic impact*: Differentiator is vapor for typical user.  
  *Urgency*: **Critical** (P0).
- **Product identity confusion** – marketed as “living project intelligence” but functions as document/contract coherence analyzer.  
  *Strategic impact*: Misaligned go‑to‑market; user expectations mismatch.  
  *Urgency*: **High** (P1).

### AI / LangGraph
- **AI readiness is best‑in‑class for stage** – model routing, prompt cache, cost control, PII gate, golden evals, honest scoring.  
  *Supporting evidence*: Claude (7.5), Codex (6.5), DeepSeek (6), Gemini (9). Consensus: strong foundation.
- **LangGraph is used as a pipeline DAG, not a true agentic mesh** – but it works well for single‑doc processing.  
  *Disagreement noted*: See Phase 3. Consensus: it is not the bottleneck; missing project‑level graph is the real issue.
- **HITL exists and is correctly implemented** (langgraph.interrupt, checkpointer, resumable).  
  *Gaps*: No role queues, no approval chains, no learning loop from corrections.
- **Silent failure swallowing** (broad `except Exception: return []`) is dangerous – degrades trust and hides extraction failures.  
  *Consensus*: 3 of 4 audits flag this as high risk.

### User Experience
- **No daily‑use loop** – product is document‑centric, not PM‑centric.  
  *Supporting evidence*: All audits rate user adoption potential low (2–4.5/10).  
  *Root cause*: Missing workflows (change orders, RFIs, progress tracking, daily briefings).
- **Role‑specific workflows absent** – Contract Manager is the best fit today; Project Manager, Construction Manager, Executive have little to do.

### Project Intelligence
- **Temporal intelligence missing** – no snapshots, no trend analysis, no “what changed.”
- **Schedule/cost intelligence missing** – cannot parse P6/MS Project, no EVM, no SPI/CPI.
- **No change‑order / RFI domain objects** – generic documents only.
- **Knowledge graph is rudimentary** – nodes/edges without reasoning.

### Scalability
- **Single‑doc sequential processing** limits throughput.  
  *Consensus*: Not a near‑term blocker at current scale, but will become one.
- **Celery + Postgres checkpointer** scales horizontally in theory, but singleton compiled graph may cause coordination issues.

### Enterprise Readiness
- **RLS + Clerk + audit + DLQ** are real.  
- **Missing**: SSO/SAML depth, SOC2 evidence, data residency, configurable HITL policies, escalation timers.

### Technical Debt
- **Dual module structure** (`src/coherence/` vs `src/modules/coherence/`) – duplicate engines.  
- **Repository root clutter** (stray scripts, logs, test.db) – credibility and security risk.  
- **Mixed mutation contract** in LangGraph nodes (some mutate state, some return patches).

---

## PHASE 3 — CONTRADICTIONS & DISAGREEMENTS

| Topic | Position A | Position B | Most Likely Reality | Confidence |
|-------|------------|------------|---------------------|------------|
| **LangGraph usage** | Claude: “near‑optimally for single‑doc” – Codex: “not yet optimal” – DeepSeek: “glorified pipeline” – Gemini: “rigid DAG” | – | **Partially optimal**: The graph is correct for per‑document extraction, but the *unit of work* is wrong for project intelligence. The real problem is missing project‑level graph, not LangGraph itself. | HIGH |
| **Low_budget_mode coherence degradation** | Claude & DeepSeek flag it as critical | Codex & Gemini do not mention | **Likely true**: The live per‑upload coherence uses low_budget_mode, skipping LLM nodes. This is a product‑reality gap. | MEDIUM |
| **Coherence scorer runtime bug (param mismatch)** | Only DeepSeek claims `seed_signals`/`seed_coverage` kwargs cause breakage | Claude, Codex, Gemini do not mention | **Low confidence** – may be a misinterpretation or local uncommitted change. Not corroborated. | LOW |
| **Repo hygiene severity** | Claude & DeepSeek call it a “credibility tax” and “security‑leak surface” | Codex & Gemini ignore | **Medium severity** – likely present but not existential. Still worth cleaning. | MEDIUM |
| **Primary bottleneck** | Claude: missing temporal core + cross‑doc coherence. DeepSeek: missing health system. Gemini: missing temporal diffing. Codex: missing versioning. | – | **Root cause synthesis**: The three missing subsystems (temporal/versioning, cross‑doc coherence, health) are co‑equal bottlenecks. No single one is the only bottleneck. | HIGH |
| **Adoption potential** | DeepSeek: 2/10, Codex: 2.5/10, Gemini: 2/10, Claude: 4.5/10 | Claude slightly more optimistic | **Very low** – all audits agree it is not daily‑use ready. Claude’s higher score reflects UI surface completeness, not workflow adoption. | HIGH |

---

## PHASE 4 — FALSE POSITIVES & OVERSTATEMENTS

| Claim | Source Audit | Why It May Be Incorrect | Confidence |
|-------|--------------|--------------------------|------------|
| “coherence_scorer_node passes kwargs that evaluate_coherence_async() doesn’t accept — broken” | DeepSeek | No other audit found this; may be a local uncommitted change or misinterpretation. The codebase may have been updated, or the call signature differs. | LOW |
| “Hardcoded Excel row/column assumptions (row 10, Spanish column names)” | DeepSeek, Claude | Likely true for specific BC3 or schedule formats, but overstates fragility. Many Excel parsers are robust; the claim may be exaggerated. | MEDIUM (true in some cases, but not universal) |
| “__pycache__ in git (infrastructure/supabase/)” | DeepSeek | Minor hygiene issue; not a strategic risk. Overstated as “technical debt.” | HIGH (true but low impact) |
| “PostgreSQL checkpoint table will grow unbounded” | DeepSeek | True, but manageable with retention policies and partitioning. Not an immediate crisis. | MEDIUM (real but solvable) |
| “No horizontal scaling – Celery processes sequentially” | DeepSeek, Claude | Celery can scale horizontally with more workers. The bottleneck is single‑doc graph, not Celery itself. Overstatement. | MEDIUM |

---

## PHASE 5 — ROOT CAUSE ANALYSIS

### Root Cause 1: Missing Temporal Project‑State Model
**Explanation**: The system treats each document analysis as a standalone snapshot. There is no event‑sourced or versioned representation of project entities (risks, WBS, obligations, budgets) over time. Version is just a counter, not a history.

**Consequences**:  
- Cannot answer “what changed” between revisions.  
- No trend analysis, early warning, or predictive alerts.  
- Change‑order and RFI workflows impossible.  
- “Living project companion” is marketing fiction.

**Affected subsystems**: Documents, Analysis, Coherence, Alerts, Health (missing), Knowledge Graph.

### Root Cause 2: Product Identity / Scope Confusion
**Explanation**: The team built a world‑class document‑coherence analyzer but markets it as a project intelligence platform. The mental model of the product is document‑centric, not project‑centric.

**Consequences**:  
- User adoption near zero for PMs.  
- Roadmap sprawl – adding modules without consolidating the core.  
- Differentiator (cross‑document coherence) is not live in the hot path.  
- Executive dashboard, portfolio view, health metrics absent.

**Affected subsystems**: Entire product strategy, UX, roadmap.

### Root Cause 3: Orchestration Unit of Work is Wrong
**Explanation**: The LangGraph orchestrates “analyze one document” instead of “synthesize project state from N documents.” Cross‑document reasoning is an afterthought (separate API endpoint).

**Consequences**:  
- Coherence score is computed per document against itself.  
- No project‑level graph to fuse contract, schedule, budget.  
- Every new document triggers a full re‑analysis of that document, not a delta against project state.

**Affected subsystems**: Analysis graph, Coherence engine, API design.

### Root Cause 4: Silent Failure Swallowing
**Explanation**: Widespread `except Exception: return []` makes extraction failures indistinguishable from “nothing found.”

**Consequences**:  
- False confidence – user sees “0 risks” when extractor crashed.  
- No degradation alerts for operations.  
- Hard to debug or improve extraction quality.

**Affected subsystems**: All extraction nodes (N4, N5, N6, N8, N10, stakeholders, KG).

### Root Cause 5: No Domain Model for Change, Health, or Workflow
**Explanation**: Change orders, RFIs, progress reports, schedule updates, and health scores are not first‑class domain objects. They are either generic documents or absent.

**Consequences**:  
- Cannot track approval chains, impacts, or lifecycle.  
- No actionable “today” queue for PMs.  
- Alerts are reactive and uncorrelated.

**Affected subsystems**: Projects, Alerts, HITL, Workflow (missing).

---

## PHASE 6 — STRATEGIC PROJECT IDENTITY

### What is C2Pro TODAY?

**Document Analysis Platform** (with strong contract/coherence specialization)

All audits converge: it ingests documents, extracts clauses/risks/WBS, computes an internal coherence score, and displays results. It is not a project intelligence platform because it lacks:
- Temporal tracking
- Cross‑document synthesis in the live path
- Health metrics
- PM workflows

### What SHOULD C2Pro become?

**AI‑Native Project Intelligence Overlay**  
Not a replacement for Primavera, Procore, or Aconex. Instead, the intelligence layer that sits on top of existing systems of record.

**Why**:  
- The market gap is not another document store or scheduler – it’s an AI that reads, compares, and alerts across all project artifacts.  
- The team’s AI eval discipline and honest scoring are a genuine moat.  
- EPC/construction teams have massive document volumes but no tool that semantically tracks changes and conflicts.

**Expected market position**: First‑mover in AI‑powered cross‑document coherence and change‑impact analysis for capital projects.

**Competitive advantage**:  
- Real cross‑document coherence (once wired correctly) is defensible.  
- HITL + audit trail meets enterprise compliance needs.  
- Golden‑corpus evals ensure quality.

**Long‑term defensibility**:  
- Domain‑specific model fine‑tuning (contracts, schedules, BOQs).  
- Network effects from cross‑project pattern detection (PMO benchmarking).  
- Integration depth with existing PM systems.

---

## PHASE 7 — ARCHITECTURAL CONSENSUS

| Statement | Verdict | Justification |
|-----------|---------|----------------|
| **LangGraph architecture is fundamentally sound** | **Agree** | All audits acknowledge correct state management, checkpointer, HITL interrupts. The problem is the *unit of work*, not the framework. |
| **Current orchestration is a primary bottleneck** | **Partially Agree** | For single‑document processing, it is fine. For project intelligence, the missing project‑level graph is the bottleneck, not the per‑doc graph. |
| **Project‑state modeling is missing** | **Agree** | Unanimous consensus. No `ProjectSnapshot`, no `ProjectHealth`, no temporal entity versioning. |
| **Temporal intelligence is missing** | **Agree** | Unanimous. No semantic diff, no timeline, no trend analysis. |
| **Project health engine is missing** | **Agree** | Unanimous. Coherence score is not health. |
| **Alerting system is insufficient** | **Agree** | Exists but reactive, uncorrelated, no predictive early warning. |
| **HITL is strategically important** | **Agree** | All audits see it as a differentiator, but note missing features (role queues, escalation, learning loop). |
| **Document intelligence is currently the strongest capability** | **Agree** | Unanimous. Parsing, RAG, clause extraction, citation validation are robust. |

---

## PHASE 8 — PRIORITIZATION MATRIX

All distinct recommendations from the four audits have been consolidated. Below are the unique, non‑duplicate items with consensus‑based scoring.

| Capability / Fix | Impact (1‑10) | Complexity (1‑10) | Strategic Importance (1‑10) | Timing |
|----------------|---------------|--------------------|-----------------------------|--------|
| **Immutable document revisions + semantic diff engine** | 10 | 8 | 10 | **Critical (P0)** |
| **Cross‑document coherence on live hot path (ProjectGraph tier 2)** | 10 | 6 | 10 | **Critical (P0)** |
| **Project Health Engine v1 (Risk/Contract/Docs/Governance)** | 10 | 7 | 10 | **Critical (P0)** |
| **Typed graph state (replace dict[str,Any]) + NodeResult for error handling** | 9 | 5 | 9 | **Critical (P0)** |
| **Temporal snapshot store (project_snapshot, trends)** | 9 | 6 | 9 | **Critical (P0)** |
| **Replace silent failure swallowing (except Exception → NodeResult)** | 8 | 4 | 8 | **Critical (P0)** |
| **Repo hygiene / secret sweep** | 6 | 2 | 5 | **Important (P1)** |
| **HITL → eval flywheel (human corrections → golden corpus)** | 8 | 7 | 8 | **Important (P1)** |
| **Daily adoption hook (Morning Briefing digest, alert ranking)** | 8 | 4 | 8 | **Important (P1)** |
| **Configurable HITL policies + escalation timers** | 7 | 5 | 7 | **Important (P1)** |
| **Schedule ingestion (P6 XML, MSP) → activity model** | 9 | 8 | 9 | **Important (P1)** |
| **Change Order / RFI as first‑class domain objects** | 9 | 6 | 9 | **Important (P1)** |
| **Alert correlation + deduplication + impact estimation** | 8 | 5 | 8 | **Important (P1)** |
| **Portfolio/PMO layer (cross‑project health rollup)** | 9 | 7 | 9 | **Future (P2)** |
| **Cost actuals + EVM (CPI/SPI)** | 8 | 7 | 8 | **Future (P2)** |
| **Procore/Aconex/SharePoint connectors (passive ingestion)** | 8 | 7 | 8 | **Future (P2)** |
| **Multi‑industry config abstraction (doc‑types as config)** | 6 | 6 | 6 | **Future (P2)** |
| **BIM/IFC ingestion** | 5 | 9 | 5 | **Future (P3)** |
| **Mobile field app** | 7 | 8 | 7 | **Future (P3)** |

**Note**: “Critical (P0)” items are those that must be solved before the product can credibly claim to be a project intelligence platform. They are derived from consensus across all audits.

---

## PHASE 9 — MASTER CONSOLIDATED ROADMAP

### Next 30 Days
1. **Fix silent failure swallowing** – replace `except Exception: return []` with `NodeResult(status, data, error)` in all extraction nodes.  
2. **Repo hygiene** – remove root scripts, logs, test.db, add secret scanning to CI.  
3. **Document the two coherence engines** – clarify in code and docs that the live path uses low_budget_mode, and the full cross‑document endpoint is separate.  
4. **Implement project_snapshot table** – minimal temporal store to record scores and entity counts per project daily.  
5. **Typed graph state** – convert `dict[str,Any]` fields to Pydantic models for Risk, WBSActivity, BudgetItem, Citation.

### Next 90 Days (Critical P0)
1. **Immutable document revisions + clause‑level diff v1** – store binary per version, compute structural diff (added/removed/modified clauses).  
2. **ProjectGraph (Tier 2) – cross‑document coherence on live path** – fan‑out to per‑doc extraction, reduce to project‑level coherence with LLM enabled (remove low_budget_mode default for project scoring).  
3. **Project Health Engine v1** – implement Schedule (SPI proxy), Cost (CPI proxy), Risk, Contract, Documentation health dimensions with honest nulls.  
4. **Temporal early‑warning detectors** – compare snapshots to detect scope creep, schedule slip, new incoherence.  
5. **HITL role queues** – implement basic routing by persona (Contract Manager, PM) with approval/reject.  

### Next 6 Months (Important P1)
1. **Semantic diff engine** – not just structural; detect changed quantities, dates, obligations.  
2. **Morning Briefing digest** – email/Slack summary of changes, new alerts, health trends.  
3. **Alert correlation & deduplication** – group related alerts, suppress noise, rank by severity×impact.  
4. **Schedule ingestion (P6 XML / MSP)** – parse activities, durations, dependencies → basic CPM model.  
5. **Change Order workflow** – request → impact analysis (schedule/cost) → approval chain → implement.  
6. **HITL → eval flywheel** – store human corrections, generate golden test cases, periodically fine‑tune prompts.  

### Next 12 Months (Future P2/P3)
1. **Portfolio dashboard** – roll up health, risks, alerts across projects.  
2. **Cost actuals + EVM** – integrate with ERP/accounting data.  
3. **Connectors to Procore/Aconex/ACC** – passive ingestion.  
4. **Multi‑industry abstraction** – generalize document types and coherence categories via config.  
5. **Predictive forecasting** – ML models to predict completion date and final cost.  
6. **Mobile field app** – daily reports, photo capture, inspections.  

---

## PHASE 10 — FINAL VERDICT

### Scores (Consensus‑Derived)

| Dimension | Score (0‑10) | Rationale | Supporting Audits |
|-----------|--------------|-----------|-------------------|
| **Technical Maturity** | 6.5 – 7.0 | Hexagonal, tests, CI, multi‑tenancy are strong. Debt: untyped state, silent failures, dual modules. | Claude (6.5), Codex (6.5), DeepSeek (7), Gemini (8.5) → consensus ~7 |
| **Product Maturity** | 3.0 – 3.5 | No health engine, no temporal tracking, no PM workflows. Coherence score is not health. | Claude (5.0), Codex (3), DeepSeek (3), Gemini (3.5) → consensus ~3.5 |
| **Architecture Quality** | 7.0 | Well‑structured for document analysis; missing project‑state and event‑sourcing layers. | All audits acknowledge strengths and gaps. |
| **AI Readiness** | 7.0 – 7.5 | Model routing, evals, honest scoring, HITL are best‑in‑class. Cross‑doc coherence not live reduces score. | Claude (7.5), Codex (6.5), DeepSeek (6), Gemini (9) → consensus ~7.5 |
| **Enterprise Readiness** | 5.5 | RLS, audit, DLQ are real. Missing SSO depth, compliance evidence, configurable policies. | Claude (5.5), Codex (5.5), DeepSeek (5), Gemini (7) → consensus ~5.5 |
| **Scalability** | 5.5 – 6.0 | Async/Celery/RLS good. Single‑doc graph and missing project‑level parallelism are limits. | Claude (6.0), Codex (5), DeepSeek (5), Gemini (8) → consensus ~5.5 |
| **User Adoption Potential** | 2.5 – 3.0 | No daily workflow, no role‑specific queues, no mobile/field tools. | Claude (4.5), Codex (2.5), DeepSeek (2), Gemini (2) → consensus ~3 |
| **Long‑Term Potential** | 8.0 – 8.5 | Foundation is rare; market underserved; gaps are addressable. | Claude (8.0), Codex (8.5), DeepSeek (8), Gemini (9.5) → consensus ~8.5 |

---

### Answers to Strategic Questions

**1. What is the single most important thing the team is misunderstanding today?**  
They believe that a document‑coherence score and a dashboard constitute “project intelligence.” In reality, project intelligence requires **time, change, and health** – three completely missing subsystems. Without these, the product remains a static document auditor, not a living companion.

**2. What is the biggest risk if the current trajectory continues?**  
The team will keep adding document‑parsing features and UI polish, while the core product remains unusable for daily project management. They will build a “demo‑quality everywhere, production‑quality nowhere” platform – impressive to investors, abandoned by users. The differentiator (cross‑document coherence) will remain degraded, and competitors will catch up on AI basics.

**3. What is the biggest opportunity?**  
**The change‑impact report** – when a new contract revision or change order arrives, automatically show what changed, what it conflicts with across schedule/budget, and what it will cost. No incumbent does this. That single workflow, delivered reliably, is a wedge into every EPC and capital projects team.

**4. What should be the primary focus of C2Pro v3.0?**  
**Project‑level temporal intelligence** – immutable document revisions + semantic diff + cross‑document coherence in the hot path + project health engine. Everything else is secondary. v3.0 must answer: “What changed since last week, and is the project healthier or sicker?”

**5. If you became CTO tomorrow, what would be your first 10 actions?**  
1. **Replace silent `except Exception: return []` with `NodeResult`** – stop manufacturing false confidence.  
2. **Implement immutable document revisions** – store binary per version, baseline for diffing.  
3. **Build ProjectGraph (Tier 2)** – cross‑document coherence on live path, remove low_budget_mode default.  
4. **Create `project_snapshot` table** – record health, scores, counts daily.  
5. **Ship clause‑level structural diff** – “these clauses added/removed/modified.”  
6. **Project Health v1** – Risk, Contract, Documentation dimensions (data already exists).  
7. **HITL role queues** – PM and Contract Manager queues with approval buttons.  
8. **Morning Briefing email digest** – highest‑ROI adoption hook.  
9. **Repo hygiene + secret scanning** – credibility tax removal.  
10. **Freeze new modules** – no 26th module until health engine is live and diffing works.

---

**Final Assessment**: C2Pro has the bones of a category‑defining AI project intelligence platform. But today it is a high‑quality document analyzer wearing a costume. The gap between “document coherence” and “project health” is not incremental – it is foundational. The team must choose: become the world’s best contract‑coherence tool (a smaller market) or build the missing temporal, cross‑document, and health subsystems to become a true project intelligence platform. The audits unanimously recommend the latter. The path is clear. The work is substantial but achievable. No amount of UI polish will substitute for these three pillars.

**End of Master Audit Consolidation**