# Runbooks

Operational procedures for development, testing, migrations, authentication, incidents and platform operation.

Runbooks describe **how to operate** an already-defined architecture. They do not override ADRs, Product Control or executable security policy.

## Core runbooks

- [Clerk auth — development vs production](./CLERK_AUTH_DEV_PROD_GUIDE.md)
- [Clerk test-key rotation](./CLERK_TEST_KEY_ROTATION_RUNBOOK.md)
- [Auth bootstrap fallback policy](./AUTH_BOOTSTRAP_FALLBACK_POLICY.md)
- [Database migration authority](./RUNBOOK_DATABASE_MIGRATION_AUTHORITY_2026-03-19.md)
- [Migration health check](./RUNBOOK_MIGRATION_HEALTH_CHECK_2026-02-15.md)
- [Test infrastructure bootstrap](./RUNBOOK_TEST_INFRA_BOOTSTRAP_2026-02-15.md)
- [I13 real E2E infrastructure](./I13_REAL_E2E_INFRA_RUNBOOK.md)
- [Backup and restore](./backup-restore.md)
- [CI/CD setup](./ci-cd-setup.md)
- [Incident response](./incident-response.md)
- [Migration sub-runbooks](./migrations/)
- [Supabase runbooks](./supabase/)

## Product qualification

The #715 production-qualification procedure is deliberately kept with the Product Control/qualification contract:

- [Production qualification operator runbook](../product/production-qualification-operator-runbook.md)
- [Qualification evidence contract](../product/qualification-evidence-contract-v1.md)

Do not adapt ordinary local/E2E shortcuts into that production procedure.

## Historical/configuration reports

Some older files in this directory are dated setup/configuration reports. Their original date is evidence context; verify them against current manifests before acting on them.

## Related

- [Documentation index](../README.md)
- [Architecture](../architecture/README.md)
- [Testing](../testing/README.md)
