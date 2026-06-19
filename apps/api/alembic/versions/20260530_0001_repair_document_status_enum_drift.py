"""repair live document_status enum drift.

Revision ID: 20260530_0001
Revises: 20260529_0001
Create Date: 2026-05-30

Production still carries the legacy PostgreSQL enum name `documentstatus` on
`documents.upload_status` from legacy SQL migration 004, while the current
SQLAlchemy mapper binds the canonical `document_status` enum. This follows
the same pattern established in 20260516_0004 for the document_type column.

Test Suite ID: TS-CI-BACKEND-GUARDS-001.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260530_0001"
down_revision: str | None = "20260529_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            legacy_label TEXT;
        BEGIN
            -- Drop column default so it doesn't interfere with type rename/cast
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                  AND column_name = 'upload_status'
                  AND column_default IS NOT NULL
            ) THEN
                ALTER TABLE documents ALTER COLUMN upload_status DROP DEFAULT;
            END IF;

            -- Case 1: Only legacy type exists — rename it to canonical
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'documentstatus')
               AND NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_status') THEN
                ALTER TYPE documentstatus RENAME TO document_status;

            -- Case 2: Both types exist — merge legacy values into canonical, then migrate column
            ELSIF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'documentstatus')
               AND EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_status') THEN
                FOR legacy_label IN
                    SELECT enumlabel
                    FROM pg_enum
                    WHERE enumtypid = 'documentstatus'::regtype
                LOOP
                    EXECUTE format(
                        'ALTER TYPE document_status ADD VALUE IF NOT EXISTS %L',
                        legacy_label
                    );
                END LOOP;

                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'documents'
                      AND column_name = 'upload_status'
                      AND udt_name = 'documentstatus'
                ) THEN
                    ALTER TABLE documents
                    ALTER COLUMN upload_status TYPE document_status
                    USING upload_status::text::document_status;
                END IF;
            END IF;

            -- Ensure all canonical Python DocumentStatus enum values exist
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_status') THEN
                ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'uploaded';
                ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'queued';
                ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'processing';
                ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'parsed';
                ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'parsed_pending_analysis';
                ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'analyzed';
                ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'error';
            END IF;

            -- Restore the default on document_status
            ALTER TABLE documents ALTER COLUMN upload_status SET DEFAULT 'uploaded';
        END
        $$;
        """
    )


def downgrade() -> None:
    # Recovery migration only; do not reintroduce legacy enum drift automatically.
    pass
