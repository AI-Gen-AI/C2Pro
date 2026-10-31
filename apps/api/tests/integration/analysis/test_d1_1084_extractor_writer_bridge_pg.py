"""D1/#1084 — PROPOSED, NOT EXECUTED: two original extractors -> existing canonical writer.

Target: AI-Gen-AI/C2Pro PR #1112, exact SHA 3b0762562c6dba24c16375c4d5a55c4669914993.
This is a handoff test, not a modification to that PR. The owner must validate
AUTH WORK, ownership, runner checkout, and source-code compatibility first.

Runs only with a disposable PostgreSQL test DB and the repository's existing
pytest fixtures. No Clerk real-browser, production, or D1 global acceptance claim.

The two extractors and the persistent writer intentionally have different
interfaces: we compare independently read immutable-source identity/content,
not invent an extractor-output-to-writer adapter.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.application.canonical_structured_wbs_links import (
    APPROVAL,
    ApproveStructuredWBSLinkService,
    ImmutableXLSXRowReader,
    ReadStructuredWBSLinksService,
    StructuredWBSLinkError,
)
from src.analysis.application.extract_budget_revision_evidence_use_case import (
    AuthoritativeApprovedScopeService,
    ExtractBudgetRevisionEvidenceUseCase,
)
from src.analysis.application.extract_schedule_revision_evidence_use_case import (
    AuthoritativeScheduleScopeService,
    ExtractScheduleRevisionEvidenceUseCase,
)
from src.core.auth.models import User
from src.core.exceptions import C2ProException
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from tests.integration.analysis.test_s7_structured_wbs_three_source_pg import (
    _SyntheticImmutableStorage,
    _structured_document,
)
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import _scope
from tests.modules.integration.test_pc2a2_wbs_governed_apply import _baseline_one
from tests.modules.integration.test_pc2a3_wbs_authority_enforcement import _baseline_two

pytestmark = pytest.mark.asyncio
EVENT_TYPES = ("budget.wbs_link_approved", "schedule.wbs_link_approved")


def _link_args(w: dict, item: dict, **overrides) -> dict:
    payload = {
        **item,
        "tenant_id": w["tenant"],
        "project_id": w["project"],
        "actor_user_id": w["actor"],
        "expected_wbs_baseline_id": w["baseline"],
        "expected_wbs_node_id": w["node"],
        "approval": APPROVAL,
        "idempotency_key": f"d1-1084-bridge-{item['family']}-approval",
        "reason": "Human approval of exact source row and governed WBS node",
    }
    payload.update(overrides)
    return payload


async def _events(session: AsyncSession, w: dict) -> list[ProjectEventORM]:
    return list((await session.scalars(
        select(ProjectEventORM).where(
            ProjectEventORM.tenant_id == w["tenant"],
            ProjectEventORM.project_id == w["project"],
            ProjectEventORM.event_type.in_(EVENT_TYPES),
        )
    )).all())


async def _must_reject_without_event(
    test_session_factory, w: dict, reader: ImmutableXLSXRowReader,
    item: dict, *, previous_count: int,
    expected_error: str | None = None, expected_code: str | None = None, **changes,
) -> None:
    """Assert the *specific* fail-closed reason and independent durable count."""
    assert (expected_error is None) != (expected_code is None)
    async with test_session_factory() as attempt:
        service = ApproveStructuredWBSLinkService(attempt, reader)
        if expected_code is not None:
            with pytest.raises(C2ProException) as rejected:
                await service.execute(**_link_args(w, item, **changes))
            assert rejected.value.code == expected_code
        else:
            with pytest.raises(StructuredWBSLinkError) as rejected:
                await service.execute(**_link_args(w, item, **changes))
            assert str(rejected.value) == expected_error
        await attempt.rollback()
    async with test_session_factory() as independent:
        assert len(await _events(independent, w)) == previous_count


async def test_d1_1084_extractors_to_canonical_writer_identity_bridge_pg(
    db: AsyncSession, test_session_factory, tmp_path: Path,
) -> None:
    # Real governance baseline (no SQL shortcut, no mock resolver).
    scope = await _scope(db)
    _, ids, approved = await _baseline_one(db, scope)
    actor = await db.get(User, scope.author.user_id)
    assert actor is not None
    actor.clerk_user_id = f"d1-1084-clerk-fixture-{actor.id.hex}"
    await db.commit()
    w = {
        "tenant": scope.tenant,
        "project": scope.project,
        "actor": actor.id,
        "baseline": approved.baseline_id,
        "node": ids["1.1"],
    }

    # Unmodified synthetic XLSX fixture already used by product S7.
    paths: dict[str, Path] = {}
    budget = await _structured_document(db, w, tmp_path, "budget", paths)
    schedule = await _structured_document(db, w, tmp_path, "schedule", paths)
    items = {"budget": budget, "schedule": schedule}
    reader = ImmutableXLSXRowReader(_SyntheticImmutableStorage(paths), ExcelFileParser())

    extracted: dict[str, object] = {}
    for family, item in items.items():
        async with test_session_factory() as read_session:
            revision = await SqlAlchemyDocumentRevisionRepository(read_session).get_by_id(
                item["source_revision_id"], w["tenant"]
            )
            assert revision is not None
            assert revision.document_id == item["source_document_id"]
            assert revision.blob_hash == item["expected_blob_hash"]
            source_path = paths[revision.blob_key]
            document = Document(
                id=item["source_document_id"], tenant_id=w["tenant"],
                project_id=w["project"],
                document_type=(DocumentType.BUDGET if family == "budget" else DocumentType.SCHEDULE),
                filename=f"{family}.xlsx", upload_status=DocumentStatus.UPLOADED,
                file_format=".xlsx",
            )
            if family == "budget":
                result = await ExtractBudgetRevisionEvidenceUseCase(
                    parser=ExcelFileParser(),
                    approved_scope_service=AuthoritativeApprovedScopeService(read_session),
                ).execute(
                    document=document, revision=revision,
                    source_path=source_path, existing_row_identities=(),
                )
            else:
                result = await ExtractScheduleRevisionEvidenceUseCase(
                    parser=ExcelFileParser(),
                    approved_scope_service=AuthoritativeScheduleScopeService(read_session),
                ).execute(
                    document=document, revision=revision,
                    source_path=source_path, existing_row_identities=(),
                )
            assert len(result.rows) == 1
            [source_row] = result.rows
            assert source_row.identity == (item["source_revision_id"], item["source_locator"])
            assert (source_row.tenant_id, source_row.project_id, source_row.document_id) == (
                w["tenant"], w["project"], item["source_document_id"]
            )
            assert source_row.wbs_node_id == w["node"]
            assert (
                source_row.wbs_baseline_id if family == "budget"
                else source_row.approved_wbs_baseline_id
            ) == w["baseline"]
            # Contract bridge: independent immutable re-read of the same revision,
            # locator and SOURCE CONTENT. No invented direct service coupling.
            parsed_again = await reader.read_row(
                revision=revision, family=family,
                source_locator=source_row.source_locator,
            )
            assert str(parsed_again["source_locator"]) == source_row.source_locator
            assert str(parsed_again["wbs_node_id"]) == str(source_row.wbs_node_id)
            if family == "budget":
                assert parsed_again["item"].strip() == source_row.description
                assert Decimal(str(parsed_again["quantity"])) == source_row.quantity
                assert str(parsed_again["unit"]).strip() == source_row.unit
                assert Decimal(str(parsed_again["unit_price"])) == source_row.unit_price
                assert Decimal(str(parsed_again["total"])) == source_row.amount
                assert parsed_again["currency"].strip() == source_row.currency
                assert parsed_again["tax_basis"].strip() == source_row.tax_basis
            else:
                assert parsed_again["task"].strip() == source_row.activity_name
                assert parsed_again["source_activity_id"] == source_row.source_activity_id
                assert str(parsed_again["duration"]) == source_row.duration_source
                assert str(parsed_again["start_date"]) == source_row.start_date.isoformat()
                assert str(parsed_again["end_date"]) == source_row.end_date.isoformat()
            extracted[family] = source_row

    # Negative approvals BEFORE the positive: no partial canonical event.
    for family, item in items.items():
        for changes, reason, code in (
            ({"approval": ""}, "explicit typed human approval is required", None),
            ({"actor_user_id": uuid4()}, "authenticated human approver required", None),
            ({"tenant_id": uuid4()}, "project unavailable to tenant", None),
            ({"project_id": uuid4()}, "project unavailable to tenant", None),
            ({"source_revision_id": uuid4()}, "source document/revision/hash unavailable", None),
            ({"expected_blob_hash": "0" * 64}, "source document/revision/hash unavailable", None),
            ({"source_locator": "Sheet!999"}, "source locator is missing or ambiguous", None),
            ({"expected_wbs_baseline_id": uuid4()}, "approved WBS baseline changed", None),
            ({"expected_wbs_node_id": uuid4()}, None, "WBS_NODE_NOT_CURRENT_BASELINE"),
        ):
            await _must_reject_without_event(
                test_session_factory, w, reader, item, previous_count=0,
                expected_error=reason, expected_code=code, **changes,
            )

    # Tamper only a COPY, not the original persisted synthetic object.
    source_key = f"synthetic/s7/{budget['source_revision_id']}.xlsx"
    original_path = paths[source_key]
    tampered_copy = tmp_path / "tampered-copy.xlsx"
    tampered_copy.write_bytes(original_path.read_bytes() + b"tampered")
    try:
        paths[source_key] = tampered_copy
        await _must_reject_without_event(
            test_session_factory, w, reader, budget, previous_count=0,
            expected_error="immutable structured source unavailable",
        )
    finally:
        paths[source_key] = original_path
    assert original_path.read_bytes() != tampered_copy.read_bytes()

    receipts = {}
    for family, item in items.items():
        async with test_session_factory() as writer_session:
            receipt = await ApproveStructuredWBSLinkService(writer_session, reader).execute(
                **_link_args(w, item)
            )
            assert not receipt.replayed
            receipts[family] = receipt
            await writer_session.commit()

    # Independent transaction + DB readback. Check events, not cached response DTOs.
    async with test_session_factory() as observer:
        committed = await _events(observer, w)
        assert len(committed) == 2
        assert {e.event_type for e in committed} == set(EVENT_TYPES)
        assert {e.event_id for e in committed} == {v.event_id for v in receipts.values()}
        for e in committed:
            p = e.payload
            family = p["family"]
            item = items[family]
            row = extracted[family]
            assert (e.tenant_id, e.project_id, e.source_revision_id) == (
                w["tenant"], w["project"], item["source_revision_id"]
            )
            assert e.actor == f"user:{w['actor']}"
            assert p["source_document_id"] == str(item["source_document_id"])
            assert p["source_revision_id"] == str(row.revision_id)
            assert p["source_blob_hash"] == item["expected_blob_hash"]
            assert p["source_locator"] == row.source_locator
            assert p["wbs_baseline_id"] == str(w["baseline"])
            assert p["wbs_node_id"] == str(row.wbs_node_id)
            assert p["authority"] == "EXPLICIT_HUMAN_CANONICAL_LINK"
            assert p["approval"] == APPROVAL
        views = await ReadStructuredWBSLinksService(observer, reader).list(
            tenant_id=w["tenant"], project_id=w["project"]
        )
        assert {v.family for v in views} == {"budget", "schedule"}
        assert all(v.state == "CURRENT" for v in views)
        assert all(v.wbs_node_id == w["node"] for v in views)

    # SCOPE LIMIT: revoke trust in the existing Schedule artifact; this does NOT
    # create/approve a newer replacement revision. Durable event count stays two.
    async with test_session_factory() as switch:
        artifact = await switch.scalar(select(DocumentArtifactORM).where(
            DocumentArtifactORM.tenant_id == w["tenant"],
            DocumentArtifactORM.project_id == w["project"],
            DocumentArtifactORM.document_revision_id == schedule["source_revision_id"],
        ))
        assert artifact is not None
        artifact.trust_state = "superseded"
        artifact.lifecycle_status = "superseded"
        await switch.commit()
    await _must_reject_without_event(
        test_session_factory, w, reader, schedule, previous_count=2,
        expected_error="source revision is not trusted",
    )

    # Genuine WBS apply retires node 2 and changes baseline to #2. No direct
    # SQL authority mutations; the previously approved links remain historical.
    await _baseline_two(db, scope, ids)
    await _must_reject_without_event(
        test_session_factory, w, reader, budget, previous_count=2,
        expected_error="approved WBS baseline changed",
    )  # old baseline
    await _must_reject_without_event(
        test_session_factory, w, reader, budget, previous_count=2,
        expected_wbs_node_id=ids["2"],
        expected_code="WBS_NODE_NOT_CURRENT_BASELINE",
    )  # retired node on the current WBS cannot acquire a link

    async with test_session_factory() as independent:
        assert len(await _events(independent, w)) == 2
