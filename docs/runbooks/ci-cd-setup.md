# CI/CD Setup Guide

This document describes the GitHub Actions workflows and required secrets configuration for C2Pro.

## Workflows Overview

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | PR to main, Push to main | Run tests, linting, security checks |
| `deploy-staging.yml` | Push to main | Auto-deploy to staging |
| `deploy-production.yml` | Manual (workflow_dispatch) | Deploy to production with approval |

## Required GitHub Secrets

### Supabase

| Secret | Description | Environment |
|--------|-------------|-------------|
| `SUPABASE_URL` | Supabase project URL | All |
| `SUPABASE_ANON_KEY` | Supabase anonymous key | All |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | All |
| `SUPABASE_DB_URL_STAGING` | Database connection string | Staging |
| `SUPABASE_DB_URL_PRODUCTION` | Database connection string | Production |
| `SUPABASE_URL_PRODUCTION` | Production Supabase URL | Production |
| `SUPABASE_ANON_KEY_PRODUCTION` | Production anon key | Production |

### Railway (Backend)

| Secret | Description | Environment |
|--------|-------------|-------------|
| `RAILWAY_TOKEN` | Railway API token | Staging |
| `RAILWAY_TOKEN_PRODUCTION` | Railway API token | Production |

### Vercel (Frontend)

| Secret | Description | Environment |
|--------|-------------|-------------|
| `VERCEL_TOKEN` | Vercel API token | All |
| `VERCEL_ORG_ID` | Vercel organization ID | All |
| `VERCEL_PROJECT_ID` | Vercel project ID (staging) | Staging |
| `VERCEL_PROJECT_ID_PRODUCTION` | Vercel project ID (production) | Production |

### API URLs

| Secret | Description | Environment |
|--------|-------------|-------------|
| `STAGING_API_URL` | Backend API URL for staging | Staging |
| `PRODUCTION_API_URL` | Backend API URL for production | Production |

### External Services

| Secret | Description | Environment |
|--------|-------------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key | All |

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
