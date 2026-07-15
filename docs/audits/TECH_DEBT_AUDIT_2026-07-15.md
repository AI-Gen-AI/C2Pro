# C2Pro Repository Health and Technical-Debt Audit — 2026-07-15

> **LEADER VERIFICATION (2026-07-15)**: Cross-checked against git and live CI. **CONFIRMED**: `pnpm audit` HTTP 410 (P0 → `TASK-DEV-024`; reproduced locally, still broken on pnpm@latest); duplicate `psycopg[binary]` floors; divergent `apps/api/docker-compose.test.yml`; minimal `apps/web/.gitignore`; `typescript 5.3.3` pin; `tailwindcss-animate` build-time-only. **REFUTED**: "committed `__pycache__` / 66+ tracked .pyc" — `git ls-files` shows 0 tracked `__pycache__` paths (disk-only, ignored). **SUPERSEDED**: any task-ID table inside this file — canonical registrations are `TASK-DEV-024`…`029` as recorded in `backlogs/DEV_DEVOPS.md`. The 2026-07-14 audit remains the primary remediation plan; this file is an addendum.

**Status:** Diagnosis complete; remediation has not started. Owner approval is required before code, configuration, dependency, or tracked-file deletion work.

**Scope:** Live CI, package-manager consistency, `apps/api`, `apps/web`, and repository hygiene. This report refreshes and supersedes the evidence in `TECH_DEBT_AUDIT_2026-07-14.md`; existing task IDs are retained where the finding was already registered.

## Executive verdict

The current `main` head (`e6f5028a`) passes the required `CI Status` gate, CodeQL, and secret scanning. The repository is nevertheless not at the requested “all gates green” quality bar:

- Three open major-upgrade PRs are genuinely red: bcrypt 5 (`#233`), redis 8 (`#230`), and Vite 8 (`#227`).
- The JavaScript dependency-audit lane now fails with HTTP 410 when it is triggered. This is a CI/tooling failure, not a vulnerability finding.
- Backend advisory gates remain materially red: Ruff reports 206 violations, mypy reports 1,370 errors in 303 files, and the integration suite has a known 14-failure/10-error CI baseline.
- Backend unit tests pass, but the unit gate measures only 46% total coverage while CI disables the configured 70% threshold.
- Frontend lint, typecheck, 849 Vitest tests, and a Next.js 16.2.10 production build pass locally. Local Playwright execution is blocked before assertions by Clerk token/network access.
- npm and pnpm are genuinely mixed in active developer and test surfaces. The pnpm lockfile is healthy today, but the mixing already produces npm configuration warnings and makes override behavior inconsistent.
- At least 238 generated/test artifacts are tracked (232 Vitest coverage shards plus six named API/web test outputs), alongside misleading root/API files that require usage checks before any deletion.

## Evidence and gate matrix

|Area|Command or source|Result|
|---|---|---|
|Current CI|`gh run list --branch main --limit 30`; `gh run view ... --log-failed`|Latest `main` CI run `29365707269` succeeded. Older backend-changing runs remain run-level red because advisory Ruff/integration jobs fail.|
|Open PRs|`gh pr checks 238,233,230,227,224,225,226`; failed logs|`#238`, `#224`, `#225`, `#226` green; `#233`, `#230`, `#227` red for the causes recorded below.|
|Backend lint|CI-equivalent Ruff 0.15.21|206 errors; 94 auto-fixable.|
|Backend types|CI-equivalent strict mypy|1,370 errors in 303 files (784 files checked).|
|Backend contracts|ADR-013 contract gate|3 passed; one `PytestAssertRewriteWarning`.|
|Backend S5|Security-focused S5 gate|22 passed; same bootstrap warning.|
|Backend unit|CI unit command|1,595 passed, 16 skipped, 11 deselected; 9 warnings; total coverage 46%.|
|Python dependencies|`pip-audit -r apps/api/requirements.txt`|No known vulnerabilities. Current reused `.venv` fails `pip check` because stale `supafunc 0.4.7` requires `httpx<0.28`; this package is not declared directly in the current requirements and must be rechecked in a clean environment.|
|Migrations|Scratch Postgres; full `alembic upgrade head`; single-head assertion|Pass. 64 Alembic revision files; one head, `20260708_0001`. Supabase mirror contains 20 SQL migrations ending at the corresponding waitlist migration.|
|Local test bootstrap|`bootstrap_test_infra.py --start-services --require-redis --recreate-db`|Fail: root Compose exposes Redis at 6380, while the script defaults to 6379. CI masks this with a separate Redis service on 6379.|
|Backend integration local|CI command with Postgres 5433 and Redis 6380|Did not complete within 10 minutes after producing errors/skips. Current CI evidence remains 14 failed/10 errors/3 skipped.|
|Frontend install|`pnpm install --frozen-lockfile`|Pass; lockfile current.|
|Frontend quality|`pnpm lint`; `pnpm typecheck`; sequential after build|Pass. A parallel build/typecheck attempt produced transient missing `.next/types` errors because both mutate/read `.next`; sequential gates are authoritative.|
|Frontend tests|`pnpm test:all`|269 files, 849 tests passed. Warnings include missing third-party source maps and repeated `MaxListenersExceededWarning`.|
|Frontend build|`pnpm build`|Pass; Next.js 16.2.10, 29 static pages. No Next/Fast Refresh deprecation warning.|
|Playwright|Two CI smoke specs, local temp output|Reached global setup, then timed out when Clerk testing-token retrieval failed with `fetch failed`. CI passes these specs when its external credentials/network are available.|
|JS dependency audit|`pnpm audit --audit-level critical --prod`; PR logs|Fail: `ERR_PNPM_AUDIT_BAD_RESPONSE`, registry legacy audit endpoint HTTP 410. No vulnerability conclusion can be drawn from this failed job.|

## P0 — red CI or blocked development

|ID|Area and classification|Concrete evidence|Impact|Fix risk|Effort|Proposed remediation|
|---|---|---|---|---|---|---|
|`TASK-DEV-024`|CI dependency audit — **CI/tool compatibility**|PR `#233` and `#230` logs plus local `pnpm audit` return `ERR_PNPM_AUDIT_BAD_RESPONSE` and HTTP 410 from the retired legacy audit endpoint.|Any dependency-audit-triggering change gets a red audit job; security visibility is absent, not green.|Medium: replacement must preserve critical-vulnerability blocking and cannot silently retire the gate.|S|First test a supported pnpm v10 patch using the bulk endpoint. If still unsupported, use an already-approved platform-native dependency review/Dependabot signal or request approval for a replacement audit tool. Add a workflow regression test and a live successful audit run.|
|`TASK-DEV-017` / PR `#233`|Backend auth dependency — **real code/dependency incompatibility**|passlib 1.7.4 with bcrypt 5 raises missing `bcrypt.__about__` and the new 72-byte password `ValueError`; security job has 12 setup errors.|Blocks bcrypt security update and breaks auth/password test setup.|High: authentication compatibility and stored hashes are sensitive.|M|Rebase, decide supported hashing adapter/version, write focused failing compatibility tests, then fix without weakening password tests. Defer/ignore the major only with recorded rationale if upstream compatibility is unavailable.|
|`TASK-DEV-017` / PR `#230`|Redis dependency — **real resolver conflict**|Kombu 5.6.x requires `redis<6.5`; PR requests redis 8.0.1. Required jobs fail during dependency resolution.|Blocks the upgrade before tests; forcing it risks Celery/cache behavior.|High.|M|Rebase, establish the compatible Kombu/Celery range, test cache/rate-limit/Celery paths, then either perform the compatible grouped upgrade or explicitly defer redis 8.|
|`TASK-DEV-017` + `TASK-DEV-022` / PR `#227`|Frontend dependency governance — **configuration conflict**|Install fails with `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH`; root overrides pin Vite 7.3.5 while the PR declares Vite 8.|All frontend checks and Vercel fail before execution.|Medium.|S–M|Define one root override source, add an override/Dependabot consistency guard, then rebase and assess Vite 8 as a deliberate major migration.|

The current `main` required gate is green; these P0 items refer to actively red CI lanes/PRs, not an assertion that deployed `main` is currently broken.

## P1 — high-risk debt likely to hurt future phases

|ID|Area and classification|Concrete evidence|Impact|Fix risk|Effort|Proposed remediation|
|---|---|---|---|---|---|---|
|`TASK-DEV-004`|Backend integration — **real defects plus test isolation debt**|Current CI baseline: 14 failures, 10 errors, 3 skips; examples include alert setup errors, LangSmith 201-vs-202 drift, and a document fixture missing `tenant_id`. Local run also failed to finish within 10 minutes.|Cross-module regressions can merge because the job is advisory; local feedback is too slow/unreliable.|High.|L|Classify failures by shared root cause, repair fixtures/tenant contracts first under RED/GREEN, remove hangs, then promote the suite to required.|
|`TASK-DEV-009`|Backend lint — **accumulated code debt**|Ruff 0.15.21: 206 errors, 94 auto-fixable.|Run-level CI remains red for backend changes; new lint regressions are hidden in baseline noise.|Medium.|M|Apply safe mechanical fixes in bounded batches, review semantic findings separately, keep rule set unchanged, and promote only at zero.|
|`TASK-DEV-006`|Backend typing — **accumulated type debt**|Strict mypy: 1,370 errors in 303 files; repository contains 145 `# type: ignore` comments.|Static contracts are not enforcing architecture/API changes; broad fixes risk behavior drift.|High.|L|Create module-sized error-budget batches, prioritize ports/DTOs/use cases, prohibit blanket ignores, and ratchet the advisory baseline down to zero.|
|`TASK-DEV-019`|Coverage governance — **CI misconfiguration and coverage gap**|Unit run reports 46%; `ci.yml` overrides to `--cov-fail-under=0`, `pyproject.toml` states 70, Codecov states 80, and frontend has no enforced threshold. Examples at 0% in this unit lane include several admin, AI graph, ingestion, WBS, and observability modules.|Critical paths can regress while the nominal policy appears stronger than the executed gate.|High: immediately enforcing 70 would make CI red without adding protection intelligently.|L|Publish per-module baseline, add focused tests for critical paths, ratchet upward without lowering the existing documented target, and make CI/config/Codecov agree.|
|`TASK-DEV-018`|Frontend production build — **CI coverage gap**|Local `pnpm build` passes, but `ci.yml` does not run it; Vercel is the only build signal and is not the repository join gate.|Next build/runtime-boundary errors can merge if preview checks are absent or non-required.|Low.|S|Add pnpm production build to frontend CI (or require a stable Vercel build check) and add workflow meta-tests.|
|`TASK-DEV-023`|E2E coverage — **test coverage gap / external dependency**|CI executes 2 of 29 Playwright specs. Five document-pipeline cases use unconditional `test.skip(true, ...)`; local smoke cannot start assertions without Clerk token access.|Most user journeys and stateful document paths are not continuously exercised; local reproduction depends on external state.|High.|L|Inventory each spec’s data contract, build a reliable approved test environment, triage skipped cases with real fixtures, and add a non-blocking scheduled lane before promotion. Do not add or preserve skips merely to obtain green.|
|`TASK-DEV-025`|Local backend bootstrap — **environment/config drift**|`docker-compose.test.yml` maps Redis 6380; `bootstrap_test_infra.py:98` defaults to 6379; runbook describes CI’s 6379 service.|The documented local CI reproduction command fails even when Compose starts correctly.|Low–medium.|S|Make the script derive/accept the canonical Compose port, update the runbook to distinguish local 6380 from CI 6379, and add a focused bootstrap contract test.|
|`TASK-DEV-016`|Package manager — **real consistency defect**|See dedicated verdict and plan below.|Wrong CLI can bypass pnpm overrides/workspace semantics and create divergent installs.|Medium.|M|Execute the dedicated pnpm standardization plan after approval.|

### npm vs pnpm verdict and standardization plan

**Verdict: a real, contained conflict exists.** There are no tracked `package-lock.json`, `npm-shrinkwrap.json`, or `yarn.lock` files in the active workspace, and `pnpm install --frozen-lockfile` passes. Ignored/vendor/sandbox directories contain non-authoritative lockfiles, but they do not participate in this workspace. The conflict is active command usage, not a currently drifted tracked lockfile.

Evidence:

- `pnpm-workspace.yaml`, `pnpm-lock.yaml`, and root `packageManager: "pnpm@10.25.0"` define pnpm as canonical.
- npm remains in `Makefile` (seven commands), `README.md`, `QUICK_START.md`, `apps/web/README_SETUP.md`, `apps/web/package.json` (`verify:openspec`), and multiple active runbooks/test docs.
- `apps/web/playwright.config.ts:17` starts Next with `npm run dev`; local execution emits `npm warn Unknown env config "verify-deps-before-run"`, which npm says will cease working in its next major version.
- `.github/workflows/wireframe-coverage.yml:39` uses `npx tsx` after a pnpm install.
- The root manifest duplicates override policy (`overrides` and `pnpm.overrides`), the web manifest has another `overrides` block, and PR `#227` demonstrates a real override/lockfile failure.
- Node is pinned to 22 in CI but not through `engines`, `.nvmrc`, or equivalent contributor setup. No `only-allow pnpm` preinstall guard exists.

Target state: pnpm is the only workspace package manager; Corepack activates the exact declared pnpm version; Node compatibility is pinned consistently; one root `pnpm.overrides` block is authoritative; active docs, hooks, CI, Playwright, Docker/deploy instructions, and scripts call pnpm.

Ordered migration:

1. Inventory hosting settings not stored in Git (Vercel/Railway install/build commands) and record the owner verification result. Do not infer them from repository files.
2. Add compatible Node `engines` plus a repository Node-version file, keep `packageManager`, document Corepack activation, and add an `only-allow pnpm` preinstall guard. Adding a new guard package requires owner approval under repository governance; prefer an existing mechanism if available.
3. Collapse root/web override blocks into one root `pnpm.overrides`; document each retained pin and align Dependabot ignores before regenerating the lockfile.
4. Replace active `npm install`, `npm run`, and `npx` commands with pnpm equivalents in scripts, Playwright, workflows, Makefile, and current docs. Preserve historical/archive text unless it is presented as current guidance.
5. Remove any tracked non-pnpm lockfile if one appears during remediation, only after explicit deletion approval. None is currently tracked.
6. Update contributor and deployment runbooks and add grep/meta-tests preventing active npm commands and extra lockfiles.

Verification:

- From a clean worktree and empty dependency store: enable Corepack, run `pnpm install --frozen-lockfile`, `pnpm lint`, `pnpm typecheck`, `pnpm test:all`, `pnpm build`, and the approved Playwright lane.
- Run backend-independent workflow/meta-tests and inspect Vercel/Railway builds to prove they use pnpm.
- Confirm exactly one tracked JS lockfile and one override source; run the repaired dependency audit.

Rollback: commit manifest/guard, command/doc migration, and lockfile regeneration as separate themes. If clean install or hosting fails, revert only the failing theme and restore the previous `pnpm-lock.yaml`; do not generate or commit an npm lockfile as fallback.

## P2 — hygiene and consistency

|ID|Area and classification|Concrete evidence|Impact|Fix risk|Effort|Proposed remediation|
|---|---|---|---|---|---|---|
|`TASK-DEV-020`|Tracked artifacts/root clutter — **repository hygiene**|232 tracked files under `apps/web/coverage/.tmp`; tracked `apps/web/test-results/.last-run.json`; API JUnit/coverage outputs; `=2.0.0`, `=3.2.0`; a backlog backup; API-root standalone/copy tests, generated outputs, and legacy modules. Current ignore rules do not cover all producer paths.|Noisy diffs, misleading code search, repository growth, and accidental reuse of stale outputs.|Medium: some suspicious files may still be referenced.|M|Perform an import/reference and history check, present the exact deletion list for approval, untrack only generated/obsolete files, and add producer-specific ignore rules. Never use a broad `*.json`/`*.xml` ignore that could hide source assets.|
|`TASK-DEV-008` + `TASK-DEV-016`|Makefile/docs drift — **developer-experience defect**|`openapi` text is embedded in the help recipe; targets use `venv` vs `.venv`, legacy `docker-compose`, and npm while CI uses pnpm/composite setup.|Documented commands do not reliably reproduce CI.|Medium.|M|Make the Makefile a thin, tested wrapper over canonical commands and update current docs in the same batch.|
|`TASK-DEV-021`|Husky enforcement — **hook logic defect**|Python Ruff branch lacks failure propagation and the script’s final echo exits zero.|Developers can commit Ruff failures while believing the hook enforces them.|Low after `TASK-DEV-009`.|S|After the baseline is clean, make staged-file Ruff failure propagate and add a shell/meta-test.|
|`TASK-DEV-022`|Root manifest/dependency ownership — **configuration debt**|Root package name is `package.json`; runtime dependencies overlap/diverge from `apps/web`; override policy is duplicated at root and web. `pnpm outdated -r` shows patch updates and multiple deliberate majors.|Phantom ownership and override drift make installs and Dependabot changes hard to reason about.|Medium–high.|M|Prove root imports/scripts, remove only unused declarations, centralize overrides, and handle majors separately from patch/minor updates.|
|`TASK-DEV-028`|Python manifest/environment reproducibility — **dependency hygiene**|`requirements.txt:14-15` declares overlapping `psycopg[binary]` lower bounds. A reused local `.venv` has an orphaned `supafunc`/httpx conflict while clean requirements resolution passes pip-audit.|Local environments can disagree with CI and produce false diagnoses; duplicate bounds obscure the intended floor.|Low.|S|Recreate a clean venv, run `pip check` and pip-audit, remove only the redundant bound under a focused requirements test, and document the clean-bootstrap command. Do not introduce a new lock/constraints system without approval.|
|`TASK-DEV-026`|Frontend test harness — **warning/flakiness precursor**|All 849 tests pass, but Vitest repeatedly reports `MaxListenersExceededWarning`; third-party CSS source maps are also missing.|Listener accumulation can become flakiness or hide resource leaks; warning noise obscures new regressions.|Medium.|S–M|Identify which setup/listener is added per worker, add cleanup and a focused regression. Treat third-party source-map noise separately; do not raise the listener limit to silence it.|
|Existing P2 follow-ups|Runbook/manual settings — **documentation/external state**|`docs/runbooks/ci-cd-setup.md` still carries stale Ruff/protection wording. `TASK-DEV-007` retains CODECOV_TOKEN, Production reviewers, stale staging environment, dead-secret pruning, and Vercel pnpm verification. `TASK-DEV-005` records the paused i13 cron.|Operators may trust obsolete setup instructions; coverage/release controls remain incomplete.|Low–medium.|S–M|Update the runbook alongside the owning fixes; owner must verify or change GitHub/Vercel/Railway settings.|
|Static modernization signals|Backend/API compatibility — **looming debt, not a current failure**|Current tests emit no Pydantic/FastAPI deprecation warnings, but production code still contains seven Pydantic v1-style `class Config` blocks and one `.dict()` call. Next build is already 16.2.10, so “Next.js 14 deprecations” are not current.|Future dependency upgrades may convert compatibility paths into failures.|Medium.|M|Handle only when covered by focused tests or as part of an approved dependency upgrade; do not perform speculative bulk rewrites.|

No tracked secret was discovered in the audit, and current gitleaks/CodeQL checks are green. Database/repository tenant-scope compliance was not re-certified line-by-line by this CI-focused audit; existing security gates passed, and any future repository change must retain explicit `tenant_id` filtering.

## Proposed execution order

Each numbered item is a separate small commit theme unless the owner changes the order:

1. `TASK-DEV-024`: restore a functioning JS dependency-audit signal.
2. `TASK-DEV-017`: triage/rebase the three red major-upgrade PRs; fix or explicitly defer each independently.
3. `TASK-DEV-025`: repair local Redis/bootstrap reproducibility.
4. `TASK-DEV-004`: integration root-cause batches until stable, then required.
5. `TASK-DEV-009`, then `TASK-DEV-021`: Ruff baseline, followed by truthful hook enforcement.
6. `TASK-DEV-006`: module-sized mypy burn-down.
7. `TASK-DEV-018` and `TASK-DEV-019`: production-build gate and honest coverage ratchet.
8. `TASK-DEV-016` + `TASK-DEV-022`: pnpm/toolchain/override standardization.
9. `TASK-DEV-023` + `TASK-DEV-026`: E2E breadth and frontend test-harness stability.
10. `TASK-DEV-020`, `TASK-DEV-028`, `TASK-DEV-008`, and runbook/manual follow-ups: approval-gated hygiene and reproducibility cleanup.

## Approval gate

No remediation, dependency change, gate relaxation, tracked-file deletion, or broad configuration change was performed in this phase. Approve or amend the execution order before remediation starts. During remediation, every batch will use focused RED/GREEN evidence where behavior is involved, keep one theme per commit, rerun affected gates, and update this report’s resolution status.

## Resolution register

|Task|Status|
|---|---|
|`TASK-DEV-024` dependency audit|Pending approval|
|`TASK-DEV-017` major PR triage|Pending approval|
|`TASK-DEV-025` local Redis bootstrap|Pending approval|
|`TASK-DEV-004` integration baseline|Pending approval|
|`TASK-DEV-009` Ruff baseline|Pending approval|
|`TASK-DEV-006` mypy baseline|Pending approval|
|`TASK-DEV-018` frontend build CI|Pending approval|
|`TASK-DEV-019` coverage policy|Pending approval|
|`TASK-DEV-016` pnpm standardization|Pending approval|
|`TASK-DEV-022` manifest/override hygiene|Pending approval|
|`TASK-DEV-023` E2E breadth|Pending approval|
|`TASK-DEV-020` artifacts|Pending approval|
|`TASK-DEV-026` test warnings|Pending approval|
|`TASK-DEV-028` Python dependency hygiene|Pending approval|
