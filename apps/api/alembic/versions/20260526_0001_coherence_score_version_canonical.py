"""Canonicalize coherence_score_version enum to 'coherence-v1' / 'coherence-v2'.

Phase F — ADR-009 §F: Replace the legacy score_version string zoo
('v0_flag_based', 'v1_exponential_decay') with the closed 2-value canonical enum.

Upgrade path:
  (a) Add 'coherence-v1' and 'coherence-v2' to the existing enum.
  (b) Backfill: all legacy / NULL rows → 'coherence-v1'.
  (c) Drop deprecated enum values ('v0_flag_based', 'v1_exponential_decay').
  (d) Update column default to 'coherence-v1'.

Downgrade path:
  Rename canonical values back to legacy; re-add dropped values.

Both paths are idempotent (DO $$ BEGIN … END $$; guards).

Revision ID: 20260526_0001
Revises: 20260524_0001
Create Date: 2026-05-26

Suite ID: TS-INT-ALEMBIC-COH-VERSION-001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260526_0001"
down_revision: str = "20260524_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUM_NAME = "coherence_score_version"
_TABLE = "coherence_results"
_COLUMN = "score_version"


def upgrade() -> None:
    """Canonicalize score_version enum values."""
    op.execute("SET LOCAL lock_timeout = '30s';")

    # (a) Add new canonical values to the existing enum (IF NOT EXISTS guard)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = '{_ENUM_NAME}'::regtype
                  AND enumlabel = 'coherence-v1'
            ) THEN
                ALTER TYPE {_ENUM_NAME} ADD VALUE 'coherence-v1';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = '{_ENUM_NAME}'::regtype
                  AND enumlabel = 'coherence-v2'
            ) THEN
                ALTER TYPE {_ENUM_NAME} ADD VALUE 'coherence-v2';
            END IF;
        END
        $$;
        """
    )

    # (b) Backfill all legacy and NULL rows to 'coherence-v1'
    op.execute(
        f"""
        UPDATE {_TABLE}
        SET {_COLUMN} = 'coherence-v1'
        WHERE {_COLUMN} IN ('v0_flag_based', 'v1_exponential_decay')
           OR {_COLUMN} IS NULL;
        """
    )

    # (c) Update column default to canonical value
    op.execute(
        f"""
        ALTER TABLE {_TABLE}
        ALTER COLUMN {_COLUMN} SET DEFAULT 'coherence-v1';
        """
    )

    # (d) Drop legacy enum values.
    # PostgreSQL does not support DROP VALUE directly, so we recreate the enum.
    # Strategy: rename old enum, create new canonical enum, alter column type, drop old.
    op.execute(
        f"""
        DO $$
        BEGIN
            -- Only proceed if legacy values still exist in the enum
            IF EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = '{_ENUM_NAME}'::regtype
                  AND enumlabel IN ('v0_flag_based', 'v1_exponential_decay')
            ) THEN
                -- Rename current enum to a temp name
                ALTER TYPE {_ENUM_NAME} RENAME TO {_ENUM_NAME}_old;

                -- Create the new canonical enum
                CREATE TYPE {_ENUM_NAME} AS ENUM ('coherence-v1', 'coherence-v2');

                -- Alter the column to use the new enum type (rows already backfilled)
                ALTER TABLE {_TABLE}
                ALTER COLUMN {_COLUMN} TYPE {_ENUM_NAME}
                USING {_COLUMN}::text::{_ENUM_NAME};

                -- Set default on new enum type
                ALTER TABLE {_TABLE}
                ALTER COLUMN {_COLUMN} SET DEFAULT 'coherence-v1';

                -- Drop old enum
                DROP TYPE {_ENUM_NAME}_old;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Revert canonical enum back to legacy values."""
    op.execute("SET LOCAL lock_timeout = '30s';")

    op.execute(
        f"""
        DO $$
        BEGIN
            -- Only downgrade if legacy values are absent (i.e., upgrade was applied)
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = '{_ENUM_NAME}'::regtype
                  AND enumlabel = 'v0_flag_based'
            ) THEN
                -- Rename canonical enum to temp
                ALTER TYPE {_ENUM_NAME} RENAME TO {_ENUM_NAME}_new;

                -- Recreate legacy enum
                CREATE TYPE {_ENUM_NAME} AS ENUM ('v0_flag_based', 'v1_exponential_decay');

                -- Map 'coherence-v1' → 'v1_exponential_decay', 'coherence-v2' → 'v1_exponential_decay'
                UPDATE {_TABLE}
                SET {_COLUMN} = 'v1_exponential_decay'::text
                WHERE {_COLUMN}::text IN ('coherence-v1', 'coherence-v2');

                -- Alter column to legacy enum
                ALTER TABLE {_TABLE}
                ALTER COLUMN {_COLUMN} TYPE {_ENUM_NAME}
                USING {_COLUMN}::text::{_ENUM_NAME};

                -- Restore legacy default
                ALTER TABLE {_TABLE}
                ALTER COLUMN {_COLUMN} SET DEFAULT 'v0_flag_based';

                -- Drop new enum
                DROP TYPE {_ENUM_NAME}_new;
            END IF;
        END
        $$;
        """
    )
