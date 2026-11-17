"""P1 S7: real-PG current-row binding vs a concurrent revision rollover.

Only original synthetic Budget XLSX is used. A second revision is manufactured
solely inside disposable test PostgreSQL to test actual concurrent INSERT; it
does NOT exist in the source corpus or represent an approved document change.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.structured_source_binding import (
    resolve_alert_original_rows,
    revalidate_listed_alert_source_bindings,
)
from src.documents.domain.models import DocumentType
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    TRIPLET_DIR,
    _project,
    _upload_and_ingest,
    worker,  # noqa: F401 - pytest fixture imported from existing harness
)

pytestmark = pytest.mark.asyncio


async def test_new_revision_insert_waits_for_original_source_binding_transaction(
    db: AsyncSession,
    test_session_factory,
    worker,
    test_user,
) -> None:
    project = await _project(db, test_user.tenant_id)
    document, old = await _upload_and_ingest(
        db,
        worker,
        test_user,
        project,
        filename="triplet-budget.xlsx",
        content=(TRIPLET_DIR / "triplet-budget.xlsx").read_bytes(),
        document_type=DocumentType.BUDGET,
    )
    await db.commit()
    source_ref = {
        "family": "budget",
        "document_id": str(document.id),
        "revision_id": str(old.revision_id),
        "source_locator": "Presupuesto!5",
    }
    async with test_session_factory() as reader, test_session_factory() as observer:
        alert = SimpleNamespace(
            alert_metadata={
                "detection_evidence": {"structured_sources": [source_ref.copy()]},
            }
        )
        await resolve_alert_original_rows(
            reader,
            tenant_id=test_user.tenant_id,
            project_id=project,
            payloads=[alert],
        )
        assert alert.alert_metadata["original_row_binding"] == (
            "CURRENT_SOURCE_ROW_RESOLVED_NOT_HITL_APPROVED"
        )
        created = uuid4()
        started = asyncio.Event()

        async def rollover() -> None:
            async with test_session_factory() as writer:
                await writer.execute(text("SET LOCAL lock_timeout = '3000ms'"))
                started.set()
                # A real revision rollover must first close the uniquely-open
                # interval; FOR SHARE on the original revision blocks this.
                await writer.execute(
                    text(
                        "UPDATE document_revisions SET valid_to=clock_timestamp() "
                        "WHERE revision_id=:r AND tenant_id=:t"
                    ),
                    {"r": old.revision_id, "t": test_user.tenant_id},
                )
                await writer.execute(
                    text("""
                    INSERT INTO document_revisions
                    (revision_id, document_id, project_id, tenant_id,
                     rev_no, parent_revision_id, blob_hash, blob_key, valid_from, created_at)
                    SELECT :new_id, document_id, project_id, tenant_id,
                           rev_no + 1, revision_id, blob_hash, blob_key,
                           clock_timestamp(), clock_timestamp()
                      FROM document_revisions WHERE revision_id=:old_id
                """),
                    {"new_id": created, "old_id": old.revision_id},
                )
                await writer.commit()

        running = asyncio.create_task(rollover())
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            await asyncio.sleep(0.15)
            assert not running.done(), (
                "new revision became current while original binding held lock"
            )
            # The alert's source is still the original when its own
            # transaction completes.
            await reader.commit()
            await asyncio.wait_for(running, timeout=5)
        finally:
            if not running.done():
                running.cancel()
                await asyncio.gather(running, return_exceptions=True)
            await reader.rollback()

        # Retired original is *historically* the source of the alert, but can
        # no longer be labelled current after the concurrent rollover.
        stale = SimpleNamespace(
            alert_metadata={
                "detection_evidence": {"structured_sources": [source_ref.copy()]},
            }
        )
        await resolve_alert_original_rows(
            observer,
            tenant_id=test_user.tenant_id,
            project_id=project,
            payloads=[stale],
        )
        assert stale.alert_metadata["original_row_binding"] == "NOT_VERIFIED"
        assert (
            stale.alert_metadata["detection_evidence"]["structured_sources"][0].get("blob_sha256")
            is None
        )
        assert (
            await observer.scalar(
                text("""
            SELECT count(*) FROM document_revisions
             WHERE document_id=:d AND valid_to IS NULL
        """),
                {"d": document.id},
            )
            == 1
        )
        assert (
            await observer.scalar(
                text("""
            SELECT revision_id FROM document_revisions
             WHERE document_id=:d AND valid_to IS NULL
        """),
                {"d": document.id},
            )
            == created
        )
        # The historical record stays immutable but read API marks the
        # recorded "CURRENT" observation stale after a real revision insert.
        listed = SimpleNamespace(
            original_row_binding="CURRENT_SOURCE_ROW_RESOLVED_NOT_HITL_APPROVED",
            detection_evidence=SimpleNamespace(
                structured_sources=[
                    SimpleNamespace(**{**source_ref, "blob_sha256": old.blob_hash}),
                ]
            ),
        )
        await revalidate_listed_alert_source_bindings(
            observer,
            tenant_id=test_user.tenant_id,
            project_id=project,
            alerts=[listed],
        )
        assert listed.original_row_binding == "STALE_SOURCE"
        assert listed.detection_evidence.structured_sources[0].blob_sha256 == old.blob_hash
        await observer.rollback()
