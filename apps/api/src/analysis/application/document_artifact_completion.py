"""Tier-1 completion hook for ADR-017 DocumentArtifact hand-off.

TS-UT-ADR017-TRG-001
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
from src.core.database import get_raw_session, init_db
from src.core.tasks.project_graph_tasks import enqueue_project_graph
from src.core.tenants.types import require_tenant_id

logger = logging.getLogger(__name__)


async def _persist_artifact(final_state: Mapping[str, Any]) -> None:
    project_id = UUID(str(final_state["project_id"]))
    tenant_id = require_tenant_id(str(final_state["tenant_id"]))
    artifact = build_document_artifact(final_state)
    await init_db()
    async with get_raw_session() as session:
        try:
            await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
            await SqlAlchemyDocumentArtifactRepository(session).save(
                artifact,
                project_id=project_id,
                tenant_id=tenant_id,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
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
