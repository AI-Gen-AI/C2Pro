# CI/CD Runbook

How C2Pro's GitHub Actions CI/CD works: pipelines, triggers, secrets, environments, branch protection, the release process, and how to extend CI for new apps/services.

**Architecture in one paragraph**: deploys are platform-owned — Railway auto-deploys `apps/api` and Vercel auto-deploys `apps/web` on every push to `main` (Vercel also builds a preview per PR). The deploy gate is therefore **branch protection on `main`**: nothing merges without the required `CI Status` check. Releases are certified and published (tag + changelog + optional Gate 7 evidence validation) by `release.yml`, which does **not** deploy. All third-party actions are pinned to full commit SHAs; Dependabot keeps the pins fresh.

---

## Pipeline Overview

```
PR / push to main
│
├── ci.yml ──────────────── detect-changes (paths-filter)
│     ├─ backend lane (apps/api/** changed)
│     │    ├─ backend-lint          ruff                    ~40s   ADVISORY
│     │    ├─ backend-typecheck     mypy                    ~2m    ADVISORY
│     │    ├─ backend-unit          pytest unit + ADR/S5    ~3m    required
│     │    ├─ backend-security      multi-tenant isolation  ~3m    required
│     │    ├─ backend-integration   pytest integration      ~3m    ADVISORY
│     │    └─ backend-migrations    alembic from scratch    ~2.5m  required (only on migration changes)
│     ├─ frontend lane (apps/web/** changed)
│     │    ├─ frontend-quality      tsc + eslint + ADR-009  ~1.5m  required
│     │    ├─ frontend-test         vitest + orval drift    ~2m    required
│     │    └─ frontend-e2e-smoke    2 Playwright specs      ~3m    required
│     └─ ci-status ← THE single required branch-protection check
│
├── secret-scan.yml          gitleaks worktree scan         ~10s
├── openapi-drift.yml        spec ↔ runtime drift           ~1m    (backend paths)
├── wireframe-coverage.yml   TC coverage gate               ~30s   (web paths)
├── evaluation-regression.yml eval suites                   ~1m    (eval paths)
├── golden-corpus-evals.yml  15-bundle corpus               ~1m    (evals/** paths)
├── codeql.yml               SAST python + JS/TS            ~4-8m  (not required yet)
├── dependency-review.yml    new-dep vulnerability gate     ~20s
└── dependency-audit.yml     pip-audit + pnpm audit         (dep-file changes only)

push to main additionally:  Railway deploy (api) + Vercel deploy (web) [platform-side]
tag v* :                    release.yml → certify → [Production approval] → GitHub Release
```

Typical PR wall-clock: **~3–3.5 min** (docs-only PRs: **<1 min** — every lane skips). Path filtering happens *inside* `ci.yml` via the `detect-changes` job so that `ci-status` always reports — required checks must never be left "expected" forever by a `paths:`-filtered workflow.

## Trigger Matrix

| Workflow | PR | push main | schedule | dispatch | tag |
|---|---|---|---|---|---|
| `ci.yml` | ✓ | ✓ (+py3.12 leg) | — | ✓ (runs all lanes) | — |
| `secret-scan.yml` | ✓ | ✓ (+`feat/**`) | — | — | — |
| `openapi-drift.yml` | ✓ (backend paths) | — | — | ✓ | — |
| `wireframe-coverage.yml` | ✓ (web paths) | — | — | — | — |
| `evaluation-regression.yml` | ✓ (eval paths) | ✓ (eval paths) | daily 05:00 | ✓ | — |
| `golden-corpus-evals.yml` | ✓ (`evals/**`) | ✓ (`evals/**`) | — | ✓ | — |
| `codeql.yml` | ✓ | ✓ | weekly Mon | — | — |
| `dependency-review.yml` | ✓ | — | — | — | — |
| `dependency-audit.yml` | ✓ (dep files) | — | weekly Mon | ✓ | — |
| `qa-swarm.yml` | — | — | weekly Mon | ✓ | — |
| `scheduled-drift-checks.yml` | — | — | every 6h | ✓ | — |
| `i13-real-e2e-scheduled.yml` | — | — | **paused** | ✓ | — |
| `real-document-operability.yml` | — | — | — | ✓ (operator) | — |
| `release.yml` | — | — | — | ✓ | ✓ `v*` |

## Advisory (non-blocking) jobs

Three jobs run but do not gate merges. All are tracked in `backlogs/DEV_DEVOPS.md`:

| Job | Why advisory | How to promote to required |
|---|---|---|
| `backend-integration` | 14 failures + 10 errors pre-existing on main (sqlalchemy pool teardown), previously hidden by `continue-on-error` | Fix the suite (TASK-DEV-004), then move the job entry from `ADVISORY_JOBS` to `REQUIRED_JOBS` in the `ci-status` gate step of `ci.yml` |
| `backend-typecheck` (mypy) | strict-mode baseline never enforced; large error count expected | Clean the baseline (TASK-DEV-006), then remove `continue-on-error: true` and move it into `REQUIRED_JOBS` |
| `backend-lint` (ruff) | ~57 pre-existing violations under ruff==0.2.1 (`ruff check .` was never a CI gate; the Husky pre-commit hook does not reliably run) | Clean the baseline — 35 of 57 are `--fix`-able (TASK-DEV-009) — then move it into `REQUIRED_JOBS` |

## Required Secrets and Variables

Configure under **Settings → Secrets and variables → Actions**.

| Name | Kind | Used by | Notes |
|---|---|---|---|
| `CLERK_SECRET_KEY` | secret | ci.yml (frontend-test, e2e-smoke) | E2E smoke skips gracefully if absent |
| `CLERK_TESTING_TOKEN` | secret | ci.yml (e2e-smoke) | Alternative to secret key for Playwright |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | secret or variable | ci.yml frontend lane | Falls back to a mock `pk_test_…` value |
| `CODECOV_TOKEN` | secret | ci.yml (backend-unit) | **New** — upload is non-fatal if missing |
| `ANTHROPIC_API_KEY` | secret | qa-swarm, evaluation-regression | Real API spend — schedule/dispatch only |
| `LANGSMITH_API_KEY` | secret | evaluation-regression | Tracing for eval runs |
| `SLACK_WEBHOOK_URL` | secret | evaluation-regression (drift notify) | Optional |
| `DRIFT_ALERT_WEBHOOK_URL` | secret | scheduled-drift-checks | Optional escalation hook |

No longer needed by any workflow (were used by the retired `deploy-production.yml`): `RAILWAY_TOKEN_PRODUCTION`, `VERCEL_TOKEN`, `PRODUCTION_API_URL`, and the `SUPABASE_*_PRODUCTION` / staging family. Safe to delete from repo secrets.

## GitHub Environments

| Environment | Purpose | Action needed |
|---|---|---|
| `Production` | Approval gate for `release.yml` → publish | Add **Required reviewers** so releases pause for a human |
| `Preview` / `c2pro-api / production` | Created by the Vercel / Railway GitHub apps | Leave alone |
| `staging` | Leftover from deleted `deploy-staging.yml` | Delete |

## Branch Protection for `main` (do this — currently unprotected)

**Settings → Branches → Add branch ruleset** (or classic protection rule) for `main`:

1. Require a pull request before merging (approvals: per team size; 0 is acceptable solo, the check gate still applies).
2. Require status checks to pass:
   - **`CI Status`** (the `ci-status` join job — the only check from `ci.yml` you should require)
   - **`gitleaks`** (from Secret Scan)
   - Optionally **`Vercel`** (preview build = the frontend production-build gate; CI deliberately does not duplicate `next build`)
3. Block force pushes (default in rulesets).
4. Do **not** require individual lane jobs (`backend-unit`, etc.) — they legitimately skip on unrelated changes; `CI Status` accounts for that.

With auto-deploy on `main`, this ruleset *is* the production deploy gate.

## Deploys, Migrations, Rollback

- **Railway** (`c2pro-api` project, `C2Pro` service): builds from GitHub `apps/api` (Railpack), health check `/api/v1/health`. `start.sh` runs `alembic upgrade head` at boot — migrations apply on every backend deploy.
- **Vercel** (`v0-c2-pro` → c2pro.io): Git integration on `main`; PR pushes build preview deployments.
- **Migration safety in CI**: any PR touching `apps/api/alembic/**` or `supabase/migrations/**` triggers `backend-migrations`, which recreates a scratch Postgres, applies the full chain from zero, and asserts a **single Alembic head** (the dual-head crash-loop of 2026-06 is now a PR-time failure).
- **Rollback**: use the platform dashboards (Railway → previous deployment → Redeploy; Vercel → Deployments → Promote previous). For migration rollbacks follow `docs/runbooks/RUNBOOK_DATABASE_MIGRATION_AUTHORITY_2026-03-19.md`. Database safety first, backend second, frontend third. Do not retry a failed deploy until root cause is understood.

## Release Process

```bash
git tag v1.2.3 <sha-on-main>
git push origin v1.2.3        # → release.yml
```

1. **certify** — verifies the tag commit is on `main`, its `CI Status` check succeeded, and (if `evidence/releases/<tag>/` exists) validates the Gate 7 bundle via `scripts/validate_release_evidence.py`.
2. **publish** — waits for `Production` environment approval (if reviewers configured), then creates the GitHub Release with auto-generated notes (PR-based; conventional-commit titles keep them readable).

Manual path: **Actions → Release → Run workflow** with the tag name; `allow_missing_ci` exists as an escape hatch for pre-overhaul commits that have no `CI Status` check.

Gate 7 evidence bundles keep their existing layout (`manifest.yaml`, `signoff.md`, `performance.md`, `disaster-recovery.md`) under `evidence/releases/<tag>/` — name the bundle directory after the tag to get automatic validation. The signoff/rollback-owner governance defined in the 2026-03-22 release-governance pass still applies; the promotion mechanics changed (staging deploys and CLI-driven production deploys were retired), the accountability model did not.

## Adding CI for a New App/Service (Phase 3+)

Everything is additive — no pipeline rewrites:

1. **Filter**: add a key in `detect-changes` (in `ci.yml`), e.g. `worker: ["apps/worker/**"]`, and expose it in the job `outputs`.
2. **Jobs**: add lane jobs with `needs: detect-changes` + `if: needs.detect-changes.outputs.worker == 'true'`. Reuse the setup composites:
   - `.github/actions/setup-python-backend` (Python toolchain + libmagic + cached pip install)
   - `.github/actions/setup-node-web` (pnpm + Node + frozen install)
   For a new Python service, generalize the composite with an input for the requirements path rather than duplicating it.
3. **Gate**: add the new jobs to `ci-status.needs` **and** to `REQUIRED_JOBS` (or `ADVISORY_JOBS` while stabilizing) in the gate step.
4. **Security**: if it's a new language, add it to the `codeql.yml` matrix; if it has its own manifest, add a `dependabot.yml` entry and a path in `dependency-audit.yml`.
5. Branch protection needs no change — `CI Status` already covers the new lane.

## Scheduled Workflow Health

| Workflow | Cadence | State (2026-07-12) |
|---|---|---|
| evaluation-regression | daily 05:00 | green |
| scheduled-drift-checks | every 6h | fixed in the CI/CD overhaul (was failing 100% on a deleted-test reference) |
| qa-swarm | weekly Mon 02:00 | opens draft PRs with generated tests; consumes `ANTHROPIC_API_KEY` |
| dependency-audit | weekly Mon 06:00 | new |
| codeql | weekly Mon 03:26 | new |
| i13-real-e2e-scheduled | **paused** | fixture connects to Postgres 5432 instead of 5433 — re-enable the cron in the workflow after the app-side fix (`backlogs/DEV_DEVOPS.md`) |

## Troubleshooting

- **`CI Status` failed but all visible jobs are green** — a required lane was *cancelled* (e.g. superseded push race). Re-run the workflow.
- **Lint/type failures**: `cd apps/api && ruff check .` / `mypy src`; frontend `pnpm typecheck && pnpm lint` in `apps/web`.
- **backend-security / backend-integration infra failures**: reproduce with `python apps/api/scripts/bootstrap_test_infra.py --start-services --require-redis --recreate-db`, then run the pytest command from the job. Postgres runs on **5433** (`docker-compose.test.yml`), Redis on 6379 (service container in CI).
- **openapi-drift failures**: `make openapi` (or `python apps/api/scripts/generate_openapi.py`) and commit, or add `[openapi]` to the commit message when intentional.
- **E2E smoke skipped**: `CLERK_SECRET_KEY` / `CLERK_TESTING_TOKEN` not configured for that run context (expected on forks).
- **Workflow lint before pushing workflow changes**: `actionlint` (all workflows are actionlint-clean as of the overhaul).

---

Last Updated: 2026-07-12

Changelog:

- 2026-07-12: Full rewrite for the CI/CD overhaul — consolidated ci.yml + ci-status gate, SHA-pinned actions, CodeQL/dependency-review/dependency-audit/dependabot added, release.yml (tag-driven certification, platform-owned deploys), deploy-production.yml retired, artifact purge, advisory-job policy, extension recipe.
- 2026-03-22: Added release promotion, rollback, and environment signoff workflow to close the release-governance leadership gap.
- 2026-02-13: Added metadata block during repository-wide docs format pass.
