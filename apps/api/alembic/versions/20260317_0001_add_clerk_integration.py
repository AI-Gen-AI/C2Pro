"""Add Clerk integration columns

Revision ID: clerk_integration
Revises: 20260310_0001_add_documents_tables
Create Date: 2026-03-17

Adds clerk_org_id to tenants and clerk_user_id to users
for Clerk authentication integration.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260317_clerk_int"
down_revision = "20260315_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add clerk_org_id to tenants
    op.add_column(
        "tenants",
        sa.Column("clerk_org_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_tenants_clerk_org_id",
        "tenants",
        ["clerk_org_id"],
        unique=True,
    )

    # Add clerk_user_id to users
    op.add_column(
        "users",
        sa.Column("clerk_user_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_users_clerk_user_id",
        "users",
        ["clerk_user_id"],
        unique=True,
    )


def downgrade() -> None:
    # Remove clerk_user_id from users
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.drop_column("users", "clerk_user_id")

    # Remove clerk_org_id from tenants
    op.drop_index("ix_tenants_clerk_org_id", table_name="tenants")
    op.drop_column("tenants", "clerk_org_id")
