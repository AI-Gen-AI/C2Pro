"""
Refers to Suite ID: TS-E2E-PER-LRG-001

E2E RED tests for large-load and performance contracts.
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time
from uuid import uuid4

import pytest

from src.core.auth.models import Tenant, User


if os.getenv("C2PRO_TEST_LIGHT") == "1":
    pytest.skip(
        "Performance RED suite is skipped in light test mode; run in dedicated perf environment.",
        allow_module_level=True,
    )


def _headers(generate_token, user: User, tenant: Tenant) -> dict[str, str]:
    token = generate_token(
        user_id=user.id,
        tenant_id=tenant.id,
        email=user.email,
        role="admin",
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_project(test_tenant: Tenant) -> dict:
    from src.projects.adapters.http.router import _add_fake_project

    project = {
        "id": uuid4(),
        "tenant_id": test_tenant.id,
        "name": "Performance RED Project",
        "code": f"PER-RED-{uuid4().hex[:6]}",
        "project_type": "construction",
        "estimated_budget": 750000.0,
        "currency": "EUR",
        "version": 1,
    }
    _add_fake_project(project)
    return project


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_001_large_bulk_upload_meets_throughput_sla_and_contract(
    client,
    test_user: User,
    test_tenant: Tenant,
    generate_token,
) -> None:
    """TS-E2E-PER-LRG-001: 100 docs bulk upload must satisfy SLA + perf metadata."""
    headers = _headers(generate_token, test_user, test_tenant)
    project = await _seed_project(test_tenant)

    docs = [
        {"filename": f"doc-{i}.pdf", "document_type": "contract", "file_data": f"blob-{i}"}
        for i in range(100)
    ]
    start = time.perf_counter()
    response = await client.post(
        f"/api/v1/projects/{project['id']}/documents/bulk",
        json={"documents": docs},
        headers=headers,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert response.status_code == 202
    assert elapsed_ms < 3000
    body = response.json()
    assert body["processing_ms"] <= 3000
    assert body["throughput_docs_per_sec"] >= 33


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_002_list_projects_p95_under_1500ms_for_10_concurrent_requests(
    client,
    test_user: User,
    test_tenant: Tenant,
    generate_token,
) -> None:
    """TS-E2E-PER-LRG-001: p95 latency guardrail under concurrent read load."""
    headers = _headers(generate_token, test_user, test_tenant)

    async def do_request() -> tuple[int, float]:
        t0 = time.perf_counter()
        res = await client.get("/api/v1/projects", headers=headers)
        return res.status_code, (time.perf_counter() - t0) * 1000

    results = await asyncio.gather(*[do_request() for _ in range(10)])
    statuses = [s for s, _ in results]
    latencies = sorted(ms for _, ms in results)

    assert all(s == 200 for s in statuses)
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    assert p95 < 1500


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_003_overload_returns_structured_429_with_retry_after(
    client,
    test_user: User,
    test_tenant: Tenant,
    generate_token,
) -> None:
    """TS-E2E-PER-LRG-001: overload must degrade gracefully with structured 429."""
    headers = _headers(generate_token, test_user, test_tenant)
    project = await _seed_project(test_tenant)

    payload = {"items": [{"code": "1", "name": "Root", "level": 1}]}
    responses = await asyncio.gather(
        *[
            client.post(
                f"/api/v1/projects/{project['id']}/wbs/bulk",
                json=payload,
                headers=headers,
            )
            for _ in range(10)
        ]
    )
    throttled = [r for r in responses if r.status_code == 429]

    assert len(throttled) >= 1
    for response in throttled:
        assert "Retry-After" in response.headers
        assert response.json()["detail"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_004_bulk_endpoint_exposes_server_timing_header(
    client,
    test_user: User,
    test_tenant: Tenant,
    generate_token,
) -> None:
    """TS-E2E-PER-LRG-001: performance endpoint must expose Server-Timing."""
    headers = _headers(generate_token, test_user, test_tenant)
    project = await _seed_project(test_tenant)

    response = await client.post(
        f"/api/v1/projects/{project['id']}/documents/bulk",
        json={"documents": [{"filename": "a.pdf", "document_type": "contract", "file_data": "x"}]},
        headers=headers,
    )

    assert response.status_code == 202
    assert "Server-Timing" in response.headers
    assert "app;" in response.headers["Server-Timing"]


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_005_tenant_isolation_under_load_has_balanced_latency(
    client,
    test_user: User,
    test_tenant: Tenant,
    test_user_2: User,
    test_tenant_2: Tenant,
    generate_token,
) -> None:
    """TS-E2E-PER-LRG-001: load on tenant A must not starve tenant B."""
    headers_a = _headers(generate_token, test_user, test_tenant)
    headers_b = _headers(generate_token, test_user_2, test_tenant_2)

    async def timed_list(headers: dict[str, str]) -> float:
        t0 = time.perf_counter()
        res = await client.get("/api/v1/projects", headers=headers)
        assert res.status_code == 200
        return (time.perf_counter() - t0) * 1000

    lat_a, lat_b = await asyncio.gather(
        asyncio.gather(*[timed_list(headers_a) for _ in range(6)]),
        asyncio.gather(*[timed_list(headers_b) for _ in range(6)]),
    )

    mean_a = statistics.mean(lat_a)
    mean_b = statistics.mean(lat_b)
    assert abs(mean_a - mean_b) < 300


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_006_perf_observability_snapshot_endpoint_available(
    client,
    test_user: User,
    test_tenant: Tenant,
    generate_token,
) -> None:
    """TS-E2E-PER-LRG-001: perf snapshot endpoint must exist for load runs."""
    headers = _headers(generate_token, test_user, test_tenant)

    response = await client.get("/api/v1/observability/performance/snapshot", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert "p95_ms" in body
    assert "p99_ms" in body
    assert "error_rate" in body

