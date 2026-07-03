Now I have enough to write the full analysis. Let me compose it:

---

# C2Pro — Complete Technical Due Diligence Report

_Reviewed: June 2026 | Repository: [AI-Gen-AI/C2Pro](https://github.com/AI-Gen-AI/C2Pro)_

---

## 1. Executive Summary

C2Pro is a **Contract Intelligence Platform** targeting the construction and engineering sector, designed to perform tri-dimensional cross-auditing of contracts, schedules, and budgets using AI (specifically Claude Sonnet) to detect cost-generating inconsistencies before they materialize.

The project is real, ambitious, and structurally sound in concept. But the repository, as-is, is a **working laboratory** — not a product. It shows the hallmarks of a highly capable solo/micro-team developer building while thinking out loud: exceptional domain clarity paired with chronic repository hygiene failures. The technical foundations are partially solid; the product surface is essentially invisible to any external observer. The project self-reports at ~65% of Sprint S2, with CTO security gates 1–4 validated. In reality, from an investor or enterprise adoption perspective, the effective production readiness is closer to 20–25%.

---

## 2. Repository Scorecard

|Category|Score (/10)|Notes|
|---|---|---|
|Architecture|6/10|Monorepo with clear separation, but scattered; `apps/`, `core/`, `infrastructure/` coexist with undocumented cross-dependencies|
|Code Quality|4/10|Unclean root dir, no consistent naming, scratch files committed alongside prod code|
|Security|5/10|RLS + JWT in Supabase, `.gitleaks.toml` present, but `.env.staging` committed to repo — critical leakage risk|
|AI Design|5/10|Claude Sonnet used, skill registry exists, blackboard pattern attempted; no prompt versioning or eval pipeline|
|Product Strategy|7/10|Sharp problem definition, clear ICP (construction/engineering), differentiated positioning; go-to-market absent|
|Scalability|4/10|Supabase + Redis + R2 chosen; no queue system, no worker isolation, no horizontal scaling strategy|
|Maintainability|3/10|Root contains: Spanish `.txt` files, a `.pdf` contract, `=2.0.0` empty file, `nombre prueba` test file|
|Documentation|6/10|Extensive internal docs (`diseño arquitectura.md` at 66KB, `agents.md` at 21KB), but no public-facing docs|
|Innovation|7/10|Tri-dimensional coherence engine concept is genuinely novel for the sector|
|Enterprise Readiness|2/10|No observability (Gate 7 not complete), no multi-tenant isolation beyond DB-level RLS, no SLA framework|

---

## 3. Top 25 Critical Findings

**Ranked by impact:**

1. **`.env.staging` committed to the repository** — [`.env.staging`](https://github.com/AI-Gen-AI/C2Pro/blob/main/.env.staging) is a tracked file containing likely real credentials for staging infrastructure. This is a P0 security incident waiting to happen.
    
2. **Repository root is a garbage dump** — Files like `"nombre prueba"`, `"=2.0.0"` (empty), `{.txt`, `Simular un ecosistema de agentes ex.txt`, `TASK-FRT-005 you have to guide me.txt`, and a 1.2MB **actual PDF contract** (`HVPNL_First Contract (Main Contents).pdf`) are committed at root. This alone disqualifies the repo from external contributor participation.
    
3. **Production PDF contract in a public (or semi-public) repo** — `HVPNL_First Contract (Main Contents).pdf` is a real vendor contract committed to Git history. This is a legal and confidentiality violation that cannot be undone without a complete history rewrite.
    
4. **No `packages/` implementation despite monorepo architecture** — The README describes `packages/` as shared packages "for the future," yet `pnpm-workspace.yaml` declares a monorepo workspace. The monorepo overhead exists with none of the benefits.
    
5. **`blackboard.json` at 126KB committed to root** — The blackboard is a runtime AI coordination artifact and should never be in Git. It signals that the AI agent's working memory is being manually committed.
    
6. **`diseño arquitectura.md` at 66KB and `Sin título.txt` at 40KB in root** — Internal design documents with Spanish names live at the root of a supposedly professional project. No path discipline.
    
7. **`stablish only 5 as much as possible.txt` at 211KB** — A massive scratch file (likely an AI conversation dump) is tracked in the repo.
    
8. **Dual lock files: both `pnpm-lock.yaml` and `package-lock.json` committed** — Indicates inconsistent package manager usage; creates reproducibility failures.
    
9. **Gate 7 (Observability) explicitly incomplete** — No structured logging, no distributed tracing, no metrics pipeline. The system is a black box in production.
    
10. **Gate 5 (Coherence Score Formal) is 65% complete** — The core value proposition of the product is not yet implemented. Every demo, pitch, or test is built on an incomplete engine.
    
11. **`.mypy_cache` committed to the repository** — Build artifacts in Git indicate no proper `.gitignore` discipline was applied early.
    
12. **`CUsersesus_DocumentsAIZTWQc2proC2PRO_MASTER_BACKLOG.md` at 64KB** — This filename is a Windows path corruption artifact. It's a duplicate of `C2PRO_MASTER_BACKLOG.md` pushed by mistake via a Windows path error.
    
13. **No CI/CD pipeline evidence** — GitHub Actions badges exist in README but no evidence of passing pipelines. The `tests.yml` and `e2e-security-tests.yml` references need verification.
    
14. **`tmp-gh-artifacts/`, `temp_conflicting_frontend_files/`, `playwright-report/` committed** — Temporary CI artifacts and unresolved merge conflicts are in the main branch.
    
15. **`context/` as "working memory non-canonical"** — The system has no actual persistent memory infrastructure; `context/` is a human-managed simulation of agent memory.
    
16. **No `LICENSE` file** — The README claims "Proprietary" license but no actual LICENSE file exists. Legally ambiguous.
    
17. **`analyze_payload.json` in root** — 9.6KB test payload committed to root instead of `tests/fixtures/`.
    
18. **`calibration_dataset.example.json` is only an example** — No real calibration dataset or eval infrastructure exists. The AI has no ground-truth validation path.
    
19. **`sandbox/` exists but is architecturally undefined** — Its relationship to `core/` is unclear, meaning prototype code may be silently promoted to production.
    
20. **`backlogs/`, `backups/`, `worktrees/` directories** — These are developer workflow artifacts masquerading as project structure. `worktrees/` especially should never be in a repo.
    
21. **Frontend type safety at "95%"** — The README admits 5% type-unsafe frontend. In a contract analysis platform handling legal documents, this is unacceptable.
    
22. **`Adapta y mejora el prompt para mi i.txt`** — Prompt engineering artifacts committed to root reveal that prompts are developed ad hoc without versioning or regression testing.
    
23. **`skills-lock.json` exists but no skills execution test suite** — A lockfile for skills without integration tests means skill drift is undetectable.
    
24. **`openspec/` and `evals/` directories exist but are empty or undocumented** — Critical infrastructure directories with no content signal aspirational architecture that hasn't been built.
    
25. **No public API documentation, no OpenAPI export, no Swagger published** — Despite FastAPI auto-generating docs, there is no published spec. External integrators have no surface to work against.
    

---

## 4. Top 25 Quick Wins (Highest ROI)

1. **Immediately rotate and remove `.env.staging`** from Git history using `git filter-repo`
    
2. **Remove `HVPNL_First Contract (Main Contents).pdf`** from Git history — legal urgency
    
3. **Add `.gitignore` entries** for `blackboard.json`, `.mypy_cache`, `playwright-report/`, `tmp-gh-artifacts/`, `test-results/`
    
4. **Move all `.txt` scratch files** to `context/` or delete them; enforce root cleanliness policy
    
5. **Consolidate to single package manager** (choose `pnpm`, delete `package-lock.json`)
    
6. **Add a real `LICENSE` file** — even a proprietary EULA template
    
7. **Create `tests/fixtures/`** and move `analyze_payload.json`, `calibration_dataset.example.json` there
    
8. **Delete `CUsersesus_*` duplicate files** — Windows path garbage
    
9. **Add `CONTRIBUTING.md`** with explicit "no scratch files in root" policy
    
10. **Publish OpenAPI spec** from FastAPI to `/docs` on GitHub Pages
    
11. **Create a `.github/CODEOWNERS`** file to enforce review requirements
    
12. **Wire SonarCloud** (`.sonarcloud.properties` exists but may not be active) to PRs
    
13. **Add `pre-commit` hook** to block commits with `.txt` files to root
    
14. **Document `context/` vs `sandbox/` boundary** explicitly with examples
    
15. **Tag first release** — even `v0.1.0-alpha` — to establish release cadence
    
16. **Add health check endpoint** to FastAPI (`/health`, `/ready`) for infra monitoring
    
17. **Enable Dependabot** for both Python and Node dependencies
    
18. **Create a GitHub Issues template** for bugs, features, and security reports
    
19. **Add `mypy` and `ruff` to CI** — type checking infrastructure exists but isn't enforced
    
20. **Move `diseño arquitectura.md`** to `docs/architecture/` with proper English filename
    
21. **Add `docker-compose.override.yml.example`** for local dev customization
    
22. **Create a `Makefile` target audit** — `Makefile` exists at 8KB; standardize all developer commands through it
    
23. **Add `SECURITY.md`** with responsible disclosure policy
    
24. **Create `evals/` baseline** — even 10 golden examples — to anchor the Coherence Engine's quality
    
25. **Add structured logging** (Python `structlog` or `loguru`) as a 2-hour task
    

---

## 5. Top 25 Strategic Opportunities

1. **The Coherence Engine is genuinely novel** — No mainstream SaaS product cross-audits contract + schedule + budget in one pass. This is a real moat if executed.
    
2. **Target public procurement markets** — Spain, Netherlands (HVPNL reference), EU public tenders all mandate multi-document consistency. C2Pro could be a compliance tool.
    
3. **Build a "Contract Memory" product** — Store extracted clauses, obligations, and deadlines across all company contracts as a vector DB. Competitors don't do this.
    
4. **Become an MCP server** — Expose C2Pro's analysis capabilities as an MCP tool so Claude, GPT, and Gemini users can call it natively.
    
5. **White-label for law firms and quantity surveyors** — These professionals manually do exactly what C2Pro automates. They will pay €500–2000/month per seat.
    
6. **ISO 20400 / EU procurement directive compliance module** — Automatic compliance checking against procurement regulations is a recurring legal need.
    
7. **Integrate with BIM tools** (Autodesk, Bentley) — Construction projects use BIM; a C2Pro plugin for BIM schedule extraction would unlock enterprise AEC market.
    
8. **"Incoherence as a Service" API** — Sell the core detection engine as an API to insurance companies, banks, and auditors who underwrite construction projects.
    
9. **Build an eval dataset from public contracts** — Spanish BOE, EU TED database, and public procurement portals contain thousands of real contracts for training.
    
10. **Add Spanish-language prompt optimization** — The domain expertise is clearly in Spanish; prompts likely perform better in Spanish for Spanish contract analysis.
    
11. **Real-time webhook-based monitoring** — Alert when a contract document is updated mid-project (milestone slippage detection).
    
12. **Multi-language contract support** — EU construction markets need FR, DE, NL, IT support. This is a premium tier feature.
    
13. **Human-in-the-loop review UI (Gate 6)** — A legal professional annotation interface would differentiate from raw AI outputs and create a training flywheel.
    
14. **Partner with Supabase** — This project is a showcase for Supabase's RLS capabilities; a partnership could yield marketing exposure.
    
15. **Publish the skill registry as open-source** — The `skill_registry.yaml` pattern is genuinely interesting and could attract developer community contributions.
    
16. **Add Zapier/Make.com integration** — Allow non-technical procurement officers to trigger analyses from document uploads in Google Drive or SharePoint.
    
17. **Build a "before you sign" product variant** — Pre-signature coherence review for SMEs at €49/document is a low-friction entry point.
    
18. **Target infrastructure funds and PE firms** — Private equity firms acquiring construction companies need due diligence on inherited contracts. High willingness to pay.
    
19. **Create a "contract health score" public benchmark** — Publishing industry-level data on contract incoherence rates would generate inbound SEO and thought leadership.
    
20. **Add a Slack/Teams bot** — "Ask C2Pro" bot for project managers to query their contract status in natural language.
    
21. **Temporal coherence detection** — Detect when contract deadlines have passed without schedule updates (time-based trigger analysis).
    
22. **Risk register auto-generation** — Automatically produce a project risk register from contract clause analysis, replacing a manual process.
    
23. **Integration with Procore, Autodesk Construction Cloud** — These platforms have millions of construction project users and open APIs.
    
24. **Regulatory watch module** — Alert when new procurement regulations affect existing contracts in portfolio.
    
25. **Offer a "certification" program** — Certify contracts as "C2Pro Validated" for a fee, creating a B2B trust signal.
    

---

## 6. Development Roadmap

## Next 30 Days — Emergency Hygiene

- Remove `.env.staging`, the PDF contract, and all scratch `.txt` files from Git history
    
- Enforce root cleanliness with pre-commit hooks
    
- Complete Gate 5: deliver the Coherence Score as a working, testable API endpoint
    
- Set up structured logging and a basic health dashboard (Gate 7 foundation)
    
- Tag `v0.1.0-alpha` and publish a minimal OpenAPI spec
    

## Next 90 Days — Core Product Completable

- Complete Gate 6: Human-in-the-loop annotation interface (React component for clause review)
    
- Complete Gate 7: Observability — integrate OpenTelemetry, send traces to Grafana or Datadog
    
- Build `evals/` pipeline: 50+ golden test cases for the Coherence Engine
    
- Implement prompt versioning: store prompts in DB with version history, A/B test capability
    
- Launch private beta with 3–5 construction/engineering firms
    
- Create public landing page and demo video
    

## Next 6 Months — Product–Market Fit Sprint

- Add document upload pipeline (PDF → text → structured extraction → coherence analysis) as a complete user flow
    
- Implement subscription billing (Stripe) with 3 tiers: Solo, Team, Enterprise
    
- Build the "Contract Memory" vector DB (pgvector in Supabase or Pinecone)
    
- Add multi-language support (Spanish + English as V1)
    
- Release MCP server so Claude/GPT users can call C2Pro as a tool
    
- Achieve first 10 paying customers
    

## Next 12 Months — Platform Ambition

- Launch "Incoherence API" as a standalone product
    
- Build BIM integration prototype (IFC file parsing)
    
- Open pilot with EU public procurement portal (TED integration)
    
- Achieve SOC 2 Type I compliance (prerequisite for enterprise sales)
    
- Hire first dedicated backend and frontend engineers
    
- Target €150K ARR from direct sales + API revenue
    

---

## 7. Investor Perspective

**Is this project investable?** Not yet — but it could be in 90 days with discipline.

**Why not yet:** The repository presents as a one-person R&D lab. There is no working demo, no paying customers, no clean codebase that a technical due diligence team could evaluate without finding the PDF contract, the staging secrets, and the 211KB scratch file. The core product feature (Coherence Engine) is still incomplete.

**Why it could be:** The problem is real and well-defined. The 15–30% cost overrun statistic in construction is empirically validated globally. The tri-dimensional analysis concept (contract + schedule + budget) is a genuine differentiator. The technology stack (FastAPI, Supabase, Claude) is modern and defensible. The security-first approach (RLS, CTO Gates) is a sign of mature thinking for a solo developer.

**What would make it investable:**

- A working Coherence Engine demo on a real sample contract
    
- 3+ reference customers (even unpaid pilots)
    
- Clean repository and professional presentation
    
- A credible ARR path to €500K within 24 months
    

**Estimated market potential:** The global construction project management software market is ~$10B. The contract compliance/analytics subsegment for EU/Spain public procurement alone is €500M+. C2Pro doesn't need to own 1% to be a valuable company — it needs to own 0.01% to be a €50M business.

**Biggest risks:**

- Solo dependency — one developer is an existential risk
    
- AI commoditization — large players (Procore, Autodesk) could add coherence checking as a feature in 18 months
    
- Legal complexity — contract analysis software faces professional liability questions in some jurisdictions
    
- Adoption friction — construction firms are notoriously slow technology adopters
    

---

## 8. CTO Perspective

**Would you adopt this in production today?** No.

**What would block adoption:**

- The Coherence Engine (the core feature) is not complete
    
- No observability means no way to diagnose production failures
    
- The AI pipeline has no eval framework; quality degradation is undetectable
    
- The committed `.env.staging` file means credentials may already be compromised
    
- No SLA, no uptime guarantee, no disaster recovery plan
    

**What must be fixed first (in order):**

1. Rotate all credentials, remove secrets from history
    
2. Complete the Coherence Engine to a testable state
    
3. Add structured logging + basic OpenTelemetry
    
4. Build a 50-case eval suite to establish quality baseline
    
5. Document the data flow from document upload to coherence report
    

---

# What the Maintainers Probably Haven't Realized Yet

**1. The blackboard pattern you're using is architecturally significant.** [`blackboard.json`](https://github.com/AI-Gen-AI/C2Pro/blob/main/blackboard.json) at 126KB in the repo root is a committed version of what should be a live, distributed coordination store. The Blackboard Pattern for multi-agent coordination is academically established and commercially rare. Formalizing this into a proper event-sourced blackboard with Redis pub/sub would make C2Pro's agent orchestration genuinely state-of-the-art — and publishable.

**2. The skill registry (`skill_registry.yaml`) is a hidden product.** You've essentially built a declarative skill composition system. This pattern — defining AI agent capabilities as versioned YAML manifests — is exactly what enterprise AI orchestration platforms charge for. This could be extracted as an open-source framework to build developer community around C2Pro.

**3. Your real competitive advantage is domain data, not the AI.** Every contract analysis you run generates labeled data on what coherence failures look like. This is a training flywheel. After 1,000 analyzed contracts, you will have a fine-tunable dataset that no competitor can replicate. You should be storing every analysis result in a structured way _now_, even if you don't use it for 12 months.

**4. The EU AI Act (2024–2026 rollout) is a tailwind, not a headwind.** Contract analysis AI in construction is "limited risk" under the EU AI Act — it requires transparency obligations but not conformity assessment. Your competitors in general-purpose AI will struggle; you can market C2Pro as "EU AI Act compliant by design" which is a genuine enterprise sales accelerator.

**5. You're building for construction but the engine works for any multi-document coherence problem.** Insurance policies vs. claims, pharmaceutical trial protocols vs. regulatory submissions, software RFPs vs. vendor proposals — the coherence engine is domain-agnostic. The construction focus is correct for go-to-market, but the underlying IP is much broader.

**6. The HVPNL contract in your repo may be your first real customer signal.** If HVPNL (likely a Dutch energy/infrastructure entity) is a real relationship, that's a warm enterprise pilot waiting to happen — not a security incident to hide. Turn it into a case study.

**7. You have `evals/` directory but no evals.** The fact that you created the directory means you know evals matter. The gap between knowing and doing is the most dangerous place in AI product development — you're living there right now. A system with no evals is a system that degrades silently.

**8. The git history itself is a product artifact.** The Spanish `.txt` files, the prompts, the agent simulation files — these tell the story of how an AI platform gets built. Curating this into a public "build in public" narrative would generate significant developer community interest and inbound marketing at zero cost.

---

Would you like a **second-pass analysis focused exclusively on architecture, AI-agent design, monetization strategy, security, or roadmap execution?**