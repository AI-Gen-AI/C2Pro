# C2Pro — Technical Due-Diligence & Strategic Review

**Repository:** `github.com/AI-Gen-AI/C2Pro` (cloned and inspected directly — `main` @ `e665914`) **Review date:** 14 June 2026 **Method:** Full clone (4,841 tracked files), commit-history analysis, source/architecture inspection, security scan, backlog/ADR review. Every numeric claim below was measured from the working tree, not estimated.

> **Framing.** This is written as an acquirer's pre-investment technical DD, per your instructions: brutally honest, evidence-first, no protecting the project's feelings. It also credits what is genuinely strong — because the strong parts are the investable parts, and pretending everything is broken would be as useless as pretending nothing is.

---

## 1. Executive Summary

C2Pro is a **vertical contract-intelligence platform** whose live, productized core is the **Coherence Score™ engine** — an AI system that cross-checks an EPC/construction contract against its schedule and budget and flags incoherences before they become overruns. The codebase is a monorepo: a **FastAPI/Python backend (~225K LOC, 1,472 files)** and a **Next.js 14 / TypeScript frontend (~54K LOC, 724 files)**, on Supabase Postgres (RLS), Redis, Cloudflare R2, Clerk auth, Celery, LangGraph/LangChain, pgvector, and the Claude API.

The single most important thing to understand is the **gap between two C2Pros living in one repo**:

1. **The focused wedge that is actually shipping** — the `src/coherence/` bounded context. This is where ~all recent work goes (ADR-009 "evidence-aware v2," "honest scoring," category routing). It is genuinely well-engineered: ADR-driven, shadow-mode rollout, canary gating, MAE auto-block, 4,574 Python test functions, 15 CI workflows. The engineering _judgment_ on display here is the strongest signal in the whole project.
    
2. **The grand multi-agent platform that is mostly deferred or dormant** — `src/modules/*` + `src/analysis/*` + `ai/agents` + a root-level "blackboard" agent swarm. This is the original maximalist vision: ingestion → OCR → clause extraction → hybrid RAG → knowledge graph → risk scoring → WBS/BOM → procurement planning → RACI inference → HITL → decision intelligence. The most ambitious flows (Procurement Plan, RACI, Stakeholder Resolution, intelligent WBS) are explicitly marked **`[PHASE 2 DEFERRED]`** in the backlog.
    

The narrowing to the coherence wedge is the **right** strategic call. But it has not been finished cleanly, and the repo carries the cost of the abandoned ambition as **architectural duplication, dead-ish code, and severe hygiene debt**.

**Three findings dominate everything else:**

- 🔴 **A live `service_role` Supabase key, JWT signing secret, and database credentials are committed in `.env.staging`** (real-format JWTs, present in git history at `cc9d080`). `.gitignore` _does_ ignore `.env.*` — the file was force-added. This is a textbook critical breach. **Rotate all staging credentials today and purge them from history.**
- 🟠 **The "tridimensional" promise is currently bi-dimensional.** Per the project's own backlog (`TASK-BCK-064`, P0), after a schedule upload parses successfully, `/coherence/evaluate/diagnostics` still returns `score_missing_dimensions=["schedule"]`. The schedule leg — one of the three pillars of the product's headline claim — is not yet contributing to scoring.
- 🟠 **Bus factor = 1.** 118 of 121 commits are the founder (two capitalizations of the same identity); the rest are Dependabot. The repo's git history is ~1 month old (first commit 2026-05-09) carrying 225K LOC — i.e. a large pre-existing, heavily AI-agent-assisted codebase re-initialized into a fresh repo.

**Net verdict:** A sharp, defensible product wedge built on rare domain expertise, wrapped in genuinely senior engineering judgment — currently undermined by a critical secret leak, an unfinished core promise, repo-hygiene debt (≈29% of all files are committed `.mypy_cache`), and single-founder risk. **Not production-ready and not institutionally investable _as-is_, but a credible pre-seed story after a focused 30–90 day remediation.**

---

## 2. Repository Scorecard

|Category|Score (/10)|Notes|
|---|---|---|
|**Architecture**|7|Clean hexagonal/DDD with 20 bounded contexts, ports/adapters, 9 ADRs. Undercut by two coexisting generations (`coherence/` vs `modules/coherence/`) and duplicate concerns (`ai/` vs `core/ai`, `mcp/` vs `core/mcp`).|
|**Code Quality**|6|Core engine (`scoring.py`, 897 LOC) is excellent — documented, principled, tested. Dragged down by ~1,500 junk/cache files, 10 committed chat transcripts, and dead-code ambiguity. Only 36 inline TODO/FIXMEs (work is tracked in backlogs — good).|
|**Security**|4|Strong _practices_ (RLS on 19 tables, 42 security tests, gitleaks + Husky hooks, e2e-security CI, no secrets in code) — but a committed live `service_role` key + JWT secret is a critical exposure that caps the score. No `SECURITY.md`.|
|**AI Design**|7|Thoughtful: evidence-maturity model, deterministic+LLM hybrid (27 evaluators), cost-gated LLM layer, "honest" null scoring instead of fabricated 100/0. Heavy LangGraph/LangChain dependence; most agentic flows deferred.|
|**Product Strategy**|8|Razor-sharp ICP (procurement lead, pre-award gate, packages >€5M, EPC) matched to the founder's own 15-yr domain. "Coherence Score™" is a genuine named-category asset.|
|**Scalability**|6|Modular monolith + Celery + Redis + pgvector + per-tenant RLS is appropriate for stage. Risks: Celery task-registration drift (`TASK-BCK-077`), single-instance assumptions, no load evidence.|
|**Maintainability**|6|Backlog/ADR discipline is exceptional. But 225K LOC under one maintainer, plus duplication and junk, is a real long-term liability.|
|**Documentation**|6|Extensive `docs/` (ADRs, runbooks, decision log, status). Hurt by drift: deprecated-but-present files, docs dated 2026-03 in a repo first-committed 2026-05, README overstating "tridimensional."|
|**Innovation**|7|The honest null-state, evidence-maturity layer (EML), and cross-dimensional deterministic evaluators are genuinely novel _within the vertical_.|
|**Enterprise Readiness**|4|Multi-tenancy + RLS + CI are real assets. But: leaked creds, Sentry DSN not wired (`TASK-INF-055`), live 500s in prod (`TASK-BCK-051`), no SLA evidence, no LICENSE, bus factor 1.|
|**Overall maturity**|**5.5**|Strong core, unfinished edges, hygiene debt.|
|**Production readiness**|**3.5**|Blocked by the three dominant findings above.|

---

## 3. Architecture Review

### Strengths (real, not cosmetic)

- **Hexagonal/DDD done properly.** Each bounded context (`coherence`, `documents`, `procurement`, `projects`, `stakeholders`, `wbs`, `alerts`, `analysis`…) splits cleanly into `domain/ application/ adapters/ ports/`. The dependency rule (no domain imports of external deps) is consistently enforced.
- **Decision governance.** 9 ADRs (`docs/architecture/decisions/`) plus a `DECISION_LOG.md`. ADR-009 is a model of rigor: phased compatibility → shadow → canary with a shadow-MAE ≤ 15 auto-block.
- **The scoring core is principled.** `scoring.py` implements exponential-decay scoring with a floor (5.0), ceiling (97.0), scope normalization, and source-weighting (deterministic > LLM findings). This is design, not a prompt wrapper.
- **CI breadth.** 15 workflows including `evaluation-regression`, `golden-corpus-evals`, `openapi-drift`, `real-document-operability`, and scheduled drift checks — most early-stage repos have _none_ of this.

### Weaknesses

- **Two brains, one skull.** `src/coherence/` (new, evidence-aware, actively developed) and `src/modules/coherence/` (older, feeds the `analysis/` LangGraph pipeline and the I2–I14 integration tests) both exist. `src/analysis/*` still imports `src.modules.{hitl,coherence,extraction}`. There is even a `G6-06_LEGACY_ADAPTERS_RETIREMENT_PLAN.md` — _they know_, but the retirement isn't done.
- **Concern duplication:** `ai/` vs `core/ai`, `mcp/` vs `core/mcp`, `modules/scoring` vs `coherence/scoring`. A newcomer cannot tell which is canonical without reading `main.py` feature flags.
- **ADR numbering is inconsistent:** two `ADR-004` files (`004-frontend-layer-rules.md` and `ADR-004-circuit-breakers.md`); 007 and 008 are missing from the sequence.

### Risks

- The deferred agentic platform is **schema-coupled** to live code via `modules/`. "Just delete the old stuff" is not safe until `analysis/` is migrated off it — that's a real, non-trivial piece of work, not a cleanup.
- Feature-flag-gated dual implementations (`feature_coherence_analysis`, per-tenant cutover flags) are powerful but multiply the test matrix; a flag combination is an untested state waiting to happen.

### Recommendations

Pick **one** coherence engine and commit. Finish the `modules/` → bounded-context migration or formally freeze `analysis/` as a separate experimental package outside `src/`. Renumber ADRs. Document the canonical pipeline in one diagram that matches the code (the current README architecture box does not).

---

## 4. AI System Evaluation

|Dimension|Assessment|
|---|---|
|**Orchestration**|LangGraph composable subgraph; deterministic evaluators + LLM escalation cascade (doc-type priors → embedding similarity → LLM). Sound.|
|**Cost control**|`CoherenceLlmGate` cost-gates the LLM semantic layer (PR #143) — mature instinct most teams skip.|
|**Reliability / honesty**|The flagship move: insufficient evidence returns `score=null` + `score_reason`, never a fabricated number (PR #136, ADR-009 §1/§14). This is a real trust differentiator.|
|**Evidence model**|Evidence-maturity layer + coverage-aware scoring + heuristic baseline band. Genuinely differentiated IP.|
|**Weaknesses**|Heavy dependence on LangGraph/LangChain (orchestration is commodity — the moat must be the _evaluators_, not the graph). Prompt versioning/A-B in LangSmith Hub still pending (`TASK-AI-010/011`). Multi-language prompt templates deferred.|
|**Hallucination posture**|Deterministic-first with LLM as escalation, plus null-honesty, is the correct architecture for a "defensible verdict" product.|

**Scores:** AI capability **7/10**, reliability **7/10**, agent maturity **5/10** (because the multi-agent vision is mostly deferred — what ships is a disciplined hybrid scorer, not an autonomous agent system).

---

## 5. Security Audit

|Severity|Finding|Evidence|Remediation|
|---|---|---|---|
|🔴 **Critical**|Live Supabase **`service_role` key** (RLS-bypassing), **`JWT_SECRET_KEY`** (token forgery), and **`DATABASE_URL`** committed in `.env.staging`. Real-format HS256 JWTs (208/219 chars).|`.gitignore:25` ignores `.env.*`; file force-added; in history at `cc9d080`.|**Rotate all staging credentials now.** Purge from history (`git filter-repo`). Add a CI secret-scan gate that fails on any tracked `.env.*` except `.example`.|
|🟠 **High**|A **real third-party contract PDF** (`HVPNL_First Contract (Main Contents).pdf`, 1.3 MB — Haryana power utility) is committed.|Root of repo.|Confirm you have rights to redistribute it. If it's a sample/client doc, remove from history and move to access-controlled storage. Potential confidentiality/GDPR exposure.|
|🟠 **High**|**No `LICENSE` file** despite a "License: Proprietary" badge; **no `SECURITY.md`**.|Verified absent.|Add an explicit proprietary LICENSE and a vulnerability-disclosure policy. Without a license, the legal default is murky for any collaborator.|
|🟡 **Medium**|RLS test missing for `clause_embeddings`; cookie-consent endpoints lack auth guards.|`TASK-SEC-012`, `TASK-SEC-013` (their own backlog).|Close before any external pilot touches real tenant data.|
|🟡 **Medium**|Sentry DSN not configured — auth-failure monitoring is blind in prod.|`TASK-INF-055`.|Wire observability before claiming production-readiness.|
|✅ **Good**|No hard-coded secrets in source; `.env.test` correctly uses `dummy`/`test_` placeholders; `gitleaks.toml` + Husky pre-commit; 42 security tests; RLS on 19 tables; dedicated e2e-security CI.|Verified.|Maintain.|

**Security maturity: 4/10** — the _practices_ would score 7–8; a single committed god-key drags it to 4, because in real DD that one finding is disqualifying until fixed.

---

## 6. Completion Analysis

**Rough completeness of the _shipping wedge_ (coherence MVP): ~70–75%.** **Completeness of the _advertised grand platform_: ~30–40%, much of it deferred by design.**

Concrete unfinished items (from code + their own P0/P1 backlog):

- 🔴 **Schedule dimension not wired into scoring** (`TASK-BCK-064`, P0) — core promise gap.
- 🔴 **Live 500s** on project alerts & stakeholders in production (`TASK-BCK-051`, P0); log correlation blocked on prod log access.
- 🟠 `parsed_at` never persisted — parse use case has a placeholder comment, API returns `parsed=…, parsed_at=null` (`TASK-BCK-063`).
- 🟠 **v1→v2 coherence cutover incomplete** — still shadow mode; canary 10→50→100 pending (`TASK-COH-V2-CUTOVER-004`).
- 🟠 **Celery worker task-registration drift** — worker may not pick up current analysis/document tasks (`TASK-BCK-077`).
- 🟡 "108 pending QA tasks" is **mostly a manual Swagger endpoint audit** (`EPIC-QA-SWAGGER-MANUAL-VERIFICATION`, `TASK-QA-214..321`), not 108 missing features — important not to misread this as 108 holes.
- 🟡 Deferred agentic flows: Procurement Plan, RACI, Stakeholder Resolution, intelligent WBS (all `[PHASE 2 DEFERRED]`).

**Technical-debt estimate: ~25–30% of repo _content_** (cache/junk/transcripts/duplication), but the _code_ debt concentrated in two areas (engine duplication + abandoned-pipeline coupling) rather than spread thin — which is good news, because it's addressable in bounded chunks.

---

## 7. Top 25 Critical Findings (by impact)

1. 🔴 Committed live `service_role` key + JWT secret + DB creds (`.env.staging`).
2. 🟠 Schedule dimension not contributing to coherence scoring — headline claim is currently bi-dimensional (`TASK-BCK-064`).
3. 🟠 Bus factor = 1; ~1-month git history; heavily agent-generated 225K LOC.
4. 🟠 Two coexisting coherence engines (`coherence/` vs `modules/coherence/`) with live coupling via `analysis/`.
5. 🟠 Live production 500s on alerts/stakeholders (`TASK-BCK-051`).
6. 🟠 Real third-party contract PDF committed (confidentiality/IP risk).
7. 🟠 No LICENSE despite "Proprietary" badge; no SECURITY.md.
8. 🟡 ≈29% of all tracked files are committed `.mypy_cache` (1,418 files); plus `.pytest-tmp`, `playwright-report`, `backups/`, `temp_conflicting_frontend_files/`.
9. 🟡 10 pasted chat transcripts (`Sin título.txt`, `stablish only 5…txt` @ 210 KB, etc.) and local-path-named dumps (`CUsersesus_…`) in repo root.
10. 🟡 v1→v2 coherence cutover unfinished (shadow only).
11. 🟡 Celery task-registration drift — async pipeline reliability risk.
12. 🟡 `parsed_at` placeholder — document lifecycle telemetry incomplete.
13. 🟡 Sentry DSN unwired — prod auth-failure monitoring blind.
14. 🟡 `clause_embeddings` cross-tenant RLS test missing.
15. 🟡 Cookie-consent endpoints unauthenticated.
16. 🟡 ADR numbering inconsistency (two ADR-004; 007/008 missing).
17. 🟡 Documentation drift (deprecated-but-present status files; dates predate repo).
18. 🟡 README architecture diagram doesn't match actual code surface (omits the agentic platform, MCP, gamification, etc.).
19. 🟡 Feature-flag combinatorics create untested states.
20. 🟡 Heavy LangGraph/LangChain coupling → "AI wrapper" perception risk.
21. 🟡 Deferred flows still schema-coupled to live code (can't cleanly delete).
22. 🟡 No load/performance evidence behind `SLA_TARGETS.md`.
23. 🟡 `pnpm-lock.yaml` _and_ `package-lock.json` both committed — package-manager ambiguity.
24. 🟡 Stray zero-byte/garbage files (`=2.0.0`, `nombre prueba`, `{`, `.codex`) committed.
25. 🟡 EU **absolute-novelty patent timing**: any public disclosure (thesis defense/publication, or a public repo) can forfeit EU patentability — file the provisional _first_ (not legal advice; verify with IP counsel).

---

## 8. Top 25 Quick Wins (highest ROI)

1. Rotate staging creds + `git filter-repo` to purge `.env.staging` from history. _(hours; closes the critical finding)_
2. `git rm -r --cached .mypy_cache .pytest-tmp playwright-report test-results backups temp_conflicting_frontend_files tmp-gh-artifacts` and commit. _(minutes; removes ~30% of files)_
3. Delete the 10 root chat transcripts + local-path dumps + zero-byte junk. _(minutes)_
4. Add `LICENSE` (proprietary) + `SECURITY.md`. _(minutes)_
5. Remove the real contract PDF from history; move to access-controlled storage. _(hours)_
6. Pick one lockfile (pnpm) and delete `package-lock.json`. _(minutes)_
7. Add a CI gate that fails on any tracked `.env.*` besides `.example`. _(hours)_
8. Renumber ADRs; delete deprecated `MASTER_DEVELOPMENT_STATUS.md` (it already points elsewhere). _(minutes)_
9. Persist `parsed_at` (`TASK-BCK-063`) — small, removes a visible data-quality bug. _(hours)_
10. Wire the Sentry DSN (`TASK-INF-055`). _(hours)_
11. Add the `clause_embeddings` RLS test (`TASK-SEC-012`). _(hours)_
12. Guard cookie-consent endpoints (`TASK-SEC-013`). _(hours)_
13. Fix README architecture box to match reality (or label it "MVP scope"). _(minutes)_
14. Add a one-paragraph "which coherence engine is canonical" note to the repo root. _(minutes)_
15. Add a CONTRIBUTING.md + branch-protection note (even for a solo repo — investor signal). _(minutes)_
16. Tag a real semantic version + GitHub Release (no releases exist; `CHANGELOG` has only `[Unreleased]`). _(minutes)_
17. Add a status badge that reflects true coverage rather than just pass/fail. _(hours)_
18. Document the feature-flag matrix and which combinations are tested. _(hours)_
19. Move `sandbox/`, `blackboard/`, `worktrees/` out of the deliverable repo. _(minutes)_
20. Add `make clean` + ensure `.gitignore` actually covers everything currently leaking. _(minutes)_
21. Pin Python deps with hashes (`requirements.txt` + lock). _(hours)_
22. Add a CODEOWNERS file. _(minutes)_
23. Compress/relocate the 64 KB and 210 KB markdown/text artifacts polluting root. _(minutes)_
24. Add an architecture decision: freeze vs. migrate `analysis/`+`modules/` — even just writing the decision down. _(hours)_
25. Smoke-test the documented "5-minute" QUICK_START on a clean machine and fix what breaks. _(hours)_

> Items 1–6 alone would change the _first impression_ of this repo from "vibe-coded prototype" to "disciplined product" — and that first impression is what an investor's technical advisor forms in the first 10 minutes.

---

## 9. Top 25 Strategic Opportunities

1. **Own "Contract–Schedule–Budget Coherence" as a category.** No incumbent (SAP Ariba, JAGGAER, Procore) sells a defensible _coherence verdict_; generic LLMs can't sell trust. The named "Coherence Score™" is the wedge.
2. **Ship the schedule dimension and lead with "tridimensional" honestly** — it's the differentiator nobody else can casually replicate without domain models.
3. **Sell the _honesty_ (null instead of fabricated scores) as the enterprise trust feature.** Procurement directors fear false confidence more than missing data.
4. **Productize the evidence/audit trail as the moat**, not the AI — "here's _why_, with citations to clause/line" is what survives a legal dispute.
5. **EPC/infrastructure beachhead → adjacent verticals** (energy, mining, public works) where overruns are existential.
6. **Founder-as-domain-moat:** 15 yrs procurement across EMEA/LATAM/MENA is rare in AI startups. Position it. Design-partner sales should be founder-led.
7. **Patent the tridimensional auditing method** (provisional, pre-disclosure) and keep the detection engine as a trade secret.
8. **Coherence Score as an embeddable API/widget** for existing procurement suites — distribution via integration rather than rip-and-replace.
9. **Benchmark/golden-corpus as a marketing asset** — publish an accuracy report on anonymized real contracts.
10. **"Pre-award gate" workflow product** (not just a score) — the score is the hook; the workflow is the retention.
11. **Multi-language from day one** (ES/EN already partly modeled) — LATAM + MENA procurement is underserved by English-only tools.
12. **Risk-flagged clause library** as a recurring-value data product.
13. **Tenant-level benchmarking** ("your contracts vs. industry coherence") once enough data accrues — a data network effect.
14. **HITL review queue as a billable seat** — humans correcting the model is both revenue and training data.
15. **Compliance/audit export** (PDF/XLS evidence packs) for legal & finance stakeholders — already partly built.
16. **Design-partner program** with 3 EPC firms to convert the TFM into commercial proof.
17. **"Coherence regression" for change orders** — re-score on every contract amendment; recurring usage.
18. **Insurance/surety angle** — coherence score as an underwriting input for performance bonds.
19. **Sell the methodology as a standard** (a "coherence rubric") to win category authority.
20. **LangSmith-instrumented prompt marketplace internally** to iterate accuracy fast (`TASK-AI-010/011`).
21. **Vertical templates** (FIDIC, NEC, bespoke EPC) as configurable evaluator packs.
22. **Self-serve trial on a sample contract** to lower CAC (the sample-doc flow exists).
23. **Partner with QS/cost-consultancy firms** as a distribution channel.
24. **Decouple the deferred agent platform into a separate product line** later — don't kill it, _shelve it cleanly_ as optionality.
25. **Open-core the deterministic evaluator framework** (not the domain models) to build a developer moat and inbound — carefully, given the patent timing.

---

## 10. Development Roadmap

### Next 30 days — _Credibility & containment_

- Rotate + purge leaked secrets; remove the contract PDF from history. **(non-negotiable, day 1)**
- De-junk the repo (cache, transcripts, temp dirs, dual lockfile). Add LICENSE + SECURITY.md + a release tag.
- Fix the two P0 production bugs (alerts/stakeholders 500s; `parsed_at`).
- Wire Sentry; add the two pending security guards.
- Write the one decision that's been avoided: **freeze or migrate** `analysis/`+`modules/`.

### Next 90 days — _Finish the wedge_

- **Ship the schedule dimension into scoring** (`TASK-BCK-064`) — the product's headline must be true.
- Complete the v1→v2 cutover (canary to 100%); retire v1.
- Consolidate to one coherence engine; begin `modules/` retirement.
- Stand up 2–3 EPC design partners on real (anonymized) contracts.
- Publish a golden-corpus accuracy benchmark.

### Next 6 months — _From thesis to product_

- File the provisional patent (before any public disclosure/defense).
- Multi-language GA (ES/EN); FIDIC/NEC evaluator packs.
- Evidence/audit export hardening for legal & finance buyers.
- First paid pilots; basic usage analytics + SLA instrumentation backing `SLA_TARGETS.md`.
- Bring in a second engineer (reduce bus factor before it bites).

### Next 12 months — _Defensible vertical SaaS_

- Tenant benchmarking / data network effect.
- Change-order "coherence regression" recurring workflow.
- Embeddable API for procurement-suite integrations.
- Decide the fate of the agentic platform: relaunch as a deliberate product line or formally sunset.

---

## 11. Investor Perspective

**Is it investable today?** No — not by an institution, as-is. Bus factor of 1, a committed god-key, an unfinished core promise, no revenue, no license, and ~1 month of visible history are each individually a "fix first," and collectively a "not yet."

**Why it could become investable, fast:** The wedge is real and underserved, the ICP is sharp, and — critically — the _engineering judgment_ on display (honest scoring, ADR discipline, shadow/canary rollout, evidence modeling) is a strong proxy for founder quality. The domain expertise (15 yrs procurement) is the kind of unfair advantage that AI generalists can't buy. This is a "talented founder, real insight, executional gaps" profile — exactly what pre-seed exists for.

**What would make it investable:** (1) credentials rotated + repo cleaned (signals operational maturity), (2) schedule dimension shipped (headline becomes true), (3) 2–3 EPC design partners with a usage signal, (4) provisional patent filed, (5) a credible plan to de-risk bus factor.

**Estimated market potential:** EPC/construction procurement is a large, overrun-plagued spend category; even a thin SaaS slice of pre-award contract review across mid-to-large EPC firms is a meaningful TAM. The realistic early wedge (coherence review for >€5M packages) is a focused but expandable SAM. Treat any precise number with skepticism until design partners validate willingness-to-pay.

**Biggest risks:** single-founder concentration; "AI wrapper" perception (mitigate by foregrounding evaluator IP + domain); patent-timing forfeiture in the EU; scope sprawl re-diluting focus; and the gap between a brilliant TFM artifact and a supportable production service.

---

## 12. CTO Perspective

**Would I adopt this in production today?** No.

**What blocks adoption:**

- Leaked staging credentials and no incident/security posture (`SECURITY.md`, rotation, history purge).
- Live 500s on core endpoints; incomplete v2 cutover; schedule leg missing from scoring.
- Observability blind spots (Sentry unwired); no demonstrated SLA/load evidence.
- Bus factor 1 — no on-call, no second pair of eyes.

**What must be fixed first (in order):** (1) rotate/purge secrets; (2) clean repo + license; (3) kill the P0 500s; (4) finish v2 cutover and consolidate to one engine; (5) ship schedule-into-scoring; (6) wire monitoring + a basic runbook/on-call.

**What's genuinely reassuring:** Multi-tenant RLS, per-tenant feature flags, an honest-scoring philosophy, 4,574 tests, and 15 CI workflows are _above_ the bar for this stage. The bones are good. This is a project that needs _finishing and hardening_, not rebuilding.

---

## What the Maintainers Probably Haven't Realized Yet

1. **The hygiene debt is silently destroying your credibility, and it's the cheapest thing to fix.** ~29% of your repo is committed `.mypy_cache`; your root has pasted AI chat logs and a client's contract PDF. A technical advisor forms a verdict from this in 10 minutes — and right now that verdict ("vibe-coded, uncleaned") _contradicts_ the genuinely senior work inside `src/coherence/`. One afternoon flips the first impression entirely. This is the highest-leverage hour you can spend.
    
2. **Your real moat is the _honesty mechanism_, not the AI.** The decision to return `null` instead of a fabricated score (ADR-009 §1/§14) is the single most defensible, most enterprise-credible thing you've built — because procurement directors are paid to distrust false confidence. You're treating it as a bug fix; it's a _category-defining trust feature_. Lead your marketing with it.
    
3. **You shipped the right product by accident of discipline, and you're carrying the wrong product's corpse.** The narrowing to the coherence wedge is correct. But the deferred agentic platform isn't _gone_ — it's schema-coupled into live code via `modules/`, so it's taxing you (test matrix, cognitive load, "what's canonical?") without earning anything. Make the freeze-or-migrate decision _explicitly_ and write it down. Optionality you can't articulate is just debt.
    
4. **"Tridimensional" is your headline and it isn't true yet.** Per your _own_ P0 backlog, schedule evidence doesn't reach the score. Every demo where the third pillar is dark is a credibility leak with exactly the buyers (schedule-obsessed EPC PMs) you most need. This one ticket is worth more than the next ten features.
    
5. **The patent clock is the quiet existential risk.** In the EU, absolute novelty means a public defense, publication, _or this very public repo_ can forfeit patentability of the tridimensional method. The strongest IP you have (the methodology) is the one most exposed by the academic timeline. File the provisional before disclosure — and weigh making the repo private until you do. _(Not legal advice — confirm with IP counsel; but the sequencing risk is real and time-bound.)_
    
6. **Bus factor 1 is the thing that turns a great TFM into an unfundable one.** Everything else is fixable in weeks. This isn't — and investors price it heavily. Even one part-time second engineer, or a documented "anyone could pick this up" onboarding path (which your ADRs/backlog are 80% of the way toward), materially de-risks the story.
    

---

Would you like a **second-pass analysis focused exclusively on one of: (a) architecture & the engine-consolidation plan, (b) AI-agent design & evaluator IP, (c) monetization & go-to-market, (d) security & the credential-purge runbook, or (e) roadmap execution sequencing?** I can go deep on any one of these with concrete file-level and step-by-step recommendations.