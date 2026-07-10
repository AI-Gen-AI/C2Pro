"""add pilot waitlist signups table.

Revision ID: 20260708_0001
Revises: 20260628_0001
Create Date: 2026-07-08

TASK-FRT-201: capture C2Pro pilot waitlist requests through the public web
route while keeping table access fail-closed for anon/authenticated roles.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260708_0001"
down_revision: str | None = "20260628_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waitlist_signups",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("volume", sa.Text(), nullable=True),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("locale", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'c2pro.io'"),
        ),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "volume IS NULL OR volume IN ('under_20','20_100','over_100')",
            name="ck_waitlist_signups_volume",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_waitlist_signups"),
        sa.UniqueConstraint("email", name="uq_waitlist_signups_email"),
    )
    op.execute("ALTER TABLE waitlist_signups ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("waitlist_signups")
