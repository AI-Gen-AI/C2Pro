## 1. Verified Truths

|Conclusion currently in consensus|Classification|Confidence|Reason|
|---|---|--:|---|
|C2Pro is a vertical contract/document intelligence platform, not a generic agent OS|**VERIFIED**|95%|README and architecture docs define it as Contract Intelligence for construction/engineering; Gemini’s “Command & Control agent swarm” framing is inconsistent with repo evidence.|
|The technical base is real, not just a mockup|**VERIFIED**|90%|FastAPI app, routers, LangGraph workflow, config, CI, backlog and architecture docs exist.|
|It is not enterprise-production-ready|**VERIFIED**|90%|Integration tests use `continue-on-error`; real-document workflow is manual/operator-only; security backlog remains open.|
|CI exists, but some gates are weak or non-blocking|**VERIFIED**|95%|`tests.yml` exists, but unit coverage gate has `--cov-fail-under=0` and integration continues on error.|
|Real Document Operability is not yet a strong automatic production gate|**VERIFIED**|90%|Workflow uses `workflow_dispatch`, `C2PRO_AI_MOCK=1`, and real document flow only runs when operator input is true.|
|License metadata is inconsistent|**VERIFIED**|95%|README says proprietary; `package.json` says ISC.|
|Root test script is not a real test command|**VERIFIED**|95%|`package.json` root script exits with “no test specified”.|
|Coherence Score is the central technical/product asset|**VERIFIED**|85%|README, roadmap and recent PRs center on Coherence Score, scoring v2, null-safe scoring and evidence-aware behavior.|
|Coherence v2 cutover was not fully complete at least at PR #152|**VERIFIED**|85%|PR #152 explicitly says router branching needs a v2 evidence ingestion pipeline that did not yet exist.|
|Schedule contribution to scoring is/was a critical uncertainty|**PROBABLE**|75%|Backlog lists `TASK-BCK-064` as P0; PR #155 claims fix. Current runtime must verify actual state.|
|Repository hygiene is materially poor|**PROBABLE**|80%|Multiple reports cite root pollution, caches, artifacts, PDF/contracts and worktrees; direct evidence confirms at least stale worktree/submodule issue.|
|`.env.staging` / secrets exposure is a P0 incident until disproven|**PROBABLE**|70%|Several cloned-repo reports claim real-format secrets in history. I did not directly verify contents here and will not reproduce them. Treat as incident pending secret scan and rotation.|
|AI cache key appears under-scoped|**VERIFIED**|85%|Cache key uses prompt, system prompt, model, temperature and max tokens; tenant/prompt version/schema version are not visible in key builder.|
|HITL can be bypassed by environment flag|**VERIFIED**|85%|Workflow routes past HITL if `C2PRO_AI_MOCK=1` or `C2PRO_SKIP_HITL=1`; production protection must be verified.|
|Checkpointer fallback weakens production auditability if enabled in prod|**VERIFIED as code behavior / PLAUSIBLE as production risk**|75%|Code logs failure and continues after setup error; whether this occurs in production is unknown.|
|“740 commits / first commit 2025-12-29” correction|**PROBABLE**|70%|Later committee reports claim full clone corrected earlier shallow-clone error. I treat it as secondary evidence unless independently reproduced.|
|“118/121 commits and repo only one month old”|**REJECTED / OUTDATED**|85%|Later committee reports identify this as a shallow-clone cascade error.|
|Gemini’s agent-swarm / Temporal / WASM framing|**REJECTED**|95%|It describes a different product and should not influence execution.|
|Full microservices/event-driven migration should be planned now|**REJECTED**|85%|Current evidence supports stabilizing modular monolith, not architectural replacement.|
|Full Project Operating System / marketplace / BIM / mobile field app should enter near-term planning|**REJECTED**|85%|These are roadmap inflation and architecture fantasy relative to verified maturity. Several consensus files themselves mark full AI Project OS as weak/mostly rejected or future.|

---

## 2. Consensus Risks

### Consensus contamination

|Contaminated claim|Status|Why it is risky|
|---|---|---|
|“Everyone agrees C2Pro needs a Project Health Engine now”|**Downgrade to PLAUSIBLE**|Many reports repeat it, but it is a product-strategy hypothesis, not a repository fact. It may be true later, but it should not displace verified P0 stabilization.|
|“Temporal intelligence / ProjectGraph is the obvious next architecture”|**Downgrade to PLAUSIBLE**|Strong strategic idea, weak execution evidence. Requires proving current coherence/document path first.|
|“Coherence cannot be the main product”|**Downgrade to PLAUSIBLE**|Product argument, not technical fact. Coherence may still be a valid initial wedge even if not sufficient for full project health.|
|“AI Design is either 3/10 or 8/10”|**Reject extremes**|Evidence supports a real AI pipeline, but not enterprise-grade AI governance. Correct range is probably mid-level pending runtime/eval verification.|
|“Security is strong because RLS exists”|**Downgrade**|RLS is positive, but does not neutralize possible secrets exposure, weak CI, backlog security items, and production-mode uncertainty.|
|“The repo was reinitialized in May 2026 and 225K LOC appeared in one month”|**Reject**|Later full-clone committee says this was a shallow-clone cascade hallucination.|

### Authority bias

The most dangerous authority-bias case is the original Claude commit-history claim. It propagated because other reports assumed “Claude cloned the repo, therefore the count is definitive.” Later consensus reports explicitly call this out as a shallow-clone artifact and reject it. This is exactly why CLI agents should not execute from consensus documents alone.

### Cascade hallucinations

Gemini’s “Command & Control Professional for Generative AI” interpretation is a cascade risk. Any recommendations derived from it — Temporal core, WASM sandbox, agent mesh, swarm race conditions — should be excluded unless independently tied to actual C2Pro code paths.

### Roadmap inflation

Exclude from execution planning now:

|Recommendation|Why it should not enter planning yet|Evidence missing|
|---|---|---|
|Temporal.io rewrite|No verified need; current stack already has LangGraph/Celery/Postgres/Redis|Runtime bottleneck proof, failure profile, scale target|
|WASM/microVM sandbox|C2Pro is not currently verified as executing arbitrary user code|Tool execution threat model|
|Microservices/event-driven migration|Premature; modular monolith is suitable for current maturity|Load/concurrency evidence showing monolith failure|
|Dedicated graph database|Optimization, not validated need|Postgres/pgvector/relational graph limits under workload|
|Marketplace of agents|Product fantasy at current stage|Users, extensibility API, security model|
|BIM/IFC/mobile field app|Far outside verified current wedge|ICP validation and product usage data|
|Full Project Operating System|Mostly rejected by serious consensus as “not now”|Proven document/coherence wedge first|
|SOC2/SSO/SAML as immediate implementation|Important later, but premature before pilot/runtime trust|Customer requirement or enterprise pilot contract|
|Billing/metering|Not before trust path is stable|Paying customer motion|
|Fine-tuned/domain LLM|Not before eval corpus and baseline metrics|Dataset, eval harness, cost/accuracy comparison|

---

## 3. Validation Backlog

Smallest set of checks that removes the most uncertainty before CLI agents touch implementation:

|Validation Target|Why it matters|Risk if wrong|
|---|---|---|
|1. Full git-history secret scan, including `.env*`, reports, artifacts and logs|Possible `service_role` / JWT / DB credential exposure is existential|Agents may build on compromised infra; legal/security incident remains open|
|2. Confirm whether exposed credentials were rotated and whether history was purged|Secret detection alone is insufficient|False sense of security|
|3. Runtime E2E: upload contract + schedule + budget and verify all dimensions feed Coherence Score|Validates headline “tridimensional” claim|Product claim remains false or partially false|
|4. Verify current Coherence v1/v2 routing and authoritative path|PR #152 says v2 cutover needed missing ingestion pipeline|Agents may modify legacy path instead of active path|
|5. Verify `TASK-BCK-064` status in code and runtime, not just backlog/PR text|Backlog and PR disagree|Wrong P0 prioritization|
|6. Inspect AI cache keys for tenant, prompt ID, schema version, model version and redaction version|Prevents cross-tenant or stale-response risks|Data leakage or invalid AI outputs|
|7. Check production-mode guards for `C2PRO_AI_MOCK`, `C2PRO_SKIP_HITL`, checkpointer memory fallback|Test conveniences must not survive production|False approvals, missing auditability, silent degradation|
|8. Execute CI locally or in GitHub and identify which checks are blocking vs advisory|Consensus says CI exists but is partially decorative|Agents may trust bad gates|
|9. Map active runtime modules: `src/coherence`, `src/modules/coherence`, `analysis`, `procurement`, `stakeholders`|Prevents changes in dead/legacy code|Wasted CLI-agent work|
|10. Verify broad exception handling and failure surfacing in graph nodes|Silent failures can become “0 risks found”|Dangerous customer-facing false negatives|
|11. Verify migration system canonicality: Alembic vs Supabase CLI|Reports claim dual migration systems|Schema drift and broken deployments|
|12. Verify deployment topology: API/Celery same container or separated|Production scalability and failure isolation|Worker crash can affect API, or reports may be wrong|
|13. Verify auth source of truth: Clerk, Supabase Auth, JWT custom|Current consensus sees hybrid ambiguity|Security fixes may target wrong auth layer|
|14. Verify OpenAPI/client contract generation is current|Prevents frontend/backend drift|CLI agents may break API consumers silently|
|15. Inventory repo hygiene with tracked files only, not working tree noise|Needed before cleanup agents run|Agents may delete useful files or miss committed artifacts|

---

## 4. Execution Readiness Score

**Execution readiness for CLI-agent planning: 58 / 100**

Breakdown:

|Area|Score|Reason|
|---|--:|---|
|Security clarity|35|Possible secrets incident unresolved; prod-mode guard unknown|
|Architecture clarity|65|Broad structure is known, but active vs legacy paths need mapping|
|Coherence engine clarity|55|Core asset identified, but v1/v2/schedule state still uncertain|
|CI/testing trust|50|CI exists, but some gates are weak/non-blocking|
|AI orchestration trust|60|LangGraph/model router exist; runtime failure behavior needs verification|
|Deployment clarity|45|Celery/container/topology claims need direct confirmation|
|Maintainability hygiene|55|Problem likely real, but cleanup needs tracked-file inventory|

---

## 5. Go / No-Go Decision

**YES, WITH RESTRICTIONS**

CLI agents may proceed **only in verification/read-only mode first**. They should not implement new product features, not redesign architecture, not migrate to new platforms, not add roadmap items, and not touch broad refactors until the validation backlog confirms the active runtime paths.

Approved immediately:

|Approved action|Reason|
|---|---|
|Read-only repository inventory|Low risk; clarifies active vs stale files|
|Secret scan and credential exposure verification|P0 safety issue|
|CI/gate audit|Directly improves trust before execution|
|Runtime E2E verification|Determines whether product claim is true|
|Active-path mapping|Prevents agents from modifying dead code|
|License/metadata verification|Simple, factual, high-confidence issue|

Refused until verification exists:

|Refused action|Reason|
|---|---|
|Implement Project Health Engine|Strategic hypothesis, not validated execution need|
|Rewrite orchestration|Architecture fantasy until runtime bottlenecks are proven|
|Microservices/event-driven migration|Premature and high-risk|
|Marketplace / public API / open-core edition|No evidence base for current execution|
|BIM/mobile/field workflows|Roadmap inflation|
|Dedicated graph database|Optimization without bottleneck proof|
|Broad “clean everything” deletion|Needs tracked-file inventory to avoid deleting useful artifacts|
|Production deployment claims|Security/runtime gates unresolved|

---

### If I had only ONE week of engineering time before allowing CLI agents to modify the repository, what exactly would I verify first and why?

I would spend the week on **evidence pack creation**, not implementation:

1. **Day 1 — Secret incident verification.** Run full-history secret scan, identify `.env*` exposure, confirm rotation/purge status. This is first because compromised credentials invalidate every other plan.
    
2. **Day 2 — Runtime truth test.** Execute one controlled E2E flow with contract + schedule + budget and prove whether Coherence Score truly uses all three. This validates or falsifies the product’s headline claim.
    
3. **Day 3 — Active-path map.** Trace which code paths are actually used for upload, parse, analysis, coherence, HITL, alerts and UI rendering. This prevents CLI agents from editing legacy/dead modules.
    
4. **Day 4 — CI trust audit.** List every workflow, which jobs block, which use `continue-on-error`, which use mocks, and which coverage thresholds matter. Agents must not rely on decorative green checks.
    
5. **Day 5 — Production guard audit.** Verify mock/HITL/checkpointer/cache behavior under production settings. The goal is to prove the system fails closed.
    
6. **Day 6 — Migration/deployment audit.** Confirm Alembic/Supabase canonical flow and whether API/Celery are isolated. This prevents schema and runtime drift.
    
7. **Day 7 — Minimal execution authorization memo.** Produce a factual “agents may modify only these files/areas” boundary based on verified active paths.
    

Without that week of verification, CLI agents risk accelerating uncertainty rather than reducing it.