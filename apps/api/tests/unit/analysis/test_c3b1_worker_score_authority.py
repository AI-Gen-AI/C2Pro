"""Worker must not treat provisional artifact scoring as resumed N8 state.

Regression for the P0-D API change: MaterializationContent.from_artifact's
second argument means resumed, source-bound graph state, not candidate.scoring.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.tasks import materialization_tasks as tasks


@pytest.mark.asyncio
async def test_pending_worker_does_not_promote_provisional_scoring_into_n8_state(
    monkeypatch,
) -> None:
    tenant_id, project_id, document_id, artifact_id, analysis_id = (uuid4() for _ in range(5))
    obligation = SimpleNamespace(
        artifact_id=artifact_id,
        document_id=document_id,
        project_id=project_id,
        tenant_id=tenant_id,
        artifact_version=2,
        artifact_hash="a" * 64,
        materialization_state=tasks.materializer.MaterializationState.PENDING,
    )
    approved_payload = {
        "document_id": str(document_id),
        "doc_type": "contract",
        "extracted_risks": [],
        "extracted_wbs": [],
    }
    scoring_from_proposal = {"coherence_score": 60}
    rows = [
        SimpleNamespace(first=lambda: obligation),
        SimpleNamespace(
            first=lambda: SimpleNamespace(
                materialization_state=tasks.materializer.MaterializationState.PENDING
            )
        ),
        SimpleNamespace(
            first=lambda: SimpleNamespace(payload=approved_payload, scoring=scoring_from_proposal)
        ),
    ]
    session = SimpleNamespace(execute=AsyncMock(side_effect=rows))
    monkeypatch.setattr(tasks.materializer, "lock_document", AsyncMock(return_value=True))
    monkeypatch.setattr(tasks.materializer, "lock_project", AsyncMock(return_value=True))

    original = tasks.materializer.MaterializationContent.from_artifact
    observed = {}

    def checked_constructor(payload, resumed_state=None):
        observed["payload"] = payload
        observed["resumed_state"] = resumed_state
        assert resumed_state is None, (
            "Recovery Worker has no validated resumed N8 inputs: the proposal "
            "scoring dict is NOT a source-bound graph state"
        )
        return original(payload)

    monkeypatch.setattr(
        tasks.materializer.MaterializationContent,
        "from_artifact",
        staticmethod(checked_constructor),
    )
    effect = tasks.materializer.MaterializationOutcome(
        status=tasks.materializer.MaterializationStatus.CREATED,
        analysis_id=analysis_id,
    )
    persist = AsyncMock(return_value=effect)
    monkeypatch.setattr(tasks.materializer, "materialize_in_transaction", persist)

    result = await tasks._materialize(session, artifact_id=artifact_id, tenant_id=tenant_id)

    assert result["status"] == tasks.materializer.MaterializationStatus.CREATED.value
    assert observed == {"payload": approved_payload, "resumed_state": None}
    assert persist.await_count == 1
    content = persist.await_args.kwargs["content"]
    assert content.coherence_score is None
    assert content.coherence_reason == "trusted_artifact_score_requires_recalculation"
    assert content.risks == []
