"""
TS-INT-DOC-PROC-003: Ingestion-to-analysis trigger integration contract tests.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.documents.domain.models import Document, DocumentStatus, DocumentType


def _make_document() -> Document:
    return Document(
        id=uuid4(),
        project_id=uuid4(),
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        upload_status=DocumentStatus.QUEUED,
        created_by=uuid4(),
        document_metadata={},
    )


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session


class TestDocumentStatusEnumExtension:
    """Test new DocumentStatus enum values for analysis flow."""

    def test_parsed_pending_analysis_status_exists(self):
        assert hasattr(DocumentStatus, "PARSED_PENDING_ANALYSIS")
        assert DocumentStatus.PARSED_PENDING_ANALYSIS.value == "parsed_pending_analysis"

    def test_analyzed_status_exists(self):
        assert hasattr(DocumentStatus, "ANALYZED")
        assert DocumentStatus.ANALYZED.value == "analyzed"


class TestIngestionSetsParsedPendingAnalysis:
    """Test ingestion task sets document to PARSED_PENDING_ANALYSIS."""

    @pytest.mark.asyncio
    async def test_successful_ingestion_sets_parsed_pending_analysis(self):
        from src.core.tasks.ingestion_tasks import _process

        document_id = uuid4()
        tenant_id = uuid4()
        document = _make_document()
        parsed_payload = SimpleNamespace(raw_text="parsed contract text")

        with ExitStack() as stack:
            stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.init_db", new=AsyncMock())
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.get_raw_session",
                    return_value=_make_session(),
                )
            )
            mock_repo = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRepository")
            )
            mock_extraction_service = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.DocumentsEntityExtractionService")
            )
            mock_rag_service = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.SqlAlchemyRagIngestionService")
            )
            mock_trigger = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.TriggerDocumentAnalysisUseCase")
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.storage.download_file",
                    new=AsyncMock(return_value=Path("contract.pdf")),
                )
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.file_parser.parse_document_file",
                    new=AsyncMock(return_value=parsed_payload),
                )
            )

            mock_repo_instance = mock_repo.return_value
            mock_repo_instance.get_by_id = AsyncMock(return_value=document)
            mock_repo_instance.get_project_tenant_id = AsyncMock(return_value=tenant_id)
            mock_repo_instance.update_status = AsyncMock()
            mock_extraction_service.return_value.extract_entities_from_document = AsyncMock(
                return_value={"stakeholders": 1}
            )
            mock_rag_service.return_value.ingest_document_chunks = AsyncMock()
            mock_trigger.return_value.execute = AsyncMock(return_value={"status": "started"})

            await _process(document_id)

        mock_repo_instance.update_status.assert_any_call(
            document_id,
            DocumentStatus.PARSED_PENDING_ANALYSIS,
        )


class TestAnalysisTriggerAfterIngestion:
    """Test that TriggerDocumentAnalysisUseCase is called after ingestion."""

    @pytest.mark.asyncio
    async def test_ingestion_success_triggers_analysis(self):
        from src.core.tasks.ingestion_tasks import _process

        document_id = uuid4()
        tenant_id = uuid4()
        document = _make_document()
        parsed_payload = SimpleNamespace(raw_text="parsed contract text")

        with ExitStack() as stack:
            stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.init_db", new=AsyncMock())
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.get_raw_session",
                    return_value=_make_session(),
                )
            )
            mock_repo = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRepository")
            )
            mock_extraction_service = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.DocumentsEntityExtractionService")
            )
            mock_rag_service = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.SqlAlchemyRagIngestionService")
            )
            mock_trigger = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.TriggerDocumentAnalysisUseCase")
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.storage.download_file",
                    new=AsyncMock(return_value=Path("contract.pdf")),
                )
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.file_parser.parse_document_file",
                    new=AsyncMock(return_value=parsed_payload),
                )
            )

            mock_repo_instance = mock_repo.return_value
            mock_repo_instance.get_by_id = AsyncMock(return_value=document)
            mock_repo_instance.get_project_tenant_id = AsyncMock(return_value=tenant_id)
            mock_repo_instance.update_status = AsyncMock()
            mock_extraction_service.return_value.extract_entities_from_document = AsyncMock(
                return_value={}
            )
            mock_rag_service.return_value.ingest_document_chunks = AsyncMock()
            mock_trigger_instance = mock_trigger.return_value
            mock_trigger_instance.execute = AsyncMock(return_value={"status": "started"})

            await _process(document_id)

        mock_trigger_instance.execute.assert_called_once_with(document_id=document_id)

    @pytest.mark.asyncio
    async def test_ingestion_failure_does_not_trigger_analysis(self):
        from src.core.tasks.ingestion_tasks import _process

        document_id = uuid4()
        tenant_id = uuid4()
        document = _make_document()

        with ExitStack() as stack:
            stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.init_db", new=AsyncMock())
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.get_raw_session",
                    return_value=_make_session(),
                )
            )
            mock_repo = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRepository")
            )
            mock_trigger = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.TriggerDocumentAnalysisUseCase")
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.storage.download_file",
                    new=AsyncMock(return_value=Path("contract.pdf")),
                )
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.file_parser.parse_document_file",
                    new=AsyncMock(side_effect=ValueError("Parse failed")),
                )
            )

            mock_repo_instance = mock_repo.return_value
            mock_repo_instance.get_by_id = AsyncMock(return_value=document)
            mock_repo_instance.get_project_tenant_id = AsyncMock(return_value=tenant_id)
            mock_repo_instance.update_status = AsyncMock()
            mock_trigger.return_value.execute = AsyncMock()

            with pytest.raises(ValueError):
                await _process(document_id)

        mock_trigger.return_value.execute.assert_not_called()


class TestAnalysisTriggerErrorHandling:
    """Test that analysis trigger failures don't rollback ingestion."""

    @pytest.mark.asyncio
    async def test_analysis_trigger_failure_keeps_parsed_pending_analysis(self):
        from src.core.tasks.ingestion_tasks import _process

        document_id = uuid4()
        tenant_id = uuid4()
        document = _make_document()
        parsed_payload = SimpleNamespace(raw_text="parsed contract text")

        with ExitStack() as stack:
            stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.init_db", new=AsyncMock())
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.get_raw_session",
                    return_value=_make_session(),
                )
            )
            mock_repo = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRepository")
            )
            mock_extraction_service = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.DocumentsEntityExtractionService")
            )
            mock_rag_service = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.SqlAlchemyRagIngestionService")
            )
            mock_trigger = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.TriggerDocumentAnalysisUseCase")
            )
            mock_dlq_service = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.DLQService")
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.storage.download_file",
                    new=AsyncMock(return_value=Path("contract.pdf")),
                )
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.file_parser.parse_document_file",
                    new=AsyncMock(return_value=parsed_payload),
                )
            )

            mock_repo_instance = mock_repo.return_value
            mock_repo_instance.get_by_id = AsyncMock(return_value=document)
            mock_repo_instance.get_project_tenant_id = AsyncMock(return_value=tenant_id)
            mock_repo_instance.update_status = AsyncMock()
            mock_extraction_service.return_value.extract_entities_from_document = AsyncMock(
                return_value={}
            )
            mock_rag_service.return_value.ingest_document_chunks = AsyncMock()
            mock_trigger.return_value.execute = AsyncMock(
                side_effect=Exception("Analysis orchestrator unavailable")
            )
            mock_dlq_service.return_value.push = AsyncMock()

            result = await _process(document_id)

        assert result["status"] == "success"
        mock_repo_instance.update_status.assert_any_call(
            document_id,
            DocumentStatus.PARSED_PENDING_ANALYSIS,
        )

    @pytest.mark.asyncio
    async def test_analysis_trigger_failure_pushes_to_dlq(self):
        from src.core.tasks.ingestion_tasks import _process

        document_id = uuid4()
        tenant_id = uuid4()
        document = _make_document()
        parsed_payload = SimpleNamespace(raw_text="parsed contract text")

        with ExitStack() as stack:
            stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.init_db", new=AsyncMock())
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.get_raw_session",
                    return_value=_make_session(),
                )
            )
            mock_repo = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.SqlAlchemyDocumentRepository")
            )
            mock_extraction_service = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.DocumentsEntityExtractionService")
            )
            mock_rag_service = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.SqlAlchemyRagIngestionService")
            )
            mock_trigger = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.TriggerDocumentAnalysisUseCase")
            )
            mock_dlq_task = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.handle_failed_task")
            )
            mock_dlq_service = stack.enter_context(
                patch("src.core.tasks.ingestion_tasks.DLQService")
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.storage.download_file",
                    new=AsyncMock(return_value=Path("contract.pdf")),
                )
            )
            stack.enter_context(
                patch(
                    "src.core.tasks.ingestion_tasks.file_parser.parse_document_file",
                    new=AsyncMock(return_value=parsed_payload),
                )
            )

            mock_repo_instance = mock_repo.return_value
            mock_repo_instance.get_by_id = AsyncMock(return_value=document)
            mock_repo_instance.get_project_tenant_id = AsyncMock(return_value=tenant_id)
            mock_repo_instance.update_status = AsyncMock()
            mock_extraction_service.return_value.extract_entities_from_document = AsyncMock(
                return_value={}
            )
            mock_rag_service.return_value.ingest_document_chunks = AsyncMock()
            mock_trigger.return_value.execute = AsyncMock(
                side_effect=Exception("Orchestrator down")
            )
            mock_dlq_service.return_value.push = AsyncMock()

            await _process(document_id)

        mock_dlq_task.apply_async.assert_called_once()
