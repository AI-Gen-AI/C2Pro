# CI/CD Setup Guide

This document describes the GitHub Actions workflows and required secrets configuration for C2Pro.

## Workflows Overview

| Workflow                | Trigger                    | Purpose                             |
| ----------------------- | -------------------------- | ----------------------------------- |
| `ci.yml`                | PR to main, Push to main   | Run tests, linting, security checks |
| `deploy-staging.yml`    | Push to main               | Auto-deploy to staging              |
| `deploy-production.yml` | Manual (workflow_dispatch) | Deploy to production with approval  |

## Required GitHub Secrets

### Supabase

| Secret                         | Description                | Environment |
| ------------------------------ | -------------------------- | ----------- |
| `SUPABASE_URL`                 | Supabase project URL       | All         |
| `SUPABASE_ANON_KEY`            | Supabase anonymous key     | All         |
| `SUPABASE_SERVICE_ROLE_KEY`    | Supabase service role key  | All         |
| `SUPABASE_DB_URL_STAGING`      | Database connection string | Staging     |
| `SUPABASE_DB_URL_PRODUCTION`   | Database connection string | Production  |
| `SUPABASE_URL_PRODUCTION`      | Production Supabase URL    | Production  |
| `SUPABASE_ANON_KEY_PRODUCTION` | Production anon key        | Production  |

### Railway (Backend)

| Secret                        | Description                        | Environment |
| ----------------------------- | ---------------------------------- | ----------- |
| `RAILWAY_TOKEN`               | Railway API token                  | Staging     |
| `RAILWAY_SERVICE_API_STAGING` | Railway backend service identifier | Staging     |
| `RAILWAY_TOKEN_PRODUCTION`    | Railway API token                  | Production  |

### Vercel (Frontend)

| Secret                         | Description                    | Environment |
| ------------------------------ | ------------------------------ | ----------- |
| `VERCEL_TOKEN`                 | Vercel API token               | All         |
| `VERCEL_ORG_ID`                | Vercel organization ID         | All         |
| `VERCEL_PROJECT_ID`            | Vercel project ID (staging)    | Staging     |
| `VERCEL_PROJECT_ID_PRODUCTION` | Vercel project ID (production) | Production  |

### API URLs

| Secret               | Description                    | Environment |
| -------------------- | ------------------------------ | ----------- |
| `STAGING_API_URL`    | Backend API URL for staging    | Staging     |
| `PRODUCTION_API_URL` | Backend API URL for production | Production  |

### External Services

| Secret              | Description    | Environment |
| ------------------- | -------------- | ----------- |
| `ANTHROPIC_API_KEY` | Claude API key | All         |

## How to Configure Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret**
4. Add each secret from the tables above

## Environment Protection Rules

For production deployments, configure environment protection:

1. Go to **Settings** > **Environments**
2. Create `production` environment
3. Enable **Required reviewers** and add approvers
4. Optionally enable **Wait timer** for deployment delay

## Workflow Details

### CI Workflow (`ci.yml`)

Runs on every PR and push to main:

1. **Backend Lint** - Ruff, Bandit security scan
2. **Backend Tests** - pytest with PostgreSQL service
3. **Security Tests** - CTO Gates validation (RLS, MCP)
4. **Frontend Lint** - ESLint, TypeScript check
5. **Frontend Build** - Next.js production build

### Staging Deployment (`deploy-staging.yml`)

Automatic deployment on push to main:

1. **Validate** - Check which components changed
2. **Migrate Database** - Run Supabase migrations (if changed)
3. **Deploy Backend** - Railway deployment + health check
4. **Deploy Frontend** - Vercel preview deployment

### Production Deployment (`deploy-production.yml`)

Manual trigger with approval:

1. **Pre-checks** - Version validation, staging health check
2. **Migrate Database** - Production migrations with backup
3. **Deploy Backend** - Railway production + extended health check
4. **Deploy Frontend** - Vercel production deployment
5. **Post-deploy** - Create Git tag, summary
6. **Rollback** - Notify on failure with rollback steps

## Leadership Gap Closure

- [x] `LEAD-GAP-RELEASE-GOVERNANCE` Define release promotion, rollback, and environment signoff workflow for staging-to-production releases.

## Release Promotion Workflow

Promotion path:

1. Code merges to `main` only after CI passes and required reviewers approve.
2. `deploy-staging.yml` deploys the changed backend/frontend services to staging.
3. Staging validation is executed against the changed surfaces: API health, frontend build/load, critical auth path, and any feature-specific smoke checks.
4. Release candidate evidence is assembled in `evidence/releases/<release-id>/` with commit SHA, workflow references, validation notes, performance results, and DR records.
5. Production deployment is triggered manually through `deploy-production.yml` only after the Gate 7 bundle is complete and required signoff is collected.

Promotion prerequisites:

- latest `main` commit is green in CI
- staging deployment is healthy
- release bundle exists at `evidence/releases/<release-id>/`
- `manifest.yaml` references the exact candidate commit SHA
- required suite matrix is green for backend, frontend, security, evaluation, and release-time I13 reliability validation
- no open Sev-1 or Sev-2 incident affecting release-critical systems
- rollback path is confirmed for the components being changed
- on-call coverage is confirmed per `docs/runbooks/incident-response.md`

## Environment Signoff Workflow

Required signoff before production:

| Area                 | Signoff Owner          | Required Confirmation                                                   |
| :------------------- | :--------------------- | :---------------------------------------------------------------------- |
| Staging health       | Team Alpha (Sentinel)  | deploy completed, health checks pass, infra dependencies stable         |
| Backend/API behavior | Team Bravo (Nexus)     | release-critical API flows verified, no blocking data or AI regressions |
| Frontend/user flows  | Team Charlie (Prism)   | protected routes, auth flows, and affected UI paths verified in staging |
| Release authority    | Engineering Leadership | evidence reviewed, rollback owner named, production window approved     |

Signoff rules:

- Signoff must be explicit in the release ticket, workflow summary, or designated release channel.
- Missing signoff from any required owner blocks production promotion.
- If the release touches only one surface, the unaffected teams may mark "no-impact reviewed" instead of full execution, but Engineering Leadership must still approve.

## Rollback Workflow

Rollback triggers:

- failed production health checks after deploy
- tenant isolation, auth, or security regression
- data-integrity concern during or after migration
- user-facing critical path unavailable after release
- Sev-1 or Sev-2 incident attributed to the fresh deployment

Rollback responsibilities:

| Area                | Rollback Owner                                   | Validation After Rollback                                       |
| :------------------ | :----------------------------------------------- | :-------------------------------------------------------------- |
| Database migrations | Team Alpha (Sentinel)                            | schema version stable, app reconnects, no integrity alarms      |
| Backend service     | Team Alpha (Sentinel) with service owner support | `/health` and worker health green, core API smoke checks pass   |
| Frontend deployment | Team Charlie (Prism)                             | application loads, auth path works, affected UI recovers        |
| Business validation | Team Bravo (Nexus)                               | analysis/coherence critical path works against restored runtime |

Rollback execution rules:

1. Do not retry the same production deploy until root cause is understood.
2. Declare rollback decision in the incident/release channel with owner and reason.
3. Restore the affected layer in this order when applicable: database safety first, backend second, frontend third.
4. Re-run critical health and smoke checks after rollback.
5. Record the rollback outcome and whether a new release candidate is required.

## Minimum Release Evidence

Each production release must retain:

- commit SHA / tag promoted
- staging validation result
- required suite matrix with workflow or artifact references
- Swagger workbook status and unresolved item list
- named release approver
- named product, security, and operations approvers
- named rollback owner
- performance acceptance record
- backup/restore verification record
- production deploy timestamp
- post-deploy validation result
- incident or rollback reference if anything deviated

Recommended bundle layout:

```text
evidence/releases/<release-id>/
├── manifest.yaml
├── signoff.md
├── performance.md
└── disaster-recovery.md
```

## Troubleshooting

### CI Fails on PR

1. Check the specific job that failed in GitHub Actions
2. Review the logs for error messages
3. Common issues:
   - Linting errors: Run `ruff check` locally
   - Test failures: Run `pytest` locally with same env vars
   - Build failures: Run `npm run build` locally

### Staging Deploy Fails

1. Check if migrations ran successfully
2. Verify Railway deployment status
3. Check health endpoint manually
4. Review Vercel deployment logs

### Production Deploy Fails

1. **DO NOT** re-run immediately
2. Check which step failed
3. If migrations failed, check Supabase dashboard
4. Use Railway/Vercel dashboards to rollback if needed
5. Create incident report

## Local Testing

To test workflows locally, use [act](https://github.com/nektos/act):

```bash
# Install act
brew install act  # macOS
# or
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run CI workflow
act pull_request

# Run with secrets
act -s SUPABASE_URL=xxx -s SUPABASE_ANON_KEY=xxx
```

---

Last Updated: 2026-03-22

Changelog:

- 2026-03-22: Added release promotion, rollback, and environment signoff workflow to close the release-governance leadership gap.
- 2026-02-13: Added metadata block during repository-wide docs format pass.
