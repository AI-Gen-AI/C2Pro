"""
TS-E2E-FLW-DOC-001: Coherence route contract tests.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from fastapi import HTTPException

from src.coherence.router import (
    CoherenceEvaluateRequest,
    evaluate_project_coherence,
    get_coherence_dashboard,
)
from src.projects.adapters.persistence.models import ProjectORM


def _request_for_tenant(tenant_id):
    return SimpleNamespace(tenant_id=tenant_id)


@pytest.mark.asyncio
async def test_canonical_coherence_dashboard_route_exists(
    client,
    db,
    test_tenant,
    test_user,
    get_auth_headers,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Coherence Contract Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.commit()

    response = await client.get(
        f"/api/v1/coherence/dashboard/{project.id}",
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code == 200
    assert response.json()["project_id"] == str(project.id)


@pytest.mark.asyncio
async def test_legacy_coherence_dashboard_route_remains_supported(
    db,
    test_tenant,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Legacy Coherence Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.commit()

    result = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert result.project_id == str(project.id)


@pytest.mark.asyncio
async def test_canonical_coherence_evaluate_route_is_registered(
    client,
    test_user,
    test_tenant,
    get_auth_headers,
) -> None:
    response = await client.post(
        "/api/v1/coherence/evaluate",
        json={},
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code != 404

@pytest.mark.asyncio
async def test_s3_contract_pending_blocks_evaluate_before_other_document_clauses(
    monkeypatch,
) -> None:
    """No numeric Score or new alerts when contract approval is outstanding.

    Even if budget/schedule chunks would be found, the approval gate must run
    before the RAG reader. The product's current-revision resolver determines
    whether a trusted A remains canonical while a proposed B awaits approval.
    """
    project_id = uuid4()
    tenant_id = uuid4()
    seen = []

    async def _pending(_db, scoped_project, scoped_tenant):
        seen.append("approval_check")
        assert scoped_project == project_id
        assert scoped_tenant == tenant_id
        return True

    async def _forbidden_rag(*_args, **_kwargs):
        raise AssertionError("Unapproved contract must block RAG-based scoring")

    monkeypatch.setattr("src.coherence.router._contracts_awaiting_approval", _pending)
    monkeypatch.setattr("src.coherence.router.get_clauses_from_rag", _forbidden_rag)

    result = await evaluate_project_coherence(
        payload=CoherenceEvaluateRequest(project_id=project_id),
        include_diagnostics=True,
        db=None,
        current_user=_request_for_tenant(tenant_id),
        flags_service=None,
    )

    assert seen == ["approval_check"]
    assert result.overall_score is None
    assert result.score_reason == "contract_pending_approval"
    assert result.alerts == []
    assert set(result.score_missing_dimensions or []) == {
        "SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"
    }


@pytest.mark.asyncio
async def test_s3_canonical_contract_proceeds_to_normal_clause_loading(monkeypatch) -> None:
    project_id = uuid4()
    tenant_id = uuid4()
    seen = []

    async def _not_pending(_db, _project, _tenant):
        seen.append("approval_check")
        return False

    async def _no_rag_clauses(*_args):
        seen.append("rag_read")
        return []

    monkeypatch.setattr("src.coherence.router._contracts_awaiting_approval", _not_pending)
    monkeypatch.setattr("src.coherence.router.get_clauses_from_rag", _no_rag_clauses)

    with pytest.raises(HTTPException) as exc:
        await evaluate_project_coherence(
            payload=CoherenceEvaluateRequest(project_id=project_id),
            include_diagnostics=True,
            db=None,
            current_user=_request_for_tenant(tenant_id),
            flags_service=None,
        )
    assert seen == ["approval_check", "rag_read"]
    assert exc.value.status_code == 404


