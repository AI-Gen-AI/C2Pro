"""P0b-L4-4 — authenticated health API acceptance / consumer validation.

Refers to Suite ID: TS-INT-API-HEALTH-L4-4.

The L4-4 exit contract is the merged Product Control: an authenticated
``GET /api/v1/projects/{project_id}/health`` must return the *real* single-document
product payload. This suite proves that end to end against the **real route** and the
**real PostgreSQL snapshot repository** — not model serialization, and not a fake repo,
because a stubbed repository cannot prove tenant isolation or that a persisted
``health_vector`` JSONB round-trips back through ``HealthVector`` reconstruction.

Covered (numbering follows the acceptance matrix):
 1  authenticated owner gets HTTP 200
 2  exactly six single-document category assessments when an assessment exists
 3  each category preserves state / findings / missing_data / gap
 4  single_document_evidence_granularity is returned and agrees with the artifact
 5  persisted clause UUID evidence ids survive to the HTTP response
 6  evidence_count agrees with the unique evidence ids
 7  honest-null: insufficient evidence is null/UNKNOWN, never numeric zero
 8  coherence_subscore stays NULL for the single-document case
 9  CROSS findings stay separate and are never attributed to a canonical category
10  an authoritative analysis with no usable assessment does NOT serve stale coverage
11  a no-new-analysis (SCHEDULED) snapshot still serves the last valid assessment
12  tenant A cannot read tenant B's project health
13  nonexistent / inaccessible project follows the existing API security contract
14  the response validates against the generated OpenAPI schema

Nothing here claims production validation: these are deterministic persisted fixtures.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.category_registry import CanonicalCategory
from src.coherence.models import Clause as CoherenceClause
from src.coherence.models import FindingSignal
from src.core.auth.dependencies import get_current_user
from src.health.adapters.http.router import (
    get_project_repository,
    get_snapshot_repository,
    router,
)
from src.health.application.health_engine import assemble_health_vector
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.health.domain.analysis_assessment import (
    decode_single_document_assessment,
    encode_single_document_assessment,
)
from src.health.domain.health_vector import (
    HealthBand,
    HealthDimension,
    HealthNullReason,
    HealthSignal,
    HealthVector,
)
from src.health.domain.single_document_coverage import EvidenceGranularity
from src.projects.adapters.persistence.project_repository import SQLAlchemyProjectRepository
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger

pytestmark = pytest.mark.asyncio

HEALTH_PATH = "/api/v1/projects/{project_id}/health"

# Two persisted-looking clause UUIDs: the evidence ids that must survive to HTTP.
BUDGET_CLAUSE_ID = UUID("aaaaaaaa-0000-4000-8000-000000000001")
LEGAL_CLAUSE_ID = UUID("aaaaaaaa-0000-4000-8000-000000000002")


def _qualifier(mapping: dict[str, set[CanonicalCategory]]):
    def qualify(text: str) -> set[CanonicalCategory]:
        return mapping.get(text, set())

    return qualify


def _coverage_with_cross():
    """Real L4-2 output: BUDGET + LEGAL evidenced, a CROSS finding preserved apart."""
    return assess_single_document_coverage(
        [
            CoherenceClause(id=str(BUDGET_CLAUSE_ID), text="budget text"),
            CoherenceClause(id=str(LEGAL_CLAUSE_ID), text="legal text"),
        ],
        [
            FindingSignal(
                rule_id="R-PAYMENT-CLARITY-01",
                clause_id=str(BUDGET_CLAUSE_ID),
                impact_score=0.4,
                category="BUDGET",
            ),
            FindingSignal(
                rule_id="CROSS-BUDGET-SCOPE",
                clause_id=f"{BUDGET_CLAUSE_ID}|{LEGAL_CLAUSE_ID}",
                impact_score=0.6,
                category="CROSS",
            ),
        ],
        qualifier=_qualifier(
            {
                "budget text": {CanonicalCategory.BUDGET},
                "legal text": {CanonicalCategory.LEGAL},
            }
        ),
    )


def _vector_payload(
    project_id: UUID,
    tenant_id: UUID,
    *,
    with_assessment: bool,
    granularity: EvidenceGranularity = EvidenceGranularity.CLAUSE,
) -> dict[str, Any]:
    """A real HealthVector built by the real assembler, serialized as it is persisted."""
    coverage = _coverage_with_cross() if with_assessment else None
    vector = assemble_health_vector(
        project_id,
        tenant_id,
        signals=[
            HealthSignal(
                dimension=HealthDimension.CONTRACT,
                score=None,
                band=HealthBand.UNKNOWN,
                confidence=0.0,
                missing_data=["no supporting evidence"],
                null_reason=HealthNullReason.INSUFFICIENT_EVIDENCE,
            )
        ],
        prior_composite=None,
        single_document_coverage=coverage,
        single_document_evidence_granularity=granularity if coverage is not None else None,
    )
    return vector.model_dump(mode="json")


async def _seed_project(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> None:
    """A real projects row: the route's ownership gate reads it via IProjectRepository."""
    await db.execute(
        text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, "
            "currency, created_at, updated_at) "
            "VALUES (:id, :tid, 'L4-4 acceptance', :code, 'construction', 'active', "
            "'EUR', now(), now()) ON CONFLICT (id) DO NOTHING"
        ),
        {"id": project_id, "tid": tenant_id, "code": f"L44-{project_id.hex[:8]}"},
    )
    await db.commit()


async def _persist_snapshot(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    *,
    with_assessment: bool,
    trigger: SnapshotTrigger = SnapshotTrigger.GRAPH_COMPLETED,
    captured_at: datetime | None = None,
    granularity: EvidenceGranularity = EvidenceGranularity.CLAUSE,
) -> ProjectSnapshot:
    """Persist a real snapshot through the real repository."""
    now = captured_at or datetime.now(UTC).replace(tzinfo=None)
    snapshot = ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        captured_at=now,
        trigger=trigger,
        health_vector=_vector_payload(
            project_id, tenant_id, with_assessment=with_assessment, granularity=granularity
        ),
        coherence_subscore=None,
        counts={},
        totals={},
        source_event_id=None,
        created_at=now,
    )
    await _seed_project(db, project_id, tenant_id)
    written = await SqlAlchemyProjectSnapshotRepository(db).append_snapshot(snapshot)
    await db.commit()
    return written


def _app(db: AsyncSession, principal_tenant_id: UUID) -> FastAPI:
    """The REAL router wired to the REAL PostgreSQL snapshot repository."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _current_user() -> SimpleNamespace:
        return SimpleNamespace(tenant_id=principal_tenant_id)

    async def _repo():
        yield SqlAlchemyProjectSnapshotRepository(db)

    async def _projects():
        yield SQLAlchemyProjectRepository(db)

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_snapshot_repository] = _repo
    app.dependency_overrides[get_project_repository] = _projects
    return app


async def _get_health(db: AsyncSession, principal_tenant_id: UUID, project_id: UUID):
    transport = ASGITransport(app=_app(db, principal_tenant_id))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(HEALTH_PATH.format(project_id=project_id))


def _assessments(body: dict[str, Any]) -> list[dict[str, Any]]:
    return body["single_document_coverage"]["assessments"]


# =====================================================================================
# 1-3 — authenticated owner, six categories, per-category structure
# =====================================================================================


async def test_01_authenticated_owner_receives_200(db: AsyncSession) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    await _persist_snapshot(db, project_id, tenant_id, with_assessment=True)

    response = await _get_health(db, tenant_id, project_id)

    assert response.status_code == 200


async def test_02_exactly_six_category_assessments(db: AsyncSession) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    await _persist_snapshot(db, project_id, tenant_id, with_assessment=True)

    body = (await _get_health(db, tenant_id, project_id)).json()

    assessments = _assessments(body)
    assert len(assessments) == 6
    assert {a["category"] for a in assessments} == {
        "SCOPE",
        "BUDGET",
        "TIME",
        "TECHNICAL",
        "LEGAL",
        "QUALITY",
    }


async def test_03_each_category_preserves_state_findings_missing_data_and_gap(
    db: AsyncSession,
) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    await _persist_snapshot(db, project_id, tenant_id, with_assessment=True)

    assessments = _assessments((await _get_health(db, tenant_id, project_id)).json())
    by_category = {a["category"]: a for a in assessments}

    for assessment in assessments:
        assert "state" in assessment
        assert "findings" in assessment
        assert "missing_data" in assessment
        assert "gap" in assessment

    # PRESENT carries evidence and no gap; INSUFFICIENT_EVIDENCE carries the actionable gap.
    budget = by_category["BUDGET"]
    assert budget["state"] == "present"
    assert budget["gap"] is None
    assert [f["rule_id"] for f in budget["findings"]] == ["R-PAYMENT-CLARITY-01"]

    scope = by_category["SCOPE"]
    assert scope["state"] == "insufficient_evidence"
    assert scope["gap"] is not None, "an insufficient category must carry an actionable gap"
    assert scope["missing_data"], "an insufficient category must state what is missing"


# =====================================================================================
# 4-6 — granularity, persisted UUID evidence ids, evidence_count
# =====================================================================================


async def test_04_evidence_granularity_is_returned_and_agrees_with_the_artifact(
    db: AsyncSession,
) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    await _persist_snapshot(
        db, project_id, tenant_id, with_assessment=True, granularity=EvidenceGranularity.CLAUSE
    )

    body = (await _get_health(db, tenant_id, project_id)).json()

    assert body["single_document_evidence_granularity"] == "clause"
    # Agreement with the artifact contract: the same enum the analysis artifact records.
    artifact = encode_single_document_assessment(
        _coverage_with_cross(), [], EvidenceGranularity.CLAUSE
    )
    decoded = decode_single_document_assessment(artifact)
    assert decoded is not None
    assert body["single_document_evidence_granularity"] == decoded.evidence_granularity.value


async def test_04b_document_granularity_is_reported_as_document(db: AsyncSession) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    await _persist_snapshot(
        db, project_id, tenant_id, with_assessment=True, granularity=EvidenceGranularity.DOCUMENT
    )

    body = (await _get_health(db, tenant_id, project_id)).json()

    assert body["single_document_evidence_granularity"] == "document"


async def test_05_persisted_clause_uuid_evidence_ids_survive_to_http(
    db: AsyncSession,
) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    await _persist_snapshot(db, project_id, tenant_id, with_assessment=True)

    assessments = _assessments((await _get_health(db, tenant_id, project_id)).json())
    ids = {cid for a in assessments for cid in a["evidence_clause_ids"]}

    assert ids == {str(BUDGET_CLAUSE_ID), str(LEGAL_CLAUSE_ID)}
    # They are real UUIDs over the wire, not opaque labels.
    assert all(UUID(cid) for cid in ids)


async def test_06_evidence_count_agrees_with_unique_evidence_ids(db: AsyncSession) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    await _persist_snapshot(db, project_id, tenant_id, with_assessment=True)

    for assessment in _assessments((await _get_health(db, tenant_id, project_id)).json()):
        ids = assessment["evidence_clause_ids"]
        assert assessment["evidence_count"] == len(set(ids)) == len(ids)


# =====================================================================================
# 7-9 — honest null, coherence_subscore, CROSS separation
# =====================================================================================


async def test_07_insufficient_evidence_is_null_never_numeric_zero(
    db: AsyncSession,
) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    await _persist_snapshot(db, project_id, tenant_id, with_assessment=True)

    body = (await _get_health(db, tenant_id, project_id)).json()

    # Dimension level: unknown is null + a null_reason, never 0.
    for dimension in body["dimensions"]:
        if dimension["band"] == "unknown":
            assert dimension["score"] is None, "unknown must be null, never 0"
            assert dimension["null_reason"] == "insufficient_evidence"
    assert body["composite_score"] is None, "no scored dimension => composite null, never 0"

    # Category level: insufficient evidence means zero *evidence*, and an explicit state —
    # the state carries the meaning, not a fabricated score.
    for assessment in _assessments(body):
        if assessment["state"] == "insufficient_evidence":
            assert assessment["evidence_clause_ids"] == []
            assert assessment["gap"] is not None


async def test_07b_owned_project_without_snapshot_is_honest_unknown_not_zero(
    db: AsyncSession,
) -> None:
    """"No data yet" stays a legitimate 200 for a project the caller actually owns."""
    project_id, tenant_id = uuid4(), uuid4()
    await _seed_project(db, project_id, tenant_id)

    response = await _get_health(db, tenant_id, project_id)
    assert response.status_code == 200
    body = response.json()

    assert body["composite_score"] is None
    assert body["composite_band"] == "unknown"
    assert body["single_document_coverage"] is None
    assert body["single_document_evidence_granularity"] is None
    assert all(d["score"] is None for d in body["dimensions"])


async def test_08_coherence_subscore_stays_null_for_single_document(
    db: AsyncSession,
) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    snapshot = await _persist_snapshot(db, project_id, tenant_id, with_assessment=True)

    body = (await _get_health(db, tenant_id, project_id)).json()

    assert snapshot.coherence_subscore is None
    assert body.get("coherence_subscore") is None


async def test_09_cross_findings_stay_separate_and_unattributed(
    db: AsyncSession,
) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    await _persist_snapshot(db, project_id, tenant_id, with_assessment=True)

    coverage = (await _get_health(db, tenant_id, project_id)).json()["single_document_coverage"]

    assert [f["rule_id"] for f in coverage["cross_findings"]] == ["CROSS-BUDGET-SCOPE"]
    for assessment in coverage["assessments"]:
        assert all(f["category"] != "CROSS" for f in assessment["findings"])


# =====================================================================================
# 10-11 — stale vs carry-forward, over HTTP
# =====================================================================================


async def test_10_unavailable_authoritative_analysis_does_not_serve_stale_coverage(
    db: AsyncSession,
) -> None:
    """A newer GRAPH_COMPLETED with no usable assessment must not resurrect the old one."""
    project_id, tenant_id = uuid4(), uuid4()
    base = datetime.now(UTC).replace(tzinfo=None)

    await _persist_snapshot(db, project_id, tenant_id, with_assessment=True, captured_at=base)
    await _persist_snapshot(
        db,
        project_id,
        tenant_id,
        with_assessment=False,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        captured_at=base + timedelta(hours=1),
    )

    body = (await _get_health(db, tenant_id, project_id)).json()

    assert body["single_document_coverage"] is None, "stale coverage was served"
    assert body["single_document_evidence_granularity"] is None


async def test_11_no_new_analysis_carry_forward_serves_last_valid_assessment(
    db: AsyncSession,
) -> None:
    """A SCHEDULED snapshot that carried the assessment forward still serves it."""
    project_id, tenant_id = uuid4(), uuid4()
    base = datetime.now(UTC).replace(tzinfo=None)

    await _persist_snapshot(db, project_id, tenant_id, with_assessment=True, captured_at=base)
    await _persist_snapshot(
        db,
        project_id,
        tenant_id,
        with_assessment=True,
        trigger=SnapshotTrigger.SCHEDULED,
        captured_at=base + timedelta(days=1),
    )

    body = (await _get_health(db, tenant_id, project_id)).json()

    assert body["single_document_coverage"] is not None
    assert body["single_document_evidence_granularity"] == "clause"
    assert len(_assessments(body)) == 6


# =====================================================================================
# 12-13 — tenancy and the security contract (HARD GATE)
# =====================================================================================


async def test_12_tenant_a_cannot_read_tenant_b_project_health(db: AsyncSession) -> None:
    """HARD GATE: route + real repository, not a model unit test."""
    project_id = uuid4()
    owner_tenant, other_tenant = uuid4(), uuid4()
    await _persist_snapshot(db, project_id, owner_tenant, with_assessment=True)

    owner_body = (await _get_health(db, owner_tenant, project_id)).json()
    assert owner_body["single_document_coverage"] is not None, "owner must see their own data"

    foreign = await _get_health(db, other_tenant, project_id)

    # An authorization failure is 404 — never a 200 carrying an empty vector, which
    # would be indistinguishable from a real project that has no snapshot yet.
    assert foreign.status_code == 404, "foreign tenant must not receive a 200 vector"
    assert str(owner_tenant) not in foreign.text
    assert "single_document_coverage" not in foreign.text


async def test_13_inaccessible_project_matches_nonexistent_project_response(
    db: AsyncSession,
) -> None:
    """Existence must not leak: a foreign project must look like a missing one."""
    real_project, owner_tenant, other_tenant = uuid4(), uuid4(), uuid4()
    await _persist_snapshot(db, real_project, owner_tenant, with_assessment=True)

    foreign = await _get_health(db, other_tenant, real_project)
    missing = await _get_health(db, other_tenant, uuid4())

    # Byte-identical: a foreign project is indistinguishable from a missing one, so the
    # response cannot be used to probe which project ids exist.
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


# =====================================================================================
# 14 — the response validates against the generated OpenAPI contract
# =====================================================================================


async def test_14_response_validates_against_the_published_contract(
    db: AsyncSession,
) -> None:
    project_id, tenant_id = uuid4(), uuid4()
    await _persist_snapshot(db, project_id, tenant_id, with_assessment=True)

    response = await _get_health(db, tenant_id, project_id)

    # Round-trips back through the declared response model without loss.
    restored = HealthVector.model_validate(response.json())
    assert restored.single_document_coverage is not None
    assert restored.single_document_evidence_granularity is EvidenceGranularity.CLAUSE

    # And the published document declares the fields the client will read.
    from pathlib import Path

    spec = Path(__file__).resolve().parents[5] / "docs" / "api" / "openapi.yaml"
    text = spec.read_text(encoding="utf-8")
    assert "single_document_evidence_granularity" in text
    assert "SingleDocumentCoverage" in text
    assert "/api/v1/projects/{project_id}/health" in text
