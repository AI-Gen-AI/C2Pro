"""PC-2b.4 (#923) -- the OFFLINE WBS Reviewer on a real PostgreSQL (TS-INT-PC2B4-REVIEWER-001).

PC2B4_OFFLINE_ONLY. Every model call goes to the in-memory ``FakeReviewerModelAdapter``; no provider,
no telemetry exporter and no shared cache is reachable from the Reviewer. Numbered tests follow the
PC-2b.4 offline authorization: 1-6 scope and privacy, 8-13 authority, 26-27 execution, 28-31
lifecycle, plus evidence inventory / trust classification, persistence and logging. RLS itself is
proven under a NOBYPASSRLS role on the migrated database in
tests/integration/product_control/test_pc2b4_reviewer_retrieval_rls_db.py.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import socket
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.temporal.adapters.persistence.models import DocumentRevisionORM, ProjectEventORM
from src.wbs.adapters.persistence import (
    intelligence_models,  # noqa: F401 - registers the run tables
)
from src.wbs.adapters.persistence.governance_models import (
    WBSBaselineORM,
    WBSChangeSetNodeORM,
    WBSChangeSetORM,
)
from src.wbs.adapters.persistence.intelligence_models import (
    WBSIntelligenceDecisionORM,
    WBSIntelligenceItemORM,
    WBSIntelligenceRunORM,
)
from src.wbs.adapters.persistence.models import WBSNodeORM
from src.wbs.application.governed_change_service import UpdateNode
from src.wbs.intelligence.application.service import (
    Decision,
    DecisionInput,
    ItemApplicability,
    ItemKind,
    RunFreshness,
    WBSIntelligenceNotFoundError,
    WBSIntelligenceService,
)
from src.wbs.intelligence.contracts.evidence import InputClass
from src.wbs.intelligence.contracts.qualification import QualificationDimension
from src.wbs.intelligence.contracts.run import RunOutcome, RunStatus
from src.wbs.intelligence.reviewer.evidence import (
    EvidenceRequest,
    ManifestScopedChunkReader,
    ReviewerScopeError,
)
from src.wbs.intelligence.reviewer.fake_model import SYNTHETIC_PROVIDER, FakeReviewerModelAdapter
from src.wbs.intelligence.reviewer.model_port import ModelCallRequest, ReviewTask
from src.wbs.intelligence.reviewer.service import (
    EVENT_RUN_USAGE,
    ReviewResult,
    ReviewTargetKind,
    WBSReviewerService,
)
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import Scope, _scope
from tests.modules.integration.test_pc2a2_wbs_governed_apply import (
    _approve,
    _cmd,
    _new,
    _submit,
    _tree,
)

pytestmark = pytest.mark.asyncio

CONTRACT = "The Contractor shall execute earthworks, foundations and the electrical installation for the plant."
SPEC = "Interfaces between civil and electrical works shall be coordinated at each foundation."


# =========================================================================== seeding
def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _document(db: AsyncSession, s: Scope, *, document_type: DocumentType = DocumentType.CONTRACT,
                    trust: str | None = "trusted", chunks: tuple[str, ...] = (CONTRACT,),
                    metadata: dict[str, Any] | None = None, tenant: UUID | None = None,
                    project: UUID | None = None) -> tuple[UUID, UUID]:
    """A document with one revision, an optional #714 artifact of ``trust`` and stamped chunks."""
    tenant_id, project_id = tenant or s.tenant, project or s.project
    document_id, revision_id = uuid4(), uuid4()
    body = "\n".join(chunks).encode()
    blob_hash = hashlib.sha256(body).hexdigest()
    db.add(DocumentORM(id=document_id, project_id=project_id, tenant_id=tenant_id, document_type=document_type,
                       filename=f"{document_type.value}.pdf", file_format=".pdf", upload_status=DocumentStatus.PARSED,
                       created_by=s.author.user_id, file_hash=blob_hash, storage_url=f"k/{document_id}"))
    await db.flush()
    db.add(DocumentRevisionORM(revision_id=revision_id, document_id=document_id, project_id=project_id,
                               tenant_id=tenant_id, rev_no=1, blob_hash=blob_hash, blob_key=f"k/{document_id}/1",
                               valid_from=_now(), created_at=_now()))
    await db.flush()
    if trust is not None:
        db.add(DocumentArtifactORM(artifact_id=uuid4(), document_id=document_id, document_revision_id=revision_id,
                                   project_id=project_id, tenant_id=tenant_id, payload={}, lifecycle_status="active",
                                   artifact_version=1, artifact_hash="a" * 64, trust_state=trust))
        await db.flush()
    for index, content in enumerate(chunks):
        await _chunk(db, tenant_id, project_id, document_id, content,
                     {"revision_id": str(revision_id), **(metadata or {}), "chunk_index": index})
    await db.commit()
    return document_id, revision_id


async def _chunk(db: AsyncSession, tenant_id: UUID, project_id: UUID, document_id: UUID, content: str,
                 metadata: dict[str, Any]) -> None:
    await db.execute(text(
        "INSERT INTO document_chunks (id, tenant_id, document_id, project_id, content, embedding, metadata) "
        "VALUES (:id, :t, :d, :p, :c, CAST(:e AS vector), CAST(:m AS jsonb))"),
        {"id": uuid4(), "t": tenant_id, "d": document_id, "p": project_id, "c": content,
         "e": "[" + ",".join(["0"] * 1536) + "]", "m": json.dumps(metadata)})


def _redact(value: str) -> str:
    """A deterministic test anonymiser (the real one is exercised in test_05_06)."""
    return value.replace("Contractor", "<ORG_1>")


def _model(ids: dict[str, UUID] | None = None, *, findings: list[dict[str, Any]] | None = None,
           proposals: list[dict[str, Any]] | None = None, qualification: list[dict[str, Any]] | None = None
           ) -> FakeReviewerModelAdapter:
    def envelope(**parts: Any) -> str:
        return json.dumps({"contract_version": "wbs-proposal/v1", "outcome": "COMPLETE",
                           "qualification": parts.get("qualification", []), "findings": parts.get("findings", []),
                           "proposals": parts.get("proposals", [])})

    if ids is not None and proposals is None:
        proposals = [
            {"ref": "r1", "operation": "UPDATE_NODE", "node": {"node_id": str(ids["1.1"])},
             "changes": {"name": "Earthworks and grading"}, "rationale": "Clarity", "confidence_pct": 60},
            {"ref": "r2", "operation": "ADD_NODE", "creates_label": "cabling", "parent": {"node_id": str(ids["2"])},
             "spec": {"name": "Electrical installation", "code": "2.1", "control_level": "work_package"},
             "rationale": "Contract scope", "confidence_pct": 80,
             "evidence": [{"excerpt_id": "E001", "basis": "DIRECT", "quote": "the electrical installation"}]},
        ]
    if ids is not None and findings is None:
        findings = [{"ref": "f1", "dimension": "INTERFACES", "status": "WARNING", "summary": "Interface not recorded",
                     "node_ids": [str(ids["1"])],
                     "evidence": [{"excerpt_id": "E001", "basis": "INFERRED", "quote": "earthworks, foundations"}]}]
    qualification = qualification if qualification is not None else [
        {"dimension": "SCOPE_COVERAGE", "status": "SUPPORTED", "summary": "Covered",
         "evidence": [{"excerpt_id": "E001", "basis": "DIRECT", "quote": "earthworks, foundations"}]}]
    return FakeReviewerModelAdapter(script={
        ReviewTask.MAP: [envelope(findings=findings or [], proposals=proposals or [])],
        ReviewTask.REDUCE: [envelope(qualification=qualification)],
    })


def _reviewer(db: AsyncSession, model: FakeReviewerModelAdapter, **kwargs: Any) -> WBSReviewerService:
    return WBSReviewerService(db, model=model, anonymize=kwargs.pop("anonymize", _redact), **kwargs)


async def _draft(db: AsyncSession, s: Scope) -> tuple[UUID, dict[str, UUID]]:
    change_set_id = await _new(db, s, "Reviewed WBS")
    return change_set_id, await _tree(db, s, change_set_id)


async def _review_draft(db: AsyncSession, s: Scope, change_set_id: UUID, model: FakeReviewerModelAdapter,
                        **kwargs: Any) -> ReviewResult:
    result = await _reviewer(db, model).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                               target=ReviewTargetKind.DRAFT, change_set_id=change_set_id, **kwargs)
    await db.commit()
    return result


async def _count(db: AsyncSession, model: Any, **where: Any) -> int:
    query = select(func.count()).select_from(model)
    for name, value in where.items():
        query = query.where(getattr(model, name) == value)
    return int(await db.scalar(query) or 0)


async def _world(db: AsyncSession) -> tuple[Scope, UUID, dict[str, UUID]]:
    s = await _scope(db)
    await _document(db, s)
    change_set_id, ids = await _draft(db, s)
    return s, change_set_id, ids


# =========================================================================== 1-4 scope
async def test_01_02_a_foreign_tenant_or_project_is_denied(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    other = await _scope(db)
    fake = _model(ids)
    for tenant, project in ((other.tenant, s.project), (s.tenant, other.project), (other.tenant, other.project)):
        with pytest.raises(WBSIntelligenceNotFoundError):
            await _reviewer(db, fake).review(project_id=project, tenant_id=tenant, actor=s.author,
                                             target=ReviewTargetKind.DRAFT, change_set_id=change_set_id)
        await db.rollback()
    assert fake.calls == [] and await _count(db, WBSIntelligenceRunORM, project_id=s.project) == 0


async def test_03_an_unauthorized_document_or_revision_is_denied(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    other = await _scope(db)
    foreign_document, foreign_revision = await _document(db, other)
    proposed_document, proposed_revision = await _document(db, s, trust="proposed")
    trusted_document, trusted_revision = await _document(db, s)
    refused = [
        EvidenceRequest(include_document_ids=(foreign_document,)),
        EvidenceRequest(include_proposed_revision_ids=(foreign_revision,)),
        EvidenceRequest(include_proposed_revision_ids=(uuid4(),)),
        EvidenceRequest(include_proposed_revision_ids=(trusted_revision,)),  # not a PROPOSED revision
    ]
    for request in refused:
        fake = _model(ids)
        with pytest.raises(ReviewerScopeError):
            await _reviewer(db, fake).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                             target=ReviewTargetKind.DRAFT, change_set_id=change_set_id,
                                             evidence=request)
        await db.rollback()
        assert fake.calls == []
    accepted = await _review_draft(db, s, change_set_id, _model(ids),
                                   evidence=EvidenceRequest(include_proposed_revision_ids=(proposed_revision,)))
    classes = {item.canonical_source.revision_id: item.input_class for item in accepted.manifest.items
               if item.canonical_source is not None}
    assert classes[proposed_revision] is InputClass.PROPOSED_EVIDENCE
    assert trusted_document not in {proposed_document} and classes[trusted_revision] is InputClass.TRUSTED_PROJECT_EVIDENCE


async def test_04_missing_scope_fails_closed(db: AsyncSession) -> None:
    reader = ManifestScopedChunkReader(db)
    for tenant, project in ((None, uuid4()), (uuid4(), None), (None, None)):
        with pytest.raises(ValueError):
            await reader.read(tenant_id=tenant, project_id=project, allowed=[(uuid4(), uuid4())])  # type: ignore[arg-type]
    assert await reader.read(tenant_id=uuid4(), project_id=uuid4(), allowed=[]) == []


async def test_retrieval_binds_tenant_project_and_revision_under_the_privileged_role(db: AsyncSession) -> None:
    bypass = (await db.execute(text("SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user"))
              ).scalar_one()
    assert bypass is True  # precondition: only the SQL predicates separate the scopes here
    s = await _scope(db)
    other = await _scope(db)
    own_document, own_revision = await _document(db, s, chunks=("SECRET-OWN current",))
    await _chunk(db, s.tenant, s.project, own_document, "SECRET-OWN superseded", {"revision_id": str(uuid4())})
    await _chunk(db, s.tenant, s.project, own_document, "SECRET-OWN unstamped", {})
    sibling_project = await _scope(db)
    sib_document, sib_revision = await _document(db, s, chunks=("SECRET-SIBLING",), tenant=s.tenant,
                                                 project=sibling_project.project)
    foreign_document, foreign_revision = await _document(db, other, chunks=("SECRET-FOREIGN",))
    await db.commit()
    forged = [(own_document, own_revision), (sib_document, sib_revision), (foreign_document, foreign_revision),
              (own_document, foreign_revision)]
    chunks = await ManifestScopedChunkReader(db).read(tenant_id=s.tenant, project_id=s.project, allowed=forged)
    assert [c.content for c in chunks] == ["SECRET-OWN current"]
    assert {(c.document_id, c.revision_id) for c in chunks} == {(own_document, own_revision)}


# =========================================================================== 5-6 locators + PII
async def test_05_06_canonical_locators_are_captured_before_real_anonymisation(db: AsyncSession) -> None:
    s = await _scope(db)
    secret = "jane.doe@example.com"
    original = f"The Contractor shall execute earthworks; contact {secret} for the electrical installation."
    _, revision_id = await _document(db, s, chunks=(original,),
                                     metadata={"page": 7, "char_start": 1200, "char_end": 1200 + len(original)})
    change_set_id, ids = await _draft(db, s)
    fake = _model(ids, proposals=[], findings=[])
    result = await _reviewer(db, fake, anonymize=None).review(  # None -> the real PII anonymiser
        project_id=s.project, tenant_id=s.tenant, actor=s.author, target=ReviewTargetKind.DRAFT,
        change_set_id=change_set_id)
    await db.commit()
    [item] = [i for i in result.manifest.items if i.input_class is InputClass.TRUSTED_PROJECT_EVIDENCE]
    source = item.canonical_source
    assert source is not None and source.revision_id == revision_id
    assert (source.page, source.char_start, source.char_end) == (7, 1200, 1200 + len(original))
    assert secret not in item.model_visible.text and item.model_visible.anonymised
    assert len(item.model_visible.text) != len(original)  # anonymised length never becomes an offset
    for request in fake.calls:
        assert secret not in request.content and secret not in request.system


# =========================================================================== 8-13 authority
async def test_08_to_13_the_model_holds_no_governance_authority(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    before = {
        "change_sets": await _count(db, WBSChangeSetORM, project_id=s.project),
        "nodes": await _count(db, WBSChangeSetNodeORM, change_set_id=change_set_id),
        "baselines": await _count(db, WBSBaselineORM, project_id=s.project),
        "live": await _count(db, WBSNodeORM, project_id=s.project),
    }
    draft = await db.scalar(select(WBSChangeSetORM).where(WBSChangeSetORM.id == change_set_id))
    assert draft is not None
    revision = draft.revision
    await db.commit()  # the caller ends its own transaction: the Reviewer owns the session it is given
    result = await _review_draft(db, s, change_set_id, _model(ids))
    assert result.run.status == RunStatus.COMPLETED.value
    after = {
        "change_sets": await _count(db, WBSChangeSetORM, project_id=s.project),  # 8: no DRAFT created
        "nodes": await _count(db, WBSChangeSetNodeORM, change_set_id=change_set_id),  # 9: DRAFT not edited
        "baselines": await _count(db, WBSBaselineORM, project_id=s.project),  # 13: no baseline
        "live": await _count(db, WBSNodeORM, project_id=s.project),  # 12: canonical WBS untouched
    }
    assert after == before
    draft = await db.scalar(select(WBSChangeSetORM).where(WBSChangeSetORM.id == change_set_id)
                            .execution_options(populate_existing=True))
    assert draft is not None and (draft.status, draft.revision) == ("DRAFT", revision)  # 10/11: not submitted
    assert await _count(db, WBSIntelligenceDecisionORM, run_id=result.run.id) == 0
    proposals = await _count(db, WBSIntelligenceItemORM, run_id=result.run.id, kind=ItemKind.PROPOSAL.value)
    assert proposals == 2  # proposals are stored for a HUMAN to decide -- never applied


async def test_a_baseline_review_never_creates_a_draft_or_a_baseline(db: AsyncSession) -> None:
    s = await _scope(db)
    await _document(db, s)
    _, ids, applied = await _baseline_one(db, s)
    baselines = await _count(db, WBSBaselineORM, project_id=s.project)
    change_sets = await _count(db, WBSChangeSetORM, project_id=s.project)
    await db.commit()  # the caller ends its own transaction: the Reviewer owns the session it is given
    result = await _reviewer(db, _model(ids)).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                     target=ReviewTargetKind.REVIEW_OPTIMIZE,
                                                     baseline_id=applied.baseline_id)
    await db.commit()
    assert result.run.mode == "REVIEW_OPTIMIZE" and result.run.target_kind == "BASELINE"
    assert await _count(db, WBSBaselineORM, project_id=s.project) == baselines
    assert await _count(db, WBSChangeSetORM, project_id=s.project) == change_sets


async def test_only_a_human_author_requests_a_review(db: AsyncSession) -> None:
    from src.core.auth.models import UserRole
    from src.wbs.intelligence.application.service import WBSIntelligenceForbiddenError
    from tests.modules.integration.test_pc2a1_wbs_governance_foundation import _user

    s, change_set_id, ids = await _world(db)
    api = await _user(db, s.tenant, UserRole.API)
    fake = _model(ids)
    with pytest.raises(WBSIntelligenceForbiddenError):
        await _reviewer(db, fake).review(project_id=s.project, tenant_id=s.tenant, actor=api,
                                         target=ReviewTargetKind.DRAFT, change_set_id=change_set_id)
    assert fake.calls == []


# =========================================================================== targets
async def test_import_review_binds_the_import_candidate_and_its_immutable_source(db: AsyncSession) -> None:
    from tests.modules.integration.test_pc2b3_wbs_import import (
        PLANT_CSV,
        _candidate,
        _import,
        _wbs_document,
    )

    s = await _scope(db)
    await _document(db, s)
    document_id, _ = await _wbs_document(db, s, PLANT_CSV)
    source = await _import(db, s, document_id)
    candidate = await _candidate(db, s, source.id)
    result = await _reviewer(db, _model(proposals=[], findings=[])).review(
        project_id=s.project, tenant_id=s.tenant, actor=s.author, target=ReviewTargetKind.IMPORT_REVIEW,
        change_set_id=candidate.change_set_id)
    await db.commit()
    run = result.run
    assert (run.mode, run.target_kind, run.target_change_set_id) == ("IMPORT_REVIEW", "CANDIDATE",
                                                                     candidate.change_set_id)
    [imported] = [i for i in result.manifest.items if i.input_class is InputClass.HUMAN_PROVIDED_IMPORT]
    assert imported.canonical_source is not None and imported.canonical_source.revision_id == source.revision_id
    assert imported.canonical_source.blob_hash == source.blob_hash
    # a candidate that did not come from an import is not an IMPORT_REVIEW target
    change_set_id, _ = await _draft(db, s)
    with pytest.raises(Exception, match="IMPORT_REVIEW"):
        await _reviewer(db, _model(proposals=[], findings=[])).review(
            project_id=s.project, tenant_id=s.tenant, actor=s.author, target=ReviewTargetKind.IMPORT_REVIEW,
            change_set_id=change_set_id)
    await db.rollback()


# =========================================================================== inventory / sufficiency / persistence
async def test_evidence_inventory_classifies_trust_and_never_uses_wbs_sources(db: AsyncSession) -> None:
    s = await _scope(db)
    _, contract_rev = await _document(db, s)
    _, schedule_rev = await _document(db, s, document_type=DocumentType.SCHEDULE, chunks=("Schedule WBS column",))
    _, untrusted_rev = await _document(db, s, trust="proposed", chunks=("Draft scope",))
    _, unbound_rev = await _document(db, s, document_type=DocumentType.SPECIFICATION, trust=None, chunks=(SPEC,))
    _, wbs_rev = await _document(db, s, document_type=DocumentType.WBS, chunks=("1,Plant,",))
    change_set_id, ids = await _draft(db, s)
    result = await _review_draft(db, s, change_set_id, _model(ids))
    by_revision = {i.canonical_source.revision_id: i.input_class for i in result.manifest.items
                   if i.canonical_source is not None}
    assert by_revision[contract_rev] is InputClass.TRUSTED_PROJECT_EVIDENCE
    assert by_revision[schedule_rev] is InputClass.ADVISORY_EVIDENCE  # never schedule authority
    assert untrusted_rev not in by_revision  # PROPOSED evidence only when a human includes it
    assert wbs_rev not in by_revision  # a WBS source is never evidence
    assert by_revision.get(unbound_rev) in {None, InputClass.TRUSTED_PROJECT_EVIDENCE}  # single revision, resolved
    assert result.run.evidence_set_digest == result.manifest.evidence_set_digest


async def test_no_trusted_scope_evidence_abstains_with_zero_calls_and_is_persisted(db: AsyncSession) -> None:
    s = await _scope(db)
    _, proposed_rev = await _document(db, s, trust="proposed")
    change_set_id, ids = await _draft(db, s)
    fake = _model(ids)
    result = await _review_draft(db, s, change_set_id, fake,
                                 evidence=EvidenceRequest(include_proposed_revision_ids=(proposed_rev,)))
    assert fake.calls == []
    assert (result.run.status, result.run.outcome) == ("COMPLETED", RunOutcome.INSUFFICIENT_EVIDENCE.value)
    report = {r["dimension"]: r for r in result.run.qualification["results"]}
    assert report["SCOPE_COVERAGE"]["reason_code"] == "NO_TRUSTED_SCOPE_EVIDENCE"
    assert await _count(db, WBSIntelligenceItemORM, run_id=result.run.id, kind=ItemKind.PROPOSAL.value) == 0


async def test_a_completed_review_is_persisted_with_visibly_synthetic_provenance(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    result = await _review_draft(db, s, change_set_id, _model(ids))
    run = result.run
    assert (run.execution_type, run.mode, run.status) == ("AI", "REVIEW_OPTIMIZE", "COMPLETED")
    provenance = run.model_provenance or {}
    assert provenance["synthetic"] is True and provenance["production_invocation"] is False
    assert provenance["provider"] == SYNTHETIC_PROVIDER and provenance["adapter"] == "FakeReviewerModelAdapter"
    assert [r["dimension"] for r in run.qualification["results"]] == [d.value for d in QualificationDimension]
    items = (await db.execute(select(WBSIntelligenceItemORM).where(WBSIntelligenceItemORM.run_id == run.id))).scalars().all()
    methods = {item.body.get("method") for item in items if item.kind == ItemKind.FINDING.value}
    assert "AI" in methods and "DETERMINISTIC" in methods  # AI adds to deterministic findings, never replaces them
    usage = (await db.execute(select(ProjectEventORM).where(ProjectEventORM.event_type == EVENT_RUN_USAGE,
                                                             ProjectEventORM.project_id == s.project))).scalars().all()
    [event] = usage
    payload = event.payload
    assert (payload["tenant_id"], payload["project_id"], payload["run_id"]) == (str(s.tenant), str(s.project),
                                                                               str(run.id))
    assert payload["synthetic"] is True and payload["calls"] == 2 and payload["external_calls"] == 0
    assert CONTRACT not in json.dumps(payload) and "earthworks" not in json.dumps(payload).lower()


async def test_a_cancelled_review_stores_nothing_but_its_state(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    flag = {"cancel": False}

    async def cancelling(request: ModelCallRequest) -> None:
        flag["cancel"] = True  # the human cancels while the first call is in flight

    fake = _model(ids)
    fake._latency = cancelling  # the test seam of the synthetic adapter (its complete() is never replaced)
    result = await _review_draft(db, s, change_set_id, fake, cancelled=lambda: flag["cancel"])
    assert (result.run.status, result.run.outcome) == ("CANCELLED", "CANCELLED")
    assert await _count(db, WBSIntelligenceItemORM, run_id=result.run.id) == 0


async def test_a_failed_reduce_fails_the_run_and_stores_no_items(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    fake = _model(ids)
    fake.script[ReviewTask.REDUCE] = ["not json"]
    result = await _review_draft(db, s, change_set_id, fake)
    assert (result.run.status, result.run.outcome) == ("FAILED", "FAILED") and result.run.failure_reason
    assert await _count(db, WBSIntelligenceItemORM, run_id=result.run.id) == 0


# =========================================================================== 26-27 execution
async def test_26_concurrent_equivalent_reviews_create_one_run_and_one_set_of_calls(db: AsyncSession) -> None:
    """Two equal requests race: one opens the run (committed before any model call), the other reuses
    it -- RUNNING or already COMPLETED -- with no model call of its own."""
    s, change_set_id, ids = await _world(db)
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    first_model, second_model = _model(ids), _model(ids)

    async def request(session: AsyncSession, model: FakeReviewerModelAdapter) -> ReviewResult:
        result = await _reviewer(session, model).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                        target=ReviewTargetKind.DRAFT, change_set_id=change_set_id)
        await session.commit()
        return result

    try:
        async with sessions() as first_session, sessions() as second_session:
            results = await asyncio.wait_for(asyncio.gather(request(first_session, first_model),
                                                            request(second_session, second_model)), timeout=30)
    finally:
        await engine.dispose()
    opened = [r for r in results if not r.reused]
    reused = [r for r in results if r.reused]
    assert len(opened) == 1 and len(reused) == 1 and reused[0].run.id == opened[0].run.id
    assert sorted([len(first_model.calls), len(second_model.calls)]) == [0, 2]  # one set of calls
    assert await _count(db, WBSIntelligenceRunORM, project_id=s.project) == 1


async def test_27_a_full_review_opens_no_external_connection(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    s, change_set_id, ids = await _world(db)
    attempts: list[Any] = []
    real_connect = socket.socket.connect

    def guarded(self: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in {"127.0.0.1", "::1", "localhost"} and not host.startswith("/"):
            attempts.append(address)
            raise AssertionError(f"external connection attempted: {address}")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    result = await _review_draft(db, s, change_set_id, _model(ids))
    assert result.run.status == "COMPLETED" and attempts == []


async def test_reviews_log_no_evidence_text(db: AsyncSession, caplog: pytest.LogCaptureFixture) -> None:
    s, change_set_id, ids = await _world(db)
    caplog.set_level(logging.DEBUG)
    with structlog.testing.capture_logs() as captured:
        await _review_draft(db, s, change_set_id, _model(ids))
    rendered = json.dumps(captured, default=str) + caplog.text
    assert "earthworks, foundations" not in rendered and "<ORG_1>" not in rendered
    assert "Earthworks and grading" not in rendered


# =========================================================================== 28-31 lifecycle
async def _baseline_one(db: AsyncSession, s: Scope) -> tuple[UUID, dict[str, UUID], Any]:
    change_set_id = await _new(db, s, "Baseline 1")
    ids = await _tree(db, s, change_set_id)
    await _submit(db, s, change_set_id)
    return change_set_id, ids, await _approve(db, s, change_set_id)


async def test_28_a_moved_baseline_makes_a_baseline_review_stale(db: AsyncSession) -> None:
    s = await _scope(db)
    await _document(db, s)
    _, ids, applied = await _baseline_one(db, s)
    result = await _reviewer(db, _model(ids)).review(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                     target=ReviewTargetKind.REVIEW_OPTIMIZE,
                                                     baseline_id=applied.baseline_id)
    await db.commit()
    store = WBSIntelligenceService(db)
    assert (await store.freshness(result.run)).state is RunFreshness.FRESH
    change = await _new(db, s, "Change 1")
    await _cmd(db, s, change, UpdateNode(node_id=ids["2"], changes={"name": "Electrical works"}))
    await _submit(db, s, change)
    await _approve(db, s, change)
    run = await store.run(result.run.id, s.project, s.tenant)
    assert (await store.freshness(run)).state is RunFreshness.STALE


async def test_29_30_31_a_touched_item_conflicts_others_apply_and_decisions_never_approve(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    result = await _review_draft(db, s, change_set_id, _model(ids))
    store = WBSIntelligenceService(db)
    views = {v.item.ref: v.item for v in await store.items(result.run)}
    rename, add = views["c01-r1"], views["c01-r2"]
    await _cmd(db, s, change_set_id, UpdateNode(node_id=ids["1.1"], changes={"name": "Edited by a human"}))
    preview = await store.preview(project_id=s.project, run_id=result.run.id, tenant_id=s.tenant,
                                  change_set_id=change_set_id,
                                  selections=[DecisionInput(item_id=rename.id, decision=Decision.APPLY_AS_PROPOSED),
                                              DecisionInput(item_id=add.id, decision=Decision.APPLY_AS_PROPOSED)])
    states = {item.item_id: item.applicability for item in preview.items}
    assert states[rename.id] is ItemApplicability.CONFLICT  # 29
    assert states[add.id] is ItemApplicability.APPLICABLE  # 30
    revision = int(await db.scalar(select(WBSChangeSetORM.revision).where(WBSChangeSetORM.id == change_set_id)) or 0)
    baselines = await _count(db, WBSBaselineORM, project_id=s.project)
    decided = await store.decide(project_id=s.project, run_id=result.run.id, tenant_id=s.tenant, actor=s.author,
                                 decisions=[DecisionInput(item_id=add.id, decision=Decision.APPLY_AS_PROPOSED)],
                                 change_set_id=change_set_id, expected_revision=revision)
    await db.commit()
    draft = await db.scalar(select(WBSChangeSetORM).where(WBSChangeSetORM.id == change_set_id)
                            .execution_options(populate_existing=True))
    assert draft is not None and draft.status == "DRAFT" and decided.change_set_revision == revision + 1  # 31
    assert await _count(db, WBSBaselineORM, project_id=s.project) == baselines


async def test_a_review_qualifies_against_the_exact_target_digest(db: AsyncSession) -> None:
    s, change_set_id, ids = await _world(db)
    result = await _review_draft(db, s, change_set_id, _model(ids))
    store = WBSIntelligenceService(db)
    run = result.run
    deterministic = await store.request_deterministic_run(project_id=s.project, tenant_id=s.tenant, actor=s.author,
                                                          target_kind=_candidate_kind(), change_set_id=change_set_id)
    await db.commit()
    assert run.target_digest == deterministic.run.target_digest  # the same exact tree identity
    assert run.target_change_set_revision == deterministic.run.target_change_set_revision
    assert run.id != deterministic.run.id  # an AI review never reuses a deterministic run


def _candidate_kind() -> Any:
    from src.wbs.intelligence.contracts.run import TargetKind

    return TargetKind.CANDIDATE
