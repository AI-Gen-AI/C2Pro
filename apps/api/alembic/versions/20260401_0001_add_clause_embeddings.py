"""Add clause_embeddings table for Coherence Engine RAG

Revision ID: 20260401_0001
Revises: 20260321_0002
Create Date: 2026-04-01 10:00:00.000000

Suite ID: TS-DB-MIG-REC-008

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260401_0001"
down_revision: str = "20260321_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create clause_embeddings table for coherence engine
    op.create_table(
        "clause_embeddings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("clause_id", sa.String(255), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "document_type",
            sa.String(50),
            nullable=False,
            server_default="other",
        ),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding", sa.Text(), nullable=False),  # Will be cast to vector(1536)
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
            server_default="SCOPE",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Unique constraint on clause_id + project_id to prevent duplicates
        sa.UniqueConstraint("clause_id", "project_id", name="uq_clause_embeddings_clause_project"),
    )

    # Alter embedding column to use vector type
    op.execute(
        "ALTER TABLE clause_embeddings ALTER COLUMN embedding TYPE vector(1536) "
        "USING embedding::vector(1536)"
    )

    # Create indexes for efficient queries
    op.create_index("ix_clause_embeddings_clause_id", "clause_embeddings", ["clause_id"])
    op.create_index("ix_clause_embeddings_project_id", "clause_embeddings", ["project_id"])
    op.create_index("ix_clause_embeddings_document_id", "clause_embeddings", ["document_id"])
    op.create_index("ix_clause_embeddings_category", "clause_embeddings", ["category"])
    op.create_index("ix_clause_embeddings_document_type", "clause_embeddings", ["document_type"])

    # Create HNSW index for fast cosine similarity search
    # m=16, ef_construction=64 are good defaults for medium-size datasets
    op.execute(
        """
        CREATE INDEX ix_clause_embeddings_embedding_hnsw
        ON clause_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Create function for finding similar clauses
    op.execute(
        """
        CREATE OR REPLACE FUNCTION find_similar_clauses(
            query_project_id UUID,
            query_embedding vector(1536),
            similarity_threshold FLOAT DEFAULT 0.85,
            top_k INT DEFAULT 10,
            filter_categories TEXT[] DEFAULT NULL,
            filter_document_types TEXT[] DEFAULT NULL,
            exclude_clause_ids TEXT[] DEFAULT NULL
        )
        RETURNS TABLE (
            clause_id TEXT,
            document_id UUID,
            document_type TEXT,
            text TEXT,
            category TEXT,
            metadata JSONB,
            similarity_score FLOAT
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                ce.clause_id,
                ce.document_id,
                ce.document_type,
                ce.text,
                ce.category,
                ce.metadata,
                (1 - (ce.embedding <=> query_embedding))::FLOAT AS similarity_score
            FROM clause_embeddings ce
            WHERE ce.project_id = query_project_id
                AND (1 - (ce.embedding <=> query_embedding)) >= similarity_threshold
                AND (filter_categories IS NULL OR ce.category = ANY(filter_categories))
                AND (filter_document_types IS NULL OR ce.document_type = ANY(filter_document_types))
                AND (exclude_clause_ids IS NULL OR ce.clause_id != ALL(exclude_clause_ids))
            ORDER BY ce.embedding <=> query_embedding
            LIMIT top_k;
        END;
        $$
        """
    )

    # Create function for finding cross-document pairs
    op.execute(
        """
        CREATE OR REPLACE FUNCTION find_cross_document_pairs(
            query_project_id UUID,
            similarity_threshold FLOAT DEFAULT 0.85,
            max_pairs INT DEFAULT 20
        )
        RETURNS TABLE (
            source_clause_id TEXT,
            target_clause_id TEXT,
            source_document_type TEXT,
            target_document_type TEXT,
            source_category TEXT,
            target_category TEXT,
            similarity_score FLOAT
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                ce1.clause_id AS source_clause_id,
                ce2.clause_id AS target_clause_id,
                ce1.document_type AS source_document_type,
                ce2.document_type AS target_document_type,
                ce1.category AS source_category,
                ce2.category AS target_category,
                (1 - (ce1.embedding <=> ce2.embedding))::FLOAT AS similarity_score
            FROM clause_embeddings ce1
            CROSS JOIN clause_embeddings ce2
            WHERE ce1.project_id = query_project_id
                AND ce2.project_id = query_project_id
                AND ce1.clause_id < ce2.clause_id  -- Avoid duplicates
                AND ce1.document_type != ce2.document_type  -- Cross-document only
                AND (1 - (ce1.embedding <=> ce2.embedding)) >= similarity_threshold
            ORDER BY similarity_score DESC
            LIMIT max_pairs;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS find_cross_document_pairs")
    op.execute("DROP FUNCTION IF EXISTS find_similar_clauses")
    op.drop_table("clause_embeddings")
