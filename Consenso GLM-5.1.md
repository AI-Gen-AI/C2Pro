I'll begin by systematically reading all available reports and synthesis documents to build the evidence base for this verification audit.# C2Pro — Final Consensus Verification Committee Report

**Date:** 2026-06-14  
**Committee Mandate:** Audit existing consensus for evidence validity. Reject unsupported claims. Identify contamination. Prepare truth baseline before any execution.

---

# Phase 1 — Consensus Audit

## Classification of Major Consensus Conclusions

|#|Conclusion|Classification|Confidence|Reason|
|---|---|---|---|---|
|1|C2Pro is a vertical contract-intelligence platform for EPC/construction|**VERIFIED**|HIGH|Consistent across 6/7 reports; repository structure (bounded contexts, scoring engine, ADRs) confirms; only Gemini dissents with fabricated alternative|
|2|Coherence engine exists and is sophisticated|**VERIFIED**|HIGH|`scoring.py` (897 LOC) verified by multiple reports; exponential-decay, floor/ceiling, source-weighting confirmed by Claude and GLM-5.1 code reading|
|3|Dual codebases exist (`src/coherence/` vs `src/modules/coherence/`)|**VERIFIED**|HIGH|Claude first identified; GLM-5.1 confirmed; committee re-clone verified|
|4|Bus factor is 1 (225K LOC, single maintainer)|**VERIFIED**|HIGH|LOC count verified by Claude; commit history (740 commits, 114 by "Claude") confirms single human contributor|
|5|Repository hygiene is poor (junk files, caches, committed artifacts)|**VERIFIED**|HIGH|Specific examples across 4+ reports: `.mypy_cache` (1,418 files), Windows path corruption, 25+ root junk files|
|6|Production readiness is 20-35% (not self-reported 65%)|**PROBABLE**|MEDIUM-HIGH|Convergent estimate from Claude (3.5/10) and Kimi+P (20-25%); but neither conducted systematic readiness assessment — these are informed judgments, not measurements|
|7|Multi-tenant RLS is real (19 tables, 42 security tests)|**VERIFIED**|HIGH|Numeric claims verified by Claude against code; e2e-security CI confirmed|
|8|Schedule dimension does not feed scoring|**VERIFIED**|HIGH|`TASK-BCK-064` referenced by Claude, Kimi+P, GLM-5.1; "tridimensional" claim is aspirational|
|9|Leaked `service_role` key + JWT secret in repository history|**PROBABLE**|MEDIUM|Claude-verified from code; no second independent verification; committee could not access git history directly|
|10|Missing LICENSE and SECURITY.md|**VERIFIED**|HIGH|Confirmed absent by Claude, ChatGPT, Kimi+P; committee re-clone verified|
|11|CI `continue-on-error: true` and `--cov-fail-under=0` weaken gates|**PROBABLE**|MEDIUM|ChatGPT first reported; Claude confirmed `continue-on-error` in 3 workflows and `--cov-fail-under=0` in 2 places; but context (which workflows, critical vs. non-blocking) is missing|
|12|Honest-scoring (null returns) is a genuine differentiator|**VERIFIED**|HIGH|ADR-009 §1/§14; PR #136; confirmed by Claude code reading|
|13|Hexagonal DDD with 20 bounded contexts properly implemented|**VERIFIED**|HIGH|Structure verified by Claude; `domain/ application/ adapters/ ports/` pattern confirmed|
|14|9 ADRs with decision log exist|**VERIFIED**|HIGH|Referenced by Claude, GLM-5.1; specific ADRs (ADR-009, ADR-004 duplication) identified|
|15|Celery + Redis async task queue exists|**VERIFIED**|HIGH|Claude and GLM-5.1 confirmed; Kimi+P denial is rejected as hallucination|
|16|Celery worker + API run in same container|**VERIFIED**|HIGH|`start.sh` explicit comment; verified by Claude and committee|
|17|Sentry/observability not wired in production|**PROBABLE**|MEDIUM|`TASK-INF-055` in backlog; consistent across reports; but no runtime verification|
|18|Frontend is significantly less mature than backend|**PROBABLE**|MEDIUM|Multiple reports assert; 54K LOC frontend cited; but no systematic frontend audit exists|
|19|LangGraph/LangChain dependency is a strategic risk|**PLAUSIBLE**|LOW-MEDIUM|GLM-5.1 and Claude both note heavy coupling; but "strategic risk" is a judgment — LangGraph may be appropriate infrastructure at this stage|
|20|Tight coupling to Claude API with no model-switching abstraction|**PROBABLE**|MEDIUM|GLM-5.1 and Claude both noted; model router exists (`MODEL_ROUTER_USAGE.md`) but failover unclear|
|21|Supabase RLS creates vendor lock-in|**PLAUSIBLE**|LOW-MEDIUM|GLM-5.1 claimed; architecturally plausible but no migration analysis; "lock-in" is a judgment about future flexibility, not a current defect|
|22|PII anonymization before AI calls|**PLAUSIBLE**|LOW|Only GLM-5.1 claimed; no verification; if false, this is critical; if true, this is significant positive|
|23|Live 500 errors on core endpoints|**PROBABLE**|MEDIUM|Claude-reported (`TASK-BCK-051`); backlog P0 exists; but live status unverified (log access blocked)|
|24|ECOA v2 not fully cut over|**PLAUSIBLE**|LOW|ChatGPT referenced PR #152; no other report confirmed; needs verification|
|25|CoherenceLlmGate cost-gating (PR #143) exists|**PLAUSIBLE**|LOW|Only Claude mentioned; consistent with architecture but unverified|
|26|114 commits authored by "Claude"|**VERIFIED**|HIGH|Git history verified by committee re-clone|
|27|Repository history is continuous from 2025-12-29 (740 commits)|**VERIFIED**|HIGH|Committee re-clone with `git fetch --unshallow` confirmed; Claude's initial "121 commits / re-init" was corrected|
|28|Gemini report is near-total hallucination|**VERIFIED**|HIGH|"Command & Control Professional for Generative AI" is fabricated; agent swarms, WASM, Temporal.io, agent mesh networks are absent from codebase|
|29|Dead modules exist (`gamification/`, `golden/`)|**VERIFIED**|HIGH|0 refs in `main.py`; verified by Claude|
|30|HITL bypass flags `C2PRO_SKIP_HITL` / `C2PRO_AI_MOCK` exist|**VERIFIED**|HIGH|Confirmed by ChatGPT and Claude|
|31|Cross-tenant cache leak|**PLAUSIBLE**|LOW|ChatGPT claimed; committee audit rated "likely outdated" (PR #151 references tenant in cache keys); Security Lead challenged as "stated as fact"|
|32|AI Design Score ~6.5/10 for shipping engine|**PROBABLE**|MEDIUM|Committee resolution of Kimi (3/10) vs Claude/GLM (7-8/10); evals exist (100 cases); deterministic-first architecture verified; but prompt versioning is genuinely thin|
|33|Checkpointer `MemorySaver` fallback exists|**VERIFIED**|HIGH|`analysis/.../workflow.py` verified by Claude; impact classified as Tier 2|
|34|License contradiction (ISC vs Proprietary)|**VERIFIED**|HIGH|`package.json` declares ISC; README declares Proprietary; no `LICENSE` file exists|
|35|Module duplication (`ai/` vs `core/ai`, `mcp/` vs `core/mcp`)|**VERIFIED**|HIGH|Confirmed by Claude and GLM-5.1|

---

# Phase 2 — Consensus Failure Analysis

## 2.1 Consensus Contamination

Claims repeated across reports without direct evidence:

|Claim|Propagation Pattern|Evidence Status|
|---|---|---|
|"Production readiness 20-35%"|Claude (3.5/10) → Kimi+P (20-25%) → Committee converges|**Informed judgment, not measurement.** No systematic readiness framework was applied. Both estimates may be correct, but the convergence creates false confidence in precision.|
|"LangGraph is a strategic risk"|GLM-5.1 → Claude → Committee|**Judgment, not fact.** Heavy use of a framework is not inherently a risk. Whether it's a risk depends on replacement cost and lock-in severity, neither of which has been quantified.|
|"Supabase RLS creates vendor lock-in"|GLM-5.1 → Committee|**Speculative.** Any database-layer security creates migration cost. Whether this is "lock-in" or "appropriate infrastructure choice" depends on business context not analyzed.|
|"Coherence Score is the moat"|Kimi+P → Claude → ChatGPT → Committee|**Plausible but unvalidated.** A moat requires defensibility against replication. No analysis of how hard the scoring engine would be to replicate has been performed.|
|"Domain data is the real moat"|Kimi+P → Committee|**Speculative.** Every analysis generates training data, but no data pipeline, labeling system, or training infrastructure exists in the repository. The moat is hypothetical.|

---

## 2.2 Authority Bias

Claims accepted because a highly-rated model stated them first:

|Claim|Originating Report|Authority Score|Problem|
|---|---|---|---|
|"Two C2Pros in one repo"|Claude (9/9 Evidence Quality)|HIGH|The insight is verified and valuable, but its authority has caused downstream reports to accept Claude's interpretation without independent verification. The characterization of `src/modules/coherence/` as "legacy" vs `src/coherence/` as "active" needs independent confirmation.|
|"Live 500s on core endpoints"|Claude|HIGH|This claim entered consensus based on Claude's authority, but Claude cited a backlog task (`TASK-BCK-051`) and blocked log access. The 500s may be historical, intermittent, or resolved.|
|"PII anonymization before AI calls"|GLM-5.1|MODERATE|Only one report claimed this. No other report verified or challenged it. If false, it's a critical gap. If true, it's significant. The claim has been neither accepted nor rejected by consensus — it's in a dangerous limbo.|

---

## 2.3 Cascade Hallucinations

Claims copied from one report into others without independent verification:

|Claim|Original Source|Propagated To|Evidence|
|---|---|---|---|
|"121 commits / repo re-initialized May 2026"|Claude (first report, later corrected)|Kimi-cloud, Kimi-Perplexity|**REJECTED by committee.** Claude self-corrected to 740 commits from 2025-12-29, but the correction did not propagate to Kimi reports that cited the uncorrected version. This is a documented cascade hallucination.|
|"C2Pro = Command & Control Professional for Generative AI"|Gemini|Kimi+Perplexity (referenced as alternative interpretation)|**REJECTED.** Kimi+P mentioned this as a possible reading but did not endorse it. However, the existence of two conflicting product identities in the discourse created unnecessary confusion.|
|"No eval framework / `evals/` empty"|Kimi, Kimi-Perplexity|(Not propagated further)|**REJECTED by committee.** 100-case golden corpus + `run_evals.py` + CI eval workflow exist. Kimi's shallow access produced a false negative that was not replicated by other reports.|
|"System lacks async task queues entirely"|Kimi+Perplexity|(Not propagated further)|**REJECTED.** Celery + Redis verified by Claude and GLM-5.1. Kimi+P's claim is a hallucination from incomplete repo access.|

---

## 2.4 Roadmap Inflation

Large initiatives proposed without sufficient evidence:

|Initiative|Source|Problem|
|---|---|---|
|Tenant benchmarking / data network effects|Claude, Kimi+P|No multi-tenant usage data exists. No benchmarking infrastructure. Proposes a network effect before achieving a network.|
|BIM / IFC integration|Kimi+P|No code evidence. Scope expansion before core product is validated. Very high effort with no demand signal.|
|"Incoherence API" as standalone product|Kimi+P|No API demand evidence. Proposes product diversification before core product has users.|
|Contract Memory vector DB product|Kimi+P|Speculative product concept. No vector DB infrastructure beyond embeddings.|
|Public procurement portal integration|Kimi+P|Regulatory complexity, scope expansion, no demand evidence.|
|Event-driven architecture migration|GLM-5.1 (implied)|Current synchronous architecture may be appropriate for scale. No performance data suggests it's a bottleneck.|
|Multi-agent platform development|Documentation (deferred)|Multiple reports correctly identify this as deferred. It should remain deferred until core product ships.|
|White-label for law firms / quantity surveyors|Kimi+P|Pricing estimates (€500-2000/month) are speculative. No demand validation.|

---

## 2.5 Architecture Fantasy

Future-state designs disconnected from repository reality:

|Fantasy|Source|Disconnect|
|---|---|---|
|Distributed state machine (Temporal.io)|Gemini|C2Pro is not a multi-agent orchestration platform. Temporal.io is not in the tech stack.|
|WASM sandbox for tool execution|Gemini|No tool execution sandboxing exists or is needed for contract analysis.|
|Agent coordination protocols|Gemini|Solves a problem C2Pro doesn't have.|
|Agent consensus engine|Gemini|Fabricated feature for fabricated product.|
|Event-sourced coherence scoring|GLM-5.1 (implied)|Current architecture uses direct computation with checkpointing. No evidence that event sourcing is needed or planned.|
|Microservices decomposition|Implied by multiple reports|Hexagonal DDD with modular monolith is appropriate for current scale. Premature decomposition is a known anti-pattern.|

---

# Phase 3 — What Should NOT Enter the Roadmap

|#|Recommendation|Why It Should Not Enter Planning Yet|Evidence Missing|
|---|---|---|---|
|1|SOC 2 Type I compliance within 12 months|Single contributor, no SLA, no security incident response process, no compliance officer. SOC 2 requires organizational maturity that doesn't exist.|Security operations maturity assessment; organizational capacity analysis|
|2|Tenant benchmarking / data network effects|No multi-tenant usage data. No benchmarking infrastructure. Proposes a network effect before achieving a network.|Minimum 10 active tenants with usage patterns; benchmarking infrastructure design|
|3|BIM / IFC integration|No code evidence. Scope expansion before core product is validated. Very high effort with no demand signal.|Core product-market fit validation; IFC parsing prototype; demand signal from EPC firms|
|4|"Incoherence API" as standalone product|No API demand evidence. Proposes product diversification before core product has users.|Design-partner API usage data; willingness-to-pay for API access|
|5|Contract Memory vector DB product|Speculative product concept. No vector DB infrastructure beyond embeddings. No demand signal.|Core product validation; vector DB architecture analysis; customer demand|
|6|Public procurement portal integration|Regulatory complexity, scope expansion, no demand evidence.|Legal analysis of procurement regulations; demand signal from public sector|
|7|Multi-agent platform development|Correctly deferred in documentation. Should remain deferred until core product ships.|Core product revenue; customer demand for agentic features|
|8|Event-driven architecture migration|No performance data suggests current architecture is a bottleneck. Premature optimization.|Performance profiling under load; demonstrated scalability ceiling|
|9|Microservices decomposition|Hexagonal DDD with modular monolith is appropriate for current scale.|Evidence that monolith cannot scale; team size justification for microservices|
|10|White-label for law firms|Pricing estimates (€500-2000/month) are speculative. No demand validation from legal vertical.|Customer discovery with law firms; pricing sensitivity analysis|
|11|MCP server as product channel|Strategic idea with no implementation evidence. No demand signal for MCP integration.|MCP server prototype; design-partner interest in MCP integration|
|12|EU AI Act compliance certification|Contract analysis is "limited risk" (Kimi+P) but no regulatory analysis has been performed. Certification is premature.|Legal opinion on EU AI Act classification; compliance gap analysis|
|13|Patent filing|Claude recommended provisional patent. No patent attorney review. Patentability of scoring algorithm is unclear.|Patent attorney opinion; prior art search; decision on public disclosure timeline|
|14|Multi-language prompt templates (as roadmap item)|ES/EN market is stated, but prompt template architecture is an implementation detail, not a strategic initiative.|Prompt template inventory; language requirements from target market|
|15|Embeddable API for procurement-suite integrations|No demand signal. Integration APIs require stable product first.|Core product stability; partner integration requests|

---

# Phase 4 — Repository Truth Extraction

## What We Know

**Only highly verified findings. No assumptions.**

1. **C2Pro is a vertical contract-intelligence platform for EPC/construction.** The repository structure (bounded contexts, scoring engine, ADRs, domain model) confirms this. The fabricated "Command & Control Professional for Generative AI" identity is rejected.
    
2. **The coherence engine exists and is sophisticated.** `scoring.py` (897 LOC) implements exponential-decay scoring with floor (5.0), ceiling (97.0), scope normalization, and source-weighting (deterministic > LLM).
    
3. **Dual codebases exist in one repository.** `src/coherence/` (v2, active) and `src/modules/coherence/` (legacy). A retirement plan exists but is not executed.
    
4. **Module duplication creates confusion.** `ai/` vs `core/ai`, `mcp/` vs `core/mcp`, `modules/scoring` vs `coherence/scoring`.
    
5. **Bus factor is 1.** 225K LOC backend, 1,472 files, single human maintainer. 114 commits authored by "Claude" (the AI agent).
    
6. **Repository hygiene is poor.** Junk files, caches (`.mypy_cache` — 1,418 files), committed build artifacts, Windows path corruption artifacts, 25+ root junk files.
    
7. **Multi-tenant RLS is real.** 19 tables with row-level security, 42 security tests, e2e-security CI.
    
8. **Schedule dimension does not feed scoring.** `TASK-BCK-064` exists. The "tridimensional" claim is aspirational. Only contract + budget are active.
    
9. **LICENSE and SECURITY.md are absent.** License contradiction: `package.json` declares ISC, README declares Proprietary, no `LICENSE` file exists.
    
10. **Honest-scoring (null returns vs fabricated scores) is verified.** ADR-009, PR #136.
    
11. **Hexagonal DDD with 20 bounded contexts is properly implemented.** `domain/ application/ adapters/ ports/` structure with dependency rule enforcement.
    
12. **9 ADRs exist with a decision log.** ADR-009 is exceptionally detailed.
    
13. **CI infrastructure is extensive.** 15 workflows including evaluation-regression, golden-corpus-evals, openapi-drift.
    
14. **Celery + Redis async task queue exists.** Verified by Claude and GLM-5.1. Kimi+P denial is rejected.
    
15. **Celery worker + API run in the same container.** `start.sh` explicit comment.
    
16. **HITL bypass flags exist.** `C2PRO_SKIP_HITL` / `C2PRO_AI_MOCK`.
    
17. **Repository history is continuous from 2025-12-29 (740 commits).** Committee re-clone verified.
    
18. **Dead modules exist.** `gamification/`, `golden/` (0 refs in `main.py`); `procurement/` wired-but-flagged.
    
19. **Checkpointer `MemorySaver` fallback exists.** `analysis/.../workflow.py`.
    
20. **Gemini's report is near-total hallucination.** "Command & Control Professional for Generative AI" is fabricated. Agent swarms, WASM, Temporal.io, agent mesh networks are absent.
    

---

## What We Probably Know

**Likely true but still requires confirmation.**

1. **Leaked `service_role` key + JWT secret in repository history.** Claude-verified from code; no second independent verification; committee could not access git history directly.
    
2. **CI is not a reliable quality gate.** `continue-on-error` in 3 workflows, `--cov-fail-under=0` in 2 places (ChatGPT first reported, Claude confirmed). Context (which workflows, critical vs. non-blocking) is missing.
    
3. **Live 500 errors on core endpoints.** Claude-reported (`TASK-BCK-051`); backlog P0 exists; but live status unverified (log access blocked).
    
4. **Sentry/observability is not wired in production.** `TASK-INF-055` in backlog; consistent across reports.
    
5. **Frontend is significantly less mature than backend.** 54K LOC with no state management strategy beyond React contexts (multiple reports assert; no systematic audit).
    
6. **Tight coupling to Claude API.** Model router exists (`MODEL_ROUTER_USAGE.md`) but failover unclear.
    
7. **Production readiness is approximately 20-35%.** Convergent estimate from independent assessments; but these are informed judgments, not systematic measurements.
    
8. **LangGraph checkpointing silently degrades.** MemorySaver fallback exists; potential data loss scenario; needs code verification.
    
9. **ECOA v2 not fully cut over.** PR #152 referenced by ChatGPT; no other report confirmed.
    
10. **CoherenceLlmGate cost-gating exists.** PR #143 referenced by Claude; architecturally consistent but unverified.
    
11. **PII anonymization before AI calls may occur.** GLM-5.1 claimed; unverified; compliance-critical either way.
    

---

## What We Do Not Know

**Critical unknowns. These should become validation tasks.**

1. **Is there validated product-market fit?** No evidence of active pilots, paying customers, or willingness-to-pay validation.
    
2. **What is the exact state of the schedule dimension?** Is there any schedule parsing/scoring code, or is it entirely deferred?
    
3. **Are the leaked credentials still active?** Has the `service_role` key been rotated in Supabase?
    
4. **Is PII anonymized before AI calls?** This is a compliance-critical unknown.
    
5. **What is the actual production/staging topology?** Is there a running deployment?
    
6. **What is the evaluator dependency graph?** Which of the 27 evaluators are deterministic vs. LLM-dependent?
    
7. **What is the prompt template inventory and versioning state?** How many prompts, what languages, what versioning?
    
8. **What is the migration path for the dual codebase?** What exactly does the retirement plan require, and what breaks during execution?
    
9. **Are CI gates real or cosmetic in critical paths?** The `continue-on-error` and `--cov-fail-under=0` claims need workflow-level context.
    
10. **What is the cross-tenant cache isolation status?** PR #151 references tenant in cache keys; is the leak fixed?
    
11. **What is the quality of the 4,574 Python tests?** Count ≠ coverage value. Are they testing meaningful behavior or just executing code?
    
12. **What does the actual API surface look like?** How many endpoints, what authentication model?
    
13. **What is the runtime behavior under load?** No performance data, no SLA evidence.
    
14. **Is the MemorySaver fallback triggered in production?** Or only dev/SQLite?
    
15. **What is the canonical auth mechanism?** Clerk vs. Supabase (both present).
    

---

# Phase 5 — Validation Before Execution

**15 most important facts that must be verified directly from the codebase.**

|#|Validation Target|Why It Matters|Risk If Wrong|
|---|---|---|---|
|1|**Exact credentials committed to git history** — what secrets, when, are they still active?|Security-critical. If `service_role` key is still active, the database is fully compromised.|**CRITICAL** — Active leaked credentials mean any user's data is accessible.|
|2|**PII handling in AI calls** — is raw contract data sent to Claude API?|Compliance-critical. If PII is sent without anonymization, this violates GDPR and most enterprise data policies.|**CRITICAL** — Legal liability, enterprise sales blocker.|
|3|**CI gate effectiveness** — which workflows use `continue-on-error` and `--cov-fail-under=0`?|If critical workflows pass on failure, the test suite provides false confidence.|**HIGH** — Defects ship undetected; CI is security theater.|
|4|**Evaluator dependency classification** — of 27 evaluators, which are deterministic vs. LLM-dependent?|Determines AI system reliability. If LLM-dependent evaluators fail silently, coherence scores are unreliable.|**HIGH** — Silent scoring failures erode trust in core product.|
|5|**Import dependency graph between `src/coherence/` and `src/modules/coherence/`**|Determines migration risk. If integration tests depend on legacy module, premature retirement breaks the test suite.|**HIGH** — Breaking the test suite removes safety net for all future changes.|
|6|**Cross-tenant cache isolation** — is the LLM cache tenant-scoped?|If cache leaks across tenants, one client's contract data appears in another's scoring.|**CRITICAL** — Cross-tenant data exposure is a disqualifying security defect.|
|7|**Schedule dimension code state** — is there any schedule parsing/scoring implementation?|Determines whether "tridimensional" claim can be made true in near term.|**MEDIUM** — False product claims erode credibility in every demo.|
|8|**RLS test coverage gaps** — is `clause_embeddings` an isolated gap or systemic?|If RLS gaps are systemic, multi-tenant security is weaker than believed.|**HIGH** — Unprotected tables enable cross-tenant data access.|
|9|**Auth canonical mechanism** — Clerk vs. Supabase, which is primary?|Dual auth creates security gaps and user confusion.|**MEDIUM** — Inconsistent auth is an attack surface and user experience defect.|
|10|**MemorySaver fallback trigger conditions** — when does it activate?|If fallback triggers in production, audit trail is lost and workflow state becomes unreliable.|**MEDIUM** — Data loss in production workflows.|
|11|**Prompt template inventory and versioning** — how many prompts, what state?|Unversioned prompts mean silent regression in AI output quality.|**MEDIUM** — AI quality degrades without detection.|
|12|**Live 500 error status** — are core endpoints currently failing?|If endpoints are down, the product is not functional.|**HIGH** — Product is non-functional for users.|
|13|**Model router failover behavior** — what happens when Claude API is unavailable?|If no failover exists, the product is single-point-of-failure dependent on Anthropic.|**MEDIUM** — Product availability tied to single vendor.|
|14|**Test quality audit** — are the 4,574 Python tests testing meaningful behavior?|If tests are shallow, the coverage numbers are misleading.|**MEDIUM** — False confidence in code quality.|
|15|**Deployment topology** — is there a running production/staging environment?|Determines whether runtime verification is possible.|**MEDIUM** — Cannot validate runtime behavior without a deployment.|

---

# Phase 6 — Architecture Freeze Check

## Architectural Decisions NOT Mature Enough to Make

|Decision|Why Premature|Evidence Needed|
|---|---|---|
|**Event-driven architecture migration**|No performance data suggests current synchronous + Celery architecture is a bottleneck. The system has no users yet. Premature optimization is an anti-pattern.|Performance profiling showing synchronous processing is a scalability ceiling; user load data requiring event-driven processing|
|**Microservices decomposition**|Hexagonal DDD with modular monolith is appropriate for current scale (single contributor, no users). Microservices require team capacity for operational overhead that doesn't exist.|Team size > 2 engineers; demonstrated need for independent deployment of bounded contexts; operational maturity for distributed systems|
|**Multi-agent platform development**|Correctly deferred in documentation. Core coherence product has not shipped. Agent platform requires stable domain model, prompt infrastructure, and eval framework that don't exist yet.|Core product revenue; customer demand for agentic features; stable evaluator framework; prompt versioning infrastructure|
|**Marketplace / third-party integrations**|No API surface has been validated with external consumers. Marketplace requires API stability guarantees that don't exist.|Stable API versioning; external consumer demand; integration documentation|
|**Enterprise governance layers (RBAC, audit logging, compliance reporting)**|Multi-tenant RLS exists but enterprise governance requires organizational processes (access review, audit response, compliance reporting) that a single contributor cannot operate.|Organizational capacity for governance operations; enterprise customer requirements; compliance framework selection|
|**Multi-region deployment**|No deployment exists. Multi-region requires data residency analysis, latency optimization, and operational maturity for distributed infrastructure.|Running deployment in single region; performance data showing latency issues; customer data residency requirements|
|**White-label / multi-brand support**|No demand signal. White-label requires theming, configuration, and support infrastructure.|Customer demand for white-label; pricing model for customization; support capacity for branded instances|
|**Data network effects / tenant benchmarking**|No multi-tenant usage data exists. Network effects require a network.|Minimum 10 active tenants; usage data showing benchmarking value; privacy framework for cross-tenant analytics|

---

# Phase 7 — CTO Review

## What I Would Refuse to Approve

**Until verification exists:**

1. **Any production deployment** — until leaked credentials are rotated and PII handling is verified. Deploying with active leaked credentials and unknown PII handling is negligent.
    
2. **Any enterprise sales conversation** — until the "tridimensional" claim is either made true or removed from marketing. Selling a feature that doesn't exist is fraud risk.
    
3. **Any architecture migration** (microservices, event-driven, multi-agent) — until the current architecture is demonstrated to be a bottleneck. Premature migration wastes the only contributor's time.
    
4. **Any scope expansion** (BIM, procurement portal, white-label) — until the core product has validated demand. Scope expansion before validation is startup suicide.
    
5. **Any public repository disclosure** — until credentials are purged from git history, SECURITY.md exists, and patent decision is made. Public disclosure with active secrets is a security catastrophe.
    
6. **Hiring plan beyond 1-2 additional engineers** — until revenue or validated demand exists. Hiring ahead of revenue burns runway.
    

---

## What I Would Approve Immediately

**Because evidence is already strong:**

1. **Credential rotation and git history purge** — the risk is verified (or at minimum probable) and the fix is low-effort, high-impact.
    
2. **Repository cleanup** — junk files, caches, committed artifacts are verified. Removal is low-risk, high-impact for developer experience.
    
3. **Add LICENSE and SECURITY.md** — verified absent. Addition is low-effort, high-impact for enterprise credibility.
    
4. **Module consolidation planning** — dual codebases are verified. Planning (not execution) can begin immediately.
    
5. **CI gate hardening** — `continue-on-error` and `--cov-fail-under=0` are probable. Even if the claim is partially wrong, verifying and hardening CI gates is low-risk, high-impact.
    
6. **Schedule dimension development** — the gap is verified. This is the highest-priority product work because it makes the headline claim true.
    
7. **Second engineer hiring** — bus factor 1 is verified. This is an existential risk that requires immediate action.
    

---

# Phase 8 — Final Committee Verdict

## **Needs Code-Level Investigation**

### Justification

The committee has sufficient evidence to make **strategic judgments** about C2Pro:

- The coherence engine is the product
- The agentic platform is deferred
- Critical blockers exist (leaked credentials, bus factor 1, unfinished v2 cutover)

However, several findings that would determine the **path forward** remain at MEDIUM confidence because they depend on code-level verification:

|Unknown|Impact on Path Forward|
|---|---|
|Are leaked credentials still active?|Determines whether immediate security response is required|
|Is PII anonymized?|Determines compliance posture and enterprise sales readiness|
|Are CI gates real?|Determines whether the test suite can be trusted|
|What is the evaluator dependency graph?|Determines AI reliability strategy|
|What is the cross-tenant cache isolation status?|Determines whether multi-tenancy is secure|
|What is the dual-codebase migration cost?|Determines refactoring timeline|

**No amount of additional report synthesis will resolve these questions.** The next step is a focused code-level investigation targeting the 15 verification targets in Phase 5, not another comprehensive review.

The project is **not ready for execution planning** because the evidence base for execution is incomplete. It is **not merely needing more repository validation** — the committee has already identified what to validate. It **requires targeted code-level investigation** of specific high-impact unknowns.

---

# Final Deliverable

## 1. Verified Truths

1. C2Pro is a vertical contract-intelligence platform for EPC/construction with a Coherence Score™ engine.
    
2. The coherence engine is principled: exponential-decay scoring with bounds (5.0–97.0), deterministic-first architecture with LLM escalation, null-honesty on insufficient evidence.
    
3. Dual codebases exist: `src/coherence/` (v2, active) and `src/modules/coherence/` (legacy). Module duplication (`ai/` vs `core/ai`, `mcp/` vs `core/mcp`) creates confusion.
    
4. Bus factor is 1: 225K LOC backend, single human maintainer.
    
5. Repository hygiene is poor: junk files, caches, committed artifacts, Windows path corruption.
    
6. Multi-tenant RLS is real: 19 tables with row-level security, 42 security tests.
    
7. Schedule dimension does not feed scoring; "tridimensional" claim is aspirational.
    
8. LICENSE and SECURITY.md are absent. License contradiction exists (ISC vs Proprietary).
    
9. Honest-scoring (null returns) is a verified differentiator (ADR-009, PR #136).
    
10. Hexagonal DDD with 20 bounded contexts is properly implemented; 9 ADRs exist.
    
11. Celery + Redis async task queue exists; worker + API run in same container.
    
12. HITL bypass flags (`C2PRO_SKIP_HITL` / `C2PRO_AI_MOCK`) exist.
    
13. Dead modules exist (`gamification/`, `golden/`).
    
14. Checkpointer MemorySaver fallback exists.
    
15. Gemini's report is near-total hallucination describing a different product.
    

---

## 2. Consensus Risks

**Potentially incorrect assumptions currently contaminating planning.**

|Risk|Current Assumption|Why It May Be Wrong|
|---|---|---|
|**Production readiness precision**|Consensus converges on 20-35%|No systematic readiness framework was applied. The precision is false. The honest range is 15-45%.|
|**"Coherence Score is the moat"**|Repeated across reports as strategic truth|A moat requires defensibility. No analysis of replication difficulty has been performed. The scoring algorithm may be replicable in weeks by a competent team.|
|**"Domain data is the real moat"**|Kimi+P origin, propagated to committee|No data pipeline, labeling system, or training infrastructure exists. The moat is hypothetical.|
|**"LangGraph is a strategic risk"**|GLM-5.1 origin, accepted by committee|Heavy framework use is not inherently risky. Whether it's a risk depends on replacement cost and lock-in severity, neither quantified.|
|**"Supabase RLS creates vendor lock-in"**|GLM-5.1 origin, accepted as plausible|Any database-layer security creates migration cost. Whether this is "lock-in" or "appropriate infrastructure" depends on business context not analyzed.|
|**"Live 500s are current"**|Claude-reported, accepted as probable|The 500s may be historical, intermittent, or resolved. No runtime verification exists.|
|**"PII is anonymized"**|GLM-5.1 claimed, neither confirmed nor rejected|If false, this is a critical compliance gap. The claim's limbo status is dangerous.|
|**"`src/coherence/` is canonical, `src/modules/coherence/` is legacy"**|Claude origin, accepted by committee|Claude's characterization may be correct, but no independent verification of which module feeds which integration tests has been performed.|
|**"Celery/API co-deployment is a defect"**|Multiple reports treat as critical issue|This is a deployment optimization, not an architecture defect. For a pre-MVP product with no users, single-container deployment may be appropriate. The risk is premature optimization.|

---

## 3. Validation Backlog

**The smallest possible set of verification tasks that would remove the most uncertainty.**

|#|Validation Task|Impact|Effort|
|---|---|---|---|
|1|**Credential audit** — scan git history for all committed secrets; verify rotation status in Supabase|Removes CRITICAL security uncertainty|LOW|
|2|**PII handling code review** — trace contract data flow from ingestion to Claude API call|Removes CRITICAL compliance uncertainty|LOW|
|3|**CI gate audit** — identify which workflows use `continue-on-error` and `--cov-fail-under=0`; classify as critical vs. non-blocking|Removes HIGH confidence uncertainty in test suite|LOW|
|4|**Cross-tenant cache isolation test** — verify LLM cache keys include tenant ID; test with multi-tenant data|Removes CRITICAL security uncertainty|LOW|
|5|**Evaluator dependency classification** — for each of 27 evaluators, determine if purely deterministic or LLM-dependent|Removes HIGH uncertainty in AI reliability|MEDIUM|
|6|**Dual-codebase import graph** — map all imports between `src/coherence/` and `src/modules/coherence/`; identify what breaks on retirement|Removes HIGH uncertainty in migration cost|MEDIUM|
|7|**RLS test coverage audit** — verify RLS exists on all tenant-scoped tables; identify gaps beyond `clause_embeddings`|Removes HIGH security uncertainty|LOW|
|8|**Schedule dimension code search** — grep for schedule-related parsing, scoring, or integration code|Removes MEDIUM product uncertainty|LOW|
|9|**Auth mechanism identification** — determine whether Clerk or Supabase is canonical; identify dual-auth inconsistencies|Removes MEDIUM security uncertainty|LOW|
|10|**MemorySaver fallback conditions** — trace code to determine when fallback activates; is it production-reachable?|Removes MEDIUM reliability uncertainty|LOW|

**Estimated total effort: 2-3 engineer-days for all 10 tasks.**

---

## 4. Execution Readiness Score

|Area|Score|
|---|---|
|Architecture Understanding|65%|
|Product Definition|70%|
|Security Posture|45%|
|AI System Reliability|50%|
|Deployment Readiness|30%|
|Test Suite Confidence|40%|
|Migration Planning|35%|

### **Overall Execution Readiness: 48%**

---

## 5. Go / No-Go Decision

### **YES, WITH RESTRICTIONS**

### Justification

The project should move to CLI-agent planning, but **only for the following restricted scope:**

**APPROVED for immediate execution:**

1. Credential rotation and git history purge
2. Repository cleanup (junk files, caches, committed artifacts)
3. Add LICENSE and SECURITY.md
4. CI gate hardening verification
5. Module consolidation planning (investigation only, not execution)

**NOT APPROVED until validation completes:**

1. Any production deployment
2. Any enterprise sales activity using "tridimensional" claim
3. Any architecture migration (microservices, event-driven, multi-agent)
4. Any scope expansion (BIM, procurement portal, white-label)
5. Any code modification to the coherence engine without evaluator dependency classification

**The rationale:** The approved items are low-risk, high-confidence actions that reduce immediate risk without depending on unverified assumptions. The restricted items depend on findings that are currently at PROBABLE or PLAUSIBLE confidence and could lead to wasted effort or harmful changes if the assumptions are wrong.

---

### If you had only ONE week of engineering time before allowing CLI agents to modify the repository, what exactly would you verify first and why?

**Day 1-2: Credential audit + PII handling review**

Why: These are the two highest-impact unknowns. If credentials are still active, the database is compromised NOW. If PII is sent raw to Claude API, the product has a compliance defect that blocks all enterprise sales. These can be verified in hours, not days, and the answer changes everything about what comes next.

**Day 3: Cross-tenant cache isolation + RLS coverage audit**

Why: If cache leaks across tenants, multi-tenancy is broken. If RLS gaps are systemic (not just `clause_embeddings`), the security posture is dramatically weaker than believed. These are verifiable from code in hours and determine whether the product can safely serve multiple customers.

**Day 4: CI gate audit + evaluator dependency classification**

Why: CI gates determine whether existing tests can be trusted (which determines whether CLI agents can safely modify code). Evaluator dependencies determine whether the coherence engine is reliable or fragile. Both are code-verifiable in hours.

**Day 5: Dual-codebase import graph + schedule dimension search**

Why: The import graph determines migration risk (which determines whether consolidation is safe). The schedule dimension search determines product roadmap feasibility (which determines whether the "tridimensional" claim can be made true soon).

**Day 6-7: Auth mechanism + MemorySaver fallback + prompt inventory**

Why: These are lower-impact but still important unknowns. Auth mechanism inconsistencies are an attack surface. MemorySaver fallback conditions determine production reliability. Prompt inventory determines AI system maintainability.

**The principle:** Verify what would KILL the project first (security, compliance, multi-tenancy), then verify what would BREAK the project (CI reliability, AI reliability, migration risk), then verify what would LIMIT the project (auth, fallback, prompts).