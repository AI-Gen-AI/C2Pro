"""
Trigger analysis orchestration for a parsed document.

Refers to Suite ID: TS-INT-MOD-DOC-001.
"""

from __future__ import annotations

import logging
from typing import Protocol, cast
from uuid import UUID

from src.analysis.ports.orchestrator import AnalysisOrchestrator
from src.core.json_types import JsonDict
from src.core.tenants.types import require_tenant_id
from src.documents.domain.models import Document
from src.documents.ports.document_repository import IDocumentRepository

logger = logging.getLogger(__name__)


class AsyncTaskResult(Protocol):
    id: str | None


class AnalysisTask(Protocol):
    name: str

    def apply_async(self, *, kwargs: dict[str, str], queue: str) -> AsyncTaskResult:
        """Enqueue an async analysis task."""
        ...


class TriggerDocumentAnalysisUseCase:
    """Bridge documents to analysis orchestrator."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        orchestrator: AnalysisOrchestrator | None = None,
        analysis_task: AnalysisTask | None = None,
    ) -> None:
        self._document_repository = document_repository
        self._orchestrator = orchestrator
        self._analysis_task = analysis_task

    def _get_analysis_task(self) -> AnalysisTask:
        if self._analysis_task is not None:
            return self._analysis_task
        from src.core.tasks.ingestion_tasks import process_document_analysis_async

        return cast(AnalysisTask, process_document_analysis_async)

    async def _load_document(
        self,
        *,
        tenant_id: UUID | None,
        document_id: UUID,
    ) -> Document | None:
        if tenant_id is not None:
            return await self._document_repository.get_by_id(
                require_tenant_id(tenant_id), document_id
            )
        return await self._document_repository.get_by_id(document_id)  # type: ignore[call-arg]

    async def execute(
        self, *, document_id: UUID, tenant_id: UUID | None = None
    ) -> JsonDict:
        document = await self._load_document(tenant_id=tenant_id, document_id=document_id)
        if not document:
            raise ValueError("document not found or access denied")

        effective_tenant_id = tenant_id or getattr(document, "tenant_id", None)
        if effective_tenant_id is None:
            effective_tenant_id = await self._document_repository.get_project_tenant_id(
                document.project_id
            )
        if effective_tenant_id is None:
            raise ValueError("tenant_id not available")

        if not document.is_parsed():
            raise ValueError("document must be parsed before analysis")

        parsed_text = document.document_metadata.get("parsed_text") if document.document_metadata else None
        if not isinstance(parsed_text, str) or not parsed_text:
            raise ValueError("parsed_text not available")

        task = self._get_analysis_task()
        async_result = task.apply_async(
            kwargs={
                "tenant_id": str(effective_tenant_id),
                "document_id": str(document_id),
            },
            queue="document_parsing",
        )
        task_id = async_result.id
        logger.info(
            "document_analysis_task_enqueued",
            extra={
                "document_id": str(document_id),
                "tenant_id": str(effective_tenant_id),
                "task_name": task.name,
                "task_id": task_id,
                "queue": "document_parsing",
            },
        )
        return {
            "status": "queued",
            "task_id": task_id,
            "task_name": task.name,
            "queue": "document_parsing",
        }
