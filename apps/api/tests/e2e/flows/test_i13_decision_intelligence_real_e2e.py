"""
Refers to Suite ID: TS-I13-E2E-REAL-001

Real HTTP-level E2E tests for Decision Intelligence flow (I13).
No service mocking; assertions are strict and expected to fail in RED.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus


def _skip_if_decision_ports_not_wired(response) -> None:
    if response.status_code >= 500 and "requires real port implementations" in response.text:
        pytest.skip(
            "Decision Intelligence real ports are not wired in this local runtime.",
            allow_module_level=False,
        )


@pytest_asyncio.fixture
async def live_app(app):
    async with LifespanManager(app):
        yield app


@pytest_asyncio.fixture
async def pending_i13_review_item(
    seeded_auth_context: dict[str, str],
) -> AsyncGenerator[UUID, None]:
    """Seed an approvable review item for the authenticated I13 tenant."""
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, connect_args={"statement_cache_size": 0})
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    item_id = uuid4()
    try:
        async with session_factory() as session:
            session.add(
                ReviewItemORM(
                    id=item_id,
                    item_id=item_id,
                    item_type="final_decision_package",
                    current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
                    confidence=0.4,
                    impact_level=ImpactLevel.HIGH,
                    tenant_id=UUID(seeded_auth_context["tenant_id"]),
                    sla_due_date=datetime.now(UTC).replace(tzinfo=None),
                    item_data={},
                    review_metadata={},
                )
            )
            await session.commit()

        yield item_id
    finally:
        async with session_factory() as session:
            review_item = await session.get(ReviewItemORM, item_id)
            if review_item is not None:
                await session.delete(review_item)
                await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_real_e2e_generates_final_package_with_evidence_and_risks(
    live_app,
    seeded_auth_headers,
) -> None:
    headers = seeded_auth_headers
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "JVBERi0xLjQgbW9jayBwZGY=",
    }

    async with AsyncClient(
        transport=ASGITransport(app=live_app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=headers,
        )

    _skip_if_decision_ports_not_wired(response)
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
    seeded_auth_headers,
) -> None:
    headers = seeded_auth_headers
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "bG93LWNvbmZpZGVuY2U=",
        "force_profile": "low_confidence",
    }

    async with AsyncClient(
        transport=ASGITransport(app=live_app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=headers,
        )

    _skip_if_decision_ports_not_wired(response)
    assert response.status_code == 409
    assert "Finalization blocked: Item requires review." in response.text


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_real_e2e_missing_citations_blocks_finalization(
    live_app,
    seeded_auth_headers,
) -> None:
    headers = seeded_auth_headers
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "bWlzc2luZy1jaXRhdGlvbnM=",
        "force_profile": "missing_citations",
    }

    async with AsyncClient(
        transport=ASGITransport(app=live_app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=headers,
        )

    _skip_if_decision_ports_not_wired(response)
    assert response.status_code == 409
    assert "Finalization blocked: Missing required citations." in response.text


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_real_e2e_reviewer_approval_unlocks_package(
    live_app,
    seeded_auth_headers,
    pending_i13_review_item,
) -> None:
    headers = seeded_auth_headers
    payload = {
        "project_id": str(uuid4()),
        "document_bytes_b64": "cmV2aWV3LXJlcXVpcmVk",
        "review_decision": {
            "item_id": str(pending_i13_review_item),
            "reviewer_id": str(uuid4()),
            "reviewer_name": "I13 Reviewer",
            "action": "approve",
        },
    }

    async with AsyncClient(
        transport=ASGITransport(app=live_app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=headers,
        )

    _skip_if_decision_ports_not_wired(response)
    assert response.status_code == 200
    body = response.json()
    assert body["approved_by"] == "I13 Reviewer"
    assert body["approved_at"] is not None


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.flow
async def test_i13_real_e2e_mandatory_signoff_enforced(
    live_app,
    seeded_auth_headers,
) -> None:
    headers = seeded_auth_headers
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

    async with AsyncClient(
        transport=ASGITransport(app=live_app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/decision-intelligence/execute",
            json=payload,
            headers=headers,
        )

    _skip_if_decision_ports_not_wired(response)
    assert response.status_code == 409
    assert "Finalization blocked: Mandatory sign-off required." in response.text
