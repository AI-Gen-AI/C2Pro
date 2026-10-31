"""S7 joint proof: SAME project, SAME approved WBS, 3 typed approvals in real PG.

Uses real immutable XLSX row parser and checksum, authentic human user records,
and committed readback in new DB transactions. Auth is injected into ASGI for
this test: it is NOT a real browser Clerk logout/relogin qualification.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import openpyxl
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.application.approve_canonical_technical_wbs_link import (
    CANONICAL_APPROVAL,
    ApproveCanonicalTechnicalWBSLinkService,
)
from src.analysis.application.canonical_structured_wbs_links import (
    APPROVAL,
    ApproveStructuredWBSLinkService,
    ImmutableXLSXRowReader,
    ReadStructuredWBSLinksService,
    StructuredWBSLinkError,
)
from src.analysis.application.read_canonical_technical_wbs_links import (
    ReadCanonicalTechnicalWBSLinksService,
)
from src.analysis.application.record_technical_wbs_review import RecordTechnicalWBSReviewService
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.models import DocumentRevisionORM
from tests.integration.analysis.test_s7_review_service_settlement_pg import _arguments, _world

pytestmark = pytest.mark.asyncio


class _SyntheticImmutableStorage:
    download_object_is_temporary = False

    def __init__(self, mapping: dict[str, Path]):
        self.mapping = mapping

    async def download_object(self, key: str) -> Path:
        return self.mapping[key]


async def _structured_document(
    db: AsyncSession, w: dict, tmp_path: Path, family: str,
    storage: dict[str, Path],
) -> dict:
    path = tmp_path / f"{family}.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    if family == "budget":
        sheet.append([
            "Item", "Quantity", "Unit", "Unit Price", "Total", "Currency",
            "Tax Basis", "WBS Node ID",
        ])
        sheet.append(["Concrete foundation", 2, "m3", 120, 240, "EUR", "NET", str(w["node"])])
    else:
        sheet.append([
            "Task", "Start Date", "End Date", "Duration", "Activity ID", "WBS Node ID",
        ])
        sheet.append(["Foundations", "2026-11-01", "2026-11-02", 2, "ACT-100", str(w["node"])])
    book.save(path)
    book.close()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    document_id, revision_id = uuid4(), uuid4()
    key = f"synthetic/s7/{revision_id}.xlsx"
    storage[key] = path
    db.add(DocumentORM(
        id=document_id, tenant_id=w["tenant"], project_id=w["project"],
        document_type=DocumentType.BUDGET if family == "budget" else DocumentType.SCHEDULE,
        filename=f"{family}.xlsx", file_format=".xlsx", file_hash=digest,
        created_by=w["actor"],
    ))
    await db.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(DocumentRevisionORM(
        revision_id=revision_id, tenant_id=w["tenant"], project_id=w["project"],
        document_id=document_id, rev_no=1, blob_hash=digest, blob_key=key,
        valid_from=now, created_at=now,
    ))
    # The immutable revision must exist before its FK-bearing trusted artifact.
    await db.flush()
    db.add(DocumentArtifactORM(
        artifact_id=uuid4(), tenant_id=w["tenant"], project_id=w["project"],
        document_id=document_id, document_revision_id=revision_id,
        artifact_version=1, artifact_hash="b" * 64,
        payload={"document_type": family},
        trust_state="trusted", lifecycle_status="active",
    ))
    await db.commit()
    return {
        "family": family,
        "source_document_id": document_id,
        "source_revision_id": revision_id,
        "expected_blob_hash": digest,
        "source_locator": "Sheet!2",
    }


def _args(w: dict, item: dict, **overrides) -> dict:
    payload = dict(
        tenant_id=w["tenant"], project_id=w["project"], actor_user_id=w["actor"],
        expected_wbs_baseline_id=w["baseline"], expected_wbs_node_id=w["node"],
        approval=APPROVAL, idempotency_key=f"s7-{item['family']}-durable-approval",
        reason=f"Human approves exact {item['family']} row on canonical WBS",
        **item,
    )
    payload.update(overrides)
    return payload


async def test_s7_three_families_same_approved_node_persist_and_read_new_session(
    db: AsyncSession, test_session_factory, tmp_path: Path,
) -> None:
    w = await _world(db, tmp_path)
    paths: dict[str, Path] = {}
    budget = await _structured_document(db, w, tmp_path, "budget", paths)
    schedule = await _structured_document(db, w, tmp_path, "schedule", paths)
    reader = ImmutableXLSXRowReader(_SyntheticImmutableStorage(paths), ExcelFileParser())  # type: ignore[arg-type]

    # Technical is not a simulated approval: use the existing, independent
    # audit and final approval writers against the SAME approved baseline/node.
    async with test_session_factory() as session:
        review = await RecordTechnicalWBSReviewService(session, w["reader"]).execute(
            **_arguments(w)
        )
        await session.commit()
    async with test_session_factory() as session:
        technical = await ApproveCanonicalTechnicalWBSLinkService(session).execute(
            tenant_id=w["tenant"], project_id=w["project"], actor_user_id=w["actor"],
            review_event_id=review.event_id,
            expected_wbs_baseline_id=w["baseline"],
            expected_wbs_node_id=w["node"], approval=CANONICAL_APPROVAL,
            idempotency_key="s7-three-family-technical-link",
            reason="Explicit technical requirement approval against approved node",
        )
        await session.commit()

    receipts = {}
    for item in (budget, schedule):
        async with test_session_factory() as session:
            service = ApproveStructuredWBSLinkService(session, reader)
            receipt = await service.execute(**_args(w, item))
            receipts[item["family"]] = receipt.event_id
            assert not receipt.replayed
            await session.commit()
    async with test_session_factory() as observer:
        structured = await ReadStructuredWBSLinksService(observer, reader).list(
            tenant_id=w["tenant"], project_id=w["project"],
        )
        technical_links = await ReadCanonicalTechnicalWBSLinksService(observer).list(
            tenant_id=w["tenant"], project_id=w["project"],
        )
        assert {link.family for link in structured} == {"budget", "schedule"}
        assert all(link.state == "CURRENT" for link in structured)
        assert {link.event_id for link in structured} == set(receipts.values())
        assert all(link.wbs_baseline_id == w["baseline"] for link in structured)
        assert all(link.wbs_node_id == w["node"] for link in structured)
        assert len(technical_links) == 1
        assert technical_links[0].event_id == technical.event_id
        assert technical_links[0].state == "CURRENT"
        assert technical_links[0].wbs_baseline_id == w["baseline"]
        assert technical_links[0].wbs_node_id == w["node"]

    # Identical replay is idempotent; another decision or actor cannot
    # overwrite an approved source row, even if the WBS source tree exists.
    async with test_session_factory() as session:
        service = ApproveStructuredWBSLinkService(session, reader)
        replay = await service.execute(**_args(w, budget))
        assert replay.replayed and replay.event_id == receipts["budget"]
        with pytest.raises(StructuredWBSLinkError, match="already settled"):
            await service.execute(**_args(w, budget, reason="Conflicting approver intent"))
        await session.rollback()

    async with test_session_factory() as session:
        service = ApproveStructuredWBSLinkService(session, reader)
        for args in (
            _args(w, budget, tenant_id=uuid4()),
            _args(w, schedule, actor_user_id=uuid4()),
            _args(w, budget, expected_wbs_baseline_id=uuid4()),
            _args(w, schedule, expected_blob_hash="0" * 64),
        ):
            with pytest.raises((StructuredWBSLinkError, ValueError)):
                await service.execute(**args)
            await session.rollback()

    # A source loses active trust. Its historical event stays durable, but
    # independent GET must not call it CURRENT. The other two remain CURRENT.
    async with test_session_factory() as session:
        artifact = await session.scalar(select(DocumentArtifactORM).where(
            DocumentArtifactORM.document_revision_id == budget["source_revision_id"],
            DocumentArtifactORM.project_id == w["project"],
        ))
        assert artifact is not None
        artifact.trust_state = "superseded"
        artifact.lifecycle_status = "superseded"
        await session.commit()
    async with test_session_factory() as session:
        current = await ReadStructuredWBSLinksService(session, reader).list(
            tenant_id=w["tenant"], project_id=w["project"]
        )
        states = {e.family: e.state for e in current}
        assert states == {"budget": "STALE_SOURCE", "schedule": "CURRENT"}


async def test_s7_structured_row_hash_tampering_fails_closed(
    db: AsyncSession, test_session_factory, tmp_path: Path,
) -> None:
    w = await _world(db, tmp_path)
    paths: dict[str, Path] = {}
    budget = await _structured_document(db, w, tmp_path, "budget", paths)
    reader = ImmutableXLSXRowReader(_SyntheticImmutableStorage(paths), ExcelFileParser())  # type: ignore[arg-type]
    async with test_session_factory() as session:
        first = await ApproveStructuredWBSLinkService(session, reader).execute(
            **_args(w, budget)
        )
        assert not first.replayed
        await session.commit()
    source = next(iter(paths.values()))
    source.write_bytes(source.read_bytes() + b"tampered")
    async with test_session_factory() as session:
        items = await ReadStructuredWBSLinksService(session, reader).list(
            tenant_id=w["tenant"], project_id=w["project"]
        )
        assert len(items) == 1
        assert items[0].state == "UNVERIFIED"
    async with test_session_factory() as session:
        with pytest.raises(ValueError):
            await ApproveStructuredWBSLinkService(session, reader).execute(
                **_args(w, budget)
            )
        await session.rollback()
