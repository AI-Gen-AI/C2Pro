"""PR-C2 clause impact resolution over persisted relationships (real PostgreSQL).

Refers to Suite ID: TS-INT-P0C-TEMPORAL-IMPACT-001.

Upload V1 and persist its clause exactly as ingestion does (the V1 snapshot id
is the clause row id, bound to V1), re-upload V2, append the worker's analysis
events, link real rows to the V1 clause, then prove that impact follows only
those foreign keys, is tenant scoped, flags only live alerts as potentially
stale, never confirms the RACI hop, and refuses a clause it cannot prove
belongs to the earlier revision.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert
from src.core.auth.models import SubscriptionPlan, Tenant, User
from src.documents.adapters.persistence.models import ClauseORM
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.adapters.storage.local_file_storage_service import LocalFileStorageService
from src.documents.application.reupload_document_use_case import ReuploadDocumentUseCase
from src.documents.application.upload_document_use_case import UploadDocumentUseCase
from src.documents.domain.models import Clause, ClauseType, DocumentType
from src.procurement.adapters.persistence.models import BOMItemORM
from src.shared_kernel.enums import AlertSeverity, AlertStatus, AlertType
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.stakeholders.domain.models import RACIRole
from src.temporal.adapters import temporal_review_gate
from src.temporal.adapters.persistence.clause_impact_resolver import SqlAlchemyClauseImpactResolver
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.application.change_qualification import qualify_event
from src.temporal.application.impact_assessment import assess_change_impacts
from src.temporal.application.revision_change_orchestrator import build_revision_analysis_events
from src.temporal.application.temporal_review import revision_requires_temporal_review
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.entity_ref import TemporalEntityRef
from src.temporal.domain.impact import ImpactStatus
from src.wbs.adapters.persistence.models import WBSNodeORM

pytestmark = pytest.mark.asyncio


class _ProjectRepo:
    async def exists_by_id(self, _project_id: UUID, _tenant_id: UUID) -> bool:
        return True


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in ("upload_document_use_case", "reupload_document_use_case"):
        monkeypatch.setattr(
            f"src.documents.application.{module}.enqueue_project_snapshot", lambda **_kwargs: None
        )
    monkeypatch.setattr(
        "src.documents.application.reupload_document_use_case._enqueue_document_processing",
        lambda _document_id, _revision_id=None, _generation=None: None,
    )


async def _tenant_with_project(db: AsyncSession) -> tuple[UUID, UUID, UUID]:
    tenant_id, user_id, project_id = uuid4(), uuid4(), uuid4()
    db.add_all(
        [
            Tenant(
                id=tenant_id,
                name="t",
                slug=f"t-{tenant_id.hex[:8]}",
                subscription_plan=SubscriptionPlan.PROFESSIONAL,
                ai_budget_monthly=100.0,
            ),
            User(
                id=user_id,
                tenant_id=tenant_id,
                email=f"u-{user_id.hex[:8]}@test.com",
                hashed_password="h",
                first_name="t",
                last_name="t",
                role="admin",
            ),
        ]
    )
    await db.commit()
    await db.execute(
        text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
            "VALUES (:id, :tid, 'impact', :code, 'construction', 'active', 'EUR', now(), now())"
        ),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return tenant_id, user_id, project_id


def _clause(
    revision: DocumentRevision, clause_text: str, *, clause_id: UUID | None = None
) -> Clause:
    return Clause(
        id=clause_id or uuid4(),
        project_id=revision.project_id,
        tenant_id=revision.tenant_id,
        document_id=revision.document_id,
        clause_code="PEN-1",
        clause_type=ClauseType.PENALTY,
        title="Delay penalty",
        full_text=clause_text,
        extracted_entities={"evidence_location": {"revision_id": str(revision.revision_id)}},
    )


async def _analyse(db: AsyncSession, revision: DocumentRevision, clause: Clause) -> None:
    events = SqlAlchemyProjectEventRepository(db)
    prior = await events.list_for_project(revision.project_id, revision.tenant_id)
    for event in await build_revision_analysis_events(
        revision=revision, clauses=[clause], existing_events=prior
    ):
        await events.append(event)
    await db.commit()


def _persist_clause(db: AsyncSession, clause: Clause) -> None:
    db.add(
        ClauseORM(
            id=clause.id,
            tenant_id=clause.tenant_id,
            project_id=clause.project_id,
            document_id=clause.document_id,
            clause_code=clause.clause_code,
            title=clause.title,
            full_text=clause.full_text,
            extracted_entities=clause.extracted_entities,
        )
    )


def _alert(
    tenant_id: UUID, project_id: UUID, title: str, status: AlertStatus, **links: object
) -> Alert:
    return Alert(
        id=uuid4(),
        tenant_id=tenant_id,
        project_id=project_id,
        alert_type=AlertType.RISK,
        severity=AlertSeverity.HIGH,
        category="contract",
        title=title,
        message=title,
        description=title,
        status=status,
        **links,
    )


def _wbs(tenant_id: UUID, project_id: UUID, code: str, lft: int, **links: object) -> WBSNodeORM:
    return WBSNodeORM(
        id=uuid4(),
        tenant_id=tenant_id,
        project_id=project_id,
        code=code,
        name=f"Package {code}",
        lft=lft,
        rgt=lft + 1,
        depth=0,
        **links,
    )


async def test_clause_impact_follows_only_persisted_links(
    db: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = LocalFileStorageService(base_dir=tmp_path)
    tenant_a, user_a, project_a = await _tenant_with_project(db)
    tenant_b, _user_b, _project_b = await _tenant_with_project(db)
    doc_repo = SqlAlchemyDocumentRepository(db)
    rev_repo = SqlAlchemyDocumentRevisionRepository(db)
    events = SqlAlchemyProjectEventRepository(db)

    document = await UploadDocumentUseCase(
        document_repository=doc_repo,
        storage_service=storage,
        project_repository=_ProjectRepo(),  # type: ignore[arg-type]
        revision_repository=rev_repo,
        event_repository=events,
    ).execute(
        project_id=project_a,
        file=UploadFile(filename="contract.pdf", file=BytesIO(b"%PDF penalty 1% per week")),
        document_type=DocumentType.CONTRACT,
        user_id=user_a,
        tenant_id=tenant_a,
    )
    [revision_1] = await rev_repo.list_lineage(document.id, tenant_a)
    v1_clause = _clause(revision_1, "The contractor pays a delay penalty of 1% per week.")
    _persist_clause(db, v1_clause)
    await db.commit()
    await _analyse(db, revision_1, v1_clause)

    await ReuploadDocumentUseCase(
        document_repository=doc_repo,
        revision_repository=rev_repo,
        storage_service=storage,
        event_repository=events,
    ).execute(
        tenant_id=tenant_a,
        document_id=document.id,
        file_content=b"%PDF penalty 2% per week",
        user_id=user_a,
    )
    revision_1, revision_2 = await rev_repo.list_lineage(document.id, tenant_a)
    await _analyse(
        db, revision_2, _clause(revision_2, "The contractor pays a delay penalty of 2% per week.")
    )

    # Real rows linked to the V1 clause, plus one unrelated alert.
    stakeholder_id = uuid4()
    db.add(
        StakeholderORM(
            id=stakeholder_id,
            tenant_id=tenant_a,
            project_id=project_a,
            name="Owner Rep",
            source_clause_id=v1_clause.id,
        )
    )
    live = _alert(
        tenant_a, project_a, "Penalty exposure", AlertStatus.OPEN, source_clause_id=v1_clause.id
    )
    resolved = _alert(
        tenant_a,
        project_a,
        "Old penalty note",
        AlertStatus.RESOLVED,
        related_clause_ids=[v1_clause.id],
    )
    unrelated = _alert(
        tenant_a, project_a, "Unrelated", AlertStatus.OPEN, related_clause_ids=[uuid4()]
    )
    direct_wbs = _wbs(tenant_a, project_a, "1.1", 1, source_clause_id=v1_clause.id)
    raci_wbs = _wbs(tenant_a, project_a, "1.2", 3)
    bom = BOMItemORM(
        id=uuid4(),
        project_id=project_a,
        item_name="Sheet piles",
        quantity=10,
        contract_clause_id=v1_clause.id,
    )
    # Same tenant, ANOTHER project, rows pointing at the same clause id: never reported.
    other_project = uuid4()
    await db.execute(
        text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, "
            "created_at, updated_at) VALUES (:id, :tid, 'other', :code, 'construction', 'active', "
            "'EUR', now(), now())"
        ),
        {"id": other_project, "tid": tenant_a, "code": f"P-{other_project.hex[:8]}"},
    )
    foreign_alert = _alert(
        tenant_a,
        other_project,
        "Other project alert",
        AlertStatus.OPEN,
        source_clause_id=v1_clause.id,
    )
    foreign_stakeholder = StakeholderORM(
        id=uuid4(),
        tenant_id=tenant_a,
        project_id=other_project,
        name="Other",
        source_clause_id=v1_clause.id,
    )
    foreign_wbs = _wbs(tenant_a, other_project, "9.1", 1, source_clause_id=v1_clause.id)
    foreign_raci_wbs = _wbs(tenant_a, other_project, "9.2", 3)
    foreign_bom = BOMItemORM(
        id=uuid4(),
        project_id=other_project,
        item_name="Other",
        quantity=1,
        contract_clause_id=v1_clause.id,
    )
    db.add_all([live, resolved, unrelated, direct_wbs, raci_wbs, bom])
    db.add_all([foreign_alert, foreign_stakeholder, foreign_wbs, foreign_raci_wbs, foreign_bom])
    await db.flush()
    db.add_all(
        [
            StakeholderWBSRaciORM(
                id=uuid4(),
                tenant_id=tenant_a,
                project_id=project_a,
                stakeholder_id=stakeholder_id,
                wbs_item_id=raci_wbs.id,
                raci_role=RACIRole.ACCOUNTABLE,
            ),
            # A miswired cross-project RACI row is not a path either.
            StakeholderWBSRaciORM(
                id=uuid4(),
                tenant_id=tenant_a,
                project_id=other_project,
                stakeholder_id=stakeholder_id,
                wbs_item_id=foreign_raci_wbs.id,
                raci_role=RACIRole.INFORMED,
            ),
        ]
    )
    await db.commit()

    source = TemporalEntityRef(
        artifact_type="contract",
        document_id=document.id,
        revision_id=revision_1.revision_id,
        entity_type="clause",
        entity_id=str(v1_clause.id),
        evidence=[],
    )
    result = await SqlAlchemyClauseImpactResolver(db, tenant_id=tenant_a).resolve(source)

    assert result.source_verified is True
    by_target = {(link.target.entity_type, link.target.entity_id): link for link in result.links}
    assert set(by_target) == {
        ("alert", live.id),
        ("alert", resolved.id),
        ("stakeholder", stakeholder_id),
        ("wbs_node", direct_wbs.id),
        ("bom_item", bom.id),
        ("wbs_node", raci_wbs.id),
    }
    assert by_target[("alert", live.id)].target.potentially_stale is True
    assert by_target[("alert", resolved.id)].target.potentially_stale is False
    assert by_target[("alert", live.id)].relationship.via == "alerts.source_clause_id"
    assert by_target[("alert", resolved.id)].relationship.via == "alerts.related_clause_ids"
    # An aggregated "related" citation has no established strength: it can only propose.
    assert by_target[("alert", resolved.id)].relationship.link_confidence is None
    hop = by_target[("wbs_node", raci_wbs.id)].relationship
    assert hop.kind == "indirect" and hop.link_confidence is None

    # The same relationships through the stored V1 -> V2 change event.
    change = await events.get_change_for_revision(
        tenant_id=tenant_a,
        project_id=project_a,
        document_id=document.id,
        revision_id=revision_2.revision_id,
    )
    assert change is not None
    qualification = qualify_event(change)
    impacts = await assess_change_impacts(
        event=change,
        qualification=qualification,
        resolvers={"clause": SqlAlchemyClauseImpactResolver(db, tenant_id=tenant_a)},
        artifact_type="contract",
    )
    sourced = [impact for impact in impacts if impact.source.entity_id == str(v1_clause.id)]
    assert sourced, "the changed V1 clause is resolved through its persisted id"
    for impact in sourced:
        assert impact.source.revision_id == revision_1.revision_id
        for item in impact.assessment.items:
            if item.relationship.kind == "indirect":
                assert item.status == ImpactStatus.CANDIDATE
                assert item.confidence is None

    # Another tenant cannot see the clause, so nothing is claimed.
    foreign = await SqlAlchemyClauseImpactResolver(db, tenant_id=tenant_b).resolve(source)
    assert foreign.source_verified is False and foreign.links == []

    # V1's clause cannot be claimed as a clause of V2.
    stale = await SqlAlchemyClauseImpactResolver(db, tenant_id=tenant_a).resolve(
        source.model_copy(update={"revision_id": revision_2.revision_id})
    )
    assert stale.source_verified is False and stale.links == []

    # The trust seam reads the same revision-scoped events (TS-INT-P0C-TEMPORAL-REVIEW-001).
    baseline = await revision_requires_temporal_review(
        revisions=rev_repo,
        events=events,
        tenant_id=tenant_a,
        document_id=document.id,
        revision_id=revision_1.revision_id,
        artifact_type="contract",
    )
    assert (baseline.required, baseline.reason) == (False, "baseline_revision")
    own_events = await events.list_for_revision(
        tenant_id=tenant_a, revision_id=revision_2.revision_id
    )
    assert own_events and all(
        event.source_revision_id == revision_2.revision_id for event in own_events
    )
    assert (
        await events.list_for_revision(tenant_id=tenant_b, revision_id=revision_2.revision_id) == []
    )
    decision = await revision_requires_temporal_review(
        revisions=rev_repo,
        events=events,
        tenant_id=tenant_a,
        document_id=document.id,
        revision_id=revision_2.revision_id,
        artifact_type="contract",
    )
    assert decision.required is (qualification.effective_state != "ready")
    foreign_doc = await revision_requires_temporal_review(
        revisions=rev_repo,
        events=events,
        tenant_id=tenant_a,
        document_id=uuid4(),
        revision_id=revision_2.revision_id,
        artifact_type="contract",
    )
    assert (foreign_doc.required, foreign_doc.reason) == (True, "revision_document_mismatch")

    # Through the real N12 gate adapter (its own document-type lookup): a contract
    # revision with a parent but no temporal events is MISSING its assessment.
    @asynccontextmanager
    async def _tenant_session(_tenant: UUID) -> AsyncIterator[AsyncSession]:
        yield db

    monkeypatch.setattr(temporal_review_gate, "get_session_with_tenant", _tenant_session)
    gated = await temporal_review_gate.revision_requires_temporal_review(
        tenant_id=str(tenant_a),
        document_id=str(document.id),
        revision_id=str(revision_2.revision_id),
    )
    assert gated == decision
    await ReuploadDocumentUseCase(
        document_repository=doc_repo,
        revision_repository=rev_repo,
        storage_service=storage,
        event_repository=events,
    ).execute(
        tenant_id=tenant_a,
        document_id=document.id,
        file_content=b"%PDF penalty 3% per week",
        user_id=user_a,
    )
    revision_3 = (await rev_repo.list_lineage(document.id, tenant_a))[-1]
    unanalysed = await temporal_review_gate.revision_requires_temporal_review(
        tenant_id=str(tenant_a),
        document_id=str(document.id),
        revision_id=str(revision_3.revision_id),
    )
    assert (unanalysed.required, unanalysed.reason) == (True, "temporal_comparison_missing")

    # Refusals: never a claim from an id that is not this document's persisted clause.
    resolver = SqlAlchemyClauseImpactResolver(db, tenant_id=tenant_a)
    for bogus, reason in (
        (source.model_copy(update={"entity_id": "AUTO-003"}), "not a persisted id"),
        (source.model_copy(update={"document_id": uuid4()}), "another document"),
        (source.model_copy(update={"revision_id": uuid4()}), "not a revision of this document"),
        (source.model_copy(update={"entity_id": str(uuid4())}), "no longer persisted"),
    ):
        refused = await resolver.resolve(bogus)
        assert refused.source_verified is False and refused.links == []
        assert reason in str(refused.reason)

    # The What Changed detail through the real router dependencies and database.
    from types import SimpleNamespace

    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from src.core.auth.dependencies import get_current_user
    from src.temporal.adapters.http import router as temporal_router

    monkeypatch.setattr(temporal_router, "get_session_with_tenant", _tenant_session)
    app = FastAPI()
    app.include_router(temporal_router.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        tenant_id=tenant_a, id=user_a
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/projects/{project_a}/documents/{document.id}/changes/{revision_2.revision_id}"
        )
    assert response.status_code == 200
    body = response.json()
    assert body["basis"] == "observed"
    sourced_impacts = [i for i in body["impacts"] if i["source"]["entity_id"] == str(v1_clause.id)]
    assert sourced_impacts and sourced_impacts[0]["source"]["artifact_type"] == "contract"
    targets = {item["target"]["entity_id"] for item in sourced_impacts[0]["assessment"]["items"]}
    assert str(foreign_alert.id) not in targets
    # No #714 candidate is bound to this revision: the projection says so, nothing is invented.
    assert body["projection"]["status"] == "none"
    assert body["projection"]["projected_score"] is None
