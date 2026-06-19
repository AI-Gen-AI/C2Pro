"""add_category_centroids

Revision ID: 4f92ed11a27b
Revises: 20260601_0001
Create Date: 2026-06-03 00:19:46.824229

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f92ed11a27b"
down_revision: str | None = "20260601_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the category_centroids table
    op.create_table(
        "category_centroids",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("score_version", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),  # Will be cast to vector(1536)
        sa.Column("seed_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "category", "embedding_model", "score_version", name="uq_category_centroids_key"
        ),
    )

    # Enable pgvector and cast the embedding column
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "ALTER TABLE category_centroids ALTER COLUMN embedding TYPE vector(1536) "
        "USING embedding::vector(1536)"
    )


def downgrade() -> None:
    op.drop_table("category_centroids")
