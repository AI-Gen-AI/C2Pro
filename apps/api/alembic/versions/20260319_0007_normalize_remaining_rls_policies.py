"""TS-DB-MIG-REC-006

Normalize remaining legacy RLS policy names into Alembic ownership.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260319_0007"
down_revision: str | None = "20260319_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop legacy overlapping policy names already replaced by fail-closed policies."""
    op.execute('DROP POLICY IF EXISTS "Allow members to access their projects" ON projects;')
    op.execute('DROP POLICY IF EXISTS "Allow individual tenant access" ON tenants;')
    op.execute("DROP POLICY IF EXISTS tenant_self_only ON tenants;")
    op.execute('DROP POLICY IF EXISTS "Allow users to see themselves" ON users;')
    op.execute("DROP POLICY IF EXISTS tenant_isolation_ai_logs ON ai_usage_logs;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_raci ON stakeholder_wbs_raci;")


def downgrade() -> None:
    """Legacy policy cleanup is forward-only; no downgrade recreation is provided."""
