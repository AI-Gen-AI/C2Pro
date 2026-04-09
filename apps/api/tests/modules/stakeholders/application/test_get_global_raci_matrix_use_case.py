"""
TS-UA-STK-RACI-GLB-001

Tests for GetGlobalRaciMatrixUseCase.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.stakeholders.application.dtos import RaciMatrixTaskRow, RaciMatrixViewResponse
from src.stakeholders.application.get_global_raci_matrix_use_case import (
    GetGlobalRaciMatrixUseCase,
)


@pytest.mark.asyncio
async def test_execute_flattens_project_matrices_using_project_repository_tuple_contract() -> None:
    """Use case should respect ProjectRepository.list() tuple shape and merge each project matrix."""
    tenant_id = uuid4()
    project_a = SimpleNamespace(id=uuid4())
    project_b = SimpleNamespace(id=uuid4())

    project_repository = MagicMock()
    project_repository.list = AsyncMock(return_value=([project_a, project_b], 2))

    matrix_use_case = MagicMock()
    matrix_use_case.execute = AsyncMock(
        side_effect=[
            RaciMatrixViewResponse(
                matrix=[
                    RaciMatrixTaskRow(
                        task_id=uuid4(),
                        task_code="1.0",
                        task_name="Mobilization",
                        sequence_index=1,
                        assignments=[],
                    )
                ]
            ),
            RaciMatrixViewResponse(
                matrix=[
                    RaciMatrixTaskRow(
                        task_id=uuid4(),
                        task_code="2.0",
                        task_name="Execution",
                        sequence_index=1,
                        assignments=[],
                    )
                ]
            ),
        ]
    )

    response = await GetGlobalRaciMatrixUseCase(
        project_repository=project_repository,
        project_matrix_use_case=matrix_use_case,
    ).execute(tenant_id=tenant_id)

    assert [row.task_code for row in response.matrix] == ["1.0", "2.0"]
    project_repository.list.assert_awaited_once_with(tenant_id=tenant_id, page=1, page_size=1000)


@pytest.mark.asyncio
async def test_execute_skips_projects_deleted_between_list_and_matrix_build() -> None:
    """Use case should tolerate per-project drift and keep building the global response."""
    tenant_id = uuid4()
    project_a = SimpleNamespace(id=uuid4())
    project_b = SimpleNamespace(id=uuid4())

    project_repository = MagicMock()
    project_repository.list = AsyncMock(return_value=([project_a, project_b], 2))

    matrix_use_case = MagicMock()
    matrix_use_case.execute = AsyncMock(
        side_effect=[
            ValueError("project_not_found"),
            RaciMatrixViewResponse(matrix=[]),
        ]
    )

    response = await GetGlobalRaciMatrixUseCase(
        project_repository=project_repository,
        project_matrix_use_case=matrix_use_case,
    ).execute(tenant_id=tenant_id)

    assert response.matrix == []
