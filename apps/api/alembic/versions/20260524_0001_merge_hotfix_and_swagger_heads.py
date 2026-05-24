"""TS-QA-SWAGGER-MIGRATION-001: merge hotfix and Swagger migration heads.

Revision ID: 20260524_0001
Revises: 20260516_0004, 20260517_0002
Create Date: 2026-05-24
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260524_0001"
down_revision: tuple[str, str] = ("20260516_0004", "20260517_0002")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """TS-QA-SWAGGER-MIGRATION-001: no-op graph merge for Alembic single head."""


def downgrade() -> None:
    """TS-QA-SWAGGER-MIGRATION-001: no-op graph split handled by parent revisions."""
