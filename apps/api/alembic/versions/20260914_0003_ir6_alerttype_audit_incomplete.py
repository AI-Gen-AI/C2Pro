"""IR-6: the alerttype database enum accepts every AlertType the application defines.

Revision ID: 20260914_0003
Revises: 20260914_0002
Create Date: 2026-09-14

``AlertType.AUDIT_INCOMPLETE`` ("audit_incomplete") was added to the application vocabulary by
TASK-COH-V1-06 (and is pinned by tests/integration/coherence/test_alert_wiring.py), but no
migration added it to the ``alerttype`` enum created by 20260406_0004. Any write of that value
would fail with ``invalid input value for enum alerttype``.

The canonical code value is added; nothing is removed. Open product question recorded with
IR-6: ADR-019/ADR-025 keep the alert *trigger* (e.g. missing evidence) orthogonal to its
category, and ``alert_type`` is a source discriminator, so whether "audit_incomplete" belongs in
this vocabulary long term is a product decision, not a schema one.
"""

from __future__ import annotations

from alembic import op

revision = "20260914_0003"
down_revision = "20260914_0002"
branch_labels = None
depends_on = None

NEW_VALUES = ("audit_incomplete",)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for value in NEW_VALUES:
            op.execute(f"ALTER TYPE alerttype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE for enums; the added label is harmless, so downgrade is a no-op.
    pass
