"""A RACI task deleted between the use case's existence check and the insert is a missing task.

The canonical WBS FK (``stakeholder_wbs_raci_wbs_item_id_fkey`` -> ``wbs_nodes``, ADR-025) rejects
the insert at flush; the repository reports ``task_not_found`` (HTTP 404 in the RACI router)
instead of letting the IntegrityError surface as a 500. Other integrity errors are not masked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.domain.models import RaciAssignment, RACIRole


class _Session:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.added: list[object] = []
        self.rolled_back = False

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        raise self._error

    async def rollback(self) -> None:
        self.rolled_back = True


def _assignment(tenant_id) -> RaciAssignment:  # noqa: ANN001
    now = datetime.now(UTC)
    return RaciAssignment(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=tenant_id,
        stakeholder_id=uuid4(),
        wbs_item_id=uuid4(),
        raci_role=RACIRole.RESPONSIBLE,
        evidence_text=None,
        generated_automatically=False,
        manually_verified=True,
        verified_by=uuid4(),
        verified_at=now,
        created_at=now,
    )


def _integrity_error(message: str) -> IntegrityError:
    return IntegrityError("INSERT INTO stakeholder_wbs_raci ...", {}, Exception(message))


def _repository(session: _Session, tenant_id, monkeypatch: pytest.MonkeyPatch) -> SqlAlchemyStakeholderRepository:  # noqa: ANN001
    repository = SqlAlchemyStakeholderRepository(session)  # type: ignore[arg-type]

    async def _project_tenant(_project_id):  # noqa: ANN001
        return tenant_id

    monkeypatch.setattr(repository, "_get_project_tenant_id", _project_tenant)
    return repository


@pytest.mark.asyncio
async def test_task_deleted_before_insert_is_reported_as_task_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid4()
    session = _Session(
        _integrity_error(
            'insert or update on table "stakeholder_wbs_raci" violates foreign key constraint '
            '"stakeholder_wbs_raci_wbs_item_id_fkey"'
        )
    )

    with pytest.raises(ValueError, match="^task_not_found$"):
        await _repository(session, tenant_id, monkeypatch).add_raci_assignment(_assignment(tenant_id), tenant_id)

    assert session.rolled_back


@pytest.mark.asyncio
async def test_other_integrity_errors_are_not_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid4()
    session = _Session(_integrity_error('duplicate key value violates unique constraint "uq_raci_assignment"'))

    with pytest.raises(IntegrityError):
        await _repository(session, tenant_id, monkeypatch).add_raci_assignment(_assignment(tenant_id), tenant_id)

    assert not session.rolled_back
