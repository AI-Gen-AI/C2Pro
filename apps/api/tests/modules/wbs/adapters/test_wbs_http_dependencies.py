"""
WBS HTTP dependency injection contracts.
Test Suite ID: TS-CT-WBS-API-001
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.auth.dependencies import get_current_user
from src.wbs.adapters.http.router import (
    get_create_wbs_item_use_case,
    get_wbs_use_case,
    router,
)
from src.wbs.application.dtos import WBSItemDTO, WBSResponse


@dataclass
class _FakeUser:
    tenant_id: str = "tenant-123"


class _FakeGetWBSUseCase:
    async def execute(self, project_id: str, tenant_id: str) -> WBSResponse:
        return WBSResponse(
            items=[WBSItemDTO(id=uuid4(), code="1", name="Injected Item", level=1)],
            coverage={
                "total_items": 1,
                "items_with_budget": 0,
                "items_with_dates": 0,
                "items_with_alerts": 0,
                "completion_average": 0.0,
            },
            alerts=[],
        )


class _FakeCreateWBSUseCase:
    async def execute(self, project_id: str, tenant_id: str, request) -> WBSItemDTO:
        return WBSItemDTO(
            id=uuid4(),
            code=request.code or "1",
            name="Injected WBS DTO",
            level=1,
            description=request.description,
            start_date=request.start_date,
            end_date=request.end_date,
            budget=None,
            completion=request.completion or 0,
        )


@pytest.fixture
def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: _FakeUser()
    return app


def test_ct_wbs_get_route_uses_overridable_use_case_dependency(_app: FastAPI) -> None:
    """TS-CT-WBS-API-001: GET route must use a FastAPI-injected use case dependency."""
    _app.dependency_overrides[get_wbs_use_case] = lambda: _FakeGetWBSUseCase()
    client = TestClient(_app, raise_server_exceptions=False)

    response = client.get("/api/v1/projects/project-1/wbs")

    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["name"] == "Injected Item"


def test_ct_wbs_create_route_uses_overridable_use_case_dependency(_app: FastAPI) -> None:
    """TS-CT-WBS-API-001: POST route must use a FastAPI-injected use case dependency."""
    _app.dependency_overrides[get_create_wbs_item_use_case] = lambda: _FakeCreateWBSUseCase()
    client = TestClient(_app, raise_server_exceptions=False)

    response = client.post(
        "/api/v1/projects/project-1/wbs/items",
        json={
            "name": "Excavation",
            "description": "Injected path",
            "start_date": date(2026, 5, 1).isoformat(),
            "end_date": date(2026, 5, 7).isoformat(),
            "completion": 0,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["name"] == "Injected WBS DTO"
