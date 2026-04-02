# Clerk Authentication Runbook: Dev vs Production

## Purpose

This runbook is the executable procedure for closing:

- `TASK-1174` Clerk project configured in production environment
- `TASK-1175` Production Clerk keys use `pk_live_...` and `sk_live_...`
- `TASK-1176` Production domain and sign-in/sign-up URLs configured in Clerk
- `TASK-1177` Production email templates and sender verified in Clerk
- `TASK-1178` Frontend deployed with production variables
- `TASK-1179` Backend deployed and reachable from frontend

Use this document to execute production auth rollout, validate it, and capture closure evidence.

## Scope

This runbook covers:

- Clerk Production configuration
- Vercel production environment configuration
- Railway production environment configuration
- smoke tests for sign-in, sign-up, reset-password, and authenticated API flow
- evidence required to close the backlog tasks above

This runbook does not itself configure Clerk, Vercel, or Railway. It tells the operator what must be configured and how to validate completion.

## Security Guardrails

- Do not commit live credentials to `.env`, `.env.example`, `.env.staging`, or any other tracked file.
- Keep app-local developer credentials only in ignored files such as `apps/web/.env.local`.
- Use `apps/web/.env.example` as the sanitized bootstrap template for local web setup.
- Do not paste live `pk_live_...` or `sk_live_...` values into issues, PRs, or docs.
- Store production secrets only in the target secret manager or deployment platform.
- If any tracked environment file contains real secrets, treat that as a security incident and rotate them.

## Preflight

Before starting, confirm all of the following:

- you know the production frontend URL
- you know the production backend URL
- you know the Clerk production instance/domain
- you have operator access to Clerk Production, Vercel production, and Railway production
- backend migrations succeed from `apps/api`

Local backend bootstrap check:

```bash
cd apps/api
alembic upgrade head
```

If you run `alembic upgrade head` from repo root, Alembic will fail because `script_location` is resolved from `apps/api/alembic.ini`.

## Environment Matrix

### Local Development

Allowed indicators:

- `pk_test_...`
- `sk_test_...`
- `https://<instance>.clerk.accounts.dev`
- email sender `accounts.dev`
- subject containing `[Development]`

### Production

Required indicators:

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...`
- `CLERK_SECRET_KEY=sk_live_...`
- `CLERK_ISSUER=https://<production-clerk-domain>`
- `CLERK_JWKS_URL=https://<production-clerk-domain>/.well-known/jwks.json`
- production sender domain, not `accounts.dev`
- no `[Development]` markers in auth emails

### Deployment Targets

| System | Required values |
| ------ | --------------- |
| Clerk Production | live keys, production domain, allowed redirects, verified sender |
| Vercel Production | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, production API routing vars, no demo mode |
| Railway Production | `CLERK_SECRET_KEY`, `CLERK_ISSUER`, `CLERK_JWKS_URL`, database and backend runtime vars |

## Repository Readiness vs Production Completion

Repository wiring already exists, but that is not proof of production completion.

Implemented in repo:

- Clerk frontend provider exists in `apps/web/app/providers.tsx`
- protected routes exist in `apps/web/middleware.ts`
- sign-in page exists in `apps/web/app/(auth)/sign-in/[[...sign-in]]/page.tsx`
- sign-up page exists in `apps/web/app/(auth)/sign-up/[[...sign-up]]/page.tsx`
- backend Clerk settings exist in `apps/api/src/config.py`
- production deploy workflows exist in `.github/workflows/deploy-production.yml`

Not proven by repo alone:

- Clerk Production project exists and is active
- live keys are configured in production environments
- production domain/redirects are configured in Clerk
- production sender is verified
- deployed frontend is using live auth configuration
- deployed backend accepts production Clerk tokens end-to-end

## Task Closure Matrix

| Task | Definition of done | Required evidence |
| ---- | ------------------ | ----------------- |
| `TASK-1175` | live publishable and secret keys are provisioned in production secret stores | operator note or screenshot showing live-key presence without exposing full values |
| `TASK-1176` | production domain and auth redirect URLs are configured in Clerk | screenshot or operator note from Clerk dashboard |
| `TASK-1177` | production sender and templates are verified | test emails proving no `accounts.dev` and no `[Development]` |
| `TASK-1178` | production frontend uses production auth variables | live `/sign-in` and `/sign-up` validation plus deployment confirmation |
| `TASK-1179` | production backend accepts Clerk-authenticated requests from frontend | backend health check and authenticated frontend-to-backend request evidence |
| `TASK-1174` | all five subtasks above are complete and evidenced | completed matrix and smoke-test summary |

## Execution Order

Run these sections in order. Do not mark `TASK-1174` complete until all sections pass.

### 1. Complete `TASK-1175`: Provision live Clerk credentials

In Clerk Production:

1. Open the production project.
2. Retrieve or generate:
   - publishable key `pk_live_...`
   - secret key `sk_live_...`
3. Derive or copy:
   - `CLERK_ISSUER`
   - `CLERK_JWKS_URL`

Store them only in deployment platforms:

- Vercel Production:
  - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- Railway Production:
  - `CLERK_SECRET_KEY`
  - `CLERK_ISSUER`
  - `CLERK_JWKS_URL`

Pass criteria:

- no production deployment uses `pk_test_...`
- no production deployment uses `sk_test_...`

Evidence:

- operator note with masked key prefixes
- screenshot of secret presence without exposing full secrets

### 2. Complete `TASK-1176`: Configure production domain and redirects

In Clerk Production:

1. Set the primary production domain.
2. Configure allowed authentication URLs for:
   - `/sign-in`
   - `/sign-up`
3. Confirm redirects match the application behavior.

Application route references:

- `apps/web/app/(auth)/sign-in/[[...sign-in]]/page.tsx`
- `apps/web/app/(auth)/sign-up/[[...sign-up]]/page.tsx`

Pass criteria:

- the deployed production domain is registered in Clerk
- sign-in and sign-up redirects match the deployed frontend routes

Evidence:

- Clerk dashboard screenshot
- operator note with configured production URLs

### 3. Complete `TASK-1177`: Verify production email sender and templates

In Clerk Production:

1. Configure the sender domain.
2. Verify required DNS/domain ownership.
3. Review production templates for:
   - sign-up verification
   - sign-in from new device
   - password reset
4. Trigger test emails from the deployed production auth flow.

Pass criteria:

- sender is not `accounts.dev`
- email subject does not contain `[Development]`
- templates render as production templates

Evidence:

- screenshots of received emails
- operator note listing which flows were tested

### 4. Complete `TASK-1179`: Deploy and validate backend production auth

Configure Railway production environment:

- `CLERK_SECRET_KEY`
- `CLERK_ISSUER`
- `CLERK_JWKS_URL`
- `DATABASE_URL`
- other required runtime variables

Deploy backend using the production workflow or standard deployment path.

Health check:

```bash
curl --fail --silent --show-error "$PRODUCTION_API_URL/api/v1/health"
```

Pass criteria:

- production backend deploy succeeds
- health endpoint responds successfully
- backend accepts a production Clerk-authenticated request

Evidence:

- deployment log
- health check result
- authenticated API request result

### 5. Complete `TASK-1178`: Deploy and validate frontend production auth

Configure Vercel production environment:

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `NEXT_PUBLIC_API_URL` if used
- any proxy/backend routing variables required by the deployment model
- do not set `NEXT_PUBLIC_APP_MODE=demo`

Relevant runtime behavior:

- app auth provider: `apps/web/app/providers.tsx`
- protected route middleware: `apps/web/middleware.ts`
- backend proxy routing: `apps/web/app/api/[...proxy]/route-utils.ts`

Deploy frontend to production.

Pass criteria:

- `/sign-in` loads in production
- `/sign-up` loads in production
- app is not running demo mode
- frontend can initiate authenticated flow against production backend

Evidence:

- production deployment log
- screenshots of live sign-in and sign-up routes

### 6. Complete `TASK-1174`: Consolidated production auth proof

Run final smoke tests on the deployed production system:

1. sign up a new user
2. sign in with that user
3. request password reset
4. confirm email sender and subject are production-safe
5. access an authenticated application page
6. confirm frontend reaches backend successfully under authenticated session

Pass criteria:

- no dev indicators remain:
  - no `accounts.dev`
  - no `[Development]`
  - no `pk_test_...`
  - no `sk_test_...`
- `TASK-1175` through `TASK-1179` all have evidence

Evidence bundle:

- one smoke-test summary
- one screenshot set
- one operator note or ticket comment linking all evidence

## Smoke Test Checklist

- [ ] Production `/sign-in` loads
- [ ] Production `/sign-up` loads
- [ ] New user registration succeeds
- [ ] Verification/reset email arrives from production sender
- [ ] Existing user sign-in succeeds
- [ ] Authenticated page load succeeds after sign-in
- [ ] Frontend calls reach backend successfully
- [ ] Backend health endpoint returns success
- [ ] No `[Development]` or `accounts.dev` markers appear anywhere

## Fast Failure Checks

If any of these are true, stop and do not mark production auth complete:

- any environment still uses `pk_test_...` or `sk_test_...`
- Clerk issuer or JWKS points to `clerk.accounts.dev`
- auth emails still come from `accounts.dev`
- deployed frontend cannot load `/sign-in` or `/sign-up`
- backend health check fails
- authenticated frontend-to-backend flow fails

## Troubleshooting

### `FAILED: No 'script_location' key found in configuration.`

Cause:

- Alembic command was run from repo root instead of `apps/api`

Fix:

```bash
cd apps/api
alembic upgrade head
```

### I removed demo mode but still get development emails

Cause:

- frontend demo mode and Clerk environment are different concerns

Fix:

- migrate Clerk to production/live keys and verified sender

### Production frontend works but auth still behaves like development

Cause:

- Vercel or Railway production env still uses test Clerk values

Fix:

- re-check `TASK-1175`, `TASK-1178`, and `TASK-1179`

## Rollback

If production auth rollout fails after deployment:

1. stop marking any auth task complete
2. revert frontend or backend deployment through Vercel/Railway
3. restore previous production auth settings if they were known-good
4. keep collected failure evidence
5. open a blocker against `TASK-1174`

## Completion Record Template

Use this template when closing the tasks:

```text
TASK-1175: PASS | live keys configured in production secret stores
TASK-1176: PASS | production domain and redirect URLs configured in Clerk
TASK-1177: PASS | production sender/templates verified, no development markers
TASK-1178: PASS | frontend deployed with production vars, /sign-in and /sign-up validated
TASK-1179: PASS | backend deployed, health check and authenticated API flow validated
TASK-1174: PASS | aggregate production auth readiness complete

Evidence:
- Clerk dashboard screenshots: <location>
- Deployment logs: <location>
- Email screenshots: <location>
- Smoke test summary: <location>
```
