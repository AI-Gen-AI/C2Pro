# DevOps Tasks & Knowledge Base

**Category**: DevOps (DEV)
**Owner Role**: devops
**Last Updated**: 2026-07-14

**Quick Links**:
- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_devops.md)
- 📖 [CI/CD Runbook](../docs/runbooks/ci-cd-setup.md)

---

## Status View

**Pending Tasks**: 18 (`TASK-DEV-005`–`006`, `007` (partial), `008`, `015`, `016`–`019`, `021`–`026`, `028`–`030`)

**Completed**: `TASK-DEV-001` (Coherence subgraph standalone execution), `TASK-DEV-002` (Sentry DSN validation guard) — see [COMPLETED.md](COMPLETED.md) — `TASK-DEV-003` (CI/CD overhaul), `TASK-DEV-004` (backend-integration promoted to required gate ✅ 2026-07-16), `TASK-DEV-009` (ruff baseline clean + backend-lint required gate ✅ 2026-07-15), `TASK-DEV-010` (canonical OpenAPI baseline, below), `TASK-DEV-011` (Tenacity compatibility guard, below), `TASK-DEV-012` (PostCSS patch isolation, below), `TASK-DEV-013` (Python dependency audit repair, below), `TASK-DEV-014` (js-minor-patch group bump, below), `TASK-DEV-020` (artifact & junk purge + .gitignore gaps ✅ 2026-07-15), and `TASK-DEV-027` (2026-07-15 multi-agent re-audit, below).

---

## Active Tasks

### TASK-DEV-005: Fix i13 real-E2E fixture port → re-enable daily cron

**Priority**: P1 · **Owner**: backend · **Depends on**: —

`i13-real-e2e-scheduled.yml` failed 100% of daily runs since at least 2026-07-05: test setup connects to Postgres `5432` while `docker-compose.test.yml` exposes `5433` (`OSError: Connect call failed ('127.0.0.1', 5432)` at fixture setup in `tests/e2e/flows/test_i13_*`), i.e. a fixture ignores `DATABASE_URL`. The cron is paused (commented out in the workflow, dispatch still available). Fix the fixture, verify via `workflow_dispatch`, then uncomment the `schedule:` block.

### TASK-DEV-006: Clean mypy baseline → promote `backend-typecheck` to required gate

**Priority**: P1 (umbrella for EPIC-MYPY-STRICT — see backlogs/BCK_BACKEND.md) · **Owner**: backend · **Depends on**: TASK-DEV-003 (done)

`ci.yml` now runs `mypy src` (mypy 1.8.0, strict per `apps/api/pyproject.toml`) as an advisory job with the report in the step summary. Burn down the baseline (or adopt a baseline tool / relax strictness deliberately), then remove `continue-on-error: true` and add the job to `REQUIRED_JOBS` in `ci-status`. Expanded 2026-07-16 into a 22-task cross-owned WBS (TASK-DEV-031 Wave 0 + TASK-BCK-095…TASK-BCK-113 Waves 1–7 + TASK-QA-322/323) under EPIC-MYPY-STRICT.



### TASK-DEV-030: Enum semantics migration (str+Enum → StrEnum)

**Priority**: P2 · **Owner**: backend · **Depends on**: TASK-DEV-009

88 classes inherit `(str, Enum)` (ruff UP042), currently ignored + count-guarded at baseline 88. Migrating to `enum.StrEnum` is **not** blind-safe: `str(X.MEMBER)` changes from `"X.MEMBER"` to the member value, which can silently alter logs, f-strings, and serializers. Requires a per-enum audit of `str()`/f-string/serialization use, a semantic-preserving migration with regression guards, then removal of the `UP042` ignore (and the baseline guard) from `apps/api/pyproject.toml` + `ci.yml`.

### TASK-DEV-015: SonarCloud "New Code" quality debt cleanup

**Priority**: P3 · **Owner**: frontend · **Depends on**: —

Cognitive-complexity code smells (Reliability/Security rating C on new code) surfaced in `apps/web/app/(app)/raci/page.tsx`, `.../projects/page.tsx`, and `.../projects/[id]/budget/page.tsx` when the js-minor-patch fix commit (`TASK-DEV-014`, commit `15cb74cd`) edited those pages. Non-blocking; unrelated to dependencies. The SonarCloud quality gate on PR #223 failed pre-merge but is NON-BLOCKING and identical to the pre-merge failure on tip `c50ea946` (caused by the same pages edited, not the dependency bump itself). Status: not started.

### TASK-DEV-007: GitHub settings manual follow-ups (owner action)

**Priority**: P2 (was P0; core item done) · **Owner**: repo owner · **Depends on**: TASK-DEV-003 merged to main

Actions only the repo owner can do in GitHub settings — full instructions in `docs/runbooks/ci-cd-setup.md`:
- [x] Branch protection ruleset on `main`: **DONE** — active ruleset `Protect main` (id 18843913) verified 2026-07-14 via API: requires PR + required checks **`CI Status`** and **`gitleaks`**, non-fast-forward. (Legacy branch-protection API returns 404 because protection is ruleset-based — expected.)
- [x] Add `CODECOV_TOKEN` secret — verified present (set 2026-07-12).
- [x] `Production` environment: add Required reviewers — `AI-Gen-AI` already set (verified 2026-08-08).
- [x] Delete stale `staging` environment — already deleted (404 confirmed 2026-08-08).
- [x] Optional cleanup: delete now-unused secrets — `RAILWAY_TOKEN_PRODUCTION`, `VERCEL_TOKEN`, `PRODUCTION_API_URL`, `SUPABASE_*` not present in repo secrets (verified 2026-08-08).
- [x] Verify the Vercel project's install command uses pnpm — no `installCommand` override set; Vercel auto-detects pnpm from `pnpm-lock.yaml` (verified 2026-08-08).

### TASK-DEV-008: Repair corrupted Makefile `help`/`openapi` targets

**Priority**: P3 · **Owner**: devops · **Depends on**: —

The `openapi` target text is embedded *inside* the `help` recipe (Makefile lines 25–33, bad merge), so `make openapi` — documented in CLAUDE.md — does not exist and `make help` echoes garbage. Extract `openapi:` into a real target. CI does not depend on the Makefile, so this is DX-only. Fold into the TASK-DEV-016 Makefile overhaul (same file, one commit): also standardize `.venv` (targets currently activate `venv/` while setup creates `.venv/`) and migrate `docker-compose` → `docker compose`.

### TASK-DEV-016: npm→pnpm standardization (enforced end-to-end)

**Priority**: P1 · **Owner**: devops · **Depends on**: — · **Source**: `docs/audits/TECH_DEBT_AUDIT_2026-07-14.md` §4

Audit verdict: mixing is real but contained to human surfaces — Makefile (8 npm calls incl. `setup-frontend: npm install`, which bypasses `pnpm.overrides` security pins), `README.md` L147/177/180, `QUICK_START.md` ×5, `apps/web/README_SETUP.md` ×8 (incl. `npm install next-themes`), and `apps/web` script `verify:openspec: npm --prefix`. No stray lockfiles anywhere; CI/Husky/deploy are pnpm-pure. Plan: (1) guard first — root `preinstall: npx only-allow pnpm`, `engines` (node 22 / pnpm 10) in root+web, `.npmrc` `engine-strict=true`, `.nvmrc`; (2) Makefile → pnpm (with TASK-DEV-008 repair); (3) `verify:openspec` → `pnpm -w run`; (4) docs → pnpm (`npx supabase` → `pnpm exec supabase`); archived docs untouched. Verify: frozen install + frontend gates + make-target smoke + npm-grep gate.

### TASK-DEV-017: Dependabot major-bump queue triage (#233, #230, #227, green trio)

**Priority**: P1 · **Owner**: devops/backend · **Depends on**: — · **Source**: audit §3 P0-1..P0-3

`#233` bcrypt 4→5 and `#230` redis 5→8 fail required gates (stale vs main + likely real incompatibilities: passlib/bcrypt-5 API removal; redis-py three-major jump touching cache + rate limiter). Rebase → re-triage → fix-forward or defer-with-`dependabot.yml`-ignore. `#227` vite 8 hard-fails at install: root `pnpm.overrides` pins `vite 7.3.5` → `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH` (structural: any overridden package fails this way — governance fix in TASK-DEV-022). `#224`/`#225`/`#226` are GREEN majors awaiting a merge decision (pdfjs-dist needs behavioral validation of the PDF viewer).

### TASK-DEV-018: Add frontend production build to CI

**Priority**: P1 · **Owner**: devops · **Depends on**: — · **Source**: audit §3 P1-5

No CI job runs `next build`; only Vercel builds at deploy time, so build-only regressions surface post-merge. Add a build step/job to the frontend lane using the existing mock Clerk env (local build passes ~2 min), and/or make the Vercel preview check required in the ruleset. Update the workflow meta-tests accordingly.

### TASK-DEV-019: Coverage policy alignment (one enforced number)

**Priority**: P1 · **Owner**: devops · **Depends on**: — · **Source**: audit §3 P1-6

Three contradictory configs: ci.yml backend-unit runs `--cov-fail-under=0`; `apps/api/pyproject.toml` says `fail_under = 70`; `codecov.yml` targets 80% (statuses not required); vitest has no thresholds. Measure actuals first, then: enforce 70 in CI for backend (drop the `--cov-fail-under=0` override) and add vitest thresholds at measured actuals as a ratchet. Never lower an existing threshold.

### TASK-DEV-021: Husky pre-commit cannot fail on ruff — fix enforcement

**Priority**: P2 · **Owner**: devops · **Depends on**: TASK-DEV-009 (clean baseline first) · **Source**: audit §3 P2-3

Root cause of the "hook does not reliably run" note: `.husky/pre-commit` runs the ruff branch without `|| exit 1` and the script ends in `echo "✅ …"`, so it always exits 0 for Python-only changes (the ESLint branch does have `|| exit 1`). Fix after the ruff baseline is clean, and scope the check to staged files.

### TASK-DEV-022: Root package.json hygiene + single pnpm.overrides

**Priority**: P1 · **Owner**: devops · **Depends on**: — · **Source**: audit §3 P2-4 + P0-3

Root manifest is misleading: `"name": "package.json"`, unused runtime deps (next/react/recharts@^3-vs-web-@^2/@google/generative-ai/@sentry/react/lucide drift — only referenced by `context/experimental` and `docs/archive`), npm-style `overrides` duplicated beside `pnpm.overrides`, plus a third dead `overrides` block in `apps/web/package.json`. Collapse to a single root `pnpm.overrides`; per pin decide keep-as-security-pin (+ matching `dependabot.yml` ignore) vs drop; prune unused deps; rename package; regenerate lockfile; full frontend gates re-run. Extended 2026-07-15: also move `tailwindcss-animate` to devDependencies (build-time plugin, only used by tailwind.config.ts), audit the deprecated `openapi-typescript-codegen ^0.31.0` devDep (orval is the primary generator — remove if unused, else migrate to @hey-api/openapi-ts), and note that pnpm v11+ no longer reads `package.json#pnpm.overrides` (settings moved to pnpm-workspace.yaml) — keep overrides in the location our pinned pnpm 10.25.0 reads, and record the v11 migration caveat.

### TASK-DEV-023: Nightly full-E2E lane (27 of 29 Playwright spec files never run)

**Priority**: P2 · **Owner**: frontend/devops · **Depends on**: TASK-DEV-005 (i13 fixture) · **Source**: audit §3 P1-7

CI runs only 2 smoke specs; the rest rot invisibly and `document-analysis-pipeline.spec.ts` contains 5 state-conditional `test.skip(true, …)`. Add a scheduled (nightly) non-blocking workflow running the full suite with seeded data; triage conditional skips into deterministic tests or explicit quarantine.

### TASK-DEV-024: Restore the JavaScript dependency-audit gate

**Priority**: P0 · **Owner**: devops/security · **Depends on**: TASK-DEV-003 · **Source**: `docs/audits/TECH_DEBT_AUDIT_2026-07-15.md`

PR #233, PR #230, and local reproduction fail before producing a vulnerability result: pnpm reports `ERR_PNPM_AUDIT_BAD_RESPONSE` because the registry legacy audit endpoint returns HTTP 410. Validate a supported pnpm v10 patch against the bulk endpoint first; otherwise use an already-approved platform-native signal or request approval for a replacement tool. The acceptance criterion is a live audit that still blocks critical vulnerabilities, plus a workflow regression guard—not removal or weakening of the gate.

### TASK-DEV-025: Align local test-bootstrap Redis port contracts

**Priority**: P1 · **Owner**: devops/backend · **Depends on**: TASK-DEV-003 · **Source**: `docs/audits/TECH_DEBT_AUDIT_2026-07-15.md`

The canonical root test Compose file maps Redis to host port 6380, while `apps/api/scripts/bootstrap_test_infra.py` defaults to 6379. CI happens to provide a separate service container on 6379, masking the mismatch. Make local bootstrap derive or receive the canonical port, distinguish CI and local ports in the runbook, and protect the contract with a focused test.

### TASK-DEV-026: Remove frontend test-runner listener accumulation

**Priority**: P2 · **Owner**: frontend/qa · **Depends on**: — · **Source**: `docs/audits/TECH_DEBT_AUDIT_2026-07-15.md`

`pnpm test:all` is green (269 files, 849 tests) but repeatedly emits `MaxListenersExceededWarning`. Identify the setup/listener that accumulates across workers, add lifecycle cleanup and a focused regression, and retain the default listener limit so the warning cannot be merely hidden. Treat third-party CSS source-map warnings as a separate non-blocking signal.

### TASK-DEV-028: Python dependency and local-environment reproducibility

**Priority**: P2 · **Owner**: backend/devops · **Depends on**: — · **Source**: `docs/audits/TECH_DEBT_AUDIT_2026-07-15.md`

`apps/api/requirements.txt` contains two overlapping `psycopg[binary]` floors. The reused audit `.venv` also reports an orphaned `supafunc 0.4.7` versus httpx conflict even though fresh requirements resolution passes pip-audit and reports no known vulnerabilities. Recreate a clean venv, require `pip check` and `pip-audit` evidence, remove only the redundant bound under a focused requirements guard, and document the clean-bootstrap command. Any broader constraints/locking change needs separate approval.

### TASK-DEV-029: Phased TypeScript upgrade 5.3.3 → current 5.x

**Priority**: P2 · **Owner**: frontend · **Depends on**: — · **Source**: `docs/audits/TECH_DEBT_AUDIT_2026-07-15.md`

`apps/web/package.json` pins `typescript: "5.3.3"` (Jan 2024). Upgrade stepwise (5.4 → 5.5 → … → current), running `pnpm typecheck` and `pnpm build` at each step; land with per-step commits so any breaking type change bisects cleanly.

---

## Completed Tasks

### TASK-DEV-004: Fix backend integration suite → promote `backend-integration` to required gate ✅ 2026-07-16

**Priority**: P1 · **Owner**: backend · **Depends on**: TASK-DEV-003

24 failures → 0 (97 passed); root causes were tenant_id fixtures, WBS nested-set (`ck_wbs_nodes_lft_positive`), retired-router test contracts (alerts + langsmith), and tz-naive datetime columns. Fixed in #246; `backend-integration` promoted to REQUIRED_JOBS in ci.yml via #248.

---

### TASK-DEV-009: Clean ruff baseline → promote `backend-lint` to required gate ✅ 2026-07-15

**Priority**: P1 · **Owner**: backend · **Depends on**: —

206 violations cleaned in two steps: 97 via `ruff check --fix` + 24 manual fixes (PR #242). Remaining 88 are UP042 (`class X(str, Enum)`) — globally ignored with justification (StrEnum changes `str(member)` semantics) + CI baseline guard. `backend-lint` promoted to REQUIRED_JOBS. StrEnum migration tracked as TASK-DEV-030.

---

### TASK-DEV-020: Artifact & junk purge + .gitignore gaps ✅ 2026-07-15

**Priority**: P2 · **Owner**: devops · **Source**: audit §3 P2-1

268 tracked files removed in one commit + `.gitignore`/`apps/web/.gitignore` gaps closed. `blackboard.json` intentionally kept (40+ runtime references). DEV-021 (Husky `|| exit 1` fix) remains pending.

---

### TASK-DEV-027: Full repository health and technical-debt audit ✅ 2026-07-15

**Priority**: P1 · **Owner**: devops/reviewer · **Source**: owner-requested full repository audit

Completed diagnosis-only evidence collection across live `main` and open-PR CI, npm/pnpm consistency, backend CI-equivalent gates, frontend quality/build/test gates, Alembic/Supabase migration assets, dependency health, and tracked artifacts. The canonical report is `docs/audits/TECH_DEBT_AUDIT_2026-07-15.md`. No remediation, dependency change, gate relaxation, or tracked-file deletion was performed; execution is stopped at the owner approval gate.

### TASK-DEV-013: Repair advisory `pip-audit` invocation ✅ 2026-07-14

**Dependency**: `TASK-DEV-003` · **Test Suite ID**: `TS-CI-BACKEND-GUARDS-001`

**Verified root cause**: `.github/workflows/dependency-audit.yml` passed `--disable-pip` for an unhashed requirements file. pip-audit 2.10.1 rejected that combination before resolving or auditing packages. Adding `--no-deps` would have hidden transitive vulnerabilities.

**Minimal fix**: removed `--disable-pip` so pip-audit uses its normal dependency resolver. Added a focused workflow guard that requires the requirements audit command and forbids both `--disable-pip` and `--no-deps`.

**TDD and live evidence**: RED failed on the existing invalid flag. GREEN passed all 24 backend CI guards and focused Ruff. PR #237 then ran pip-audit successfully in 29 seconds and reported `No known vulnerabilities found`, proving the job evaluated the resolved dependency set instead of failing on CLI usage.

---

### TASK-DEV-014: Resolve conflicts and land js-minor-patch group bump ✅ 2026-07-14

**Dependency**: `TASK-SEC-DEPENDABOT-001` · **PR**: `#223`

**Verified root cause**: PR #223 carried the `js-minor-patch` group of 45 same-major updates on branch `dependabot/npm_and_yarn/js-minor-patch-7dfeb5d883`, with two remediation commits (`15cb74cd` TS-inference/API-client drift repair, `c50ea946` prettier drift repair). It went CONFLICTING against main after main advanced 7 commits.

**Minimal fix**: Resolved conflicts in two files — `apps/web/package.json` (chose `--ours`: our side had the newest same-major version of every dep; main's only web change `postcss ^8.5.18` was already satisfied) and `pnpm-lock.yaml` (regenerated via `pnpm install --lockfile-only`, validated with `pnpm install --frozen-lockfile`). Squash-merged to main as commit `e6f5028a`.

**TDD and live evidence**: Drift fixes verified INTACT post-merge via `pnpm typecheck` (exit 0), `pnpm lint` (exit 0), and `prettier --check` on all 3 generated API-client files (authentication.ts, documents.ts, frontend-support.ts). CI: all required checks green (Frontend Lint+Typecheck, Frontend Tests + API Drift, Frontend E2E, CodeQL, Dependency Review, pnpm audit, CI Status). SonarCloud quality gate failed but is NON-BLOCKING and PRE-EXISTING (identical failure on pre-merge tip `c50ea946` from cognitive-complexity code smells in raci/projects/budget pages edited by the TS-inference fix commit; NOT dependency-caused, NOT a regression from the merge).

---

### TASK-DEV-010: Canonical OpenAPI baseline after schema-stack upgrade ✅ 2026-07-14

**Dependency**: `TASK-DEV-003` · **Focused existing Test Suite ID**: `TS-INT-DOC-PROC-003`

**Verified root cause**: unrelated Python Dependabot PRs produced the same `docs/api/openapi.yaml` drift because commit `849558cb` upgraded FastAPI from 0.121.3 to 0.139.0 without regenerating the canonical artifact. CI generated with FastAPI 0.139.0, Pydantic 2.13.4, pydantic-core 2.46.4, Starlette 1.3.1, pydantic-settings 2.14.2, python-multipart 0.0.32, and PyYAML 6.0.3.

**Minimal fix**: regenerated only `docs/api/openapi.yaml` with that exact stack. The intentional schema delta removes six duplicate `HTTPBearer` entries, changes two upload fields from `format: binary` to `contentMediaType: application/octet-stream`, and adds Pydantic's `input`/`ctx` fields to `ValidationError`. No route or application behavior changed.

**TDD evidence**: RED was the existing `openapi-drift.yml` canonical comparison failing identically across unrelated PRs; GREEN is deterministic regeneration plus the focused canonical verification assets. The generator also reported a pre-existing duplicate worker-health operation ID, registered separately as `TASK-BCK-094` rather than expanding this fix.

---

### TASK-DEV-011: Tenacity patch-level compatibility guard ✅ 2026-07-14

**Dependency**: `TASK-SEC-DEPENDABOT-001` · **Test Suite ID**: `TASK-OPS-DOCFLOW-015`

**Verified root cause**: PR #232 safely raises Tenacity's lower bound from 9.1.2 to 9.1.4 while retaining `<10.0`, but `test_backend_ci_guards.py` asserted the entire old requirement string. The guard therefore rejected a compatible patch-level floor advance rather than detecting an actual runtime incompatibility.

**Minimal fix**: updated the requirement to `tenacity>=9.1.4,<10.0`, kept the Schemathesis dependency assertion, and split Tenacity into a semantic guard that enforces package identity, a lower bound of at least 9.1.2, and the `<10.0` major cap.

**TDD evidence**: RED failed only on the stale `tenacity>=9.1.2,<10.0` string. GREEN passed both focused requirement guards. With Tenacity 9.1.4, the two production modules constructing retry decorators (`analysis.adapters.ai.anthropic_client` and `core.ai.service`) imported successfully under the standard test bootstrap environment without network calls.

---

### TASK-DEV-012: Isolated PostCSS 8.5.17 patch update ✅ 2026-07-14

**Dependency**: `TASK-SEC-DEPENDABOT-001` · **PR**: `#228`

**Verified root cause**: `origin/main` consistently declared PostCSS 8.5.16 in the web manifest and direct lock importer. The only locally available Dependabot commit bundled PostCSS 8.5.17 with Vite 8.1.4, esbuild 0.28.1, and an 847-line lock rewrite, so reusing it would violate isolated patch-upgrade scope.

**Minimal fix**: updated only `apps/web/package.json` and the `apps/web` importer in `pnpm-lock.yaml` to 8.5.17. Existing 8.5.17 package metadata and snapshot were already present. The 8.5.16 package/snapshot remain because Tailwind 4.1.18 still references them.

**TDD evidence**: RED `pnpm install --lockfile-only --frozen-lockfile --offline --filter c2pro-web` reported exactly one manifest/lock mismatch for PostCSS. GREEN passed the same offline frozen-lockfile command after the two importer fields changed. No dependency tree was installed and no broad frontend build was claimed.

### TASK-DEV-003: CI/CD overhaul — consolidated PR pipeline, security scanning, tag-driven releases ✅ 2026-07-12

**Decisions** (owner-approved): platform auto-deploy stays the deploy path (Railway + Vercel on push to main; branch protection = deploy gate); artifact purge approved; qa-swarm off the PR path; i13 cron paused.

**What changed**:
- **New `ci.yml`** replaces `tests.yml`, `e2e-security-tests.yml`, `frontend-ci.yml`, `frontend-e2e.yml`: `detect-changes` (dorny/paths-filter) fans out backend/frontend/migrations lanes; single required **`CI Status`** join check; concurrency cancellation; per-job timeouts; least-privilege permissions; PRs run py3.11 only (3.12 leg on main pushes); Codecov upload wired (flag `backend`); new `backend-migrations` job applies the full Alembic chain from scratch + single-head assert on migration-touching PRs. Advisory jobs: `backend-integration` (TASK-DEV-004), `backend-typecheck` (TASK-DEV-006).
- **New security workflows**: `codeql.yml` (python + JS/TS, PR/main/weekly), `dependency-review.yml` (fail on high severity), `dependency-audit.yml` (pip-audit advisory + pnpm audit blocking on critical), `.github/dependabot.yml` (actions/pip/npm weekly, grouped minor-patch).
- **New `release.yml`** (tag `v*`): certify (tag on main + `CI Status` green + Gate 7 evidence validation when `evidence/releases/<tag>/` exists) → publish (GitHub Release with generated notes) behind `Production` environment. `deploy-production.yml` retired (was hard-broken: depended on the failing i13 dispatch).
- **Fixes**: `scheduled-drift-checks.yml` referenced deleted `tests/security/test_s5_stakeholders_hitl_observability_security.py` → failed 4×/day, 100% — dead reference removed; `qa-swarm.yml` pull_request mode removed (~4.5 min + Anthropic spend per backend PR push); duplicate gitleaks job dropped (secret-scan.yml is the single gate).
- **Hardening**: every third-party action SHA-pinned across all 14 workflows + 3 composite actions; concurrency groups and `permissions:` everywhere.
- **Extensibility**: composite actions `.github/actions/setup-python-backend` and `.github/actions/setup-node-web`; new-service recipe documented in the runbook.
- **Hygiene**: 1,495 tracked artifact files removed from the index (`.mypy_cache/` 1,418, `.pytest-tmp/` 65, `temp_conflicting_frontend_files/` 9, one each in `playwright-report/`, `test-results/`, `tmp-gh-artifacts/`); `.mypy_cache/` added to `.gitignore`.
- **Docs**: `docs/runbooks/ci-cd-setup.md` rewritten (trigger matrix, secrets, branch protection recipe, release process, extension guide); `.github/CICD_SETUP.md` reduced to a pointer.

**Meta-test retarget** (owner-approved follow-up in same task): backend CI-structure regression tests referenced the deleted workflows and would have failed the new pipeline's first backend run. Fixed: `tests/unit/test_backend_ci_guards.py` retargeted to `ci.yml` (3 path retargets + 2 pin-matchers loosened to `pnpm/action-setup@`/`setup-node@` prefixes for SHA pins), `tests/contract/test_graph_node_contracts.py` ADR-013 gate assertion retargeted to `ci.yml`, `tests/unit/test_ci_deploy_production_workflow.py` replaced by `tests/unit/test_ci_release_workflow.py` (guards release.yml: tag trigger, certify-before-publish, Production environment gate, evidence validation, i13/evaluation release-evidence wiring), `src/coherence/cache_keys.py` docstring workflow reference updated.

**Verification**: `actionlint` v1.7.12 — 0 findings across all workflows; `yaml.safe_load` clean on dependabot.yml + all composite actions; retargeted meta-tests pass locally (27 passed: test_backend_ci_guards.py + test_ci_release_workflow.py + ADR-013 gate assertion); ruff clean on touched Python files; run-history audit evidence: Scheduled Drift Checks 8/8 recent failures (deleted test), i13 8/8 failures (port 5432 vs 5433), integration suite red under the old `continue-on-error` mask.

### TASK-DEV-031: mypy Wave 0 — CI parity + baseline ratchet

**Priority**: P1 · **Owner**: devops · **Depends on**: TASK-DEV-003 · **Epic**: EPIC-MYPY-STRICT (umbrella TASK-DEV-006)

The `backend-typecheck` job installs only `mypy` (not the backend dependency graph), so with `ignore_missing_imports` it degrades missing types to `Any` and reports a weaker/different baseline than a full local run; it is also `continue-on-error: true` and pipes `mypy src | tee … || true`, swallowing the exit code. Fix: (1) install the full backend env via the `setup-python-backend` composite; (2) capture the real exit code (report published, result recorded); (3) generate a committed `mypy-baseline.txt` and gate on it so NEW type errors fail while the ~1,357 existing burn down per bounded context; (4) emit per-wave metrics. Keep the job advisory (not in REQUIRED_JOBS) until the baseline reaches zero — promotion is TASK-DEV-006 after TASK-QA-323. Do NOT relax `strict` or add blanket ignores.
