# Clerk Test Key Rotation Runbook

## Purpose

This runbook is the executable procedure for `TASK-1431`:

- rotate the already-exposed local Clerk test credentials
- redistribute fresh developer-only test keys through an approved secret channel
- update local workstations from sanitized templates instead of secret-bearing shared env files

This task is for development and test credentials only. It does not close production auth rollout tasks.

## Scope

This runbook covers:

- Clerk development or test instance key rotation
- local workstation update procedure
- validation that developers are using fresh test credentials from ignored local env files

This runbook does not authorize committing any secrets to the repository.

## Security Guardrails

- Do not paste new test keys into Git-tracked files.
- Do not paste new test keys into issues, PRs, chat transcripts, or docs.
- Distribute fresh test credentials only through an approved secret channel.
- Keep local developer values only in ignored files such as `apps/web/.env.local`.
- Use `apps/web/.env.example` as the setup template, not as a secret container.

## Preconditions

Before starting, confirm all of the following:

- you have operator access to the Clerk development or test instance
- you can revoke and regenerate the exposed test keys
- you have an approved secret-sharing channel for developers
- developers know that old local Clerk test keys must be removed from their workstations after rotation

## Rotation Procedure

### 1. Revoke exposed test credentials

In the Clerk development or test instance:

1. identify the currently exposed test publishable and secret keys
2. revoke or rotate them
3. confirm the old keys no longer authenticate successfully

Pass criteria:

- old `pk_test_...` and `sk_test_...` values are invalidated

Evidence:

- masked operator note showing old keys revoked
- Clerk dashboard screenshot without exposing full values

### 2. Generate fresh development credentials

In the same Clerk development or test instance:

1. generate new test publishable and secret keys
2. capture the required issuer and JWKS values

Required outputs:

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...`
- `CLERK_SECRET_KEY=sk_test_...`
- `CLERK_ISSUER=https://<instance>.clerk.accounts.dev`
- `CLERK_JWKS_URL=https://<instance>.clerk.accounts.dev/.well-known/jwks.json`

Pass criteria:

- new keys are different from the exposed ones
- new keys are usable only through approved distribution channels

### 3. Redistribute through approved secret channel

Send the fresh development credentials only through the approved secret channel.

Do not send:

- screenshots with full keys
- plaintext keys in normal team chat
- updates to tracked `.env`, `.env.example`, or docs

Pass criteria:

- developers receive the new values through the approved channel
- no repo file is modified to include real test credentials

### 4. Update local workstations

Each developer must:

1. open `apps/web/.env.example`
2. update or recreate ignored `apps/web/.env.local`
3. paste the new test keys into the ignored local file
4. remove any stale exposed values from previous local files or shell profiles if present

Minimum required local values:

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_ISSUER=https://<instance>.clerk.accounts.dev
CLERK_JWKS_URL=https://<instance>.clerk.accounts.dev/.well-known/jwks.json
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/projects
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL=/projects
```

Pass criteria:

- workstation uses fresh test keys only from ignored local env files
- sanitized templates remain non-secret

### 5. Validate local auth flow

From `apps/web` run:

```bash
npm run test:e2e -- src/tests/e2e/cross-browser-smoke.spec.ts --project cross-browser-chromium
```

Expected result:

- the smoke spec passes
- no auth failures occur due to revoked old test keys

Expected remaining warning:

- Clerk development-key warning is still expected in local development and does not indicate failure of this task

## Completion Criteria

`TASK-1431` can be marked complete only when all of the following are true:

- exposed old test keys are revoked
- fresh test keys are generated
- fresh keys are redistributed through an approved secret channel
- developers confirm local workstation update from ignored env files
- local smoke validation passes with fresh keys

## Evidence Template

Use this when closing the task:

```text
TASK-1431: PASS | Clerk test keys rotated and redistributed through approved secret channel

Evidence:
- old test keys revoked: <operator note or screenshot location>
- new test keys generated: <masked operator note>
- developer workstation update confirmed: <location>
- local smoke validation result: <location>
```

## Fast Failure Checks

Stop and do not mark the task complete if any of these are true:

- old exposed test keys still work
- new test keys were shared through a non-approved channel
- any tracked file now contains full test credentials
- local auth still relies on revoked test keys
