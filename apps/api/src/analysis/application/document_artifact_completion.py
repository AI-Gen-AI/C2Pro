"""Tier-1 completion hook for ADR-017 DocumentArtifact hand-off.

TS-UT-ADR017-TRG-001

#714 trust boundary: a HITL-gated run (``human_approval_required=True``)
persists its artifact as a PROPOSED candidate bound to its review and does
NOT enqueue the canonical ProjectGraph. Only a non-gated completion, or the
approval of the exact bound candidate (see ``finalize_v3``), is canonical.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import text

from src.analysis.adapters.graph.document_artifact_builder import build_document_artifact
from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.domain.trust import CandidateScoring, TrustState
from src.core.database import get_raw_session, init_db
from src.core.processing_authority import fence_current
from src.core.tasks.project_graph_tasks import enqueue_project_graph
from src.core.tenants.types import require_tenant_id

logger = logging.getLogger(__name__)


def _requires_human_approval(final_state: Mapping[str, Any]) -> bool:
    # Fail closed: anything but an explicit False keeps the output untrusted.
    return final_state.get("human_approval_required") is not False


async def _persist_artifact(final_state: Mapping[str, Any]) -> None:
    project_id = UUID(str(final_state["project_id"]))
    tenant_id = require_tenant_id(str(final_state["tenant_id"]))
    artifact = build_document_artifact(final_state)
    gated = _requires_human_approval(final_state)
    trust_state = TrustState.PROPOSED if gated else TrustState.TRUSTED
    thread_id = final_state.get("thread_id")
    await init_db()
    async with get_raw_session() as session:
        try:
            await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
            # #711: the artifact commits only for the current processing owner.
            await fence_current(session)
            await SqlAlchemyDocumentArtifactRepository(session).save(
                artifact,
                project_id=project_id,
                tenant_id=tenant_id,
                trust_state=trust_state,
                scoring=CandidateScoring.from_state(final_state),
                review_thread_id=str(thread_id) if gated and thread_id else None,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    if gated:
        logger.info(
            "document_artifact_candidate_proposed",
            extra={"project_id": str(project_id), "document_id": str(final_state.get("document_id"))},
        )
        return
    await enqueue_project_graph(project_id=project_id, tenant_id=tenant_id)


async def persist_artifact_and_enqueue_project_graph(final_state: Mapping[str, Any]) -> None:
    """Persist the Tier-1 artifact and enqueue Tier-2 without breaking Tier-1."""

    try:
        if not final_state.get("project_id") or not final_state.get("tenant_id"):
            logger.warning("document_artifact_completion_missing_identity")
            return
        await _persist_artifact(final_state)
    except Exception:
        logger.exception(
            "document_artifact_completion_failed",
            extra={
                "project_id": str(final_state.get("project_id")),
                "tenant_id": str(final_state.get("tenant_id")),
                "document_id": str(final_state.get("document_id")),
            },
        )


__all__ = ["persist_artifact_and_enqueue_project_graph"]
