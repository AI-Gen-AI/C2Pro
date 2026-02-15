"""
Route contract tests for I13 Decision Intelligence endpoint.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def live_app(app):
    """Refers to Suite ID: TS-I13-E2E-REAL-001."""
    async with LifespanManager(app):
        yield app


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_route_exists_and_is_not_404_when_authenticated(live_app, seeded_auth_headers) -> None:
    """Refers to Suite ID: TS-I13-E2E-REAL-001."""
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "cm91dGUtc21va2U=",
    }
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=seeded_auth_headers,
        )

    assert response.status_code != 404


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_route_contract_success_path_returns_200(live_app, seeded_auth_headers) -> None:
    """Refers to Suite ID: TS-I13-E2E-REAL-001."""
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "c3VjY2Vzcy1wYXRo",
    }
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=seeded_auth_headers,
        )
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_route_contract_low_confidence_returns_409(live_app, seeded_auth_headers) -> None:
    """Refers to Suite ID: TS-I13-E2E-REAL-001."""
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "bG93LWNvbmZpZGVuY2U=",
        "force_profile": "low_confidence",
    }
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=seeded_auth_headers,
        )
    assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_route_contract_missing_citations_returns_409(live_app, seeded_auth_headers) -> None:
    """Refers to Suite ID: TS-I13-E2E-REAL-001."""
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "bWlzc2luZy1jaXRhdGlvbnM=",
        "force_profile": "missing_citations",
    }
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=seeded_auth_headers,
        )
    assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_route_contract_mandatory_signoff_returns_409(live_app, seeded_auth_headers) -> None:
    """Refers to Suite ID: TS-I13-E2E-REAL-001."""
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "c2lnbi1vZmYtcmVxdWlyZWQ=",
        "review_decision": {
            "item_id": str(uuid4()),
            "reviewer_id": str(uuid4()),
            "reviewer_name": "I13 Signer",
            "action": "approve",
        },
        "require_sign_off": True,
    }
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=seeded_auth_headers,
        )
    assert response.status_code == 409
