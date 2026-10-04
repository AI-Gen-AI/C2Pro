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
