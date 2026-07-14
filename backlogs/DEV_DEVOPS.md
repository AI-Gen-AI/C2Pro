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

**Pending Tasks**: 7 (`TASK-DEV-004` … `TASK-DEV-009`, `TASK-DEV-013`)

**Completed**: `TASK-DEV-001` (Coherence subgraph standalone execution), `TASK-DEV-002` (Sentry DSN validation guard) — see [COMPLETED.md](COMPLETED.md) — `TASK-DEV-003` (CI/CD overhaul), `TASK-DEV-010` (canonical OpenAPI baseline, below), `TASK-DEV-011` (Tenacity compatibility guard, below), and `TASK-DEV-012` (PostCSS patch isolation, below).

---

## Active Tasks

### TASK-DEV-013: Repair advisory `pip-audit` invocation

**Priority**: P1 · **Owner**: devops · **Depends on**: TASK-DEV-003 (done)

PR #235 verified that `.github/workflows/dependency-audit.yml` invokes `pip-audit -r apps/api/requirements.txt --disable-pip`. With the unhashed requirements file, pip-audit 2.10.1 exits before auditing because `--disable-pip` requires either hashes or `--no-deps`. Add a focused workflow guard, choose an invocation that preserves transitive dependency resolution, and verify that the advisory lane produces an actual vulnerability report rather than a CLI-usage failure.

---

### TASK-DEV-004: Fix backend integration suite → promote `backend-integration` to required gate

**Priority**: P1 · **Owner**: backend · **Depends on**: TASK-DEV-003 (done)

The integration suite fails on main (as of 2026-07-12: `14 failed, 74 passed, 3 skipped, 10 errors` — sqlalchemy pool teardown, error code `gkpj`). The old `tests.yml` hid this behind `continue-on-error: true`; the new `ci.yml` runs it as a visible **advisory** job. Fix the suite, then move `backend-integration` from `ADVISORY_JOBS` to `REQUIRED_JOBS` in the `ci-status` gate step of `.github/workflows/ci.yml`.

**Checklist**:
- [ ] `pytest tests/integration/` green locally against `bootstrap_test_infra.py` infra
- [ ] `backend-integration` green in CI on a PR
- [ ] Job moved to `REQUIRED_JOBS`; advisory comment removed from `ci.yml`

### TASK-DEV-005: Fix i13 real-E2E fixture port → re-enable daily cron

**Priority**: P1 · **Owner**: backend · **Depends on**: —

`i13-real-e2e-scheduled.yml` failed 100% of daily runs since at least 2026-07-05: test setup connects to Postgres `5432` while `docker-compose.test.yml` exposes `5433` (`OSError: Connect call failed ('127.0.0.1', 5432)` at fixture setup in `tests/e2e/flows/test_i13_*`), i.e. a fixture ignores `DATABASE_URL`. The cron is paused (commented out in the workflow, dispatch still available). Fix the fixture, verify via `workflow_dispatch`, then uncomment the `schedule:` block.

### TASK-DEV-006: Clean mypy baseline → promote `backend-typecheck` to required gate

**Priority**: P2 · **Owner**: backend · **Depends on**: TASK-DEV-003 (done)

`ci.yml` now runs `mypy src` (mypy 1.8.0, strict per `apps/api/pyproject.toml`) as an advisory job with the report in the step summary. Burn down the baseline (or adopt a baseline tool / relax strictness deliberately), then remove `continue-on-error: true` and add the job to `REQUIRED_JOBS` in `ci-status`.



### TASK-DEV-009: Clean ruff baseline → promote `backend-lint` to required gate

**Priority**: P2 · **Owner**: backend · **Depends on**: —

`ruff check .` (ruff==0.2.1, config in `apps/api/pyproject.toml`) reports ~57 pre-existing violations across `apps/api` (SIM105/SIM102 in src, I001/F401/F841/E402 mostly in tests, plus stray root files `test.py` / `test_document_repository.py`); 35 are `--fix`-able. It was never a CI gate before TASK-DEV-003 and the Husky pre-commit hook does not reliably run (verified: local commits passed while `ruff check .` fails). `ci.yml` runs `backend-lint` as advisory. Fix the violations (or explicitly ignore rules that are deliberate), then move `backend-lint` from `ADVISORY_JOBS` to `REQUIRED_JOBS` in `ci-status`.

### TASK-DEV-008: Repair corrupted Makefile `help`/`openapi` targets

**Priority**: P3 · **Owner**: devops · **Depends on**: —
### TASK-DEV-007: GitHub settings manual follow-ups (owner action)

**Priority**: P0 (branch protection) · **Owner**: repo owner · **Depends on**: TASK-DEV-003 merged to main

Actions only the repo owner can do in GitHub settings — full instructions in `docs/runbooks/ci-cd-setup.md`:
- [ ] Branch protection ruleset on `main`: require PR + required checks **`CI Status`** and **`gitleaks`** (optionally `Vercel`). `main` is currently UNPROTECTED — with platform auto-deploy this ruleset is the production deploy gate.
- [ ] Add `CODECOV_TOKEN` secret (from codecov.io) so backend coverage uploads work (upload is non-fatal meanwhile).
- [ ] `Production` environment: add Required reviewers (approval gate for `release.yml` publish).
- [ ] Delete stale `staging` environment.
- [ ] Optional cleanup: delete now-unused secrets `RAILWAY_TOKEN_PRODUCTION`, `VERCEL_TOKEN`, `PRODUCTION_API_URL`, `SUPABASE_*_PRODUCTION`/staging family.
The `openapi` target text is embedded *inside* the `help` recipe (Makefile lines 25–33, bad merge), so `make openapi` — documented in CLAUDE.md — does not exist and `make help` echoes garbage. Extract `openapi:` into a real target. CI does not depend on the Makefile, so this is DX-only.

---

## Completed Tasks

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
