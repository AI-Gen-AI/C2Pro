"""repair live document_type enum drift.

Revision ID: 20260516_0003
Revises: 20260516_0002
Create Date: 2026-05-16

Railway logs for TASK-BCK-053 proved production still carries the legacy
PostgreSQL enum name `documenttype` on `documents.document_type`, while the
current SQLAlchemy mapper binds the canonical `document_type` enum. This
forward-only repair normalizes the live type without dropping document data.

Test Suite ID: TS-CI-BACKEND-GUARDS-001.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260516_0003"
down_revision: str | None = "20260516_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            legacy_label TEXT;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'documenttype')
               AND NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_type') THEN
                ALTER TYPE documenttype RENAME TO document_type;
            ELSIF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'documenttype')
               AND EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_type') THEN
                FOR legacy_label IN
                    SELECT enumlabel
                    FROM pg_enum
                    WHERE enumtypid = 'documenttype'::regtype
                LOOP
                    EXECUTE format(
                        'ALTER TYPE document_type ADD VALUE IF NOT EXISTS %L',
                        legacy_label
                    );
                END LOOP;

                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'documents'
                      AND column_name = 'document_type'
                      AND udt_name = 'documenttype'
                ) THEN
                    ALTER TABLE documents
                    ALTER COLUMN document_type TYPE document_type
                    USING document_type::text::document_type;
                END IF;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Recovery migration only; do not reintroduce legacy enum drift automatically.
    pass
