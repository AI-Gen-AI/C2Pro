"""Extend projecttype enum with new project type values used by the frontend wizard.

Revision ID: 20260808_0001
Revises: 20260807_0001
Create Date: 2026-08-08

The CreateProjectWizard sends values (epc, civil, building, maritime, chemical,
energy, municipal, oil_gas, mining) that were not in the original projecttype enum
(construction, engineering, industrial, infrastructure, other), causing every project
creation with an explicit type selection to fail with a PostgreSQL enum constraint
error → HTTP 500.

ALTER TYPE ... ADD VALUE IF NOT EXISTS is safe in PostgreSQL 12+ (Supabase uses PG 15)
and is idempotent. The new values cannot be used in the same transaction they are
added, but since we only add them (no INSERT/UPDATE in the same migration), this is fine.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0001"
down_revision: str | None = "20260807_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_VALUES = [
    "epc",
    "civil",
    "building",
    "maritime",
    "chemical",
    "energy",
    "municipal",
    "oil_gas",
    "mining",
]


def upgrade() -> None:
    conn = op.get_bind()
    for value in _NEW_VALUES:
        conn.execute(sa.text(f"ALTER TYPE projecttype ADD VALUE IF NOT EXISTS '{value}'"))


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE for enums; downgrade is intentionally a no-op.
    # The extra values are harmless and removal would require recreating the type.
    pass
