"""
Refers to Suite ID: TS-E2E-ERR-TIM-001

E2E RED tests for timeout and fallback scenarios.
All assertions define contracts that are expected to fail before GREEN implementation.
"""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from src.core.auth.models import Tenant, User


if os.getenv("C2PRO_TEST_LIGHT") == "1":
    pytest.skip(
        "Resilience RED timeout suite is skipped in light test mode; run in dedicated resilience environment.",
        allow_module_level=True,
    )


@pytest_asyncio.fixture
async def live_app(app):
    """Refers to Suite ID: TS-E2E-ERR-TIM-001."""
    async with LifespanManager(app):
        yield app


@pytest_asyncio.fixture
async def seeded_auth_headers_tenant_b(
    generate_token,
    test_user_2: User,
    test_tenant_2: Tenant,
) -> dict[str, str]:
    """Build auth headers for tenant B for isolation checks."""
    token = generate_token(
        user_id=UUID(str(test_user_2.id)),
        tenant_id=UUID(str(test_tenant_2.id)),
        email=test_user_2.email,
        role=test_user_2.role.value if hasattr(test_user_2.role, "value") else str(test_user_2.role),
    )
    return {"Authorization": f"Bearer {token}"}


def _payload(force_profile: str | None = None) -> dict:
    body = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "dGltZW91dC1zY2VuYXJpby1wYXlsb2Fk",
    }
    if force_profile:
        body["force_profile"] = force_profile
    return body


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_001_primary_timeout_returns_504_with_error_code(live_app, seeded_auth_headers) -> None:
    """TS-E2E-ERR-TIM-001: Primary timeout must map to HTTP 504 with explicit code."""
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=_payload("timeout_primary"),
            headers=seeded_auth_headers,
        )

    assert response.status_code == 504
    body = response.json()
    assert body["detail"]["code"] == "TIMEOUT_PRIMARY"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_002_timeout_with_successful_fallback_returns_fallback_metadata(
    live_app,
    seeded_auth_headers,
) -> None:
    """TS-E2E-ERR-TIM-001: Successful fallback must expose fallback metadata contract."""
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=_payload("timeout_with_fallback_success"),
            headers=seeded_auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fallback_used"
    assert body["fallback_source"] in {"cached_response", "secondary_model"}


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_003_timeout_response_includes_retry_budget_fields(live_app, seeded_auth_headers) -> None:
    """TS-E2E-ERR-TIM-001: Timeout payload must include retry budget details."""
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=_payload("timeout_primary"),
            headers=seeded_auth_headers,
        )

    assert response.status_code == 504
    body = response.json()
    assert body["detail"]["retry_count"] == 3
    assert body["detail"]["retryable"] is True


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_004_three_timeouts_open_circuit_and_fourth_request_short_circuits(
    live_app,
    seeded_auth_headers,
) -> None:
    """TS-E2E-ERR-TIM-001: Circuit breaker opens after repeated timeouts."""
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        for _ in range(3):
            response = await client.post(
                "/api/v1/decision-intelligence/execute",
                json=_payload("timeout_primary"),
                headers=seeded_auth_headers,
            )
            assert response.status_code == 504

        final = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=_payload("timeout_primary"),
            headers=seeded_auth_headers,
        )

    assert final.status_code == 503
    assert final.json()["detail"]["code"] == "CIRCUIT_OPEN"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_005_circuit_half_open_probe_recovers_to_closed_state(live_app, seeded_auth_headers) -> None:
    """TS-E2E-ERR-TIM-001: Recovery path must close breaker after successful probe."""
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=_payload("circuit_recovery_probe"),
            headers=seeded_auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["circuit_breaker_state"] == "closed"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_006_timeout_saturation_is_isolated_per_tenant(
    live_app,
    seeded_auth_headers,
    seeded_auth_headers_tenant_b,
) -> None:
    """TS-E2E-ERR-TIM-001: Timeout pressure in tenant A must not degrade tenant B."""
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        for _ in range(3):
            await client.post(
                "/api/v1/decision-intelligence/execute",
                json=_payload("timeout_primary"),
                headers=seeded_auth_headers,
            )

        tenant_a = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=_payload("timeout_primary"),
            headers=seeded_auth_headers,
        )
        tenant_b = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=_payload("normal"),
            headers=seeded_auth_headers_tenant_b,
        )

    assert tenant_a.status_code == 503
    assert tenant_b.status_code == 200


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_007_short_circuit_response_sets_retry_after_header(live_app, seeded_auth_headers) -> None:
    """TS-E2E-ERR-TIM-001: Open-circuit short-circuit must include Retry-After header."""
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        for _ in range(3):
            await client.post(
                "/api/v1/decision-intelligence/execute",
                json=_payload("timeout_primary"),
                headers=seeded_auth_headers,
            )
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=_payload("timeout_primary"),
            headers=seeded_auth_headers,
        )

    assert response.status_code == 503
    assert "Retry-After" in response.headers


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_008_timeout_or_fallback_path_emits_traceability_headers(
    live_app,
    seeded_auth_headers,
) -> None:
    """TS-E2E-ERR-TIM-001: Timeout/fallback responses must expose traceability headers."""
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=_payload("timeout_with_fallback_success"),
            headers=seeded_auth_headers,
        )

    assert response.status_code in {200, 504, 503}
    assert "X-Trace-Id" in response.headers
    assert "X-Fallback-Path" in response.headers
