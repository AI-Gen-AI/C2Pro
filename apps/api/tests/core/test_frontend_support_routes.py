"""Test Suite ID: TASK-051.

Frontend support route contracts, including their database and authenticated
dependency seams.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.auth.dependencies import get_current_user
from src.core.auth.models import User, UserRole
from src.core.frontend_support.router import (
    _get_consent_repository,
    _get_disclaimer_repository,
)
from src.core.frontend_support.router import (
    router as frontend_support_router,
)


@dataclass
class _ConsentRecord:
    categories: dict[str, bool]


class _FakeConsentRepository:
    """TS-TASK-051: In-memory seam for the repository-backed consent routes."""

    def __init__(self) -> None:
        self._records: dict[tuple[UUID, str, str], _ConsentRecord] = {}
        self.session = SimpleNamespace(commit=self._commit)

    async def _commit(self) -> None:
        return None

    async def upsert_consent(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        version: str,
        categories: dict[str, bool],
    ) -> None:
        self._records[(tenant_id, user_id, version)] = _ConsentRecord(categories=categories)

    async def get_consent(
        self, tenant_id: UUID, user_id: str, version: str
    ) -> _ConsentRecord | None:
        return self._records.get((tenant_id, user_id, version))


class _FakeDisclaimerRepository:
    """In-memory seam for disclaimer acceptance routes (SEC-014)."""

    def __init__(self) -> None:
        self._records: dict[tuple[UUID, UUID, str, str], object] = {}
        self.session = SimpleNamespace(commit=self._commit)

    async def _commit(self) -> None:
        return None

    async def get_acceptance(
        self, *, tenant_id: UUID, user_id: UUID, project_id: str, version: str
    ) -> object | None:
        return self._records.get((tenant_id, user_id, project_id, version))

    async def accept(
        self, *, tenant_id: UUID, user_id: UUID, project_id: str, version: str
    ) -> object:
        key = (tenant_id, user_id, project_id, version)
        self._records[key] = SimpleNamespace(
            tenant_id=tenant_id, user_id=user_id, project_id=project_id, version=version
        )
        return self._records[key]


def _current_user() -> User:
    return User(
        id=uuid4(),
        tenant_id=uuid4(),
        email="frontend-support@example.com",
        hashed_password="not-used-by-route-contract-tests",
        first_name="Frontend",
        last_name="Support",
        role=UserRole.USER,
        is_active=True,
        is_verified=True,
    )


def _build_client() -> tuple[TestClient, User]:
    app = FastAPI()
    app.include_router(frontend_support_router, prefix="/api/v1")
    consent_repository = _FakeConsentRepository()
    disclaimer_repository = _FakeDisclaimerRepository()
    user = _current_user()
    app.dependency_overrides[_get_consent_repository] = lambda: consent_repository
    app.dependency_overrides[_get_disclaimer_repository] = lambda: disclaimer_repository
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), user


def test_cookie_consent_round_trip_contract() -> None:
    client, user = _build_client()
    tenant_id = str(user.tenant_id)
    user_id = str(user.id)

    create_response = client.post(
        "/api/v1/compliance/cookies/consent",
        json={
            "tenantId": tenant_id,
            "userId": user_id,
            "version": "2026-02",
            "categories": {
                "necessary": True,
                "analytics": False,
                "marketing": True,
            },
        },
    )

    assert create_response.status_code == 200
    assert create_response.json() == {
        "saved": True,
        "categories": {
            "necessary": True,
            "analytics": False,
            "marketing": True,
        },
        "showBanner": False,
    }

    fetch_response = client.get(
        "/api/v1/compliance/cookies/consent",
        params={
            "tenantId": tenant_id,
            "userId": user_id,
            "version": "2026-02",
        },
    )

    assert fetch_response.status_code == 200
    assert fetch_response.json() == {
        "hasConsent": True,
        "showBanner": False,
        "requiredVersion": "2026-02",
        "categories": {
            "necessary": True,
            "analytics": False,
            "marketing": True,
        },
    }

    update_response = client.patch(
        "/api/v1/compliance/cookies/consent",
        json={
            "tenantId": tenant_id,
            "userId": user_id,
            "version": "2026-02",
            "categories": {
                "necessary": True,
                "analytics": False,
                "marketing": False,
            },
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "categories": {
            "necessary": True,
            "analytics": False,
            "marketing": False,
        },
        "trackersBlocked": ["analytics", "marketing"],
    }


def test_cookie_consent_persist_error_contract() -> None:
    client, user = _build_client()

    response = client.post(
        "/api/v1/compliance/cookies/consent",
        json={
            "tenantId": str(user.tenant_id),
            "userId": str(user.id),
            "version": "2026-02",
            "forceError": True,
        },
    )

    assert response.status_code == 500
    assert response.json() == {
        "code": "COOKIE_CONSENT_PERSIST_FAILED",
        "showBanner": True,
    }


def test_legal_disclaimer_status_and_acceptance_contract() -> None:
    client, user = _build_client()
    expected_scope = f"{user.tenant_id}:{user.id}:v1.0"

    status_response = client.get(
        "/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/status",
    )

    assert status_response.status_code == 200
    assert status_response.json() == {
        "accepted": False,
        "version": "v1.0",
        "mustPrompt": True,
        "scope": expected_scope,
    }

    accept_response = client.post(
        "/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/accept",
        json={"version": "v1.0"},
    )

    assert accept_response.status_code == 200
    assert accept_response.json() == {
        "accepted": True,
        "gateBlocked": False,
        "version": "v1.0",
    }

    accepted_status_response = client.get(
        "/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/status",
    )

    assert accepted_status_response.status_code == 200
    assert accepted_status_response.json() == {
        "accepted": True,
        "version": "v1.0",
        "mustPrompt": False,
        "scope": expected_scope,
    }


def test_legal_disclaimer_accept_persist_error_contract() -> None:
    client, _user = _build_client()

    response = client.post(
        "/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/accept",
        json={"version": "v1.0", "forceError": True},
    )

    assert response.status_code == 500
    assert response.json() == {
        "code": "DISCLAIMER_PERSIST_FAILED",
        "gateBlocked": True,
    }


def test_onboarding_sample_project_contract() -> None:
    client, _user = _build_client()

    start_response = client.post("/api/v1/onboarding/sample-project/start")
    assert start_response.status_code == 200
    assert start_response.json() == {
        "projectId": "proj_sample_001",
        "route": "/dashboard/projects/proj_sample_001",
        "reused": True,
        "duplicateCreated": False,
    }

    ready_response = client.get(
        "/api/v1/onboarding/sample-project/ready",
        params={"projectId": "proj_sample_001"},
    )
    assert ready_response.status_code == 200
    assert ready_response.json() == {
        "widgets": {
            "documents": "ready",
            "alerts": "ready",
            "stakeholders": "ready",
        }
    }

    retry_response = client.post(
        "/api/v1/onboarding/sample-project/retry",
        json={"sessionId": "onb_001"},
    )
    assert retry_response.status_code == 200
    assert retry_response.json() == {
        "sessionId": "onb_001",
        "state": "ready",
        "recovered": True,
    }

    telemetry_response = client.get(
        "/api/v1/onboarding/sample-project/telemetry",
        params={"sessionId": "onb_001"},
    )
    assert telemetry_response.status_code == 200
    assert telemetry_response.json() == {
        "events": ["start", "ready"],
        "elapsedMs": 180000,
    }
