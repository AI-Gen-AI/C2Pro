"""
Test Suite ID: TASK-051

Frontend support route contract tests for backend endpoints that were only
available through MSW mocks.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.frontend_support.router import router as frontend_support_router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(frontend_support_router, prefix="/api/v1")
    return TestClient(app)


def test_cookie_consent_round_trip_contract() -> None:
    client = _build_client()

    create_response = client.post(
        "/api/v1/compliance/cookies/consent",
        json={
            "tenantId": "tenant_demo",
            "userId": "user_demo",
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
            "tenantId": "tenant_demo",
            "userId": "user_demo",
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
            "tenantId": "tenant_demo",
            "userId": "user_demo",
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
    client = _build_client()

    response = client.post(
        "/api/v1/compliance/cookies/consent",
        json={
            "tenantId": "tenant_demo",
            "userId": "user_demo",
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
    client = _build_client()
    headers = {
        "x-tenant-id": "tenant_demo",
        "x-user-id": "user_demo",
    }

    status_response = client.get(
        "/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/status",
        headers=headers,
    )

    assert status_response.status_code == 200
    assert status_response.json() == {
        "accepted": False,
        "version": "v1.0",
        "mustPrompt": True,
        "scope": "tenant_demo:user_demo:v1.0",
    }

    accept_response = client.post(
        "/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/accept",
        headers=headers,
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
        headers=headers,
    )

    assert accepted_status_response.status_code == 200
    assert accepted_status_response.json() == {
        "accepted": True,
        "version": "v1.0",
        "mustPrompt": False,
        "scope": "tenant_demo:user_demo:v1.0",
    }


def test_legal_disclaimer_accept_persist_error_contract() -> None:
    client = _build_client()

    response = client.post(
        "/api/v1/projects/proj_demo_001/gates/gate-8/disclaimer/accept",
        headers={
            "x-tenant-id": "tenant_demo",
            "x-user-id": "user_demo",
        },
        json={"version": "v1.0", "forceError": True},
    )

    assert response.status_code == 500
    assert response.json() == {
        "code": "DISCLAIMER_PERSIST_FAILED",
        "gateBlocked": True,
    }


def test_onboarding_sample_project_contract() -> None:
    client = _build_client()

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
