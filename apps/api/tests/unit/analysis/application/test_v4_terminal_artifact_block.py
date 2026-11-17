"""V4 G1: a terminated/incomplete graph must never create trusted artifacts."""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.analysis.application import document_artifact_completion as completion


@pytest.mark.parametrize(
    "reason",
    ["classification_unassessed", "insufficient_extractable_text", "Rejected by reviewer"],
)
@pytest.mark.asyncio
async def test_terminal_unassessed_run_cannot_persist_or_enqueue(monkeypatch, reason):
    persist = AsyncMock()
    monkeypatch.setattr(completion, "_persist_artifact", persist)

    await completion.persist_artifact_and_enqueue_project_graph({
        "project_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "document_id": str(uuid4()),
        "workflow_terminated": True,
        "termination_reason": reason,
        "human_approval_required": False,
        "doc_type": "contract",
    })

    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_nonterminal_candidate_still_reaches_persistence_hook(monkeypatch):
    persist = AsyncMock()
    monkeypatch.setattr(completion, "_persist_artifact", persist)

    await completion.persist_artifact_and_enqueue_project_graph({
        "project_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "document_id": str(uuid4()),
        "workflow_terminated": False,
        "human_approval_required": True,
        "doc_type": "contract",
    })

    persist.assert_awaited_once()
