"""C3b-2 - the contract revision Temporal Intelligence journey on persisted state.

TS-INT-C3B2-JOURNEY-001 (C3b-2 tests 7-24). REAL PostgreSQL, the real upload /
re-upload use cases, the real ingestion clause staging (revision-bound rows +
immutable snapshot + L1 comparison), the REAL #714 trust authority
(``commit_candidate`` / ``reject_candidate``), the ONE C3b-1 artifact-keyed
materializer (``materialization_tasks``), and the What Changed HTTP routes over
real repositories:

    V1 TRUSTED -> V2 uploaded + analysed -> differences visible -> review
    -> V1 stays canonical until the EXACT V2 candidate is approved
    -> V2 TRUSTED -> governance-authorised effects materialize ONCE
    -> deferred effects (WBS) are qualified, not applied
    -> reload is durable -> V1 history stays inspectable.

WBS is a governed backbone: the AI proposal stays in the approved artifact and
never becomes canonical WBS here -- not even a project's first WBS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.adapters.persistence.models import Alert, Analysis, DocumentArtifactORM
from src.analysis.domain.contracts import DocumentArtifact, RiskItem, WbsActivity
from src.analysis.domain.trust import CandidateBinding, StaleCandidateError, TrustState
from src.core.auth.dependencies import get_current_user
from src.core.tasks import ingestion_tasks, materialization_tasks
from src.documents.application.get_document_with_clauses_use_case import (
    GetDocumentWithClausesUseCase,
)
from src.documents.domain.models import Document
from src.temporal.adapters.http.router import (
    get_event_repository,
    get_impact_assessor,
    get_project_repository,
    get_revision_projector,
    get_revision_status_reader,
    router,
)
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.adapters.persistence.revision_status_reader import (
    SqlAlchemyRevisionStatusReader,
)
from src.temporal.application.revision_projection import RevisionProjection
from src.temporal.domain.current_revision import CurrentRevisionStatus
from src.temporal.domain.document_revision import DocumentRevision
from src.wbs.adapters.persistence.models import WBSNodeORM
from tests.modules.integration.test_c3a_revision_bound_clauses import (
    _latest_proposed,
    _no_broker,  # noqa: F401 - autouse fixture
    _World,
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    independent_sessions,  # noqa: F401 - pytest fixture
)
from tests.support.legacy_wbs import seed_legacy_from_dicts

pytestmark = pytest.mark.asyncio

V1_BODY = (
    "1.- Penalties. The contractor pays a delay penalty of 1% per week of delay.\n\n"
    "2.- Payment. The owner pays each certified invoice within thirty days of receipt."
)
V2_BODY = (
    "1.- Penalties. The contractor pays a delay penalty of 5% per week of delay.\n\n"
    "2.- Payment. The owner pays each certified invoice within thirty days of receipt."
)
V3_BODY = (
    "1.- Penalties. The contractor pays a delay penalty of 3% per week of delay.\n\n"
    "2.- Payment. The owner pays each certified invoice within thirty days of receipt."
)
PROPOSED_WBS = [
    WbsActivity(code="1", name="Civil works (AI V2 proposal)", level=1),
    WbsActivity(code="1.1", name="Foundations (AI V2 proposal)", level=2, parent_code="1"),
]


# ── harness ──────────────────────────────────────────────────────────────────


class _Journey:
    def __init__(self, world: _World, sessions: Any) -> None:
        self.world = world
        self.db = world.db
        self.sessions = sessions

    async def stage(self, document: Document, revision: DocumentRevision, body: str) -> None:
        """The real ingestion staging: rows bound to the revision + snapshot + L1 change."""
        await ingestion_tasks._stage_contract_clauses(
            self.db,
            self.world.docs,
            document=document,
            tenant_id=self.world.tenant,
            source_revision=revision,
            authority_revision_id=revision.revision_id,
            parsed_text=body,
            parsed_payload={},
        )
        await self.db.commit()

    async def propose(
        self, document: Document, revision: DocumentRevision, *, wbs: list[WbsActivity] | None = None,
        risk: str = "Delay penalty exposure",
    ) -> CandidateBinding:
        await self.world.artifacts.save(
            DocumentArtifact(
                document_id=str(document.id),
                document_revision_id=str(revision.revision_id),
                doc_type="contract",
                extracted_risks=[RiskItem(title=risk, description="penalty clause")],
                extracted_wbs=list(wbs or []),
            ),
            project_id=self.world.project,
            tenant_id=self.world.tenant,
            trust_state=TrustState.PROPOSED,
        )
        await self.db.commit()
        return await _latest_proposed(self.db, document.id)

    async def approve(self, binding: CandidateBinding) -> Any:
        """The canonical #714 authority: exact-binding CAS + pending obligation, one txn."""
        async with self.sessions(self.world.tenant) as session:
            return await SqlAlchemyDocumentArtifactRepository(session).commit_candidate(
                binding, tenant_id=self.world.tenant
            )

    async def reject(self, binding: CandidateBinding) -> bool:
        async with self.sessions(self.world.tenant) as session:
            return await SqlAlchemyDocumentArtifactRepository(session).reject_candidate(
                binding, tenant_id=self.world.tenant
            )

    async def materialize(self, binding: CandidateBinding) -> dict[str, Any]:
        """One (at-least-once) delivery of the artifact-keyed materialization."""
        return await materialization_tasks.materialize_pending_artifact(
            artifact_id=binding.artifact_id, tenant_id=self.world.tenant, session_factory=self.sessions
        )

    async def trusted_v1(self, document: Document, v1: DocumentRevision) -> CandidateBinding:
        await self.stage(document, v1, V1_BODY)
        binding = await self.propose(document, v1, risk="Initial delay penalty")
        assert (await self.approve(binding)).outcome.value == "committed"
        assert (await self.materialize(binding))["status"] == "created"
        return binding

    async def obligation(self, artifact_id: UUID) -> Any:
        await self.db.commit()
        return (
            await self.db.execute(
                text(
                    "SELECT materialization_state, materialization_detail, materialized_analysis_id "
                    "FROM system_recovery.trusted_projection_index "
                    "WHERE artifact_id = cast(:a as uuid) AND tenant_id = cast(:t as uuid)"
                ),
                {"a": str(artifact_id), "t": str(self.world.tenant)},
            )
        ).first()

    async def counts(self) -> dict[str, int]:
        await self.db.commit()

        async def count(model: Any) -> int:
            return int(
                await self.db.scalar(
                    select(func.count()).select_from(model).where(model.project_id == self.world.project)
                )
                or 0
            )

        return {"analyses": await count(Analysis), "alerts": await count(Alert), "wbs": await count(WBSNodeORM)}

    async def analyses_of(self, artifact_id: UUID) -> list[Analysis]:
        await self.db.commit()
        return list(
            (await self.db.execute(select(Analysis).where(Analysis.source_artifact_id == artifact_id))).scalars()
        )

    async def status(self, document: Document, revision: DocumentRevision) -> Any:
        await self.db.commit()
        return await SqlAlchemyRevisionStatusReader(self.db).read(
            tenant_id=self.world.tenant,
            project_id=self.world.project,
            document_id=document.id,
            revision_id=revision.revision_id,
        )

    def app(self, *, tenant_id: UUID | None = None, owned: bool = True) -> FastAPI:
        """The What Changed routes over REAL repositories on the persisted state."""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        caller = tenant_id or self.world.tenant
        db = self.db

        class _Projects:
            async def exists_by_id(self, _project_id: UUID, _tenant_id: UUID) -> bool:
                return owned

        async def _user() -> Any:
            from types import SimpleNamespace

            return SimpleNamespace(tenant_id=caller)

        async def _events() -> Any:
            return SqlAlchemyProjectEventRepository(db)

        async def _projects() -> Any:
            return _Projects()

        async def _assessor() -> Any:
            async def assess(_event: Any, _qualification: Any) -> list[Any]:
                return []

            return assess

        async def _projector() -> Any:
            async def project(*, project_id: UUID, document_id: UUID, revision_id: UUID, qualification: Any) -> Any:
                return RevisionProjection.none(revision_id, "not under test")

            return project

        async def _status() -> Any:
            reader = SqlAlchemyRevisionStatusReader(db)

            async def read(*, project_id: UUID, document_id: UUID, revision_id: UUID) -> Any:
                return await reader.read(
                    tenant_id=caller, project_id=project_id, document_id=document_id, revision_id=revision_id
                )

            return read

        app.dependency_overrides[get_current_user] = _user
        app.dependency_overrides[get_event_repository] = _events
        app.dependency_overrides[get_project_repository] = _projects
        app.dependency_overrides[get_impact_assessor] = _assessor
        app.dependency_overrides[get_revision_projector] = _projector
        app.dependency_overrides[get_revision_status_reader] = _status
        return app

    async def detail(self, document: Document, revision: DocumentRevision, **kwargs: Any) -> Any:
        await self.db.commit()
        async with AsyncClient(transport=ASGITransport(app=self.app(**kwargs)), base_url="http://test") as client:
            return await client.get(
                f"/api/v1/projects/{self.world.project}/documents/{document.id}/changes/{revision.revision_id}"
            )

    async def timeline(self) -> list[dict[str, Any]]:
        await self.db.commit()
        async with AsyncClient(transport=ASGITransport(app=self.app()), base_url="http://test") as client:
            response = await client.get(f"/api/v1/projects/{self.world.project}/timeline", params={"limit": 100})
        assert response.status_code == 200
        return list(response.json()["items"])


@pytest.fixture
async def journey(db: AsyncSession, tmp_path: Path, independent_sessions: Any) -> _Journey:  # noqa: F811
    return _Journey(await _World(db, tmp_path).setup(), independent_sessions)


async def _wbs_rows(db: AsyncSession, project_id: UUID) -> list[tuple[Any, ...]]:
    await db.commit()
    return [
        tuple(row)
        for row in (
            await db.execute(
                select(WBSNodeORM.id, WBSNodeORM.code, WBSNodeORM.name, WBSNodeORM.parent_id)
                .where(WBSNodeORM.project_id == project_id)
                .order_by(WBSNodeORM.code)
            )
        ).all()
    ]


async def _v2_proposed(j: _Journey) -> tuple[Document, DocumentRevision, DocumentRevision, CandidateBinding]:
    document = await j.world.upload()
    [v1] = await j.world.lineage(document)
    await j.trusted_v1(document, v1)
    v2 = await j.world.reupload(document)
    await j.stage(document, v2, V2_BODY)
    binding = await j.propose(document, v2, wbs=PROPOSED_WBS)
    return document, v1, v2, binding


# ── 7-17. the full journey ───────────────────────────────────────────────────


async def test_full_v1_to_v2_journey_on_persisted_state(journey: _Journey, db: AsyncSession) -> None:
    j = journey
    document, v1, v2, binding = await _v2_proposed(j)
    v1_rows_before = sorted(
        (c.id, c.full_text) for c in await j.world.docs.list_revision_clauses(j.world.tenant, document.id, v1.revision_id)
    )
    before = await j.counts()

    # (7) V2 uploaded + analysed: its comparison against V1 is a real, current-matcher result.
    response = await j.detail(document, v2)
    assert response.status_code == 200
    change = response.json()
    assert change["event_type"] == "revision.changed"
    assert change["matcher_status"] == "current" and change["legacy_matcher"] is False
    assert change["effective"] is True and change["derivation"] == "original"
    assert change["provenance"]["source_revision_id"] == str(v1.revision_id)
    assert change["provenance"]["target_revision_id"] == str(v2.revision_id)
    modified = [c for c in change["changes"] if c.get("change_type") == "modified"]
    assert len(modified) == 1
    assert "1%" in modified[0]["before"]["full_text"] and "5%" in modified[0]["after"]["full_text"]

    # (8) review state: V2 is PROPOSED and NOT current; V1 stays canonical.
    status = change["revision_status"]
    assert status["trust_state"] == "proposed"
    assert status["is_current"] is False
    assert status["current_revision_id"] == str(v1.revision_id)
    assert status["materialization"] is None
    current = await j.world.current(document)
    assert (current.status, current.revision_id) == (CurrentRevisionStatus.TRUSTED, v1.revision_id)
    assert await j.world.current_texts(document) == set(await _texts(j, document, v1))

    # (9) a proposed candidate makes ZERO canonical effects.
    assert await j.analyses_of(binding.artifact_id) == []
    assert await j.counts() == before

    # (10) approval of the EXACT candidate through the canonical #714 authority.
    commit = await j.approve(binding)
    assert commit.outcome.value == "committed"
    obligation = await j.obligation(binding.artifact_id)
    assert obligation.materialization_state == "pending"

    # (11) governance-authorised effects materialize ONCE, whatever the deliveries.
    first = await j.materialize(binding)
    assert first["status"] == "created"
    assert (await j.materialize(binding))["status"] == "noop"
    await db.execute(
        text("UPDATE system_recovery.trusted_projection_index SET materialization_state = 'pending' "
             "WHERE artifact_id = cast(:a as uuid)"),
        {"a": str(binding.artifact_id)},
    )
    await db.commit()
    assert (await j.materialize(binding))["status"] == "already_materialized"
    [analysis] = await j.analyses_of(binding.artifact_id)
    after = await j.counts()
    assert after["analyses"] == before["analyses"] + 1
    assert after["alerts"] == before["alerts"] + 1  # one RISK alert, created once

    # (12) V2 is now TRUSTED and CURRENT; current readers switch to V2 only.
    current = await j.world.current(document)
    assert (current.status, current.revision_id) == (CurrentRevisionStatus.TRUSTED, v2.revision_id)
    assert await j.world.current_texts(document) == set(await _texts(j, document, v2))
    detail = await GetDocumentWithClausesUseCase(j.world.docs).execute(j.world.tenant, document.id)
    assert {c.revision_id for c in detail.clauses} == {v2.revision_id}

    # (13) materialized = governance-authorised effects applied; WBS deferred + qualified.
    obligation = await j.obligation(binding.artifact_id)
    assert obligation.materialization_state == "materialized"
    assert obligation.materialized_analysis_id == analysis.id
    body = (await j.detail(document, v2)).json()["revision_status"]
    assert body["trust_state"] == "trusted" and body["is_current"] is True
    assert body["materialization"]["state"] == "materialized"
    assert body["materialization"]["scope"] == "governance_authorized_effects_applied"
    assert set(body["materialization"]["qualifications"]) == {
        "WBS_GOVERNANCE_REQUIRED",
        "RISK_ALERT_RECONCILIATION_REQUIRED",
    }
    deferred = body["materialization"]["deferred_effects"]["wbs"]
    assert deferred["qualification"] == "WBS_GOVERNANCE_REQUIRED"
    assert deferred["proposed_nodes"] == len(PROPOSED_WBS)

    # (14) the What Changed timeline shows V2's comparison as the effective outcome.
    items = [i for i in await j.timeline() if i["provenance"].get("target_revision_id") == str(v2.revision_id)]
    assert [(i["event_type"], i["effective"]) for i in items] == [("revision.changed", True)]

    # (15) V1 history stays inspectable and untouched; it is no longer current.
    v1_rows_after = sorted(
        (c.id, c.full_text) for c in await j.world.docs.list_revision_clauses(j.world.tenant, document.id, v1.revision_id)
    )
    assert v1_rows_after == v1_rows_before
    v1_detail = await GetDocumentWithClausesUseCase(j.world.docs).execute(
        j.world.tenant, document.id, revision_id=v1.revision_id
    )
    assert {c.revision_id for c in v1_detail.clauses} == {v1.revision_id}
    v1_status = await j.status(document, v1)
    assert v1_status.is_current is False and v1_status.current_revision_id == v2.revision_id

    # (16) reload: a brand-new connection sees exactly the same durable state.
    async with j.sessions(j.world.tenant) as fresh:
        reloaded = await SqlAlchemyRevisionStatusReader(fresh).read(
            tenant_id=j.world.tenant, project_id=j.world.project, document_id=document.id,
            revision_id=v2.revision_id,
        )
        effective = await SqlAlchemyProjectEventRepository(fresh).get_change_for_revision(
            tenant_id=j.world.tenant, project_id=j.world.project, document_id=document.id,
            revision_id=v2.revision_id,
        )
    assert reloaded is not None
    assert (reloaded.trust_state, reloaded.is_current, reloaded.materialization.state) == (  # type: ignore[union-attr]
        "trusted", True, "materialized",
    )
    assert effective is not None and effective.event_id == UUID(change["event_id"])

    # (17) a replay after reload still changes nothing.
    assert (await j.materialize(binding))["status"] == "noop"
    assert await j.counts() == after


async def _texts(j: _Journey, document: Document, revision: DocumentRevision) -> list[str | None]:
    return [c.full_text for c in await j.world.docs.list_revision_clauses(j.world.tenant, document.id, revision.revision_id)]


# ── 18-21. WBS stays governed ────────────────────────────────────────────────


async def test_first_wbs_is_never_auto_created_and_the_proposal_is_recoverable(
    journey: _Journey, db: AsyncSession
) -> None:
    j = journey
    document, _v1, v2, binding = await _v2_proposed(j)
    assert await _wbs_rows(db, j.world.project) == []  # the project has NO WBS

    await j.approve(binding)
    assert (await j.materialize(binding))["status"] == "created"

    # (18) no Baseline #1 is created from the AI proposal, even with no WBS at all.
    assert await _wbs_rows(db, j.world.project) == []
    # (20) WBS_GOVERNANCE_REQUIRED is visible on the revision's API status.
    status = (await j.detail(document, v2)).json()["revision_status"]
    assert "WBS_GOVERNANCE_REQUIRED" in status["materialization"]["qualifications"]
    # (21) the exact proposal is recoverable from the approved artifact it names.
    source = status["materialization"]["deferred_effects"]["wbs"]["proposal_source"]
    assert source["artifact_id"] == str(binding.artifact_id)
    assert source["artifact_version"] == binding.artifact_version
    assert source["artifact_hash"] == binding.artifact_hash
    artifact = await db.get(DocumentArtifactORM, binding.artifact_id)
    assert artifact is not None and artifact.trust_state == "trusted"
    assert [(n["code"], n["name"]) for n in artifact.payload["extracted_wbs"]] == [
        (n.code, n.name) for n in PROPOSED_WBS
    ]


async def test_existing_wbs_baseline_is_never_changed_by_an_approved_revision(
    journey: _Journey, db: AsyncSession
) -> None:
    j = journey
    document = await j.world.upload()
    [v1] = await j.world.lineage(document)
    await j.trusted_v1(document, v1)
    # A canonical WBS that governance already owns (same visible code as the proposal).
    await seed_legacy_from_dicts(
        db, j.world.project, [{"code": "1", "name": "Civil works (approved baseline)"}], j.world.tenant
    )
    await db.commit()
    baseline = await _wbs_rows(db, j.world.project)

    v2 = await j.world.reupload(document)
    await j.stage(document, v2, V2_BODY)
    binding = await j.propose(document, v2, wbs=PROPOSED_WBS)
    await j.approve(binding)
    assert (await j.materialize(binding))["status"] == "created"

    # (19) the existing baseline is byte-identical: no replace, upsert or relink.
    assert await _wbs_rows(db, j.world.project) == baseline
    status = await j.status(document, v2)
    assert status is not None and status.materialization is not None
    assert "WBS_GOVERNANCE_REQUIRED" in status.materialization.qualifications


# ── 22-24. trust / stale / scope ─────────────────────────────────────────────


async def test_rejected_v2_never_becomes_current_and_writes_nothing(journey: _Journey) -> None:
    j = journey
    document, v1, v2, binding = await _v2_proposed(j)
    before = await j.counts()

    assert await j.reject(binding) is True
    # (22) V1 stays canonical; V2 is inspectable history, never current.
    current = await j.world.current(document)
    assert current.revision_id == v1.revision_id
    status = (await j.detail(document, v2)).json()
    assert status["revision_status"]["trust_state"] == "rejected"
    assert status["revision_status"]["is_current"] is False
    assert status["event_type"] == "revision.changed"  # the comparison stays readable
    assert await j.analyses_of(binding.artifact_id) == []
    assert await j.counts() == before


async def test_v2_superseded_by_trusted_v3_materializes_nothing(journey: _Journey) -> None:
    j = journey
    document, _v1, v2, v2_binding = await _v2_proposed(j)
    v3 = await j.world.reupload(document)
    await j.stage(document, v3, V3_BODY)
    v3_binding = await j.propose(document, v3)
    await j.approve(v3_binding)
    assert (await j.materialize(v3_binding))["status"] == "created"
    before = await j.counts()

    # (23) V3's proposal superseded the pending V2 candidate, so the late V2
    # approval is refused by the #714 authority itself; a delivery for it is a
    # no-op (no obligation). The row-level race -- V2 committed, V3 trusted before
    # V2's materialization lock -- is the C3b-1 stale guard (obsolete, 0 writes).
    with pytest.raises(StaleCandidateError):
        await j.approve(v2_binding)
    assert (await j.materialize(v2_binding))["status"] == "no_obligation"
    assert await j.analyses_of(v2_binding.artifact_id) == []
    assert await j.counts() == before
    current = await j.world.current(document)
    assert current.revision_id == v3.revision_id
    v2_status = await j.status(document, v2)
    assert v2_status is not None and v2_status.is_current is False
    assert v2_status.trust_state == "superseded" and v2_status.materialization is None
    v3_status = await j.status(document, v3)
    assert v3_status is not None and v3_status.is_current is True


async def test_foreign_tenant_and_wrong_scope_read_nothing(journey: _Journey) -> None:
    j = journey
    document, _v1, v2, _binding = await _v2_proposed(j)

    # (24) another tenant learns neither the change nor its status.
    foreign = await j.detail(document, v2, tenant_id=uuid4())
    assert foreign.status_code == 404
    unowned = await j.detail(document, v2, owned=False)
    assert unowned.status_code == 404
    reader = SqlAlchemyRevisionStatusReader(j.db)
    assert await reader.read(
        tenant_id=uuid4(), project_id=j.world.project, document_id=document.id, revision_id=v2.revision_id
    ) is None
    assert await reader.read(
        tenant_id=j.world.tenant, project_id=uuid4(), document_id=document.id, revision_id=v2.revision_id
    ) is None
    assert await reader.read(
        tenant_id=j.world.tenant, project_id=j.world.project, document_id=uuid4(), revision_id=v2.revision_id
    ) is None


# ── 1-6 on the journey: a legacy V2 comparison, recomputed, read effectively ─


async def test_legacy_v2_comparison_is_recomputed_and_every_reader_uses_the_effective_result(
    journey: _Journey, db: AsyncSession
) -> None:
    from src.temporal.adapters.persistence.document_revision_repository import (
        SqlAlchemyDocumentRevisionRepository,
    )
    from src.temporal.adapters.persistence.revision_trust_reader import (
        SqlAlchemyRevisionTrustReader,
    )
    from src.temporal.application import temporal_review
    from src.temporal.application.legacy_recomputation import (
        RecomputeStatus,
        recompute_legacy_changes_for_project,
    )
    from src.temporal.application.revision_change_orchestrator import build_revision_analysis_events

    j = journey
    document = await j.world.upload()
    [v1] = await j.world.lineage(document)
    await j.trusted_v1(document, v1)
    v2 = await j.world.reupload(document)
    rows = await j.world.persist(document, v2, *_extracted(j, document, V2_BODY))
    # History written before C3b-2: the same comparison, stamped by the v1 matcher.
    events = SqlAlchemyProjectEventRepository(db)
    for event in await build_revision_analysis_events(
        revision=v2, clauses=rows, existing_events=await events.list_for_project(j.world.project, j.world.tenant)
    ):
        if event.event_type == "revision.changed":
            payload = dict(event.payload)
            payload["provenance"] = {**payload["provenance"], "diff_engine_version": "p0c-structural-l1-v1"}
            event = event.model_copy(update={"payload": payload})
            legacy_id = event.event_id
        await events.append(event)
    await db.commit()
    stored_legacy = (await db.execute(
        text("SELECT payload::text FROM project_events WHERE event_id = :e"), {"e": legacy_id}
    )).scalar_one()

    async def gate() -> Any:
        await db.commit()
        return await temporal_review.revision_requires_temporal_review(
            revisions=SqlAlchemyDocumentRevisionRepository(db), events=SqlAlchemyProjectEventRepository(db),
            trust=SqlAlchemyRevisionTrustReader(db), tenant_id=j.world.tenant, document_id=document.id,
            revision_id=v2.revision_id, artifact_type="contract",
        )

    before = await gate()
    assert before.reason == "temporal_identity_unverified" and before.required is True

    [outcome] = await recompute_legacy_changes_for_project(
        events, tenant_id=j.world.tenant, project_id=j.world.project
    )
    await db.commit()
    assert outcome.status is RecomputeStatus.RECOMPUTED
    assert await recompute_legacy_changes_for_project(
        events, tenant_id=j.world.tenant, project_id=j.world.project
    ) == [type(outcome)(RecomputeStatus.ALREADY_RECOMPUTED, legacy_id, outcome.recomputed_event_id)]

    # The approval gate reads the EFFECTIVE (current-matcher) comparison: the
    # pairing identity is now verified, and the decision is exactly what that
    # comparison's own qualified state calls for (never the legacy reading).
    from src.temporal.application.change_qualification import qualify_event

    recomputed = await events.get(outcome.recomputed_event_id, j.world.tenant)  # type: ignore[arg-type]
    assert recomputed is not None
    qualification = qualify_event(recomputed)
    assert qualification.identity_verified is True
    after = await gate()
    assert after.reason == (
        "temporal_identity_resolved" if qualification.effective_state == "ready" else "temporal_changes_need_review"
    )
    # The detail API returns the recomputation; the legacy original stays readable
    # by id, labelled historical, and is never mutated.
    current = (await j.detail(document, v2)).json()
    assert current["event_id"] == str(outcome.recomputed_event_id)
    assert current["event_type"] == "revision.recomputed" and current["effective"] is True
    assert current["derived_from_event_id"] == str(legacy_id)
    assert current["provenance"]["recomputed_from_engine"] == "p0c-structural-l1-v1"
    async with AsyncClient(transport=ASGITransport(app=j.app()), base_url="http://test") as client:
        historical = (await client.get(
            f"/api/v1/projects/{j.world.project}/documents/{document.id}/changes/{v2.revision_id}",
            params={"event_id": str(legacy_id)},
        )).json()
    assert historical["effective"] is False and historical["legacy_matcher"] is True
    assert historical["superseded_by_event_id"] == str(outcome.recomputed_event_id)
    assert (await db.execute(
        text("SELECT payload::text FROM project_events WHERE event_id = :e"), {"e": legacy_id}
    )).scalar_one() == stored_legacy
    timeline = {
        i["event_id"]: i for i in await j.timeline() if i["provenance"].get("target_revision_id") == str(v2.revision_id)
    }
    assert timeline[str(legacy_id)]["effective"] is False
    assert timeline[str(outcome.recomputed_event_id)]["effective"] is True


def _extracted(j: _Journey, document: Document, body: str) -> list[Any]:
    """The clauses ingestion extracts from ``body`` (fresh ids)."""
    return ingestion_tasks._extract_contract_clauses(
        document_id=document.id, project_id=j.world.project, tenant_id=j.world.tenant,
        parsed_text=body, parsed_payload={},
    )
