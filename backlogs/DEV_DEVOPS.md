# DevOps Tasks & Knowledge Base

**Category**: DevOps (DEV)
**Owner Role**: devops
**Last Updated**: 2026-07-12

**Quick Links**:
- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_devops.md)
- 📖 [CI/CD Runbook](../docs/runbooks/ci-cd-setup.md)

---

## Status View

**Pending Tasks**: 5 (TASK-DEV-004 … TASK-DEV-008)

**Completed**: `TASK-DEV-001` (Coherence subgraph standalone execution), `TASK-DEV-002` (Sentry DSN validation guard) — see [COMPLETED.md](COMPLETED.md) — and `TASK-DEV-003` (CI/CD overhaul, below).

---

## Active Tasks

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

### TASK-DEV-007: GitHub settings manual follow-ups (owner action)

**Priority**: P0 (branch protection) · **Owner**: repo owner · **Depends on**: TASK-DEV-003 merged to main

Actions only the repo owner can do in GitHub settings — full instructions in `docs/runbooks/ci-cd-setup.md`:
- [ ] Branch protection ruleset on `main`: require PR + required checks **`CI Status`** and **`gitleaks`** (optionally `Vercel`). `main` is currently UNPROTECTED — with platform auto-deploy this ruleset is the production deploy gate.
- [ ] Add `CODECOV_TOKEN` secret (from codecov.io) so backend coverage uploads work (upload is non-fatal meanwhile).
- [ ] `Production` environment: add Required reviewers (approval gate for `release.yml` publish).
- [ ] Delete stale `staging` environment.
- [ ] Optional cleanup: delete now-unused secrets `RAILWAY_TOKEN_PRODUCTION`, `VERCEL_TOKEN`, `PRODUCTION_API_URL`, `SUPABASE_*_PRODUCTION`/staging family.

### TASK-DEV-008: Repair corrupted Makefile `help`/`openapi` targets

**Priority**: P3 · **Owner**: devops · **Depends on**: —

The `openapi` target text is embedded *inside* the `help` recipe (Makefile lines 25–33, bad merge), so `make openapi` — documented in CLAUDE.md — does not exist and `make help` echoes garbage. Extract `openapi:` into a real target. CI does not depend on the Makefile, so this is DX-only.

---

## Completed Tasks

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

**Verification**: `actionlint` v1.7.12 — 0 findings across all workflows; `yaml.safe_load` clean on dependabot.yml + all composite actions; run-history audit evidence: Scheduled Drift Checks 8/8 recent failures (deleted test), i13 8/8 failures (port 5432 vs 5433), integration suite red under the old `continue-on-error` mask.
