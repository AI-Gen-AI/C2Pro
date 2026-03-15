"""Add document_chunks table for RAG

Revision ID: 20260315_0001
Revises: 20260225_0001
Create Date: 2026-03-15 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260315_0001"
down_revision: str = "20260310_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create document_chunks table
    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),  # Will be cast to vector(1536)
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Alter embedding column to use vector type
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")

    # Create indexes
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_project_id", "document_chunks", ["project_id"])

    # Create HNSW index for fast similarity search
    op.execute(
        """
        CREATE INDEX ix_document_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Create match_documents function for similarity search
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_documents(
            query_project_id UUID,
            query_embedding vector(1536),
            match_count INT DEFAULT 5
        )
        RETURNS TABLE (
            content TEXT,
            metadata JSONB,
            distance FLOAT
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                dc.content,
                dc.metadata,
                (dc.embedding <=> query_embedding)::FLOAT AS distance
            FROM document_chunks dc
            WHERE dc.project_id = query_project_id
            ORDER BY dc.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS match_documents")
    op.drop_table("document_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")
