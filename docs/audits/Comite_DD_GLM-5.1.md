
---

# Phase 1 — Report Quality Assessment

## 1.1 Claude — _C2Pro Technical Due-Diligence & Strategic Review_

|Dimension|Score (/10)|
|---|---|
|Evidence Quality|9|
|Repository Awareness|9|
|Technical Depth|8|
|Architectural Rigor|8|
|Product Insight|8|
|Security Insight|7|
|Actionability|8|
|Hallucination Risk|2 (low risk)|

**Strongest Contributions:**

- The "two C2Pros in one repo" frame (`src/coherence/` vs `src/modules/coherence/`) is the single most important structural insight across all reports
- Verified numeric claims: 225K LOC backend, 4,574 Python test functions, 15 CI workflows, RLS on 19 tables
- Honest-scoring architecture (null returns vs fabricated scores) identified as genuine differentiator
- ADR-009 shadow-mode rollout analysis (shadow-MAE ≤ 15 auto-block) shows actual code reading
- Self-corrected errors in the multi-model synthesis (§0)

**Weakest Contributions:**

- Enterprise readiness score of 4/10 may underweight the RLS + CI + feature flag infrastructure
- Some strategic recommendations (patent filing, data network effects) are plausible but unsupported by current evidence
- "Founder-as-domain-moat" is a narrative judgment, not a technical finding

**Unique Contributions:**

- Dual-engine retirement plan documentation (`G6-06_LEGACY_ADAPTERS_RETIREMENT_PLAN.md`)
- Live 500s on core endpoints as production blocker
- Committed `service_role` key + JWT secret as critical exposure
- CoherenceLlmGate cost-gating (PR #143) as mature AI cost control pattern

---

## 1.2 ChatGPT — _C2Pro Complete Technical Due Diligence Report_

|Dimension|Score (/10)|
|---|---|
|Evidence Quality|5|
|Repository Awareness|5|
|Technical Depth|4|
|Architectural Rigor|3|
|Product Insight|4|
|Security Insight|5|
|Actionability|6|
|Hallucination Risk|5|

**Strongest Contributions:**

- CI `continue-on-error` discovery — if verified, this means CI is not a real gate
- `--cov-fail-under=0` making coverage threshold meaningless
- ECOA v2 not fully cut over (PR #152 reference)
- Repo hygiene as due-diligence red flag

**Weakest Contributions:**

- Does not deeply analyze the coherence engine architecture
- Generic security recommendations (add SECURITY.md, rotate secrets) without repository-specific context
- No architectural pattern identification beyond surface observations
- "License metadata contradictory (Proprietary vs ISC)" — needs verification

**Unique Contributions:**

- Real-document workflow is manual and mock-enabled, not an automatic gate
- Root test script exits with "no test specified"

---

## 1.3 Gemini — _C2Pro Complete Technical Due Diligence Report_

|Dimension|Score (/10)|
|---|---|
|Evidence Quality|1|
|Repository Awareness|1|
|Technical Depth|2|
|Architectural Rigor|1|
|Product Insight|1|
|Security Insight|2|
|Actionability|2|
|Hallucination Risk|9 (extreme)|

**Strongest Contributions:**

- Generic best-practice recommendations that happen to be valid for any project (add `.gitignore`, structured logging, `SECURITY.md`)

**Weakest Contributions:**

- **Fundamental product misidentification.** Describes C2Pro as "Command & Control Professional for Generative AI" — a multi-agent orchestration platform with agent swarms, WASM sandboxing, Temporal.io, and agent mesh networks. None of this exists in the repository. The expanded name is fabricated.
- All 25 critical findings reference a different product architecture
- TAM estimate of "$15B" is disconnected from any defensible analysis
- Proposed architecture (distributed state machine, Temporal-driven agent engine) is architecture fantasy

**Unique Contributions:**

- None that survive scrutiny. Generic items (circuit breakers, semantic caching, idempotency keys) are valid engineering concerns but are not grounded in this codebase.

**Verdict: ❌ REJECTED IN BLOCK. This report analyzed a different product. Only generic best-practice items that are independently confirmed by other reports should be retained.**

---

## 1.4 Kimi+Perplexity — _C2Pro Complete Technical Due Diligence Report_

|Dimension|Score (/10)|
|---|---|
|Evidence Quality|6|
|Repository Awareness|6|
|Technical Depth|5|
|Architectural Rigor|5|
|Product Insight|7|
|Security Insight|5|
|Actionability|7|
|Hallucination Risk|5|

**Strongest Contributions:**

- Best market positioning insight: C2Pro should sell to Project Control Directors and Procurement Leads, not legal teams
- EU AI Act tailwind analysis (contract analysis is "limited risk" — genuine sales accelerator)
- Competitive moat is domain data, not AI — every analysis generates labeled training data
- Production readiness estimate of 20-25% is likely more honest than self-reported 65%

**Weakest Contributions:**

- Claimed system lacks async task queues entirely — contradicted by Celery evidence verified by Claude and GLM-5.1
- Recommendation to switch from Clerk to Supabase native auth without evaluating frontend breakage
- AI Design Score of 3/10 is too low for a system with 27 evaluators and principled scoring

**Unique Contributions:**

- Windows path corruption artifact (`CUsersesus_DocumentsAIZTWQc2proC2PRO_MASTER_BACKLOG.md`)
- Dual lock files (pnpm-lock.yaml + package-lock.json) as reproducibility risk
- `.mypy_cache` committed to repository
- Gate 7 (Observability) explicitly incomplete finding
- Contract Memory as vector DB product concept

---

## 1.5 Kimi (Cloud) — _Informe de Síntesis Cruzada_

|Dimension|Score (/10)|
|---|---|
|Evidence Quality|5|
|Repository Awareness|5|
|Technical Depth|4|
|Architectural Rigor|4|
|Product Insight|5|
|Security Insight|4|
|Actionability|5|
|Hallucination Risk|4|

**Strongest Contributions:**

- 25 junk files in repository root identified
- `blackboard.json` as runtime artifact that should not be in Git
- "Skill registry" as hidden product concept
- `evals/` and `openspec/` directories exist but are empty

**Weakest Contributions:**

- No LOC measurement or code depth analysis
- Overestimates frontend "type-unsafe 5%" as "unacceptable" — disproportionate for pre-MVP
- No deep analysis of coherence engine quality

**Unique Contributions:**

- Blackboard pattern as architecturally significant
- Empty `evals/` and `openspec/` directories

---

## 1.6 GLM-5.1 — _C2Pro Complete Technical Due-Diligence & Strategic Analysis_

|Dimension|Score (/10)|
|---|---|
|Evidence Quality|6|
|Repository Awareness|6|
|Technical Depth|6|
|Architectural Rigor|6|
|Product Insight|6|
|Security Insight|5|
|Actionability|5|
|Hallucination Risk|4|

**Strongest Contributions:**

- Two `core/` directories and two `ai/` directories create constant confusion
- No event-driven architecture — all synchronous HTTP
- LangGraph checkpointing silently degrades as data loss scenario
- PII anonymization before AI calls noted as real security measure
- Multi-tenant RLS at database layer confirmed

**Weakest Contributions:**

- "No message queue beyond Celery" — Celery IS a message queue (backed by Redis/RabbitMQ); the finding is imprecise
- "Frontend has no state management strategy beyond React contexts" — not verified
- Some overlap with Claude's findings without adding new evidence

**Unique Contributions:**

- Supabase lock-in risk for RLS (migrating off would require rewriting all security)
- Tight coupling to Claude API with no abstraction for model switching
- Product vision at 35-40% of stated ambition

---

# Phase 2 — Cross-Report Comparison

## 2.1 Universal Agreement (HIGH Confidence)

|Finding|Supporting Reports|Evidence|
|---|---|---|
|Repository hygiene is poor — junk files, caches, committed artifacts|ChatGPT, Kimi+P, Kimi, Claude, GLM-5.1|Multiple specific examples (`.mypy_cache`, path corruption, 25 root junk files)|
|Bus factor is 1 — single contributor risk|Claude, Kimi+P, GLM-5.1|225K LOC, 1,472 files under one maintainer|
|Coherence engine is the strongest technical component|Claude, GLM-5.1, Kimi+P|`scoring.py` (897 LOC), principled exponential-decay, ADR-009|
|Dual codebases / module duplication exist|Claude, GLM-5.1, Kimi|`src/coherence/` vs `src/modules/coherence/`, `ai/` vs `core/ai`|
|Production readiness is overstated|ChatGPT, Kimi+P, Claude|Self-reports 65%; actual estimate 20-35%|
|Missing LICENSE file despite proprietary badge|Claude, ChatGPT, Kimi+P|Verified absent|
|No `SECURITY.md`|Claude, Gemini (generic), Kimi+P|Verified absent|
|Schedule dimension not yet in scoring|Claude, Kimi+P, GLM-5.1|"Tridimensional" claim is aspirational|
|Multi-tenant RLS is real and implemented|Claude, GLM-5.1|19 tables with RLS, 42 security tests|
|No production deployment evidence / SLA data|Claude, ChatGPT, GLM-5.1|No load testing, no uptime metrics|

---

## 2.2 Emerging Consensus (MEDIUM Confidence)

|Finding|Supporting Reports|Evidence Status|
|---|---|---|
|Leaked/staged credentials in repository|Claude (committed `service_role` key + JWT), ChatGPT|Claude verified; needs second independent confirmation|
|CI is not a reliable gate|ChatGPT (`continue-on-error`, `--cov-fail-under=0`), Claude (15 workflows but quality unclear)|ChatGPT claims need code-level verification|
|Observability is unwired in production|Claude (Sentry DSN not configured, `TASK-INF-055`), Kimi+P (Gate 7 incomplete)|Consistent but needs runtime verification|
|Honest-scoring (null returns) is a genuine differentiator|Claude, Kimi+P|Code-level evidence (PR #136, ADR-009 §1/§14)|
|Frontend is significantly less mature than backend|Claude, GLM-5.1, Kimi|54K LOC frontend with deferred state management|
|LangGraph/LangChain dependency is a strategic risk|Claude, GLM-5.1|Both note heavy coupling; moat must be evaluators, not graph|
|Product positioning unclear (framework vs. vertical SaaS)|Gemini (wrong context but flagged), Claude, GLM-5.1|Agentic platform deferred; coherence wedge is the real product|

---

## 2.3 Significant Disagreements

### Disagreement 1: Product Identity

||Position A|Position B|
|---|---|---|
|**Claim**|C2Pro is a multi-agent orchestration platform (Command & Control Professional for Generative AI)|C2Pro is a vertical contract-intelligence platform (Coherence Score™ engine for EPC)|
|**Source**|Gemini|Claude, Kimi+P, GLM-5.1, ChatGPT|
|**Evidence**|None from repository|Repository structure, bounded contexts, scoring engine, ADRs|
|**Verdict**|**Position A is REJECTED.** Gemini hallucinated the product identity. Every other report confirms Position B.||

---

### Disagreement 2: AI Design Quality

||Position A|Position B|
|---|---|---|
|**Claim**|AI design is poor (3/10) — lacks fundamental capabilities|AI design is strong for the core (6.5-7/10) with specific weaknesses|
|**Source**|Kimi (cloud)|Claude, GLM-5.1, Kimi+P (partially)|
|**Evidence Available**|Kimi worked from shallow repo tree|Claude verified 27 evaluators, deterministic-first architecture, cost-gating, null-honesty|
|**Evidence Missing**|Whether Kimi accessed scoring.py|Independent code review of evaluator quality|
|**Committee Position**|**Lean B.** Kimi's low score appears driven by limited code access, not substantive analysis. The deterministic+LLM hybrid architecture with null-honesty is verified by multiple reports.||

---

### Disagreement 3: Celery / Async Task Queue Existence

||Position A|Position B|
|---|---|---|
|**Claim**|System completely lacks async task queues|Celery + Redis task queue exists|
|**Source**|Kimi+Perplexity|Claude, GLM-5.1|
|**Evidence Available**|Kimi+P may not have accessed infrastructure code|Claude verified Celery presence, `TASK-BCK-077` references Celery task-registration drift|
|**Committee Position**|**Lean B.** Multiple reports confirm Celery. Kimi+P's claim is likely a hallucination from incomplete repo access.||

---

### Disagreement 4: Architecture Verdict

||Position A|Position B|
|---|---|---|
|**Claim**|Architecture is fundamentally broken and requires rebuild|Architecture is sound at core but has unfinished edges and hygiene debt|
|**Source**|Gemini (rejected)|Claude, GLM-5.1|
|**Evidence Available**|Gemini's claims are about a different product|Hexagonal DDD with 20 bounded contexts, 9 ADRs, principled scoring core|
|**Committee Position**|**Lean B.** Gemini's position is disqualified. The remaining evidence supports "strong core, unfinished edges."||

---

### Disagreement 5: Production Readiness

||Position A|Position B|
|---|---|---|
|**Claim**|Production readiness ~3.5/10|Production readiness ~20-25%|
|**Source**|Claude|Kimi+Perplexity|
|**Evidence Available**|Claude: leaked creds, live 500s, missing SLA, bus factor 1|Kimi+P: gates incomplete, product surface invisible|
|**Analysis**|These are actually convergent. 3.5/10 ≈ 25%. The disagreement is framing, not substance.||
|**Committee Position**|**Consensus.** Both estimates converge on approximately 20-35% production readiness.||

---

# Phase 3 — Hallucination Audit

## 3.1 Potential Hallucinations

|Claim|Source Report|Risk Level|Reason|
|---|---|---|---|
|C2Pro = "Command & Control Professional for Generative AI"|Gemini|**CRITICAL**|Expanded name is fabricated. No evidence in repository. Entire report built on false premise.|
|Agent swarms, WASM sandboxing, Temporal.io, agent mesh networks|Gemini|**CRITICAL**|None of these technologies or patterns exist in the codebase.|
|Race conditions in agent state serialization|Gemini|**HIGH**|Unverifiable; likely projected from generic multi-agent concerns onto wrong product.|
|System lacks async task queues entirely|Kimi+Perplexity|**HIGH**|Contradicted by verified Celery + Redis infrastructure.|
|AI Design Score of 3/10|Kimi (cloud)|**MEDIUM**|Likely result of shallow code access; contradicted by verified evaluator architecture.|
|"Incoherence API" as standalone product concept|Kimi+Perplexity|**MEDIUM**|Speculative product idea, not based on repository evidence.|
|BIM integration prototype (IFC parsing)|Kimi+Perplexity|**MEDIUM**|Roadmap item with no code evidence.|
|Agent consensus engine / voting mechanisms|Gemini|**HIGH**|Fabricated feature for a product that doesn't exist.|
|$15B TAM estimate|Gemini|**HIGH**|No methodology provided; applied to wrong product category.|
|Automated security patching agent|Gemini|**HIGH**|Fabricated feature.|
|Differential privacy filters|Gemini|**HIGH**|Fabricated feature.|
|KG-RAG implementation|Gemini|**HIGH**|Fabricated feature.|

---

## 3.2 Recommendations to Discard

|Recommendation|Source|Reason for Discard|
|---|---|---|
|Rebuild on distributed state machine (Temporal.io)|Gemini|Architecture fantasy. C2Pro is not a multi-agent orchestration platform.|
|WASM sandbox for tool execution|Gemini|Technology not present or needed for contract intelligence platform.|
|Agent coordination protocols (Contract Net, hierarchical voting)|Gemini|Solves a problem this product doesn't have.|
|Automated security patching agent|Gemini|Fabricated feature for fabricated product.|
|On-premises air-gapped deployment|Gemini|Premature for a product at 20-35% readiness.|
|Agent consensus engine|Gemini|Fabricated feature.|
|Dynamic tool discovery via OpenAPI specs|Gemini|Fabricated feature.|
|Immediate switch from Clerk to Supabase native auth|Kimi+Perplexity|Breaks frontend; no migration analysis provided.|
|Launch "Incoherence API" as standalone product|Kimi+Perplexity|No evidence of API-first demand; premature product strategy.|
|SOC 2 Type I compliance within 12 months|Kimi+Perplexity|Ambitious for a single-contributor project at current maturity.|

---

# Phase 4 — Confidence-Based Findings

## Tier 1 Findings (HIGH Confidence — Directly Supported by Evidence)

1. **C2Pro is a vertical contract-intelligence platform** for EPC/construction, not a multi-agent orchestration framework. Its core product is the Coherence Score™ engine.
    
2. **Dual codebases exist in one repository** — `src/coherence/` (v2, active, evidence-aware) and `src/modules/coherence/` (legacy, feeds analysis pipeline). A retirement plan exists but is not executed.
    
3. **Module duplication creates confusion** — `ai/` vs `core/ai`, `mcp/` vs `core/mcp`, `modules/scoring` vs `coherence/scoring`. New contributors cannot determine which is canonical without reading `main.py` feature flags.
    
4. **Repository hygiene is poor** — junk files, caches, `.mypy_cache`, Windows path corruption artifacts, committed build artifacts in Git.
    
5. **Bus factor is 1** — 225K LOC backend, 1,472 files, single maintainer.
    
6. **Coherence engine is principled and well-engineered** — exponential-decay scoring with floor (5.0) and ceiling (97.0), scope normalization, source-weighting (deterministic > LLM), null-honesty on insufficient evidence.
    
7. **Multi-tenant RLS is real** — 19 tables with row-level security, 42 security tests, e2e-security CI.
    
8. **Production readiness is overstated** — self-reports ~65%; independent assessment converges on 20-35%.
    
9. **Schedule dimension is not yet in scoring** — the "tridimensional" claim (contract + schedule + budget) is aspirational. Only contract + budget are active.
    
10. **Missing LICENSE and SECURITY.md** — verified absent despite proprietary badge.
    
11. **Honest-scoring (null returns vs fabricated scores) is a genuine trust differentiator** — verified in ADR-009, PR #136.
    
12. **Hexagonal DDD architecture is properly implemented** — 20 bounded contexts with `domain/ application/ adapters/ ports/` structure; dependency rule consistently enforced.
    
13. **ADR governance exists and is substantial** — 9 ADRs with a decision log; ADR-009 is exceptionally detailed.
    
14. **CI infrastructure is extensive** — 15 workflows including evaluation-regression, golden-corpus-evals, openapi-drift.
    
15. **Leaked/staged credentials in repository** — committed `service_role` key and JWT secret (Claude-verified).
    

---

## Tier 2 Findings (MEDIUM Confidence — Need Validation)

1. **CI is not a reliable quality gate** — `continue-on-error` in integration tests and `--cov-fail-under=0` in unit tests (ChatGPT-reported; needs code verification).
    
2. **Live 500 errors on core endpoints** — Claude-reported (`TASK-BCK-051`); needs runtime verification.
    
3. **Sentry DSN is not configured in production** — `TASK-INF-055` exists in backlog; needs deployment verification.
    
4. **Frontend is significantly less mature than backend** — 54K LOC with no state management strategy beyond React contexts (GLM-5.1 claimed; needs verification).
    
5. **LangGraph checkpointing silently degrades** — potential data loss scenario (GLM-5.1 claimed; needs code verification).
    
6. **Supabase RLS lock-in** — migrating off Supabase would require rewriting all security (GLM-5.1 claimed; architecturally plausible).
    
7. **Tight coupling to Claude API** — no abstraction for model switching (GLM-5.1 and Claude both noted; needs code verification).
    
8. **ECOA v2 not fully cut over** — PR #152 reference (ChatGPT; needs verification).
    
9. **Observability is fundamentally incomplete** — no structured logging, no distributed tracing, no metrics pipeline (Kimi+P; consistent with Sentry finding).
    
10. **Dual lock files** — both `pnpm-lock.yaml` and `package-lock.json` committed (Kimi+P; needs verification).
    

---

## Tier 3 Findings (LOW Confidence — Interesting but Unproven)

1. **The "skill registry" is a hidden product concept** — Kimi cloud identified; significance unclear.
    
2. **Contract Memory as vector DB product** — Kimi+P strategic suggestion; no code evidence.
    
3. **EU AI Act compliance as sales accelerator** — Kimi+P; plausible regulatory analysis but no market validation.
    
4. **Domain data as competitive moat** — every analysis generates labeled training data; Kimi+P; plausible but no data pipeline evidence.
    
5. **MCP server as product channel** — Kimi+P; strategic idea with no implementation evidence.
    
6. **White-label for law firms / quantity surveyors** — Kimi+P; pricing estimates (€500-2000/month) are speculative.
    
7. **Provisional patent before public disclosure** — Claude; legally sound advice but no patent evidence.
    
8. **Data network effect through tenant benchmarking** — Claude; plausible but no implementation.
    
9. **PII anonymization before AI calls** — GLM-5.1 claimed; if true, this is a significant security positive; needs verification.
    
10. **CoherenceLlmGate as cost control** — Claude (PR #143); needs verification but architecturally consistent with null-honesty pattern.
    

---

# Phase 5 — Consensus Roadmap Refinement

## 5.1 Candidate Roadmap Items

|Initiative|Evidence Strength|Impact|Effort|Confidence|
|---|---|---|---|---|
|Rotate/purge leaked credentials|HIGH (verified)|CRITICAL|LOW|HIGH|
|Add LICENSE and SECURITY.md|HIGH (verified)|HIGH|LOW|HIGH|
|Remove junk files / clean repository|HIGH (verified)|MEDIUM|LOW|HIGH|
|Execute legacy coherence module retirement|HIGH (verified dual codebase)|HIGH|MEDIUM|HIGH|
|Fix CI gates (remove `continue-on-error`, set real coverage threshold)|MEDIUM|HIGH|LOW|MEDIUM|
|Wire Sentry / observability stack|MEDIUM (backlog exists)|HIGH|MEDIUM|MEDIUM|
|Complete v2 cutover and consolidate to single engine|MEDIUM|HIGH|HIGH|MEDIUM|
|Ship schedule dimension into scoring|HIGH (verified gap)|CRITICAL|HIGH|HIGH|
|Hire second engineer / reduce bus factor|HIGH (verified single contributor)|CRITICAL|HIGH|MEDIUM|
|Add model-switching abstraction layer|MEDIUM (Claude API coupling)|MEDIUM|MEDIUM|MEDIUM|
|Fix live 500s on core endpoints|MEDIUM (needs verification)|HIGH|MEDIUM|MEDIUM|
|Implement structured logging / distributed tracing|MEDIUM|HIGH|HIGH|MEDIUM|
|Multi-language prompt templates|LOW|MEDIUM|MEDIUM|LOW|
|Embeddable API for procurement-suite integrations|LOW|HIGH|HIGH|LOW|
|Contract Memory vector DB product|SPECULATIVE|HIGH|VERY HIGH|LOW|
|MCP server product|SPECULATIVE|MEDIUM|HIGH|LOW|
|BIM / IFC integration|SPECULATIVE|MEDIUM|VERY HIGH|VERY LOW|

---

## 5.2 Roadmap Items Requiring Validation

|Item|Why It Should NOT Enter Roadmap Yet|Evidence Required|
|---|---|---|
|SOC 2 Type I compliance|Single contributor, no SLA evidence, no security incident response process|Demonstrate basic security operations maturity first|
|Tenant benchmarking / data network effects|No multi-tenant usage data exists|Minimum 10 active tenants with usage patterns|
|Change-order "coherence regression" workflow|Core coherence engine incomplete|Ship schedule dimension first|
|White-label for law firms|No demand validation|Customer discovery interviews with target personas|
|BIM / IFC integration|No code evidence, very high effort, scope creep risk|Proven product-market fit on core coherence product|
|"Incoherence API" standalone|No API demand evidence|Validate via design-partner usage of existing API|
|Public procurement portal integration|Scope expansion before core is complete|Core product must be revenue-generating first|

---

# Phase 6 — Expert Committee Review

## CTO

**Strongly agrees with:**

- Leaked credentials are a P0 blocker
- Bus factor 1 is an existential risk
- Production readiness is 20-35%, not 65%
- The honest-scoring architecture is the right technical instinct for enterprise trust

**Challenges:**

- Is the dual-codebase problem a design choice or technical debt? If the legacy engine feeds integration tests (I2-I14), premature retirement could break the test suite
- The "rebuild vs. finish" question: Claude says "finish and harden, don't rebuild" — but the module duplication suggests the architecture is mid-migration. What's the migration completion cost?

**Still needs:**

- Runtime verification: are the live 500s reproducible?
- CI audit: is `continue-on-error` in critical paths or only in non-blocking workflows?
- Deployment evidence: what does the actual production/staging topology look like?

**Would prioritize:**

1. Credential rotation and repo cleanup (hours, not days)
2. CI hardening (make gates real)
3. Second engineer hiring (begins reducing bus factor immediately)

---

## Principal Engineer

**Strongly agrees with:**

- Hexagonal DDD is properly implemented — this is rare and valuable
- The scoring core (`scoring.py`, 897 LOC) is excellent engineering
- ADR governance is above-average for this stage
- Module duplication (`ai/` vs `core/ai`, etc.) is the highest-priority refactoring target

**Challenges:**

- Is LangGraph truly a strategic risk, or is it appropriate infrastructure for the current stage? Replacing it prematurely could be over-engineering
- The "no event-driven architecture" critique (GLM-5.1) may be premature — a modular monolith with Celery may be correct for current scale
- ADR numbering inconsistency (two ADR-004s) suggests governance discipline is degrading, not improving

**Still needs:**

- Code-level review of the evaluator implementations — are they genuinely deterministic or do they have hidden LLM dependencies?
- Database migration strategy — is Supabase/RLS a deliberate choice or convenience?
- Performance profiling of scoring pipeline under load

**Would prioritize:**

1. Module consolidation (eliminate duplication, complete v2 cutover)
2. ADR cleanup (fix numbering, add missing ADRs for pending decisions)
3. Test suite audit (verify coverage on critical paths, not just line count)

---

## Product Lead

**Strongly agrees with:**

- "Coherence Score™" as a named category asset is genuinely defensible
- The ICP (procurement lead, pre-award gate, packages >€5M, EPC) is razor-sharp
- Schedule dimension must ship before the "tridimensional" claim becomes credible
- The honest-scoring null-state is the enterprise trust feature — sell the honesty, not the AI

**Challenges:**

- Is there validated demand from the target persona, or is this founder-driven conviction?
- The "founder-as-domain-moat" narrative (15 years EPC procurement) is powerful but creates dependency on a single voice
- Multiple reports suggest EPC beachhead → adjacent verticals, but no evidence of EPC beachhead success yet

**Still needs:**

- Customer discovery: have procurement directors at EPC firms validated willingness to pay?
- Competitive analysis: what do SAP Ariba, JAGGAER, Procore users actually lack?
- Usage data: are there any active pilot users?

**Would prioritize:**

1. Schedule dimension completion (makes headline claim true)
2. First 2-3 paid design partners (validates willingness to pay)
3. Evidence/audit export hardening (survives legal scrutiny — this is the moat)

---

## Security Lead

**Strongly agrees with:**

- Leaked `service_role` key + JWT secret is a critical exposure
- RLS on 19 tables + 42 security tests + e2e-security CI is genuinely above-average security posture
- Missing `SECURITY.md` and vulnerability disclosure policy blocks enterprise adoption
- No encryption at rest for memory layers (Gemini reported, but likely true given JSON storage patterns)

**Challenges:**

- The "no hard-coded secrets" finding (Claude verified) appears to contradict the "leaked service_role key" finding — which is it? Both may be true: secrets may have been committed after the initial gitleaks scan
- PII anonymization before AI calls (GLM-5.1) — if true, this is significant. If false, it's a critical gap. Must verify.

**Still needs:**

- Full credential audit: what exactly was committed and when?
- PII handling verification: is sensitive data sent to Claude API without anonymization?
- RLS test coverage: the missing RLS test for `clause_embeddings` (Claude reported) — is this an isolated gap or systemic?

**Would prioritize:**

1. Credential rotation and git history purge
2. PII anonymization verification
3. Complete RLS test coverage
4. Add SECURITY.md and vulnerability disclosure policy

---

## AI Systems Architect

**Strongly agrees with:**

- Deterministic-first with LLM escalation cascade is the correct architecture for a "defensible verdict" product
- Cost-gating the LLM layer (CoherenceLlmGate) shows mature AI engineering instinct
- The evidence-maturity layer (EML) with coverage-aware scoring is genuinely differentiated IP
- Heavy LangGraph/LangChain dependence is a real but manageable risk — the moat must be the evaluators, not the orchestration

**Challenges:**

- Are the 27 evaluators truly deterministic, or do some have hidden LLM calls that would break under API changes?
- Prompt versioning and A/B testing in LangSmith Hub is pending (`TASK-AI-010/011`) — this is critical for AI system reliability
- Multi-language prompt templates are deferred, but the product targets ES/EN markets — this is not optional

**Still needs:**

- Evaluator dependency graph: which evaluators are purely deterministic vs. LLM-dependent?
- Prompt template inventory: how many prompts exist, and what's the versioning state?
- Fallback behavior: what happens when Claude API is unavailable? Are there graceful degradation paths?

**Would prioritize:**

1. Prompt versioning and A/B infrastructure (prevents silent regression)
2. Evaluator dependency classification (deterministic vs. LLM)
3. Multi-language prompt template architecture (market requirement)
4. Fallback/degradation testing for API outages

---

# Phase 7 — Questions for Repository Verification

**Architecture Uncertainty:**

1. **What is the exact import dependency graph between `src/coherence/` and `src/modules/coherence/`?** Which integration tests (I2-I14) depend on the legacy module, and what breaks if it's retired?
    
2. **What is the migration completion plan in `G6-06_LEGACY_ADAPTERS_RETIREMENT_PLAN.md`?** Is it actionable or aspirational? What's the estimated effort?
    
3. **Does `main.py` contain feature flags that gate between v1 and v2 coherence engines?** If so, what's the current default and what would cutover require?
    

**Product Uncertainty:**

4. **What is the actual state of the schedule dimension in the codebase?** Is there any schedule parsing/scoring code, or is it entirely deferred?
    
5. **Are there any active pilot users or design partners?** Is there usage telemetry or feedback data?
    
6. **What does the current API surface look like?** How many endpoints are exposed, and what's the authentication/authorization model?
    

**AI Workflow Uncertainty:**

7. **Of the 27 evaluators, how many are purely deterministic vs. LLM-dependent?** What is the fallback behavior when LLM calls fail?
    
8. **What is the prompt template inventory?** How many prompts exist, what's their versioning state, and are they language-parameterized?
    
9. **Is CoherenceLlmGate (PR #143) merged and active?** What are the cost thresholds and bypass conditions?
    
10. **What does the evidence-maturity layer (EML) actually implement?** Is it a coverage metric, a confidence score, or something else?
    

**Security Uncertainty:**

11. **Exactly what credentials were committed, when, and are they still active?** Has the `service_role` key been rotated in Supabase?
    
12. **Is PII anonymized before AI calls, or is raw contract data sent to the Claude API?** This is a compliance-critical question.
    
13. **What RLS tests are missing?** Specifically, is the `clause_embeddings` gap isolated or indicative of broader RLS test coverage issues?
    

**Deployment Uncertainty:**

14. **What does the actual production/staging topology look like?** Is there a running deployment, and if so, what infrastructure does it use?
    
15. **What is the current CI/CD pipeline behavior?** Specifically: are `continue-on-error` and `--cov-fail-under=0` in critical paths or non-blocking workflows?
    

---

# Phase 8 — Consensus Maturity Score

|Area|Confidence|
|---|---|
|Architecture|65%|
|Product|55%|
|Security|60%|
|AI Design|70%|
|Maintainability|75%|
|Scalability|40%|
|Roadmap|35%|

### Overall Consensus Confidence: **57%**

**Rationale:** The committee has high confidence in what C2Pro _is_ (contract intelligence platform with principled scoring core) and what its _critical blockers_ are (leaked creds, bus factor 1, unfinished v2 cutover). Confidence drops significantly for _product-market fit validation_, _runtime behavior_, _deployment topology_, and _forward-looking roadmap_ — areas where repository evidence is insufficient and speculation dominates.

---

# Final Output

## What We Know

1. C2Pro is a vertical contract-intelligence platform for EPC/construction with a Coherence Score™ engine that cross-audits contracts, schedules, and budgets.
    
2. The coherence engine is principled: exponential-decay scoring with bounds (5.0–97.0), deterministic-first architecture with LLM escalation, null-honesty on insufficient evidence, and cost-gated LLM usage.
    
3. Hexagonal DDD with 20 bounded contexts is properly implemented; 9 ADRs exist with a decision log.
    
4. Multi-tenant RLS is real: 19 tables with row-level security, 42 security tests, e2e-security CI.
    
5. Dual codebases exist: `src/coherence/` (v2, active) and `src/modules/coherence/` (legacy). Module duplication (`ai/` vs `core/ai`, `mcp/` vs `core/mcp`) creates confusion.
    
6. Repository hygiene is poor: junk files, caches, committed build artifacts, Windows path corruption.
    
7. Bus factor is 1: 225K LOC backend, single maintainer.
    
8. Schedule dimension is not in scoring; "tridimensional" claim is aspirational.
    
9. LICENSE and SECURITY.md are absent.
    
10. CI infrastructure exists (15 workflows) but may not be reliable (unverified claims of `continue-on-error` and `--cov-fail-under=0`).
    
11. Production readiness is approximately 20-35%, not the self-reported 65%.
    
12. Gemini's report is a near-total hallucination describing a different product.
    

---

## What We Think We Know

1. Leaked credentials exist in the repository (Claude-verified `service_role` key + JWT secret; needs second confirmation).
    
2. Live 500 errors exist on core endpoints (Claude-reported `TASK-BCK-051`; needs runtime verification).
    
3. Sentry/observability is not wired in production (consistent across reports; `TASK-INF-055` in backlog).
    
4. The frontend is significantly less mature than the backend (multiple reports; no state management strategy beyond React contexts).
    
5. Tight coupling to Claude API with no model-switching abstraction (GLM-5.1 and Claude both noted).
    
6. Supabase RLS creates vendor lock-in for the security architecture (architecturally plausible).
    
7. PII anonymization may occur before AI calls (GLM-5.1 claimed; unverified and compliance-critical).
    
8. The honest-scoring null-state is a genuine trust differentiator (verified in ADR-009, PR #136).
    
9. LangGraph/LangChain dependency is real but manageable; the evaluators, not the orchestration, are the moat.
    

---

## What We Do Not Know Yet

1. **Whether there is any validated product-market fit.** No evidence of active pilots, paying customers, or willingness-to-pay validation.
    
2. **The exact state of the schedule dimension.** Is there any code, or is it entirely deferred?
    
3. **Runtime behavior under load.** No performance data, no SLA evidence, no deployment topology information.
    
4. **The evaluator dependency graph.** Which of the 27 evaluators are deterministic vs. LLM-dependent? What breaks when the LLM API is unavailable?
    
5. **PII handling in AI calls.** Is sensitive contract data sent raw to Claude API? This is a compliance-critical unknown.
    
6. **The migration path for the dual codebase.** What exactly does the retirement plan require, and what breaks during execution?
    
7. **Whether CI gates are real or cosmetic.** The `continue-on-error` and `--cov-fail-under=0` claims need code-level verification.
    
8. **Prompt template inventory and versioning state.** How many prompts, what languages, what versioning?
    
9. **Whether the leaked credentials are still active.** Has rotation occurred?
    
10. **The actual production/staging infrastructure.** Is there a running deployment?
    

---

## What Must Be Verified Next

**Priority 1 (Blocks All Enterprise Progress):**

1. Credential audit: what was committed, when, is it still active, has it been rotated?
2. PII handling verification: is raw contract data sent to Claude API?
3. Schedule dimension code state: is there any schedule parsing/scoring implementation?

**Priority 2 (Blocks Production Readiness):** 4. CI gate audit: verify `continue-on-error` and `--cov-fail-under=0` claims 5. Runtime verification: reproduce live 500 errors, test observability stack 6. Evaluator dependency classification: deterministic vs. LLM-dependent inventory

**Priority 3 (Blocks Strategic Decisions):** 7. Dual-codebase migration plan: actionable assessment of retirement effort 8. Frontend maturity assessment: state management, component architecture, test coverage 9. Customer discovery: are there any active pilot users or design partners?

---

## Committee Verdict

### **Requires Code-Level Investigation**

**Justification:**

The committee has sufficient evidence to make strategic judgments about C2Pro's _direction_ (the coherence engine is the product; the agentic platform is deferred) and _critical blockers_ (leaked credentials, bus factor 1, unfinished v2 cutover). However, several findings that would determine the _path forward_ remain at MEDIUM confidence because they depend on code-level verification:

- Whether CI gates are real or cosmetic determines whether the existing test suite can be trusted
- Whether PII is anonymized before AI calls determines compliance posture
- Whether the leaked credentials are still active determines immediate security response
- The evaluator dependency graph determines AI system reliability strategy
- The schedule dimension code state determines product roadmap feasibility

**No amount of additional report synthesis will resolve these questions.** The next step is a focused code-level investigation targeting the 15 verification questions in Phase 7, not another comprehensive review.

The project is **not ready for detailed planning** because the evidence base for planning is incomplete. It is **not merely needing more repository validation** — the committee has already identified what to validate. It **requires targeted code-level investigation** of specific high-impact unknowns.

---

# Consensus Delta

**What single piece of new evidence would most increase committee confidence by the largest amount?**

## A complete runtime deployment audit — demonstrating the system actually processing a real contract end-to-end with observability output.

This single evidence source would simultaneously resolve:

1. **Are the live 500s real?** (Runtime verification)
2. **Is PII anonymized?** (Observe the Claude API payload)
3. **Is observability wired?** (Check Sentry/trace output)
4. **What's the actual latency and error profile?** (Performance baseline)
5. **Does the coherence engine produce defensible verdicts on real data?** (Product validation)
6. **What is the actual deployment topology?** (Infrastructure clarity)

Short of runtime access, the **second-highest-value evidence** would be a **targeted credential audit and PII handling code review**, because these are compliance-critical findings that could either confirm a critical security exposure or provide genuine reassurance — and they can be verified from the repository alone.