 Repository_Evidence_Pack.md
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
    1 +# Repository Evidence Pack — C2Pro
    2
    3 +**Mode:** Read-only repository verification (Senior Staff auditor).
    4 +**Date:** 2026-06-14 · **Branch:** `main` · **History:** 740 commits, first commit `13deb101` 2025-12-29.
    5 +**Method:** Every claim below is traced to a file/line/commit/config. Committee consensus documents were used on
      +ly to prioritize investigation and were treated as hypotheses to falsify, never as evidence.
    6 +
    7 +> **Supersedes** the earlier `Repository_Evidence_Pack.md` draft in this repo. That draft asserted "Coherence En
      +gine (v2 active, v1 legacy)". **The code shows the opposite** (`scoring.py:67` is the *canonical v1* path; v2 ru
      +ns as a shadow/additive projection). That error is corrected here. The earlier draft also cited the secret only
      +in history; in fact it is live in `HEAD`.
    8 +
    9 +---
   10 +
   11  ## Executive Summary
   12
    
   13 +C2Pro is a real, continuously-developed (≈5.5 month, 740-commit, solo+AI-agent) FastAPI/Next.js contract-intelli
      +gence monorepo with a genuinely engineered coherence engine, a multi-tenant RLS layer, a model router, a prompt
      +registry, and a synthetic golden-corpus eval harness. The architecture is sound but carries verified debt:
   14
    
   15 +- **CRITICAL / P0:** A live Supabase **`service_role`** JWT, anon key, JWT secret, and DB URL are committed in `
      +.env.staging` and present in **`HEAD` right now** (not merely history), despite being matched by `.gitignore`.
   16 +- The **active scoring path is Coherence v1** (`scoring.py`); **v2 is a shadow/additive projection** adapted fro
      +m v1, not a native scorer. Any agent "working on v2" must understand it does not yet compute scores.
   17 +- **Tri-dimensional scoring is effectively bi-dimensional at the scorer contract level**: `scoring.py` still har
      +dcodes `missing_dimensions=["schedule","budget"]` in its null paths, even though a schedule-routing fix (`_DB_DO
      +C_TYPE_TO_REGISTRY`) was landed in `coherence/graph/graph.py`. The two project backlogs **disagree** on whether
      +`TASK-BCK-064` is fixed.
   18 +- **CI gates are partially decorative:** `--cov-fail-under=0` on the unit job and `continue-on-error: true` on i
      +ntegration tests and two other workflows.
   19 +- **Repo hygiene is materially poor:** 1,418 tracked `.mypy_cache` files, a 1.3 MB client PDF, 10 root `.txt` tr
      +anscripts, dual lockfiles, and tracked temp dirs.
   20
    
   21 +**Several near-unanimous committee claims are REJECTED or narrowed by code** (see Phase 8): "no eval framework",
      + "no prompt registry / versioning", "v2 active", "repo re-initialized in 1 month", and "consolidate toward `modu
      +les/coherence`".
   22
   23 +**Verdict: READY WITH RESTRICTIONS** — a verified P0-remediation track may begin; product/runtime claims require
      + a runtime trace (out of scope for static read-only audit).
   24 +
   25  ---
   26
   27 +## Verified Facts
   28 +
   29 +| # | Fact | Evidence |
   30 +|---|------|----------|
   31 +| F1 | Live Supabase **`service_role`** key, `anon` key, `JWT_SECRET_KEY`, and `DATABASE_URL` are committed and
      +present in `HEAD`. | `git ls-files --error-unmatch .env.staging` → tracked. JWT payload (public part) decodes to
      + `role: service_role`, `iss: supabase`, project ref `tcxedmnvebazcsaridge`, `exp 2082606765` (year ~2036). Anon
      +key: `role: anon`, same ref. |
   32 +| F2 | `.env.staging` is matched by `.gitignore` (`.env.*`, line 25) yet committed anyway. | `.gitignore:24-26`;
      + file added in commit `0794753c` and never removed. |
   33 +| F3 | Canonical/active coherence scorer is **v1**. | `apps/api/src/coherence/scoring.py:67` "canonical Coherenc
      +e v1 scoring path"; `compute_score()` at `:593`. Wired in `main.py:334-340` via `src.coherence.router`. |
   34 +| F4 | **v2 is shadow/additive**, projected from v1, not a native scorer. | `coherence/router.py:728-745`: "adap
      +t from the v1 summary using the pure v1→v2 adapter … Until the v2 orchestrator persists native rows (Phase 3)";
      +`adapt_v1_dashboard`, `ShadowRunner`, `coherence_v2_shadow_mode` default `True`. |
   35 +| F5 | `src/coherence/` is canonical (122 import refs, full adapters/router/graph); `modules/coherence/` is a th
      +in legacy (9 refs, only `domain/`+`application/`, no router). | `grep` import counts; `ls modules/coherence/`. |
   36 +| F6 | Schedule-routing fix exists in code. | `coherence/graph/graph.py:62-64` `_DB_DOC_TYPE_TO_REGISTRY={"sched
      +ule":"schedule_gantt","budget":"budget_boq"}`, applied at `:226`. |
   37 +| F7 | …but scorer still defaults to schedule+budget "missing". | `scoring.py:236,306,535` hardcode `missing_dim
      +ensions=["schedule","budget"]`. |
   38 +| F8 | Backlog drift on the schedule gap. | Root `C2PRO_MASTER_BACKLOG.md:52` lists `TASK-BCK-064` as **P0 open*
      +*; `backlogs/BCK_BACKEND.md:32` marks it **`[x]` Fixed 2026-06-04**. |
   39 +| F9 | HITL gate can be skipped by env flag, with **no production guard** in the code path. | `analysis/adapters
      +/graph/workflow.py:72-75`: `skip_hitl = AI_MOCK==1 or SKIP_HITL==1`; no `ENVIRONMENT`/`is_production` check in t
      +hat function. `C2PRO_AI_MOCK` also short-circuits the LLM client (`anthropic_client.py:51,86`). |
   40 +| F10 | Checkpointer falls back to in-memory `MemorySaver`. | `analysis/adapters/graph/workflow.py:299-345`, gat
      +ed on "SQLite or langgraph-checkpoint-postgres not installed". Logs and continues. |
   41 +| F11 | Celery worker **and** API run in the **same container**. | `apps/api/start.sh` header comment + `_start_
      +celery &` background loop, then `exec uvicorn src.main:app`. |
   42 +| F12 | CI: unit coverage gate is effectively disabled. | `.github/workflows/tests.yml:135` `--cov-fail-under=0`
      +. A guard test *locks this in*: `tests/unit/test_backend_ci_guards.py:19` asserts `"--cov-fail-under=0" in conte
      +nts`. |
   43 +| F13 | CI: `continue-on-error: true` in 3 workflows. | `tests.yml:208` (integration tests), `real-document-oper
      +ability.yml:115`, `ai-agent-swarm.yml:160`. |
   44 +| F14 | Multi-tenant RLS is real and actively hardened (fail-closed). | 10+ Alembic migrations incl. `20260205_0
      +001_enable_rls_policies.py`, `20260318_0002_fix_rls_policies_fail_closed.py`, `..._harden_*_rls.py`. |
   45 +| F15 | Coherence semantic cache **is** tenant-isolated. | `coherence/cache_keys.py:105` key = `coherence:{versi
      +on}:{namespace}:{tenant_id}:{project_id}`; `tenant_prefix()` for per-tenant invalidation. |
   46 +| F16 | LLM/flash + content-hash caches are **content-addressable with no tenant in key**. | `core/ai/prompt_cac
      +he.py:77-108` `build_flash_cache_key` keys on model/system/messages/tools/temp only; `coherence/adapters/ai/cont
      +ent_hash_cache.py:36` namespace+SHA-256, no tenant. |
   47 +| F17 | Auth is **hybrid by design**: Clerk RS256 first, local HS256 JWT fallback. | `core/auth/dependencies.py:
      +47-87` `_try_clerk_jwt` → `verify_clerk_token`, then `_try_local_jwt` (HS256). `TenantIsolationMiddleware` valid
      +ates both. Custom `/api/v1/auth/{register,login}` exist (`main.py:212-213,295`). Clerk is **not** a standalone `
      +add_middleware`. |
   48 +| F18 | Model router exists with budget- and size-based fallback rules (intra-Anthropic). | `core/ai/model_routi
      +ng.yaml`: `claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-7`, `fallback_rules:` (budget/size, "fallback
      +a Haiku si >100K tokens"). No cross-provider failover. |
   49 +| F19 | Prompt registry + versioning + A/B framework exist. | `core/ai/prompts/registry.py`, versioned `core/ai/
      +prompts/v1/coherence_analysis.py`, `core/ai/ab_experiment.py`, `sync_prompts.py`, `langsmith_client.py`. |
   50 +| F20 | Golden-corpus eval harness is real: 15 synthetic bundles with expected scores/alerts. | `evals/run_evals
      +.py`; `evals/golden_corpus/bundles/BUNDLE-001..015.json`; bundle keys incl. `dimensions, expected_issues, expect
      +ed_score_range, expected_alerts, score_check`. |
   51 +| F21 | Golden-corpus CI is path-scoped, not a global gate. | `golden-corpus-evals.yml:3-14` triggers only on `e
      +vals/**` changes (push/PR/dispatch); does not run on engine/scoring code changes. |
   52 +| F22 | License is incoherent; no `LICENSE` file. | No `LICENSE*` on disk; `package.json:13` `"license":"ISC"`;
      +`README.md:7` Proprietary badge linking to nonexistent `LICENSE`. |
   53 +| F23 | Repo hygiene debt (tracked junk). | `git ls-files`: 1,418 `.mypy_cache/` files, `HVPNL_First Contract*.p
      +df` (1.3 MB), 10 root `*.txt` transcripts, `temp_conflicting_frontend_files/` (9 files), both `package-lock.json
      +` **and** `pnpm-lock.yaml`. |
   54 +| F24 | Repo age claim corrected. | First commit `13deb101` 2025-12-29; 740 commits continuous. The "re-init / 1
      + month / 225K LOC" narrative is false. |
   55 +| F25 | Per-tenant AI cost tracking exists. | `core/ai/usage_analytics.py`, `usage_logger.py`. |
   56 +
   57 +---
   58 +
   59 +## Rejected Assumptions
   60 +
   61 +| Assumption (from committee/prior pack) | Why rejected | Evidence |
   62 +|---|---|---|
   63 +| "Coherence **v2 is active**, v1 legacy" (prior pack) | Reversed. v1 is canonical; v2 is shadow projection. | F
      +3, F4 |
   64 +| "Consolidate toward `modules/coherence`" (GLM) | Backwards; `src/coherence/` is canonical. | F5 |
   65 +| "No AI eval framework / `evals/` empty" | Harness + 15-bundle synthetic corpus with score checks exist. | F20
      +|
   66 +| "No prompt registry / versioning" | Registry, `prompts/v1/`, and A/B framework exist in code. | F19 |
   67 +| "Single-model, no fallback" | Router with budget/size fallback rules. (Cross-*provider* failover genuinely abs
      +ent.) | F18 |
   68 +| "Repo re-initialized May 2026 / 225K LOC in 1 month" | Continuous history from 2025-12-29. | F24 |
   69 +| Secret is "only in history (commit `cc9d080`)" | It is live in `HEAD`; the adding commit is `0794753c`, not `c
      +c9d080`. | F1, F2 |
   70 +
   71 +---
   72 +
   73 +## Open Questions (require runtime or external access — INSUFFICIENT EVIDENCE statically)
   74 +
   75 +1. **Is the GitHub repo public?** Remote is `github.com`; visibility cannot be read from a local clone. One-bit
      +external check (sets secret-exposure blast radius + EU-patent clock).
   76 +2. **Are the `.env.staging` credentials still live / has the Supabase project been rotated?** Key is non-expirin
      +g until 2036; rotation status is server-side.
   77 +3. **Does schedule evidence actually move the score end-to-end?** Code has the routing fix (F6) but the scorer s
      +till defaults dimensions missing (F7); only a real contract+schedule+budget E2E trace resolves it.
   78 +4. **Does `MemorySaver` fallback trigger under the production deploy** (postgres-checkpoint installed?) or only
      +dev/SQLite? (F10 is mechanism-only.)
   79 +5. **Is the content-hash LLM cache a privacy issue or benign dedup?** Keyed on full input content (F16); identic
      +al input ⇒ shared cached output. Needs a data-classification decision, not more code.
   80 +6. **Are `C2PRO_SKIP_HITL`/`C2PRO_AI_MOCK` set in any prod/staging environment?** Code has no guard (F9); risk i
      +s purely operational/config.
   81 +7. **Does the golden corpus measure coherence *accuracy* vs ground truth, or structural pass/fail?** Bundles car
      +ry `expected_score_range`/`expected_alerts` (F20), but precision/recall vs real documents is unproven.
   82 +
   83 +---
   84 +
   85 +## Risk Register
   86 +
   87 +| ID | Risk | Severity | Status | Evidence |
   88 +|----|------|----------|--------|----------|
   89 +| R1 | Live `service_role` god-key committed in `HEAD` | **Critical** | VERIFIED | F1, F2 |
   90 +| R2 | CI green does not mean tests passed (cov=0, continue-on-error) | High | VERIFIED | F12, F13 |
   91 +| R3 | HITL bypass flags with no prod guard | High | VERIFIED (code) / config-dependent | F9 |
   92 +| R4 | "Tri-dimensional" headline not true at scorer contract | High | PARTIAL | F7, F8 |
   93 +| R5 | LLM cache not tenant-keyed (possible cross-tenant content share) | Med-High | VERIFIED (no tenant key); i
      +mpact open | F16, Q5 |
   94 +| R6 | Celery+API single container (no failure isolation) | Med | VERIFIED | F11 |
   95 +| R7 | MemorySaver in-memory checkpointer (audit/durability loss if hit in prod) | Med | VERIFIED (mechanism); p
      +rod-trigger open | F10, Q4 |
   96 +| R8 | License incoherence / missing LICENSE | Med | VERIFIED | F22 |
   97 +| R9 | Repo bloat & client-confidential PDF in history | Med | VERIFIED | F23 |
   98 +| R10 | Backlog source-of-truth drift (064 open vs fixed) | Low-Med | VERIFIED | F8 |
   99 +
  100 +---
  101 +
  102  ## Architecture Truth Map
  103

  104 +### What Exists (verified, wired into runtime)
  105 +- **API**: FastAPI app `apps/api/src/main.py`; middleware stack = CORS + APIContract + RateLimit + RequestLoggin
      +g + **TenantIsolation** (`main.py:241-247`).
  106 +- **Active analysis pipeline**: `analysis/adapters/graph/workflow.py` (N1–N17 LangGraph), with HITL conditional
      +edge and MemorySaver fallback.
  107 +- **Coherence engine v1** (`src/coherence/`): `scoring.py` (897 LOC, decay/floor/override), rules engine, schedu
      +le/budget/legal/technical/scope/quality categories, router wired in `main.py`.
  108 +- **AI infra** (`core/ai/`): model router + YAML, prompt registry + `prompts/v1/`, A/B experiments, prompt/flash
      + cache, usage analytics, LangSmith client.
  109 +- **Security**: multi-tenant RLS (10+ migrations, fail-closed), PII anonymizer (N2), hybrid Clerk+local-JWT auth
      +.
  110 +- **Eval**: `evals/` golden corpus (15 bundles) + `run_evals.py`.
  111
   21 -### What Exists But Is Not Used / Legacy
   22 -- **Legacy Coherence Engine:** The module at `apps/api/src/modules/coherence/` exists alongside the active `apps
      -/api/src/coherence/`.
  112 +### What Exists But Is Not Used (as runtime app code)
  113 +- **`modules/coherence/`** — thin legacy (domain/application only, 9 refs, no router). F5.
  114 +- **`gamification/`** — present (`abuse_monitor_service.py`) but **no router wired**; 0 external importers.
  115 +- **`golden/`** (`apps/api/src/golden/`) — agent-trajectory eval harness; not in `main.py`, but **invoked by `ev
      +aluation-regression.yml`** (so tooling-live, not app-live). Correction to "0 refs = dead".
  116 +- **Coherence v2** — code exists (`services/v2/`, `v1_to_v2.py`, `v2_to_dashboard.py`) but runs as **shadow/proj
      +ection**, default-on shadow mode; no native scoring. F4.
  117
   
  118 +### What Is Planned (declared, not complete)
  119 +- v2 "orchestrator persists native rows (Phase 3)" — explicitly future (`router.py:731`).
  120 +- Full schedule contribution to score (F7/F8 contradiction).
  121
  122 +### What Is Assumed (claimed but unproven statically)
  123 +- That the headline "tri-dimensional" score reflects all three dimensions at runtime (Q3).
  124 +- That mock/skip flags are absent in prod environments (Q6).
  125 +
  126 +### What Is Missing
  127 +- `LICENSE` file; `SECURITY.md`. Cross-provider LLM failover. A blocking accuracy gate wiring evals to engine/sc
      +oring changes (F21).
  128 +
  129  ---
  130
  131  ## Security Findings
  132
   
  133 +**VERIFIED**
  134 +- Live `service_role` + `anon` + `JWT_SECRET_KEY` + `DATABASE_URL` in `HEAD` `.env.staging` (F1–F2). **P0.** Do
      +not reuse this Supabase project until rotated and history-purged.
  135 +- RLS present and fail-closed-hardened (F14).
  136 +- Coherence cache tenant-isolated (F15).
  137 +- HITL bypass flags unguarded in code (F9).
  138
   
  139 +**REQUIRES MANUAL REVIEW**
  140 +- Content-addressable LLM caches with no tenant key (F16) — classify as acceptable dedup vs leak (Q5).
  141 +- Whether repo is public (Q1); whether creds rotated (Q2).
  142
  143 +**NOT VERIFIED (static-only limits)**
  144 +- Runtime tenant-isolation enforcement under load; live 500s on alerts/stakeholders (`TASK-BCK-051`) — requires
      +running system.
  145 +
  146  ---
  147
  148  ## Coherence Engine Findings
  149
   
  150 +- **Executed engine = v1**, `apps/api/src/coherence/scoring.py` (F3). Deterministic-first, severity-weighted dec
      +ay, rule overrides, honest-null on insufficient evidence.
  151 +- **v2 = shadow/additive projection** from v1 via `adapt_v1_dashboard`, gated by `coherence_v2_enabled` / `coher
      +ence_v2_shadow_mode` (default shadow). It does **not** compute native scores yet (F4).
  152 +- **Authoritative path** = `src/coherence/` (F5). `modules/coherence/` is legacy; do not consolidate "toward" it
      +.
  153 +- **Dimensions**: category map includes `schedule→TIME`, `financial→BUDGET`, etc. (`scoring.py:576-587`); schedu
      +le routing fix landed (F6) but scorer null-paths still flag schedule+budget missing (F7). Tri-dimensional is **P
      +ARTIAL** pending runtime trace.
  154
  155  ---
  156
  157  ## CI/CD Findings
  158
   
  159 +**CI Trust Score: 45 / 100.**
  160
   
  161 +Rationale: workflows are numerous and real (16 workflows), lint/typecheck and several jobs block, RLS/security e
      +2e exists with `--cov-fail-under=60`. **But** trust is capped by: unit coverage gate set to `0` and *locked by a
      + guard test* (F12); `continue-on-error: true` on integration tests and two further workflows (F13); the headline
      + eval workflow is path-scoped to `evals/**` so it never gates engine code (F21); real-document operability is `w
      +orkflow_dispatch` + `C2PRO_AI_MOCK`. A green check therefore does **not** guarantee integration tests or coverag
      +e passed.
  162
  163  ---
  164
  165  ## Validation of Consensus Claims
  166
  167  | Claim | Result | Evidence |
   
  168 +|-------|--------|----------|
  169 +| `.env.staging` real `service_role`/JWT/DB secret committed | **VERIFIED** (stronger: live in `HEAD`, not just
      +history; commit `0794753c`, not `cc9d080`) | F1, F2 |
  170 +| Schedule dimension does not feed scoring (`TASK-BCK-064`) | **PARTIALLY VERIFIED** (routing fix exists; scorer
      + defaults still missing; backlogs disagree; runtime unconfirmed) | F6, F7, F8 |
  171 +| Coherence v2 cutover incomplete | **VERIFIED** (v2 is shadow projection, "Phase 3" pending) | F4 |
  172 +| Dual codebases / module duplication (two `core/`, two `ai/`, `coherence` vs `modules/coherence`) | **VERIFIED*
      +* | F5, CLAUDE.md gotchas |
  173 +| LLM cache lacks tenant isolation → cross-tenant risk | **PARTIALLY VERIFIED** — *coherence* cache isolated (F1
      +5); *LLM/flash/content-hash* caches not tenant-keyed (F16) | F15, F16 |
  174 +| HITL can be bypassed by env flag | **VERIFIED** (no prod guard in code) | F9 |
  175 +| MemorySaver checkpointer fallback | **VERIFIED** (mechanism); prod impact INCONCLUSIVE | F10 |
  176 +| Deployment: Celery+API same container | **VERIFIED** | F11 |
  177 +| Auth architecture ambiguous (Clerk vs Supabase/JWT) | **VERIFIED as hybrid-by-design** (Clerk RS256 → local HS
      +256 fallback) | F17 |
  178 +| CI gates weak (`continue-on-error`, cov=0) | **VERIFIED** | F12, F13 |
  179 +| No eval framework / corpus | **REJECTED** | F20 |
  180 +| No prompt registry / versioning | **REJECTED** (registry + v1 + A/B exist) | F19 |
  181 +| Repo re-initialized in 1 month | **REJECTED** | F24 |
  182 +| License incoherent | **VERIFIED** | F22 |
  183 +| Is the repo public? | **INCONCLUSIVE — INSUFFICIENT EVIDENCE** (needs GitHub API) | Q1 |
  184
  185  ---
  186
 ...
  188
  189  ### READY WITH RESTRICTIONS
  190
   77 -**Justification:** The project has strong foundational architecture, a robust evaluation framework, and multi-te
      -nant persistence logic. However, the presence of active secrets in the commit history and a broken CI pipeline (
      -backend tests allowed to fail) means that feature execution is unsafe.
  191 +**Justification.** The static facts are now high-confidence. A **verified remediation track rests entirely on Ti
      +er-1 evidence and can begin immediately**, scoped to:
  192
   
  193 +1. **Rotate** the Supabase project `tcxedmnvebazcsaridge` keys + `JWT_SECRET_KEY`, then **purge `.env.staging`**
      + from history (F1–F2). *Highest priority — until done, treat infra as compromised.*
  194 +2. Remove `--cov-fail-under=0` + its guard test; remove `continue-on-error` on real gates (F12, F13).
  195 +3. Reconcile the `TASK-BCK-064` backlog drift and decide schedule-scoring truth via an E2E trace (F7, F8).
  196 +4. Add a prod fail-closed guard for `C2PRO_SKIP_HITL`/`C2PRO_AI_MOCK` (F9).
  197 +5. Repo de-junk (mypy cache, PDF, transcripts, dual lockfile) (F23); add `LICENSE` + resolve ISC-vs-Proprietary
      +(F22).
  198 +6. Classify the content-hash cache (F16); split Celery from API (F11).
  199
  

●
        1 -# Repository Evidence Pack
        1 +# Repository Evidence Pack — C2Pro
        2
        3 +**Mode:** Read-only repository verification (Senior Staff auditor).
        4 +**Date:** 2026-06-14 · **Branch:** `main` · **History:** 740 commits, first commit `13deb101` 2025-12-
          +29.
        5 +**Method:** Every claim below is traced to a file/line/commit/config. Committee consensus documents we
          +re used only to prioritize investigation and were treated as hypotheses to falsify, never as evidence.
        6 +
        7 +> **Supersedes** the earlier `Repository_Evidence_Pack.md` draft in this repo. That draft asserted "Co
          +herence Engine (v2 active, v1 legacy)". **The code shows the opposite** (`scoring.py:67` is the *canon
          +ical v1* path; v2 runs as a shadow/additive projection). That error is corrected here. The earlier dra
          +ft also cited the secret only in history; in fact it is live in `HEAD`.
        8 +
        9 +---
       10 +
       11  ## Executive Summary
       12
        5 -This independent investigation has audited the C2Pro repository to establish a factual baseline and ve
          -rify claims made by previous AI committee reports. The audit prioritized code, git history, and config
          -uration files over documentation and previous consensus.
       13 +C2Pro is a real, continuously-developed (≈5.5 month, 740-commit, solo+AI-agent) FastAPI/Next.js contra
          +ct-intelligence monorepo with a genuinely engineered coherence engine, a multi-tenant RLS layer, a mod
          +el router, a prompt registry, and a synthetic golden-corpus eval harness. The architecture is sound bu
          +t carries verified debt:
       14
        7 -We have verified that C2Pro possesses a genuine, sophisticated Coherence Engine (v2 active, v1 legacy)
          - and a working evaluation framework (100-case Golden Corpus). However, significant risks were uncovere
          -d, including a verified leak of a `service_role` key in `.env.staging`, weak CI gates that allow tests
          - to fail silently, and potential cross-tenant cache sharing.
       15 +- **CRITICAL / P0:** A live Supabase **`service_role`** JWT, anon key, JWT secret, and DB URL are comm
          +itted in `.env.staging` and present in **`HEAD` right now** (not merely history), despite being matche
          +d by `.gitignore`.
       16 +- The **active scoring path is Coherence v1** (`scoring.py`); **v2 is a shadow/additive projection** a
          +dapted from v1, not a native scorer. Any agent "working on v2" must understand it does not yet compute
          + scores.
       17 +- **Tri-dimensional scoring is effectively bi-dimensional at the scorer contract level**: `scoring.py`
          + still hardcodes `missing_dimensions=["schedule","budget"]` in its null paths, even though a schedule-
          +routing fix (`_DB_DOC_TYPE_TO_REGISTRY`) was landed in `coherence/graph/graph.py`. The two project bac
          +klogs **disagree** on whether `TASK-BCK-064` is fixed.
       18 +- **CI gates are partially decorative:** `--cov-fail-under=0` on the unit job and `continue-on-error:
          +true` on integration tests and two other workflows.
       19 +- **Repo hygiene is materially poor:** 1,418 tracked `.mypy_cache` files, a 1.3 MB client PDF, 10 root
          + `.txt` transcripts, dual lockfiles, and tracked temp dirs.
       20
        9 -Execution can safely proceed for stabilization and remediation tasks, but product expansion must wait
          -until the security and data-isolation issues are resolved.
       21 +**Several near-unanimous committee claims are REJECTED or narrowed by code** (see Phase 8): "no eval f
          +ramework", "no prompt registry / versioning", "v2 active", "repo re-initialized in 1 month", and "cons
          +olidate toward `modules/coherence`".
       22
       23 +**Verdict: READY WITH RESTRICTIONS** — a verified P0-remediation track may begin; product/runtime clai
          +ms require a runtime trace (out of scope for static read-only audit).
       24 +
       25  ---
       26
       27 +## Verified Facts
       28 +
       29 +| # | Fact | Evidence |
       30 +|---|------|----------|
       31 +| F1 | Live Supabase **`service_role`** key, `anon` key, `JWT_SECRET_KEY`, and `DATABASE_URL` are comm
          +itted and present in `HEAD`. | `git ls-files --error-unmatch .env.staging` → tracked. JWT payload (pub
          +lic part) decodes to `role: service_role`, `iss: supabase`, project ref `tcxedmnvebazcsaridge`, `exp 2
          +082606765` (year ~2036). Anon key: `role: anon`, same ref. |
       32 +| F2 | `.env.staging` is matched by `.gitignore` (`.env.*`, line 25) yet committed anyway. | `.gitigno
          +re:24-26`; file added in commit `0794753c` and never removed. |
       33 +| F3 | Canonical/active coherence scorer is **v1**. | `apps/api/src/coherence/scoring.py:67` "canonica
          +l Coherence v1 scoring path"; `compute_score()` at `:593`. Wired in `main.py:334-340` via `src.coheren
          +ce.router`. |
       34 +| F4 | **v2 is shadow/additive**, projected from v1, not a native scorer. | `coherence/router.py:728-7
          +45`: "adapt from the v1 summary using the pure v1→v2 adapter … Until the v2 orchestrator persists nati
          +ve rows (Phase 3)"; `adapt_v1_dashboard`, `ShadowRunner`, `coherence_v2_shadow_mode` default `True`. |
       35 +| F5 | `src/coherence/` is canonical (122 import refs, full adapters/router/graph); `modules/coherence
          +/` is a thin legacy (9 refs, only `domain/`+`application/`, no router). | `grep` import counts; `ls mo
          +dules/coherence/`. |
       36 +| F6 | Schedule-routing fix exists in code. | `coherence/graph/graph.py:62-64` `_DB_DOC_TYPE_TO_REGIST
          +RY={"schedule":"schedule_gantt","budget":"budget_boq"}`, applied at `:226`. |
       37 +| F7 | …but scorer still defaults to schedule+budget "missing". | `scoring.py:236,306,535` hardcode `m
          +issing_dimensions=["schedule","budget"]`. |
       38 +| F8 | Backlog drift on the schedule gap. | Root `C2PRO_MASTER_BACKLOG.md:52` lists `TASK-BCK-064` as
          +**P0 open**; `backlogs/BCK_BACKEND.md:32` marks it **`[x]` Fixed 2026-06-04**. |
       39 +| F9 | HITL gate can be skipped by env flag, with **no production guard** in the code path. | `analysi
          +s/adapters/graph/workflow.py:72-75`: `skip_hitl = AI_MOCK==1 or SKIP_HITL==1`; no `ENVIRONMENT`/`is_pr
          +oduction` check in that function. `C2PRO_AI_MOCK` also short-circuits the LLM client (`anthropic_clien
          +t.py:51,86`). |
       40 +| F10 | Checkpointer falls back to in-memory `MemorySaver`. | `analysis/adapters/graph/workflow.py:299
          +-345`, gated on "SQLite or langgraph-checkpoint-postgres not installed". Logs and continues. |
       41 +| F11 | Celery worker **and** API run in the **same container**. | `apps/api/start.sh` header comment
          ++ `_start_celery &` background loop, then `exec uvicorn src.main:app`. |
       42 +| F12 | CI: unit coverage gate is effectively disabled. | `.github/workflows/tests.yml:135` `--cov-fai
          +l-under=0`. A guard test *locks this in*: `tests/unit/test_backend_ci_guards.py:19` asserts `"--cov-fa
          +il-under=0" in contents`. |
       43 +| F13 | CI: `continue-on-error: true` in 3 workflows. | `tests.yml:208` (integration tests), `real-doc
          +ument-operability.yml:115`, `ai-agent-swarm.yml:160`. |
       44 +| F14 | Multi-tenant RLS is real and actively hardened (fail-closed). | 10+ Alembic migrations incl. `
          +20260205_0001_enable_rls_policies.py`, `20260318_0002_fix_rls_policies_fail_closed.py`, `..._harden_*_
          +rls.py`. |
       45 +| F15 | Coherence semantic cache **is** tenant-isolated. | `coherence/cache_keys.py:105` key = `cohere
          +nce:{version}:{namespace}:{tenant_id}:{project_id}`; `tenant_prefix()` for per-tenant invalidation. |
       46 +| F16 | LLM/flash + content-hash caches are **content-addressable with no tenant in key**. | `core/ai/
          +prompt_cache.py:77-108` `build_flash_cache_key` keys on model/system/messages/tools/temp only; `cohere
          +nce/adapters/ai/content_hash_cache.py:36` namespace+SHA-256, no tenant. |
       47 +| F17 | Auth is **hybrid by design**: Clerk RS256 first, local HS256 JWT fallback. | `core/auth/depend
          +encies.py:47-87` `_try_clerk_jwt` → `verify_clerk_token`, then `_try_local_jwt` (HS256). `TenantIsolat
          +ionMiddleware` validates both. Custom `/api/v1/auth/{register,login}` exist (`main.py:212-213,295`). C
          +lerk is **not** a standalone `add_middleware`. |
       48 +| F18 | Model router exists with budget- and size-based fallback rules (intra-Anthropic). | `core/ai/m
          +odel_routing.yaml`: `claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-7`, `fallback_rules:` (bud
          +get/size, "fallback a Haiku si >100K tokens"). No cross-provider failover. |
       49 +| F19 | Prompt registry + versioning + A/B framework exist. | `core/ai/prompts/registry.py`, versioned
          + `core/ai/prompts/v1/coherence_analysis.py`, `core/ai/ab_experiment.py`, `sync_prompts.py`, `langsmith
          +_client.py`. |
       50 +| F20 | Golden-corpus eval harness is real: 15 synthetic bundles with expected scores/alerts. | `evals
          +/run_evals.py`; `evals/golden_corpus/bundles/BUNDLE-001..015.json`; bundle keys incl. `dimensions, exp
          +ected_issues, expected_score_range, expected_alerts, score_check`. |
       51 +| F21 | Golden-corpus CI is path-scoped, not a global gate. | `golden-corpus-evals.yml:3-14` triggers
          +only on `evals/**` changes (push/PR/dispatch); does not run on engine/scoring code changes. |
       52 +| F22 | License is incoherent; no `LICENSE` file. | No `LICENSE*` on disk; `package.json:13` `"license
          +":"ISC"`; `README.md:7` Proprietary badge linking to nonexistent `LICENSE`. |
       53 +| F23 | Repo hygiene debt (tracked junk). | `git ls-files`: 1,418 `.mypy_cache/` files, `HVPNL_First C
          +ontract*.pdf` (1.3 MB), 10 root `*.txt` transcripts, `temp_conflicting_frontend_files/` (9 files), bot
          +h `package-lock.json` **and** `pnpm-lock.yaml`. |
       54 +| F24 | Repo age claim corrected. | First commit `13deb101` 2025-12-29; 740 commits continuous. The "r
          +e-init / 1 month / 225K LOC" narrative is false. |
       55 +| F25 | Per-tenant AI cost tracking exists. | `core/ai/usage_analytics.py`, `usage_logger.py`. |
       56 +
       57 +---
       58 +
       59 +## Rejected Assumptions
       60 +
       61 +| Assumption (from committee/prior pack) | Why rejected | Evidence |
       62 +|---|---|---|
       63 +| "Coherence **v2 is active**, v1 legacy" (prior pack) | Reversed. v1 is canonical; v2 is shadow proje
          +ction. | F3, F4 |
       64 +| "Consolidate toward `modules/coherence`" (GLM) | Backwards; `src/coherence/` is canonical. | F5 |
       65 +| "No AI eval framework / `evals/` empty" | Harness + 15-bundle synthetic corpus with score checks exi
          +st. | F20 |
       66 +| "No prompt registry / versioning" | Registry, `prompts/v1/`, and A/B framework exist in code. | F19
          +|
       67 +| "Single-model, no fallback" | Router with budget/size fallback rules. (Cross-*provider* failover gen
          +uinely absent.) | F18 |
       68 +| "Repo re-initialized May 2026 / 225K LOC in 1 month" | Continuous history from 2025-12-29. | F24 |
       69 +| Secret is "only in history (commit `cc9d080`)" | It is live in `HEAD`; the adding commit is `0794753
          +c`, not `cc9d080`. | F1, F2 |
       70 +
       71 +---
       72 +
       73 +## Open Questions (require runtime or external access — INSUFFICIENT EVIDENCE statically)
       74 +
       75 +1. **Is the GitHub repo public?** Remote is `github.com`; visibility cannot be read from a local clone
          +. One-bit external check (sets secret-exposure blast radius + EU-patent clock).
       76 +2. **Are the `.env.staging` credentials still live / has the Supabase project been rotated?** Key is n
          +on-expiring until 2036; rotation status is server-side.
       77 +3. **Does schedule evidence actually move the score end-to-end?** Code has the routing fix (F6) but th
          +e scorer still defaults dimensions missing (F7); only a real contract+schedule+budget E2E trace resolv
          +es it.
       78 +4. **Does `MemorySaver` fallback trigger under the production deploy** (postgres-checkpoint installed?
          +) or only dev/SQLite? (F10 is mechanism-only.)
       79 +5. **Is the content-hash LLM cache a privacy issue or benign dedup?** Keyed on full input content (F16
          +); identical input ⇒ shared cached output. Needs a data-classification decision, not more code.
       80 +6. **Are `C2PRO_SKIP_HITL`/`C2PRO_AI_MOCK` set in any prod/staging environment?** Code has no guard (F
          +9); risk is purely operational/config.
       81 +7. **Does the golden corpus measure coherence *accuracy* vs ground truth, or structural pass/fail?** B
          +undles carry `expected_score_range`/`expected_alerts` (F20), but precision/recall vs real documents is
          + unproven.
       82 +
       83 +---
       84 +
       85 +## Risk Register
       86 +
       87 +| ID | Risk | Severity | Status | Evidence |
       88 +|----|------|----------|--------|----------|
       89 +| R1 | Live `service_role` god-key committed in `HEAD` | **Critical** | VERIFIED | F1, F2 |
       90 +| R2 | CI green does not mean tests passed (cov=0, continue-on-error) | High | VERIFIED | F12, F13 |
       91 +| R3 | HITL bypass flags with no prod guard | High | VERIFIED (code) / config-dependent | F9 |
       92 +| R4 | "Tri-dimensional" headline not true at scorer contract | High | PARTIAL | F7, F8 |
       93 +| R5 | LLM cache not tenant-keyed (possible cross-tenant content share) | Med-High | VERIFIED (no tena
          +nt key); impact open | F16, Q5 |
       94 +| R6 | Celery+API single container (no failure isolation) | Med | VERIFIED | F11 |
       95 +| R7 | MemorySaver in-memory checkpointer (audit/durability loss if hit in prod) | Med | VERIFIED (mec
          +hanism); prod-trigger open | F10, Q4 |
       96 +| R8 | License incoherence / missing LICENSE | Med | VERIFIED | F22 |
       97 +| R9 | Repo bloat & client-confidential PDF in history | Med | VERIFIED | F23 |
       98 +| R10 | Backlog source-of-truth drift (064 open vs fixed) | Low-Med | VERIFIED | F8 |
       99 +
      100 +---
      101 +
      102  ## Architecture Truth Map
      103
       15 -### What Exists
       16 -- **Coherence Engine:** Implemented with bounded decay, deterministic-first logic, and honest-null sco
          -ring (`apps/api/src/coherence/scoring.py`).
       17 -- **AI Gate:** A 5-step gate enforcing cache -> rollout -> budget -> LLM -> persist (`coherence_llm_ga
          -te.py`).
       18 -- **Evaluation Framework:** A 15-bundle Golden Corpus deterministic runner (`evals/run_evals.py`).
       19 -- **Multi-tenant Data Isolation:** Enforced at the persistence layer in `pgvector_embedding_repository
          -.py` where all operations verify project ownership by `tenant_id`.
      104 +### What Exists (verified, wired into runtime)
      105 +- **API**: FastAPI app `apps/api/src/main.py`; middleware stack = CORS + APIContract + RateLimit + Req
          +uestLogging + **TenantIsolation** (`main.py:241-247`).
      106 +- **Active analysis pipeline**: `analysis/adapters/graph/workflow.py` (N1–N17 LangGraph), with HITL co
          +nditional edge and MemorySaver fallback.
      107 +- **Coherence engine v1** (`src/coherence/`): `scoring.py` (897 LOC, decay/floor/override), rules engi
          +ne, schedule/budget/legal/technical/scope/quality categories, router wired in `main.py`.
      108 +- **AI infra** (`core/ai/`): model router + YAML, prompt registry + `prompts/v1/`, A/B experiments, pr
          +ompt/flash cache, usage analytics, LangSmith client.
      109 +- **Security**: multi-tenant RLS (10+ migrations, fail-closed), PII anonymizer (N2), hybrid Clerk+loca
          +l-JWT auth.
      110 +- **Eval**: `evals/` golden corpus (15 bundles) + `run_evals.py`.
      111
       21 -### What Exists But Is Not Used / Legacy
       22 -- **Legacy Coherence Engine:** The module at `apps/api/src/modules/coherence/` exists alongside the ac
          -tive `apps/api/src/coherence/`.
      112 +### What Exists But Is Not Used (as runtime app code)
      113 +- **`modules/coherence/`** — thin legacy (domain/application only, 9 refs, no router). F5.
      114 +- **`gamification/`** — present (`abuse_monitor_service.py`) but **no router wired**; 0 external impor
          +ters.
      115 +- **`golden/`** (`apps/api/src/golden/`) — agent-trajectory eval harness; not in `main.py`, but **invo
          +ked by `evaluation-regression.yml`** (so tooling-live, not app-live). Correction to "0 refs = dead".
      116 +- **Coherence v2** — code exists (`services/v2/`, `v1_to_v2.py`, `v2_to_dashboard.py`) but runs as **s
          +hadow/projection**, default-on shadow mode; no native scoring. F4.
      117
       24 -### What Is Planned
       25 -- The "Tri-dimensional scoring" (Contract + Budget + Schedule) is partially implemented. Schedule rule
          -s (mapped to "TIME") exist (e.g., `RuleR1_ScheduleContractDateMismatch`), but `scoring.py` still issue
          -s warnings about `missing_dimensions=["schedule", "budget"]`, indicating the ingestion/scoring flow fo
          -r schedules is not 100% complete.
      118 +### What Is Planned (declared, not complete)
      119 +- v2 "orchestrator persists native rows (Phase 3)" — explicitly future (`router.py:731`).
      120 +- Full schedule contribution to score (F7/F8 contradiction).
      121
      122 +### What Is Assumed (claimed but unproven statically)
      123 +- That the headline "tri-dimensional" score reflects all three dimensions at runtime (Q3).
      124 +- That mock/skip flags are absent in prod environments (Q6).
      125 +
      126 +### What Is Missing
      127 +- `LICENSE` file; `SECURITY.md`. Cross-provider LLM failover. A blocking accuracy gate wiring evals to
          + engine/scoring changes (F21).
      128 +
      129  ---
      130
      131  ## Security Findings
      132
       31 -### VERIFIED
       32 -- **Secret Exposure:** `.env.staging` was committed to the repository (commit `0794753c...` "feat(api)
          -: [CE-S2-001]") containing a real `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, and a direct conne
          -ction `DATABASE_URL`. The consensus claim identified the wrong commit (`cc9d080`), but the leak itself
          - is real and represents a P0 incident.
       33 -- **Tenant Isolation in DB:** Verified. `pgvector_embedding_repository.py` enforces tenant checks (`_v
          -erify_project_tenant`).
      133 +**VERIFIED**
      134 +- Live `service_role` + `anon` + `JWT_SECRET_KEY` + `DATABASE_URL` in `HEAD` `.env.staging` (F1–F2). *
          +*P0.** Do not reuse this Supabase project until rotated and history-purged.
      135 +- RLS present and fail-closed-hardened (F14).
      136 +- Coherence cache tenant-isolated (F15).
      137 +- HITL bypass flags unguarded in code (F9).
      138
       35 -### REQUIRES MANUAL REVIEW
       36 -- **Cross-Tenant LLM Cache Leak:** The `ContentHashCache` (`adapters/ai/content_hash_cache.py`) uses a
          - SHA-256 key without a tenant prefix (`_ns_key` uses `coherence.llm_gate:key`). While the key is built
          - from the rule and canonical clause text (acting as a content-addressable deduplication cache), this m
          -eans one tenant could theoretically receive an LLM response generated for another tenant if their clau
          -se text matches exactly. Requires review to determine if this is an accepted content-deduplication str
          -ategy or a privacy leak.
      139 +**REQUIRES MANUAL REVIEW**
      140 +- Content-addressable LLM caches with no tenant key (F16) — classify as acceptable dedup vs leak (Q5).
      141 +- Whether repo is public (Q1); whether creds rotated (Q2).
      142
      143 +**NOT VERIFIED (static-only limits)**
      144 +- Runtime tenant-isolation enforcement under load; live 500s on alerts/stakeholders (`TASK-BCK-051`) —
          + requires running system.
      145 +
      146  ---
      147
      148  ## Coherence Engine Findings
      149
       42 -- **Active vs Legacy:** The authoritative active path is `apps/api/src/coherence/` (v2). The legacy pa
          -th is `apps/api/src/modules/coherence/` (v1).
       43 -- **Rule Categories:** The engine actively evaluates SCOPE, BUDGET, TIME (Schedule), TECHNICAL, LEGAL,
          - and QUALITY.
       44 -- **Budget Escapes:** A `BudgetTrackerService` and `coherence_llm_gate.py` actively track and limit LL
          -M spend, transitioning to a `budget_exhausted` state and failing closed to deterministic rules or null
          - scores when the budget is depleted.
      150 +- **Executed engine = v1**, `apps/api/src/coherence/scoring.py` (F3). Deterministic-first, severity-we
          +ighted decay, rule overrides, honest-null on insufficient evidence.
      151 +- **v2 = shadow/additive projection** from v1 via `adapt_v1_dashboard`, gated by `coherence_v2_enabled
          +` / `coherence_v2_shadow_mode` (default shadow). It does **not** compute native scores yet (F4).
      152 +- **Authoritative path** = `src/coherence/` (F5). `modules/coherence/` is legacy; do not consolidate "
          +toward" it.
      153 +- **Dimensions**: category map includes `schedule→TIME`, `financial→BUDGET`, etc. (`scoring.py:576-587
          +`); schedule routing fix landed (F6) but scorer null-paths still flag schedule+budget missing (F7). Tr
          +i-dimensional is **PARTIAL** pending runtime trace.
      154
      155  ---
      156
      157  ## CI/CD Findings
      158
       50 -### CI Trust Score: 40/100
      159 +**CI Trust Score: 45 / 100.**
      160
       52 -- **Blocking Gates:** Linter and some test workflows are blocking.
       53 -- **Advisory / Bypassed Gates:** The "Full backend suite gate" in `.github/workflows/real-document-ope
          -rability.yml` explicitly sets `continue-on-error: true`. If the main test suite fails, the CI pipeline
          - still succeeds.
       54 -- **Coverage:** We found `--cov-fail-under=70` in the Operability workflow, but the fact that the enti
          -re backend test suite can fail without blocking the pipeline completely undermines CI trust.
      161 +Rationale: workflows are numerous and real (16 workflows), lint/typecheck and several jobs block, RLS/
          +security e2e exists with `--cov-fail-under=60`. **But** trust is capped by: unit coverage gate set to
          +`0` and *locked by a guard test* (F12); `continue-on-error: true` on integration tests and two further
          + workflows (F13); the headline eval workflow is path-scoped to `evals/**` so it never gates engine cod
          +e (F21); real-document operability is `workflow_dispatch` + `C2PRO_AI_MOCK`. A green check therefore d
          +oes **not** guarantee integration tests or coverage passed.
      162
      163  ---
      164
      165  ## Validation of Consensus Claims
      166
      167  | Claim | Result | Evidence |
       61 -|---------|---------|---------|
       62 -| Secret exposure in `.env.staging` | **VERIFIED** | Found in git history (commit `0794753ce8`). Conta
          -ins `SUPABASE_SERVICE_ROLE_KEY` and DB URL. |
       63 -| Schedule scoring gap | **PARTIALLY VERIFIED** | Schedule is mapped to TIME. Rules exist (`RuleR1_Sch
          -eduleContractDateMismatch`), but `scoring.py` flags "missing_dimensions". |
       64 -| Coherence v2 cutover / Dual Codebases | **VERIFIED** | `src/coherence/` and `src/modules/coherence/`
          - both exist. |
       65 -| No AI eval framework / prompt registry | **REJECTED** | `evals/run_evals.py` and `evals/golden_corpu
          -s/` exist and are highly sophisticated. |
       66 -| Cache tenant isolation leak | **PARTIALLY VERIFIED** | `ContentHashCache` does not prefix by tenant.
          - Operates as a global content-addressable cache. |
       67 -| HITL bypass via env flags | **VERIFIED** | Mocks and bypasses exist for real document operability te
          -sts (`C2PRO_AI_MOCK`). |
       68 -| MemorySaver checkpointer fallback | **VERIFIED** | Found evidence of state management falling back,
          -though actual prod config dictates impact. |
       69 -| Repo age / reinitialized in 1 month | **REJECTED** | Git history dates back to Dec 2025. |
      168 +|-------|--------|----------|
      169 +| `.env.staging` real `service_role`/JWT/DB secret committed | **VERIFIED** (stronger: live in `HEAD`,
          + not just history; commit `0794753c`, not `cc9d080`) | F1, F2 |
      170 +| Schedule dimension does not feed scoring (`TASK-BCK-064`) | **PARTIALLY VERIFIED** (routing fix exis
          +ts; scorer defaults still missing; backlogs disagree; runtime unconfirmed) | F6, F7, F8 |
      171 +| Coherence v2 cutover incomplete | **VERIFIED** (v2 is shadow projection, "Phase 3" pending) | F4 |
      172 +| Dual codebases / module duplication (two `core/`, two `ai/`, `coherence` vs `modules/coherence`) | *
          +*VERIFIED** | F5, CLAUDE.md gotchas |
      173 +| LLM cache lacks tenant isolation → cross-tenant risk | **PARTIALLY VERIFIED** — *coherence* cache is
          +olated (F15); *LLM/flash/content-hash* caches not tenant-keyed (F16) | F15, F16 |
      174 +| HITL can be bypassed by env flag | **VERIFIED** (no prod guard in code) | F9 |
      175 +| MemorySaver checkpointer fallback | **VERIFIED** (mechanism); prod impact INCONCLUSIVE | F10 |
      176 +| Deployment: Celery+API same container | **VERIFIED** | F11 |
      177 +| Auth architecture ambiguous (Clerk vs Supabase/JWT) | **VERIFIED as hybrid-by-design** (Clerk RS256
          +→ local HS256 fallback) | F17 |
      178 +| CI gates weak (`continue-on-error`, cov=0) | **VERIFIED** | F12, F13 |
      179 +| No eval framework / corpus | **REJECTED** | F20 |
      180 +| No prompt registry / versioning | **REJECTED** (registry + v1 + A/B exist) | F19 |
      181 +| Repo re-initialized in 1 month | **REJECTED** | F24 |
      182 +| License incoherent | **VERIFIED** | F22 |
      183 +| Is the repo public? | **INCONCLUSIVE — INSUFFICIENT EVIDENCE** (needs GitHub API) | Q1 |
      184
      185  ---
      186
     ...
      188
      189  ### READY WITH RESTRICTIONS
      190
       77 -**Justification:** The project has strong foundational architecture, a robust evaluation framework, an
          -d multi-tenant persistence logic. However, the presence of active secrets in the commit history and a
          -broken CI pipeline (backend tests allowed to fail) means that feature execution is unsafe.
      191 +**Justification.** The static facts are now high-confidence. A **verified remediation track rests enti
          +rely on Tier-1 evidence and can begin immediately**, scoped to:
      192
       79 -Implementation agents may begin work strictly on the following stabilization paths:
       80 -1. Rotating credentials and purging the git history of `.env.staging`.
       81 -2. Removing `continue-on-error: true` from critical CI gates and ensuring tests pass.
       82 -3. Consolidating the coherence modules (removing `modules/coherence` legacy).
       83 -4. Verifying if the LLM Content Cache should be tenant-isolated.
      193 +1. **Rotate** the Supabase project `tcxedmnvebazcsaridge` keys + `JWT_SECRET_KEY`, then **purge `.env.
          +staging`** from history (F1–F2). *Highest priority — until done, treat infra as compromised.*
      194 +2. Remove `--cov-fail-under=0` + its guard test; remove `continue-on-error` on real gates (F12, F13).
      195 +3. Reconcile the `TASK-BCK-064` backlog drift and decide schedule-scoring truth via an E2E trace (F7,
          +F8).
      196 +4. Add a prod fail-closed guard for `C2PRO_SKIP_HITL`/`C2PRO_AI_MOCK` (F9).
      197 +5. Repo de-junk (mypy cache, PDF, transcripts, dual lockfile) (F23); add `LICENSE` + resolve ISC-vs-Pr
          +oprietary (F22).
      198 +6. Classify the content-hash cache (F16); split Celery from API (F11).
      199
       85 -No roadmap product features (e.g., BIM integration, new multi-agent meshes) should be implemented unti
          -l these restrictions are lifted.
      200 +**Restrictions — do NOT begin until verified at runtime:**
      201 +- Any work premised on v2 being a live scorer (it is shadow — F4).
      202 +- Consolidating "toward `modules/coherence`" (it is legacy — F5).
      203 +- Cross-tenant cache "fix" before the data-classification decision (Q5).
      204 +- Any product/roadmap expansion (BIM, agent mesh, microservices, graph DB) — no evidence base.
      205
      206 +The product/runtime layer (schedule contribution, cache leak impact, prod checkpointer, live 500s, eva
          +l accuracy) **requires a runtime trace**, which a read-only static audit cannot supply.
      207 +
      208 +---
      209 +
      210  ## Recommended Next Investigation
       88 -- Review the `ContentHashCache` keys to decide if global content-addressability violates tenant data p
          -rivacy constraints.
       89 -- Perform a complete test run locally to see what actually fails when `continue-on-error` is removed.
      211   No newline at end of file
      212 +
      213 +1. **One end-to-end runtime trace** on a real anonymized contract+schedule+budget set with production-
          +equivalent config — resolves Q3, Q4, Q5, Q6, Q7 simultaneously.
      214 +2. **One-bit external check:** is the GitHub repo public? (Q1) — sets secret blast-radius and patent u
          +rgency.
      215 +3. **Confirm Supabase rotation status** for project `tcxedmnvebazcsaridge` (Q2).
      216 +4. **Import-graph** `analysis/` → `modules/` to scope retiring `modules/coherence/` safely.

● Done. I completed a read-only verification across all 9 phases and wrote Repository_Evidence_Pack.md (superseding the
  prior draft, which had a reversed v1/v2 claim and understated the secret exposure).

  What the evidence actually shows

  Critical, independently verified:
  - Live service_role key in HEAD. .env.staging is gitignored (.env.*) yet committed and present right now — JWT payload  decodes to role: service_role, iss: supabase, project ref tcxedmnvebazcsaridge, exp ~2036. The prior pack said "only
  in history, commit cc9d080"; truth is live in HEAD, added in 0794753c.

  Key corrections to consensus / prior pack:

  ![[Pasted image 20260615213149.png]]
  
  Confirmed as stated: HITL bypass flags with no prod guard (F9); MemorySaver fallback (F10); Celery+API one container
  (start.sh); CI --cov-fail-under=0 locked by a guard test + continue-on-error ×3; hybrid Clerk→local-JWT auth; license
  incoherence; 1,418 tracked .mypy_cache files + client PDF + 10 root transcripts; 740 commits since 2025-12-29 (re-init  story rejected).

  Verdict: READY WITH RESTRICTIONS. A P0 remediation track (rotate/purge secret, fix CI gates, reconcile backlog, guard
  skip-flags, de-junk, license) rests on Tier-1 evidence and can start now. Anything depending on v2-as-live-scorer,
  schedule-contribution, cache-leak impact, or prod checkpointer behavior needs a runtime trace — which a static
  read-only audit cannot provide.

  Marked INSUFFICIENT EVIDENCE (require external/runtime access): repo public status, Supabase rotation status, true
  end-to-end tri-dimensional scoring, prod checkpointer trigger, eval accuracy vs ground truth.

  No files were modified except the requested deliverable.
  
  
  │           Claim           │                                     My finding                                      │
  ├───────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │ "v2 active, v1 legacy"    │ Reversed — scoring.py:67 is canonical v1; v2 is a shadow projection                 │
  │                           │ (adapt_v1_dashboard, shadow default on), not a native scorer                        │
  ├───────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │ "no eval framework"       │ Rejected — 15-bundle synthetic golden corpus + run_evals.py                         │
  ├───────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │ "no prompt                │ Rejected — prompts/registry.py, versioned prompts/v1/, ab_experiment.py             │
  │ registry/versioning"      │                                                                                     │
  ├───────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │ "consolidate toward       │ Backwards — src/coherence/ is canonical (122 refs vs 9)                             │
  │ modules/coherence"        │                                                                                     │
  ├───────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │                           │ Backlog drift — root backlog says P0-open, BCK_BACKEND.md says fixed; routing fix   │
  │ TASK-BCK-064 schedule fix │ is in graph.py:62, but scoring.py still defaults                                    │
  │                           │ missing_dimensions=["schedule","budget"]                                            │
  ├───────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
  │ cache cross-tenant leak   │ Split verdict — coherence cache is tenant-keyed (cache_keys.py:105);                │
  │                           │ LLM/flash/content-hash caches are not (content-addressable, F16)                    │
  └───────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────┘

  Confirmed as stated: HITL bypass flags with no prod guard (F9); MemorySaver fallback (F10); Celery+API one container
  (start.sh); CI --cov-fail-under=0 locked by a guard test + continue-on-error ×3; hybrid Clerk→local-JWT auth; license
  incoherence; 1,418 tracked .mypy_cache files + client PDF + 10 root transcripts; 740 commits since 2025-12-29 (re-init  story rejected).

  Verdict: READY WITH RESTRICTIONS. A P0 remediation track (rotate/purge secret, fix CI gates, reconcile backlog, guard
  skip-flags, de-junk, license) rests on Tier-1 evidence and can start now. Anything depending on v2-as-live-scorer,
  schedule-contribution, cache-leak impact, or prod checkpointer behavior needs a runtime trace — which a static
  read-only audit cannot provide.

  Marked INSUFFICIENT EVIDENCE (require external/runtime access): repo public status, Supabase rotation status, true
  end-to-end tri-dimensional scoring, prod checkpointer trigger, eval accuracy vs ground truth.

  No files were modified except the requested deliverable