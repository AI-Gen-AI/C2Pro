"""Canonicalize coherence_score_version enum to 'coherence-v1' / 'coherence-v2'.

Phase F — ADR-009 §F: Replace the legacy score_version string zoo
('v0_flag_based', 'v1_exponential_decay') with the closed 2-value canonical enum.

Upgrade path:
  (a) Rename the legacy enum and create the canonical enum.
  (b) Rewrite the column with a CASE cast that maps legacy/NULL rows to
      'coherence-v1'.
  (c) Drop the legacy enum.
  (d) Update column default to 'coherence-v1'.

Downgrade path:
  Rename canonical values back to legacy; re-add dropped values.

The upgrade avoids ALTER TYPE ADD VALUE because PostgreSQL cannot safely use a
new enum label in the same migration transaction.

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

    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = '{_ENUM_NAME}'::regtype
                  AND enumlabel IN ('v0_flag_based', 'v1_exponential_decay')
            ) THEN
                ALTER TABLE {_TABLE}
                ALTER COLUMN {_COLUMN} DROP DEFAULT;

                ALTER TYPE {_ENUM_NAME} RENAME TO {_ENUM_NAME}_old;

                CREATE TYPE {_ENUM_NAME} AS ENUM ('coherence-v1', 'coherence-v2');

                ALTER TABLE {_TABLE}
                ALTER COLUMN {_COLUMN} TYPE {_ENUM_NAME}
                USING (
                    CASE {_COLUMN}::text
                        WHEN 'v0_flag_based' THEN 'coherence-v1'
                        WHEN 'v1_exponential_decay' THEN 'coherence-v1'
                        WHEN 'coherence-v2' THEN 'coherence-v2'
                        ELSE 'coherence-v1'
                    END
                )::{_ENUM_NAME};

                ALTER TABLE {_TABLE}
                ALTER COLUMN {_COLUMN} SET DEFAULT 'coherence-v1';

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
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumtypid = '{_ENUM_NAME}'::regtype
                  AND enumlabel = 'v0_flag_based'
            ) THEN
                ALTER TABLE {_TABLE}
                ALTER COLUMN {_COLUMN} DROP DEFAULT;

                ALTER TYPE {_ENUM_NAME} RENAME TO {_ENUM_NAME}_new;

                CREATE TYPE {_ENUM_NAME} AS ENUM ('v0_flag_based', 'v1_exponential_decay');

                ALTER TABLE {_TABLE}
                ALTER COLUMN {_COLUMN} TYPE {_ENUM_NAME}
                USING (
                    CASE {_COLUMN}::text
                        WHEN 'coherence-v1' THEN 'v1_exponential_decay'
                        WHEN 'coherence-v2' THEN 'v1_exponential_decay'
                        ELSE 'v1_exponential_decay'
                    END
                )::{_ENUM_NAME};

                ALTER TABLE {_TABLE}
                ALTER COLUMN {_COLUMN} SET DEFAULT 'v0_flag_based';

                DROP TYPE {_ENUM_NAME}_new;
            END IF;
        END
        $$;
        """
    )
