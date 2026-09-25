"""C2.5 — Cross-Tenant Admin / DLQ Boundary

Revision ID: 20260907_0001
Revises: 20260906_0002
Create Date: 2026-09-07

WHAT THIS ADDS
--------------
1. Capability role: c2pro_admin_ops (NOLOGIN, NOSUPERUSER, NOBYPASSRLS,
   NOCREATEROLE, non-owner).

2. Admin policies on dlq_failed_tasks targeted TO c2pro_admin_ops:
   - SELECT USING (true)
   - UPDATE (retry_count, status, updated_at, next_retry_at) USING (true)

3. Column-level UPDATE grant on exactly the columns modified by
   DLQService.increment_retry():
   retry_count, status, updated_at, next_retry_at

4. NO INSERT, DELETE, schema CREATE, unrelated table access.

NOT IN THIS MIGRATION
---------------------
- No LOGIN principal is created. The deployment/runtime LOGIN principal
  is an ops/deployment responsibility and receives membership in
  c2pro_admin_ops (capability role). In the disposable gate we create
  a synthetic LOGIN member to prove the design.

- No app.admin_ops GUC. The admin policy is evaluated via the capability
  role membership, not a GUC. The policy uses
  CURRENT_USER / has_role('c2pro_admin_ops') semantics.

ROLE BOOTSTRAP MODEL
--------------------
OWNER_BOOTSTRAP (not Alembic).

This migration does NOT create the c2pro_admin_ops capability role.
The owner/bootstrap step (analogous to C2 checkpoint boundary) provisions:

  c2pro_admin_ops
  - NOLOGIN
  - NOSUPERUSER
  - NOBYPASSRLS
  - NOCREATEROLE
  - non-owner

Production/deployment creates or supplies the LOGIN principal separately
and grants membership in c2pro_admin_ops.

No password or LOGIN secret in repository code.

This migration:
- REQUIRES c2pro_admin_ops to exist
- fails closed with explicit error if absent
- creates only policies/grants/schema-level contract
- never silently creates an elevated role
"""

from __future__ import annotations

from alembic import op

revision = "20260907_0001"
down_revision = "20260906_0002"
branch_labels = None
depends_on = None

_ADMIN_ROLE = "c2pro_admin_ops"
_TABLE = "dlq_failed_tasks"

# Columns modified by DLQService.increment_retry()
_RETRY_COLUMNS = ["retry_count", "status", "updated_at", "next_retry_at"]


def _require_admin_role() -> None:
    """Require c2pro_admin_ops role to exist; fail closed if absent.

    OWNER_BOOTSTRAP model: the capability role must be provisioned by the
    owner/bootstrap step before this migration runs (analogous to C2
    checkpoint boundary). If absent, fail with explicit actionable message.
    """
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_ADMIN_ROLE}') THEN
                RAISE EXCEPTION
                    'C2.5 OWNER_BOOTSTRAP REQUIRED: role c2pro_admin_ops does not exist. '
                    'Provision it before running this migration (analogous to C2 '
                    'checkpoint_bootstrap.py): '
                    'CREATE ROLE c2pro_admin_ops NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;';
            END IF;
        END $$;
        """
    )


def _apply_admin_policies() -> None:
    """Apply admin policies TO c2pro_admin_ops on dlq_failed_tasks."""
    # SELECT policy for cross-tenant list
    op.execute(
        f"""
        CREATE POLICY dlq_admin_select
        ON {_TABLE}
        FOR SELECT
        TO {_ADMIN_ROLE}
        USING (true);
        """
    )

    # UPDATE policy for retry (cross-tenant)
    op.execute(
        f"""
        CREATE POLICY dlq_admin_retry
        ON {_TABLE}
        FOR UPDATE
        TO {_ADMIN_ROLE}
        USING (true);
        """
    )


def _drop_admin_policies() -> None:
    """Drop admin policies from dlq_failed_tasks."""
    op.execute(f"DROP POLICY IF EXISTS dlq_admin_select ON {_TABLE}")
    op.execute(f"DROP POLICY IF EXISTS dlq_admin_retry ON {_TABLE}")


def _grant_admin_privileges() -> None:
    """Normalize and then grant minimum privileges to c2pro_admin_ops."""
    # First: normalize by deliberately revoking all existing direct table privileges
    op.execute(f"REVOKE ALL ON {_TABLE} FROM {_ADMIN_ROLE}")

    # SELECT on the table
    op.execute(f"GRANT SELECT ON {_TABLE} TO {_ADMIN_ROLE}")

    # Column-level UPDATE on exactly the columns modified by increment_retry()
    columns = ", ".join(_RETRY_COLUMNS)
    op.execute(f"GRANT UPDATE ({columns}) ON {_TABLE} TO {_ADMIN_ROLE}")

    # NO INSERT, DELETE, TRUNCATE, REFERENCES, TRIGGER
    # NO schema CREATE, no unrelated table access


def _revoke_admin_privileges() -> None:
    """Revoke privileges from c2pro_admin_ops."""
    op.execute(f"REVOKE ALL ON {_TABLE} FROM {_ADMIN_ROLE}")


def upgrade() -> None:
    """Apply admin policies and grants (requires pre-existing c2pro_admin_ops role)."""
    # Require capability role to exist (OWNER_BOOTSTRAP)
    _require_admin_role()

    # Apply admin policies
    _apply_admin_policies()

    # Grant minimum privileges
    _grant_admin_privileges()


def downgrade() -> None:
    """Remove admin policies and grants (does NOT drop role - owner responsibility)."""
    _revoke_admin_privileges()
    _drop_admin_policies()
    # Role is NOT dropped - owner/bootstrap is responsible for role lifecycle
