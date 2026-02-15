"""
Refers to Suite ID: TS-I13-E2E-REAL-001

Real HTTP-level E2E tests for Decision Intelligence flow (I13).
No service mocking; assertions are strict and expected to fail in RED.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient


def _build_headers(generate_token) -> dict[str, str]:
    token = generate_token(
        user_id=uuid4(),
        tenant_id=uuid4(),
        email="i13-flow-user@test.com",
        role="admin",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def live_app(app):
    async with LifespanManager(app):
        yield app


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_real_e2e_generates_final_package_with_evidence_and_risks(
    live_app,
    generate_token,
) -> None:
    headers = _build_headers(generate_token)
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "JVBERi0xLjQgbW9jayBwZGY=",
    }

    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["coherence_score"] >= 0
    assert len(body["risks"]) > 0
    assert len(body["evidence_links"]) > 0
    assert len(body["citations"]) > 0


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_real_e2e_low_confidence_output_is_blocked(
    live_app,
    generate_token,
) -> None:
    headers = _build_headers(generate_token)
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "bG93LWNvbmZpZGVuY2U=",
        "force_profile": "low_confidence",
    }

    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=headers,
        )

    assert response.status_code == 409
    assert "Finalization blocked: Item requires review." in response.text


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_real_e2e_missing_citations_blocks_finalization(
    live_app,
    generate_token,
) -> None:
    headers = _build_headers(generate_token)
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "bWlzc2luZy1jaXRhdGlvbnM=",
        "force_profile": "missing_citations",
    }

    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=headers,
        )

    assert response.status_code == 409
    assert "Finalization blocked: Missing required citations." in response.text


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_real_e2e_reviewer_approval_unlocks_package(
    live_app,
    generate_token,
) -> None:
    headers = _build_headers(generate_token)
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "cmV2aWV3LXJlcXVpcmVk",
        "review_decision": {
            "item_id": str(uuid4()),
            "reviewer_id": str(uuid4()),
            "reviewer_name": "I13 Reviewer",
            "action": "approve",
        },
    }

    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["approved_by"] == "I13 Reviewer"
    assert body["approved_at"] is not None


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_real_e2e_mandatory_signoff_enforced(
    live_app,
    generate_token,
) -> None:
    headers = _build_headers(generate_token)
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
            headers=headers,
        )

    assert response.status_code == 409
    assert "Finalization blocked: Mandatory sign-off required." in response.text
