# C2Pro Tech Debt Audit — 2026-07-14

**Scope**: CI failure triage, npm/pnpm consistency, backend (`apps/api`), frontend (`apps/web`), repo-wide hygiene.
**Method**: Live `gh` CI evidence (runs of 2026-07-13/14) + full local gate runs on Windows (Python 3.11.9, Node 22.21.0, pnpm 10.25.0, Docker 29.5.2).
**Status**: DIAGNOSIS COMPLETE — awaiting owner approval before any remediation.

---

## 1. Executive summary

The repo is in materially better shape than the run list suggests. The **required** CI gate (`CI Status`) is **green on main**, the frontend passes every local gate (typecheck, ESLint, 849 vitest tests, production build), and the backend unit + contract suites pass locally exactly as in CI. `main` is now protected by an active GitHub ruleset (the backlog still says it is unprotected — stale).

The real debt is concentrated in four places:

1. **Advisory-red noise**: every backend-touching push turns the CI run red via two advisory jobs (ruff: **206** violations; integration suite: **14F/10E** baseline). Three of the four "failures" on main today were only this.
2. **Three genuinely red Dependabot PRs** (bcrypt 5, redis 8, vite 8) — one of them (#227) fails for a config reason: the root `pnpm.overrides` pin fights Dependabot's lockfile.
3. **mypy strict baseline: 1,370 errors in 303 files** — the largest single debt item.
4. **npm/pnpm mixing is real but contained** to human surfaces (Makefile, onboarding docs, one package script, a bloated root manifest). Lockfile state itself is healthy: no stray `package-lock.json`/`yarn.lock` anywhere, `pnpm install --frozen-lockfile` passes locally and in CI.

Nothing found blocks day-to-day merging *today*; the risk is forward-looking: alert fatigue hiding real regressions, doc-following contributors breaking their env with npm, and the mypy/integration baselines growing unboundedly while advisory.

---

## 2. Gate status matrix (evidence, 2026-07-14)

| Gate | CI (main) | Local run (this audit) |
|---|---|---|
| Backend unit (py3.11 + 3.12) | ✅ green | ✅ pass (16 skipped, all documented) |
| ADR-013 graph contract gate | ✅ green | ✅ pass |
| Backend security suite (multi-tenant) | ✅ green | not run locally (needs compose stack; CI green is fresh) |
| Backend integration (advisory) | 🔴 14 failed / 10 errors | not run locally (known baseline, TASK-DEV-004) |
| Backend lint ruff 0.15.21 (advisory) | 🔴 fails | 🔴 **206 errors, 94 auto-fixable** |
| Backend typecheck mypy 1.8.0 strict (advisory) | 🔴 (continue-on-error) | 🔴 **1,370 errors / 303 files** |
| Frontend lint + typecheck | ✅ green | ✅ pass / pass |
| Frontend vitest (`test:all`) | ✅ green | ✅ 218 files/723 tests + 51 files/126 tests, all pass |
| Frontend production build | ⚠️ **not run in CI at all** | ✅ pass (`next build --webpack`) |
| Playwright E2E | ✅ smoke only (2 of 29 spec files) | config valid, 106 tests listed; live run needs Clerk secrets + stack |
| OpenAPI drift gate | ✅ green | n/a |
| pip-audit / pnpm audit | ✅ green today ("No known vulnerabilities found") | not duplicated locally |
| Migrations (Alembic single-head) | ✅ green | tip parity: Alembic (64 revs) & Supabase CLI (20 files) both end at `20260708…waitlist_signups` |
| Scheduled: eval-regression, qa-swarm, golden-corpus, drift-checks, secret-scan, CodeQL, wireframe | ✅ all green | n/a |
| Scheduled: i13-real-e2e | ⏸ cron paused (was 100% failing; fixture port 5432 vs 5433) | TASK-DEV-005 |

---

## 3. Findings

### P0 — CI is red / blocks development

#### P0-1 · Dependabot PR #233 (bcrypt 4→5) fails required gates
- **Area**: CI / backend deps.
- **Evidence**: PR checks failing: `Backend Security Suite`, `CI Status`, `OpenAPI Drift Check`, `pip-audit`, plus advisory lint/integration.
- **Classification**: likely **real code incompatibility** (bcrypt 5 removed APIs that passlib relies on) **plus staleness** — the PR was opened 2026-07-13, before the OpenAPI baseline repair (TASK-DEV-010) landed, so part of the red is rebase-able drift.
- **Impact**: security-relevant dependency stuck; queue rot.
- **Proposed fix**: rebase onto main → re-triage. If security suite still red, patch the hashing layer for bcrypt 5 (or explicitly defer with a `dependabot.yml` ignore + backlog task). **Risk**: low (test-protected). **Effort**: S–M.

#### P0-2 · Dependabot PR #230 (redis 5→8) fails required gates
- **Evidence**: failing `Detect Changes`, CodeQL `Analyze (python)`, `OpenAPI Drift Check`, `CI Status`. `Detect Changes` failing means the run can't even start properly — branch is stale/conflicting against main.
- **Classification**: staleness first; genuine redis-py 8 breaking-change risk second (5→8 is three majors).
- **Proposed fix**: rebase → re-triage → dedicated compatibility pass on `core/cache.py` + rate limiter if still red, or defer-with-ignore. **Risk**: medium (Redis touches rate limiting + cache). **Effort**: M.

#### P0-3 · Root `pnpm.overrides` pin fights Dependabot → #227 (vite 8) hard-fails at install
- **Evidence**: all three frontend lanes die in setup: `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH — the current "overrides" configuration doesn't match the value found in the lockfile`. Root `package.json` pins `vite: 7.3.5` in `overrides` + `pnpm.overrides`; Dependabot bumps the lockfile but cannot know about the pin.
- **Impact**: any future Dependabot PR touching an overridden package (vite, next, rollup, axios, undici, …) will fail the same way — a structural failure mode, not a one-off.
- **Proposed fix**: overrides governance (see §4 plan step 5): for each pin decide "hard security pin → add to `dependabot.yml` ignore list" or "incidental pin → remove". For #227 specifically: either close-and-defer with ignore rule, or bump the override in the PR branch. **Risk**: low. **Effort**: S.

#### P0-4 · Advisory jobs make every backend push red → signal drowned
- **Evidence**: main runs for #229/#231/#237 all conclusion=failure; job-level: only `Backend Lint (ruff, advisory)` + `Backend Integration (advisory)` failed; `CI Status` passed each time. The two web-only pushes after were green — pure path-filter artifact.
- **Impact**: the run list cannot distinguish "known baseline" from "new regression"; this audit's trigger ("CI/CD surfacing errors and failures") is largely this noise.
- **Proposed fix**: burn the baselines down rather than silencing (constraint: no gate weakening): ruff first (P1-3, cheap), integration second (P1-1). *Optional interim*: give `backend-lint`/`backend-integration` `continue-on-error: true` like `backend-typecheck` so run-level conclusion reflects the required gate — visible in job UI, still advisory. Flagged as a **decision point** since it trades run-level redness for less visibility. **Effort**: S (interim) / M (real fix).

#### P0-✔ Resolved since backlog was written: `main` branch protection
- **Evidence**: ruleset `Protect main` (id 18843913) is **active**: PR required, required checks `CI Status` + `gitleaks`, non-fast-forward. The legacy branch-protection API 404s, which is expected with rulesets. TASK-DEV-007's core item is done; remaining sub-items (CODECOV_TOKEN, `Production` env reviewers, delete stale `staging` env, prune dead secrets) are still owner-manual.
- **Proposed fix**: update TASK-DEV-007 in the backlog to reflect partial completion. **Effort**: S.

### P1 — high-risk debt likely to hurt future phases

#### P1-1 · Backend integration suite red baseline (TASK-DEV-004)
- 14 failed / 10 errors on main (sqlalchemy pool teardown, error `gkpj`). Until green, `backend-integration` can't be promoted to required, so integration regressions can merge silently. **Effort**: M–L. **Risk of fixing**: low (test-only surface, but may expose real session-lifecycle bugs — good).

#### P1-2 · mypy strict baseline: 1,370 errors / 303 files (TASK-DEV-006)
- Top offenders: `type-arg` 304, `arg-type` 231, `no-untyped-def` 228, `attr-defined` 115, `assignment` 77, `call-arg` 75. Strict mode over 784 source files.
- **Impact**: type gate is decorative; typed-API drift accumulates precisely where the AI pipeline (LangGraph state, Pydantic DTOs) most needs it.
- **Proposed fix (decision needed)**: recommend **module-tiered strictness**: strict on `shared_kernel`, `coherence`, `analysis/adapters/graph`, `modules/hitl` first; relaxed-but-checked elsewhere; ratchet with a baseline file so *new* errors fail while old ones burn down in slices. Alternative: full burn-down (L, weeks). **Effort**: M (setup + first tier). **Risk**: low.

#### P1-3 · ruff baseline: 206 errors, 94 auto-fixable (TASK-DEV-009)
- Note: backlog says "~57" — that was ruff 0.2.x; requirements now pin `ruff==0.15.21`, which finds 206. After fix, promote `backend-lint` to `REQUIRED_JOBS`. **Effort**: S–M (autofix + ~112 manual, mostly tests). **Risk**: low-medium (auto-fixes are behavior-safe classes, but re-run unit suite after).

#### P1-4 · npm/pnpm mixing — **confirmed real** (dedicated plan in §4)
- Live, user-facing surfaces still instruct npm; zero enforcement exists. Detailed verdict + standardization plan below.

#### P1-5 · CI never runs `next build`
- **Evidence**: no CI job builds the frontend; only Vercel builds at deploy time. A merge can pass all checks and still fail the production build (build-only failures: env validation, `next.config` regressions, RSC boundary errors).
- **Proposed fix**: add a `frontend-build` job (or fold into `frontend-quality`) with the same mock env CI already uses — local build passes in ~2 min — and/or make the Vercel preview check required in the ruleset. **Effort**: S. **Risk**: low.

#### P1-6 · Coverage policy is incoherent (three contradictory numbers)
- `apps/api/pyproject.toml` `fail_under = 70`; ci.yml backend-unit runs `--cov-fail-under=0` (never enforces); `codecov.yml` targets 80% but Codecov statuses aren't required checks; vitest has **no** thresholds.
- **Proposed fix**: pick one enforcement point (recommend: keep 70 in pyproject, delete the `--cov-fail-under=0` override once measured ≥70; add vitest thresholds at current actuals to ratchet). Requires a measurement first — flagged as **decision point**. **Effort**: S. **Risk**: could turn CI red if actual < configured — measure before enforcing.

#### P1-7 · E2E suite: 27 of 29 spec files never run anywhere
- CI runs only 2 smoke specs (`coherence-v1`, `journey-3-wedge`); i13 cron is paused (TASK-DEV-005: fixture connects to 5432, compose exposes 5433); `document-analysis-pipeline.spec.ts` has 5 state-conditional `test.skip(true, …)` — tests that silently skip when the environment lacks data.
- **Impact**: the E2E suite rots invisibly; flaky/broken specs will only be discovered when someone finally runs them.
- **Proposed fix**: fix i13 fixture (S), then a nightly `workflow_dispatch`+cron lane running the full Playwright suite non-blocking; triage conditional skips into seeded-data tests or explicit quarantine. **Effort**: M.

### P2 — hygiene and consistency

#### P2-1 · 234 tracked artifact files + junk (needs owner approval to delete)
- `apps/web/coverage/.tmp/` — **232 tracked JSON files, 1.9 MB** (`.gitignore` has `/coverage` root-only, so `apps/web/coverage` was never ignored).
- `apps/web/test-results/.last-run.json`, `backups/C2PRO_MASTER_BACKLOG_20260404_112755.md.bak`.
- `apps/api` root junk (tracked): `=2.0.0`, `=3.2.0` (pip shell-redirect artifacts), a file literally named `docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d`, `.pytest-collect.txt`, `.pytest-full-junit.xml`, `.pytest-security-e2e-junit.xml`, `.coverage-security-e2e.xml`, `coverage.json`, `coverage-security-workflow.xml`, `test-results-security-workflow.xml`, `test_real.pdf`, `test_error_handling_standalone copy.py`.
- Stray root-level api modules predating the src layout: `models.py`, `sqlalchemy_orm.py`, `sqlalchemy_document_repository.py`, `create_test_schema.py`, `test.py`, `test_document_repository.py`, `test_anonymizer_standalone.py`, `test_db_connection.py`, `requirements-sprint1.txt`, `run_tests.bat`, `S1.5_ANONYMIZER_IMPLEMENTATION_SUMMARY.md` — dead-code/import-shadowing candidates (need a usage check before deletion).
- Root clutter (tracked): `Consenso GLM-5.1.md`, `Consenso_Claude.md`, `consenso_chatgpt.md`, `analyze_payload.json`, `blackboard.json` (gitignored *and* tracked — ignore is ineffective), `windows-setup.md`, `run_tests_docker.ps1`; root `tests/` mixes live eval harness (`tests/accuracy/…`, used by green `evaluation-regression.yml`) with `*.xlsx` plans, a bug screenshot PNG, and legacy summary MDs.
- **Security note**: `SECRETS.md` and `claves postgre.txt` exist locally but are **NOT tracked and have zero git history** — no leak. Keep them ignored.
- **Proposed fix**: one approval-gated purge commit (`git rm --cached` + `.gitignore` additions: `apps/web/coverage/`, `.claude/scheduled_tasks.lock`), preserving anything the owner flags. **Effort**: S–M. **Risk**: low if usage-checked (I will verify nothing imports the stray api modules before proposing each deletion).

#### P2-2 · Makefile is partially broken and npm-based (TASK-DEV-008 + more)
- `openapi:` target text is embedded **inside** the `help` recipe (lines 25–33) — `make help` prints garbage, `make openapi` (documented in CLAUDE.md) doesn't exist.
- `dev-api`/`test-api`/`lint-api`/`format-api`/`typecheck` activate `venv/`, while `setup-backend` creates `.venv/` — both exist locally **with drifted package versions** (venv: pydantic 2.13.4/SQLA 2.0.50 vs .venv: 2.12.5/2.0.46).
- 8 npm invocations (see §4). Uses legacy `docker-compose` v1 syntax throughout.
- **Proposed fix**: single Makefile overhaul commit: extract `openapi`, standardize `.venv`, npm→pnpm, `docker compose`. **Effort**: S–M. **Risk**: low (CI doesn't consume the Makefile; humans do).

#### P2-3 · Husky pre-commit hook cannot fail on ruff (root cause of "unreliable hook")
- **Evidence**: `.husky/pre-commit` runs `cd apps/api && python -m ruff check . && cd ../..` with no `set -e` and no `|| exit 1`; the script ends with `echo "✅ …"`, so the hook **always exits 0 for Python changes**. (The ESLint branch does have `|| exit 1`.) This is the mechanism behind the backlog note "Husky hook does not reliably run".
- **Proposed fix**: `|| exit 1` on the ruff branch (after P1-3 cleans the baseline, otherwise every commit blocks), and scope to staged files. **Effort**: S.

#### P2-4 · Root `package.json` is misleading and bloated
- `"name": "package.json"`, plus **unused runtime dependencies** (`next`, `react`, `recharts@^3` (web uses `^2`!), `@google/generative-ai`, `@sentry/react`, `@supabase/ssr`, `lucide-react@^0.563` vs web `^0.562`, tailwind, fontsource…) — grep shows the only referencing files are `context/experimental/` prototypes and `docs/archive/`. Root also carries eslint **v10** while web pins **9.35.0**.
- Duplicated override blocks: npm-style `overrides` + `pnpm.overrides` at root, plus a third dead `overrides` block in `apps/web/package.json` (pnpm only honors root `pnpm.overrides`).
- **Impact**: Dependabot opens root-level JS PRs for phantom deps; version-skew confusion; override governance split across three blocks (cause of P0-3).
- **Proposed fix**: rename package, prune unused deps (evidence-checked), collapse to a single `pnpm.overrides`, regenerate lockfile, full gate re-run. **Effort**: M. **Risk**: medium (lockfile churn) — mitigated by frozen-install + full local gates before push.

#### P2-5 · No Node/toolchain version pinning for humans
- No `engines`, no `.nvmrc`, no `.npmrc` (`engine-strict`), no `only-allow` guard. CI pins Node 22 in the composite action; humans get whatever they have. Covered by §4 plan.

#### P2-6 · Working tree has uncommitted backlog updates
- `C2PRO_MASTER_BACKLOG.md` + `backlogs/DEV_DEVOPS.md` contain the finished TASK-DEV-014/015 records from the previous session (verified content is consistent and accurate) — should be committed as-is. `.claude/scheduled_tasks.lock` is a session lock that churns every run → untrack + ignore. **Effort**: S.

#### P2-7 · `backlogs/DEV_DEVOPS.md` has interleaved sections (bad merge)
- TASK-DEV-008's heading (line 61) is immediately followed by TASK-DEV-007's section, and DEV-008's body resumes *after* DEV-007's checklist (line 74). Same failure mode as the Makefile corruption. **Effort**: S.

#### P2-8 · Minor code-quality signals (inventory, no action proposed yet)
- Web type-safety escapes are **low**: 8 `@ts-ignore/@ts-expect-error`, 9 `: any` (2 files), 6 `eslint-disable`. API: 32 `# type: ignore`.
- Unit-test warning: 7× `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` at `apps/api/src/coherence/router.py:343` (test mock misuse — worth one small fix).
- `docs/api/openapi.yaml` duplicate `worker_health_check…` operation ID — already tracked as TASK-BCK-094.
- SonarCloud cognitive-complexity debt — already tracked as TASK-DEV-015 (P3).
- Docs referencing npm inside `docs/archive/**`, `docs/wireframes/**`, `openspec/changes/**` — historical records; propose **leaving them** (marked non-live) rather than rewriting history.

---

## 4. npm vs pnpm — verdict and standardization plan

### Verdict: **real problem, confirmed — but narrower than feared.**

**Healthy (no action needed)**: zero `package-lock.json`/`yarn.lock`/`npm-shrinkwrap.json` anywhere (tracked or untracked); `packageManager: "pnpm@10.25.0"` present; `pnpm install --frozen-lockfile` passes locally and is what CI runs (`setup-node-web` composite, pnpm version sourced from `packageManager`); Husky's ESLint step uses `pnpm --filter`; deploy surfaces contain no npm (api deploys via Dockerfile; Vercel auto-detects pnpm from the lockfile — see follow-ups).

**Mixed (the actual problem) — every live npm surface found:**

| Surface | Evidence |
|---|---|
| `Makefile` | `setup-frontend: cd apps/web && npm install` (would create a package-lock and **bypass `pnpm.overrides` security pins** like axios/undici); `dev-web`, `test-web`, `test-e2e`, `lint-web`, `format-web`, `typecheck`, `build-web` all `npm run …` |
| `apps/web/package.json` | `"verify:openspec": "npm --prefix ../.. run verify:openspec --"` |
| `README.md` | L147 `npx supabase start`, L177 `npm install`, L180 `npm run dev` |
| `QUICK_START.md` | L109/155 `npm install`, L158/176/209 `npm run dev` |
| `apps/web/README_SETUP.md` | 8 occurrences incl. `npm install next-themes` (instructs adding deps with npm!) |
| Root `package.json` | npm-semantics `overrides` block duplicated beside `pnpm.overrides`; a third dead `overrides` in `apps/web/package.json` |
| Enforcement | none: no `engines`, `.nvmrc`, `engine-strict`, or `only-allow` guard |

**Breakage caused / likely**: (a) any contributor following README/QUICK_START/Makefile gets an npm-resolved tree without the security pins and a stray `package-lock.json`; (b) the split override blocks already broke a CI lane (P0-3, `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH` on #227); (c) root phantom deps generate misdirected Dependabot PRs ("… in / for vite").

### Target state
One package manager — **pnpm 10.25.0** — used and enforced end-to-end (docs, Makefile, scripts, hooks, CI, deploy), with Corepack/`packageManager` as the version source and an install-time guard.

### Migration steps (ordered)
1. **Guard first** (so later steps can't regress): root `package.json` → `"preinstall": "npx only-allow pnpm"`; add `engines: { "node": ">=22 <23", "pnpm": ">=10" }` to root + `apps/web`; add `.npmrc` with `engine-strict=true`; add `.nvmrc` = `22`. Document `corepack enable` in README.
2. **Makefile**: all 8 targets → pnpm (`setup-frontend` → `pnpm install --frozen-lockfile` at repo root; run-targets → `pnpm --filter c2pro-web <script>`); done inside the same commit as the P2-2 repair.
3. **Scripts**: `apps/web` `verify:openspec` → `pnpm -w run verify:openspec`.
4. **Docs**: README (`npx supabase` → `pnpm exec supabase` — it's a root devDep), QUICK_START, `apps/web/README_SETUP.md` → pnpm equivalents. Archived docs untouched.
5. **Override governance** (fixes P0-3's failure mode): collapse to a single root `pnpm.overrides`; delete the npm-style root `overrides` and the dead `apps/web` `overrides`; for each surviving pin decide *keep-as-security-pin → add matching `dependabot.yml` ignore* vs *drop*. Regenerate lockfile (`pnpm install`), then validate with `pnpm install --frozen-lockfile`.
6. **Root manifest hygiene** (P2-4): rename, prune unused runtime deps — same commit series as step 5 since both touch the lockfile.

### Verification
`pnpm install --frozen-lockfile` from clean state → `pnpm --filter c2pro-web typecheck && lint && test:all && build` → backend suite untouched-but-rerun (`ruff`, unit) → `make dev-web`/`make test-web` smoke → grep-gate: no `npm install|npm run|npx ` outside `docs/archive/**`, `openspec/**`, `skills/**` (optionally encoded as a small repo meta-test alongside the existing CI-guard tests).

### Rollback
Each step is an isolated commit; only steps 5–6 touch `pnpm-lock.yaml`. Revert = `git revert` of the offending commit; no data migration, no deploy coupling (Vercel/Railway read the lockfile, which stays valid at every step).

---

## 5. Proposed execution order (for approval)

| # | Batch (one theme = one commit each) | Findings | Effort | Gate re-run after |
|---|---|---|---|---|
| 0 | Commit pending backlog updates; register new tasks + correct TASK-DEV-007 status & DEV_DEVOPS interleave; untrack `scheduled_tasks.lock` | P2-6, P2-7, P0-✔ | S | none (docs) |
| 1 | ruff burn-down (autofix 94 → manual 112) → promote `backend-lint` to required | P1-3, P0-4 | S–M | ruff + backend unit |
| 2 | Rebase + re-triage #233 (bcrypt) and #230 (redis); fix or defer-with-ignore | P0-1, P0-2 | M | PR CI |
| 3 | Override governance + root manifest hygiene + #227 decision | P0-3, P2-4 | M | full frontend gates |
| 4 | npm→pnpm standardization (guard, Makefile+repair, docs, script) | P1-4, P2-2, P2-5 | M | make targets + frontend gates |
| 5 | Husky pre-commit fix | P2-3 | S | commit dry-run |
| 6 | CI `frontend-build` job + coverage-policy decision (measure, then align) | P1-5, P1-6 | S | CI on PR |
| 7 | Artifact/junk purge (owner-approved list) + `.gitignore` gaps | P2-1 | S–M | full local gates |
| 8 | Integration suite repair → promote gate | P1-1 | M–L | compose-backed integration |
| 9 | mypy strategy (tiered strict + ratchet) — first slice | P1-2 | M | mypy |
| 10 | i13 fixture port fix → re-enable cron; nightly full-E2E lane | P1-7 | M | dispatch run |

Decision points needing explicit owner input before/during remediation:
1. **P0-4 interim**: make `backend-lint`/`backend-integration` `continue-on-error` until baselines are clean (less red, less visible) — yes/no?
2. **#233/#230/#227**: fix-forward vs defer-with-dependabot-ignore per PR.
3. **P1-2 mypy**: tiered-strict + ratchet (recommended) vs full burn-down vs relax strictness deliberately.
4. **P1-6**: which coverage number is the enforced one (recommend 70 backend now, ratchet later; add vitest thresholds at measured actuals).
5. **P2-1**: approve the deletion list (file-by-file list above; anything to keep?).

New backlog tasks to register at step 0 (IDs to confirm against the backlog at write time): pnpm standardization (→ TASK-DEV-016), Dependabot majors triage (→ TASK-DEV-017), CI frontend-build (→ TASK-DEV-018), coverage policy (→ TASK-DEV-019), artifact purge (→ TASK-DEV-020), Husky fix (→ TASK-DEV-021), root manifest hygiene (→ TASK-DEV-022), nightly E2E lane (→ TASK-DEV-023). Existing tasks referenced: TASK-DEV-004/005/006/007/008/009/015, TASK-BCK-094.

Manual follow-ups only the owner can do (unchanged from runbook + new): add `CODECOV_TOKEN`; `Production` environment required reviewers; delete stale `staging` environment; prune dead deploy secrets; verify the Vercel project's install command is pnpm (dashboard-side; repo has no `vercel.json`).

## 6. Prevention recommendations
- `only-allow pnpm` + `engine-strict` (step 4) makes wrong-tool installs impossible rather than documented-against.
- Promote advisory jobs to required as each baseline reaches zero — never the reverse.
- The existing meta-test culture (`test_backend_ci_guards.py`) is the right home for: package-manager grep-gate, Makefile target existence, and the override/dependabot-ignore consistency check.
- After merging any Dependabot group PR, immediately rebase the remaining queue (stale-branch failures were half of today's red).

## 7. Resolution log
*(to be filled during remediation; every finding above gets `RESOLVED <date+commit>` / `DEFERRED <reason>` here)*
