"""PR-C2: the analysis graph knows the exact revision its processing authority pinned.

The temporal-review seam (N12) and the #714 artifact binding both need the
revision being analysed. It is taken from the #711 processing authority, never
guessed from "the latest upload".
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


class _Orchestrator:
    def __init__(self) -> None:
        self.initial_state: dict[str, Any] | None = None

    async def run(self, initial_state: dict[str, Any], *, thread_id: str) -> dict[str, Any]:
        self.initial_state = initial_state
        return {"analysis_id": None, "human_approval_required": False}


async def _launch(monkeypatch: pytest.MonkeyPatch, authority: Any) -> dict[str, Any]:
    from src.core.tasks import ingestion_tasks

    async def _claim(**_: Any) -> None:
        return None

    monkeypatch.setattr(
        ingestion_tasks.processing_authority, "current_authority", lambda: authority
    )
    monkeypatch.setattr(
        ingestion_tasks.checkpoint_lineage, "analysis_thread_id", lambda **_: "thread-1"
    )
    monkeypatch.setattr(ingestion_tasks, "claim_review_lineage_for_current_attempt", _claim)
    orchestrator = _Orchestrator()
    document = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        document_type=SimpleNamespace(value="contract"),
        filename="c.pdf",
    )
    await ingestion_tasks._run_analysis_graph_best_effort(
        orchestrator=orchestrator,
        document=document,
        parsed_text="text",
        tenant_id=uuid4(),
        document_id=document.id,
    )
    assert orchestrator.initial_state is not None
    return orchestrator.initial_state


async def test_initial_state_carries_the_authority_pinned_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision_id = uuid4()

    state = await _launch(monkeypatch, SimpleNamespace(revision_id=revision_id))

    assert state["document_revision_id"] == str(revision_id)


async def test_no_authority_means_no_revision_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    state = await _launch(monkeypatch, None)

    assert state["document_revision_id"] is None


async def test_document_coverage_is_bound_to_authorized_revision_before_n12(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.tasks import ingestion_tasks
    from src.documents.application.document_coverage import (
        record_revision_document_coverage,
        record_revision_parsed_text_digest,
    )

    tenant, project, document_id, revision_id = (uuid4() for _ in range(4))
    text = "EPC-05: delay damages, source obligations."
    blob_hash = "a" * 64
    metadata: dict[str, Any] = {}
    record_revision_document_coverage(
        metadata,
        revision_id=revision_id, blob_hash=blob_hash,
        parsed_payload={
            "text_blocks": [{"text": text, "page": 1}],
            "document_coverage": {
                "status": "COMPLETE", "origin": "docx_file_parser",
                "limitations": [], "text_coverage_assurance": "verified_full_source_text",
            },
        },
    )
    record_revision_parsed_text_digest(
        metadata, parsed_text=text, revision_id=revision_id
    )
    metadata["parsed_text"] = text
    metadata["parsed_text_revision_id"] = str(revision_id)

    async def no_claim(**_: Any) -> None:
        return None

    monkeypatch.setattr(
        ingestion_tasks.processing_authority,
        "current_authority",
        lambda: SimpleNamespace(revision_id=revision_id),
    )
    monkeypatch.setattr(ingestion_tasks.checkpoint_lineage, "analysis_thread_id", lambda **_: "thread-rev")
    monkeypatch.setattr(ingestion_tasks, "claim_review_lineage_for_current_attempt", no_claim)

    orchestrator = _Orchestrator()
    document = SimpleNamespace(
        id=document_id, tenant_id=tenant, project_id=project,
        document_type=SimpleNamespace(value="contract"),
        filename="fixture.docx", document_metadata=metadata,
    )
    revision = SimpleNamespace(
        revision_id=revision_id, tenant_id=tenant, document_id=document_id,
        project_id=project, blob_hash=blob_hash,
    )

    async def call(bound_revision: Any) -> dict:
        await ingestion_tasks._run_analysis_graph_best_effort(
            orchestrator=orchestrator, document=document, parsed_text=text,
            tenant_id=tenant, document_id=document_id,
            source_revision=bound_revision,
        )
        assert orchestrator.initial_state is not None
        return orchestrator.initial_state

    valid = await call(revision)
    assert valid["n12_source_attestation"]["revision_id"] == str(revision_id)
    assert (await call(None))["n12_source_attestation"] is None
    assert (await call(SimpleNamespace(**{
        **vars(revision), "revision_id": uuid4(),
    })))["n12_source_attestation"] is None

    metadata["document_coverage_by_revision"][str(revision_id)]["status"] = "UNVERIFIED"
    assert (await call(revision))["n12_source_attestation"] is None
