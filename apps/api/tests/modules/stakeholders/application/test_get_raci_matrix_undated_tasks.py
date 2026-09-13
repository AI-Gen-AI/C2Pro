"""RACI matrix must load when WBS tasks carry no schedule dates (IR-3 follow-up).

Extracted WBS items frequently have no planned/actual dates. Sorting the matrix compared
``None`` with ``datetime`` and ``GET /projects/{id}/raci`` returned 500 as soon as one
undated task sat next to a dated one (reproduced on a migrated PostgreSQL journey).
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from src.procurement.domain.models import WBSItem
from src.stakeholders.application.get_raci_matrix_use_case import GetRaciMatrixUseCase


def _task(project_id, code: str, name: str, planned_start: datetime | None = None) -> WBSItem:
    return WBSItem(
        id=uuid4(),
        project_id=project_id,
        code=code,
        name=name,
        level=2,
        planned_start=planned_start,
    )


async def test_undated_tasks_do_not_break_the_matrix_and_follow_dated_tasks() -> None:
    tenant_id = uuid4()
    project_id = uuid4()
    stakeholder_repo = AsyncMock()
    stakeholder_repo.list_raci_assignments.return_value = []
    wbs_repo = AsyncMock()
    wbs_repo.get_by_project.return_value = [
        _task(project_id, "1.3", "Undated handover"),
        _task(project_id, "1.2", "Dredging", datetime(2026, 11, 1)),
        _task(project_id, "1.0", "Undated mobilisation"),
        _task(project_id, "1.1", "Quay wall", datetime(2026, 10, 1)),
    ]
    project_repo = AsyncMock()
    project_repo.exists_by_id.return_value = True

    response = await GetRaciMatrixUseCase(
        stakeholder_repository=stakeholder_repo,
        wbs_repository=wbs_repo,
        project_repository=project_repo,
    ).execute(project_id=project_id, tenant_id=tenant_id)

    assert [(row.task_code, row.sequence_index) for row in response.matrix] == [
        ("1.1", 1),
        ("1.2", 2),
        ("1.0", 3),
        ("1.3", 4),
    ]
    assert [row.planned_start for row in response.matrix][2:] == [None, None]
