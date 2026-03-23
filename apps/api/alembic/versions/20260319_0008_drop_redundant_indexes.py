"""TS-DB-MIG-REC-007

Drop redundant legacy idx_* indexes after reconciliation.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260319_0008"
down_revision: str | None = "20260319_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop redundant idx_* indexes superseded by normalized ix_* indexes."""
    op.execute("DROP INDEX IF EXISTS public.idx_ai_logs_project;")
    op.execute("DROP INDEX IF EXISTS public.idx_ai_logs_tenant;")
    op.execute("DROP INDEX IF EXISTS public.idx_alerts_analysis;")
    op.execute("DROP INDEX IF EXISTS public.idx_alerts_project;")
    op.execute("DROP INDEX IF EXISTS public.idx_alerts_severity;")
    op.execute("DROP INDEX IF EXISTS public.idx_alerts_status;")
    op.execute("DROP INDEX IF EXISTS public.idx_alerts_clause;")
    op.execute("DROP INDEX IF EXISTS public.idx_analyses_project;")
    op.execute("DROP INDEX IF EXISTS public.idx_analyses_status;")
    op.execute("DROP INDEX IF EXISTS public.idx_audit_resource;")
    op.execute("DROP INDEX IF EXISTS public.idx_audit_tenant;")
    op.execute("DROP INDEX IF EXISTS public.idx_audit_user;")
    op.execute("DROP INDEX IF EXISTS public.idx_extractions_document;")
    op.execute("DROP INDEX IF EXISTS public.idx_extractions_type;")
    op.execute("DROP INDEX IF EXISTS public.idx_raci_stakeholder;")
    op.execute("DROP INDEX IF EXISTS public.idx_raci_wbs;")
    op.execute("DROP INDEX IF EXISTS public.idx_stakeholders_project;")
    op.execute("DROP INDEX IF EXISTS public.idx_stakeholders_quadrant;")
    op.execute("DROP INDEX IF EXISTS public.idx_stakeholders_clause;")
    op.execute("DROP INDEX IF EXISTS public.idx_users_clerk_user_id;")


def downgrade() -> None:
    """Redundant index cleanup is forward-only; no duplicate index recreation is provided."""
