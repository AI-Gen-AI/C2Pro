"""#870: repair RLS on snapshot partition leaves created after P0-SEC-A.

Revision ID: 20261005_0002
Revises: 20261005_0001
Create Date: 2026-10-05

P0-SEC-A hardened the snapshot leaves that existed in September. The runtime
partition creator subsequently produced the October/November/December 2026
leaves without enabling RLS. This migration repairs exactly those known
post-hardening leaves. Runtime/ORM creation code is separately fixed so future
leaves are born with RLS enabled.

No policies are authored on leaves: direct-leaf access remains deny-by-default.
"""

from __future__ import annotations

from alembic import op

revision = "20261005_0002"
down_revision = "20261005_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261005000200_project_snapshot_partition_rls.sql"

RLS_REPAIR_TABLES: tuple[str, ...] = (
    "project_snapshots_2026_10",
    "project_snapshots_2026_11",
    "project_snapshots_2026_12",
    "project_snapshots_default",
)

UPGRADE_STATEMENTS: tuple[str, ...] = tuple(
    f"ALTER TABLE IF EXISTS public.{table} ENABLE ROW LEVEL SECURITY"
    for table in RLS_REPAIR_TABLES
)


def supabase_sql() -> str:
    """Render the Supabase CLI mirror from the same upgrade statements."""
    header = (
        "-- #870: repair RLS on snapshot partition leaves created after P0-SEC-A.\n"
        "-- Mirror of apps/api/alembic/versions/"
        "20261005_0002_project_snapshot_partition_rls.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return header + "\n" + "\n".join(
        statement.strip() + ";" for statement in UPGRADE_STATEMENTS
    ) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    """Security hardening is intentionally not reversed automatically.

    Disabling RLS would recreate the security defect. Emergency rollback
    requires an explicit reviewed security decision.
    """
