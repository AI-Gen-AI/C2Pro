"""Add documents and clauses tables

Revision ID: 20260310_0001
Revises: 20260225_0001
Create Date: 2026-03-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260310_0001"
down_revision: str = "20260225_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create ENUM types for documents
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_type') THEN
                CREATE TYPE document_type AS ENUM (
                    'contract',
                    'specification',
                    'budget',
                    'report',
                    'drawing',
                    'correspondence',
                    'other'
                );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_status') THEN
                CREATE TYPE document_status AS ENUM (
                    'uploaded',
                    'queued',
                    'processing',
                    'parsed',
                    'error'
                );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'clausetype') THEN
                CREATE TYPE clausetype AS ENUM (
                    'general',
                    'technical',
                    'legal',
                    'financial',
                    'administrative',
                    'scope',
                    'penalty',
                    'warranty',
                    'payment',
                    'delivery',
                    'other'
                );
            END IF;
        END
        $$;
        """
    )

    # Create documents table
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "document_type",
            postgresql.ENUM(
                "contract",
                "specification",
                "budget",
                "report",
                "drawing",
                "correspondence",
                "other",
                name="document_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_format", sa.String(length=10), nullable=True),
        sa.Column("storage_url", sa.Text(), nullable=True),
        sa.Column("storage_encrypted", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "upload_status",
            postgresql.ENUM(
                "uploaded",
                "queued",
                "processing",
                "parsed",
                "error",
                name="document_status",
                create_type=False,
            ),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("parsed_at", sa.DateTime(), nullable=True),
        sa.Column("parsing_error", sa.Text(), nullable=True),
        sa.Column("retention_until", sa.DateTime(), nullable=True),
        sa.Column(
            "document_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_project", "documents", ["project_id"])
    op.create_index("ix_documents_type", "documents", ["document_type"])
    op.create_index("ix_documents_status", "documents", ["upload_status"])
    op.create_index("ix_documents_created", "documents", ["created_at"])

    # Create clauses table
    op.create_table(
        "clauses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clause_code", sa.String(length=50), nullable=False),
        sa.Column(
            "clause_type",
            postgresql.ENUM(
                "general",
                "technical",
                "legal",
                "financial",
                "administrative",
                "scope",
                "penalty",
                "warranty",
                "payment",
                "delivery",
                "other",
                name="clausetype",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("text_start_offset", sa.Integer(), nullable=True),
        sa.Column("text_end_offset", sa.Integer(), nullable=True),
        sa.Column(
            "extracted_entities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("extraction_model", sa.String(length=50), nullable=True),
        sa.Column("manually_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clauses_project", "clauses", ["project_id"])
    op.create_index("ix_clauses_document", "clauses", ["document_id"])
    op.create_index("ix_clauses_type", "clauses", ["clause_type"])
    op.create_index("ix_clauses_code", "clauses", ["clause_code"])
    op.create_index("ix_clauses_verified", "clauses", ["manually_verified", "verified_at"])


def downgrade() -> None:
    op.drop_table("clauses")
    op.drop_table("documents")
    op.execute("DROP TYPE IF EXISTS clausetype")
    op.execute("DROP TYPE IF EXISTS document_status")
    op.execute("DROP TYPE IF EXISTS document_type")
