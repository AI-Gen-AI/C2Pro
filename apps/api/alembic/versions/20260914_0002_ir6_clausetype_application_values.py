"""IR-6: add the ClauseType values missing from Alembic-built clausetype enums.

Revision ID: 20260914_0002
Revises: 20260913_0002
Create Date: 2026-09-14

20260310_0001 creates ``clausetype`` only IF NOT EXISTS, with a legacy vocabulary
(general, technical, legal, financial, administrative, scope, penalty, warranty, payment,
delivery, other). Databases that kept an older type already carry the application's values
(see 20260813_0001), but every database built from the Alembic chain lacks five values that
``ClauseType`` can produce: milestone, responsibility, quality, termination, dispute. Writing any
of them raised ``invalid input value for enum clausetype``.

Only canonical application values are added. The legacy DB-only labels are left in place
(PostgreSQL cannot drop enum values without recreating the type) and no code writes them; the
migrated-schema parity test allowlists them explicitly. ``ADD VALUE IF NOT EXISTS`` is a no-op
where a value already exists, so this is safe on every database shape.
"""

from __future__ import annotations

from alembic import op

revision = "20260914_0002"
down_revision = "20260913_0002"
branch_labels = None
depends_on = None

NEW_VALUES = ("milestone", "responsibility", "quality", "termination", "dispute")


def upgrade() -> None:
    # Committed immediately so the new labels are usable by anything later in the same run.
    with op.get_context().autocommit_block():
        for value in NEW_VALUES:
            op.execute(f"ALTER TYPE clausetype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE for enums; removing labels would require recreating the type
    # and rewriting every clauses row. The added values are harmless, so downgrade is a no-op.
    pass
