"""RACI assignment writes must store naive UTC timestamps (IR-3 follow-up).

``stakeholder_wbs_raci.verified_at`` / ``created_at`` are ``timestamp without time zone``.
The upsert use case stamps timezone-aware UTC datetimes; handing those to asyncpg fails
with ``can't subtract offset-naive and offset-aware datetimes`` and
``PUT /api/v1/assignments`` returned 500 (reproduced on a migrated PostgreSQL journey).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.domain.models import RaciAssignment, RACIRole

AWARE_VERIFIED = datetime(2026, 9, 13, 19, 30, tzinfo=timezone(timedelta(hours=2)))
AWARE_CREATED = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)


def _assignment() -> RaciAssignment:
    return RaciAssignment(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        stakeholder_id=uuid4(),
        wbs_item_id=uuid4(),
        raci_role=RACIRole.CONSULTED,
        created_at=AWARE_CREATED,
        manually_verified=True,
        verified_by=uuid4(),
        verified_at=AWARE_VERIFIED,
    )


def test_new_assignment_is_mapped_with_naive_utc_timestamps() -> None:
    orm = SqlAlchemyStakeholderRepository(session=MagicMock())._to_raci_orm(_assignment())

    assert orm.verified_at == datetime(2026, 9, 13, 17, 30)
    assert orm.verified_at.tzinfo is None
    assert orm.created_at == datetime(2026, 9, 13, 17, 0)
    assert orm.created_at.tzinfo is None


async def test_updated_assignment_stores_naive_utc_verified_at() -> None:
    assignment = _assignment()
    orm = SimpleNamespace(verified_at=None)
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=orm)))
    session.flush = AsyncMock()

    await SqlAlchemyStakeholderRepository(session=session).update_raci_assignment(
        assignment, tenant_id=assignment.tenant_id
    )

    assert orm.verified_at == datetime(2026, 9, 13, 17, 30)
    assert orm.verified_at.tzinfo is None
