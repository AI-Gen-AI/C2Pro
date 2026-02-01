"""
HTTP Router Delegation Tests (TDD - RED Phase)

Refers to Suite IDs: TS-UAD-HTTP-RTR-001, TS-UAD-HTTP-ERR-001.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, FastAPI, status
from fastapi.testclient import TestClient
from pydantic import BaseModel
from unittest.mock import MagicMock

from src.core.handlers import register_exception_handlers
from src.core.exceptions import ResourceNotFoundError


class CreateThingRequest(BaseModel):
    name: str
    project_id: UUID


class CreateThingResponse(BaseModel):
    id: UUID
    name: str


def _build_app_with_router(use_case):
    router = APIRouter()

    @router.post("/things", status_code=status.HTTP_201_CREATED, response_model=CreateThingResponse)
    def create_thing(payload: CreateThingRequest):
        return use_case.execute(payload)

    @router.get("/things/{thing_id}", status_code=status.HTTP_200_OK, response_model=CreateThingResponse)
    def get_thing(thing_id: UUID):
        return use_case.get(thing_id)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    return app


class TestRouterDelegation:
    """Refers to Suite ID: TS-UAD-HTTP-RTR-001."""

    def test_create_router_delegates_to_use_case_with_dto(self):
        use_case = MagicMock()
        response_id = uuid4()
        use_case.execute.return_value = CreateThingResponse(
            id=response_id,
            name="Alpha",
        )

        app = _build_app_with_router(use_case)
        client = TestClient(app)

        payload = {"name": "Alpha", "project_id": str(uuid4())}
        response = client.post("/things", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        args, _ = use_case.execute.call_args
        assert isinstance(args[0], CreateThingRequest)
        assert args[0].name == "Alpha"
        assert str(args[0].project_id) == payload["project_id"]

    def test_get_router_returns_200(self):
        use_case = MagicMock()
        response_id = uuid4()
        use_case.get.return_value = CreateThingResponse(id=response_id, name="Beta")

        app = _build_app_with_router(use_case)
        client = TestClient(app)

        response = client.get(f"/things/{response_id}")

        assert response.status_code == status.HTTP_200_OK


class TestRouterErrorHandling:
    """Refers to Suite ID: TS-UAD-HTTP-ERR-001."""

    def test_resource_not_found_maps_to_404(self):
        use_case = MagicMock()
        use_case.get.side_effect = ResourceNotFoundError("Thing", resource_id="missing")

        app = _build_app_with_router(use_case)
        client = TestClient(app)

        response = client.get(f"/things/{uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        body = response.json()
        assert body["error_code"] == "RESOURCE_NOT_FOUND"
        assert body["status_code"] == status.HTTP_404_NOT_FOUND
