"""Add document_chunks table for RAG

Revision ID: 20260315_0001
Revises: 20260225_0001
Create Date: 2026-03-15 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import ProgrammingError

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260315_0001"
down_revision: str = "20260310_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ensure_vector_extension() -> bool:
    bind = op.get_bind()
    # Use a separate connection with autocommit for CREATE EXTENSION
    # to prevent transaction abortion on permission errors.
    connection = bind.engine.connect().execution_options(autocommit=True)
    try:
        connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.commit()
        return True
    except ProgrammingError:
        connection.rollback()
        return False
    except Exception:
        connection.rollback()
        return False
    finally:
        connection.close()


def upgrade() -> None:
    vector_available = _ensure_vector_extension()

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

    # Alter embedding column to use vector type when available.
    if vector_available:
        op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")

    # Create indexes
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_project_id", "document_chunks", ["project_id"])

    # Create HNSW index and similarity helper only when vector is available.
    if vector_available:
        op.execute(
            """
            CREATE INDEX ix_document_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )

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
