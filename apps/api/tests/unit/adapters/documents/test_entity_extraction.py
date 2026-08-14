# ruff: noqa: S101
"""
Test Suite: Entity Extraction Additional Tests
Component: Documents Module - Entity Extraction Adapter
Priority: P0

Additional tests to improve entity extraction coverage.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestDocumentsEntityExtractionService:
    """Tests for DocumentsEntityExtractionService."""

    def test_service_initialization(self):
        """Test service initialization with factories."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )

        stakeholder_factory = MagicMock(return_value=MagicMock())
        wbs_factory = MagicMock(return_value=MagicMock())
        bom_factory = MagicMock(return_value=MagicMock())
        user_id = uuid4()

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=stakeholder_factory,
            wbs_use_case_factory=wbs_factory,
            bom_use_case_factory=bom_factory,
            user_id=user_id,
        )

        assert service._user_id == user_id
        assert service._stakeholder_use_case_factory is stakeholder_factory
        assert service._wbs_use_case_factory is wbs_factory
        assert service._bom_use_case_factory is bom_factory

    def test_has_extract_method(self):
        """Test service has extract method."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )

        stakeholder_factory = MagicMock(return_value=MagicMock())
        wbs_factory = MagicMock(return_value=MagicMock())
        bom_factory = MagicMock(return_value=MagicMock())

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=stakeholder_factory,
            wbs_use_case_factory=wbs_factory,
            bom_use_case_factory=bom_factory,
            user_id=uuid4(),
        )

        assert hasattr(service, "extract_entities_from_document")


class TestExtractionServiceIntegration:
    """Integration tests for DocumentsEntityExtractionService methods."""

    @pytest.mark.asyncio
    async def test_extract_entities_contract_document(self):
        """Test extraction for CONTRACT document type extracts stakeholders."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_stakeholder_use_case = MagicMock()
        mock_stakeholder_use_case.execute = AsyncMock()

        mock_stakeholder_factory = MagicMock(return_value=mock_stakeholder_use_case)
        mock_wbs_factory = MagicMock(return_value=MagicMock())
        mock_bom_factory = MagicMock(return_value=MagicMock())

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {
            "text_blocks": [
                {"text": "Contact: john@example.com"},
                {"text": "Contact: jane@example.com"},
            ]
        }

        result = await service.extract_entities_from_document(
            document=doc,
            parsed_payload=parsed_payload,
            tenant_id=uuid4(),
        )

        assert "stakeholders" in result
        assert result["stakeholders"] >= 0

    @pytest.mark.asyncio
    async def test_extract_entities_schedule_document(self):
        """Test extraction for SCHEDULE document type extracts WBS items."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_wbs_use_case = MagicMock()
        mock_wbs_use_case.execute = AsyncMock()

        mock_stakeholder_factory = MagicMock(return_value=MagicMock())
        mock_wbs_factory = MagicMock(return_value=mock_wbs_use_case)
        mock_bom_factory = MagicMock(return_value=MagicMock())

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.SCHEDULE,
            filename="schedule.xlsx",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {"schedule": []}

        result = await service.extract_entities_from_document(
            document=doc,
            parsed_payload=parsed_payload,
            tenant_id=uuid4(),
        )

        assert "wbs_items" in result

    @pytest.mark.asyncio
    async def test_extract_entities_schedule_document_sets_wbs_level_from_code(self):
        """TS-UD-DOC-EXT-001: parsed schedule rows map into valid WBS create payloads."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_wbs_use_case = MagicMock()
        mock_wbs_use_case.replace_for_source_document = AsyncMock(
            side_effect=lambda **kwargs: kwargs["wbs_items"]
        )
        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=MagicMock(return_value=MagicMock()),
            wbs_use_case_factory=MagicMock(return_value=mock_wbs_use_case),
            bom_use_case_factory=MagicMock(return_value=MagicMock()),
            user_id=uuid4(),
        )
        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.SCHEDULE,
            filename="schedule.xlsx",
            upload_status=DocumentStatus.PARSED,
        )

        await service.extract_entities_from_document(
            document=doc,
            parsed_payload={
                "schedule": [
                    {
                        "task": "Firma del contrato",
                        "wbs": "1.1",
                        "start_date": "2024-01-01",
                        "end_date": "2024-01-01",
                    }
                ]
            },
            tenant_id=doc.tenant_id,
        )

        payload = mock_wbs_use_case.replace_for_source_document.await_args.kwargs["wbs_items"][0]
        assert payload.level == 2

    @pytest.mark.asyncio
    async def test_extract_entities_budget_document(self):
        """Test extraction for BUDGET document type extracts BOM items."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_bom_use_case = MagicMock()
        mock_bom_use_case.execute = AsyncMock()

        mock_stakeholder_factory = MagicMock(return_value=MagicMock())
        mock_wbs_factory = MagicMock(return_value=MagicMock())
        mock_bom_factory = MagicMock(return_value=mock_bom_use_case)

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.BUDGET,
            filename="budget.xlsx",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {
            "budget": [
                {"item": "Concrete", "quantity": 10, "unit": "m3", "unit_price": 100, "total": 1000},
            ]
        }

        result = await service.extract_entities_from_document(
            document=doc,
            parsed_payload=parsed_payload,
            tenant_id=uuid4(),
        )

        assert "bom_items" in result

    @pytest.mark.asyncio
    async def test_extract_entities_budget_chapters_format(self):
        """Test extraction for BUDGET with chapters format (BC3)."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_bom_use_case = MagicMock()
        mock_bom_use_case.execute = AsyncMock()

        mock_stakeholder_factory = MagicMock(return_value=MagicMock())
        mock_wbs_factory = MagicMock(return_value=MagicMock())
        mock_bom_factory = MagicMock(return_value=mock_bom_use_case)

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.BUDGET,
            filename="budget.bc3",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {
            "budget": {
                "chapters": [
                    {
                        "code": "01",
                        "units": [
                            {"description": "Excavation", "quantity": 100, "unit": "m3", "price": 15, "total": 1500}
                        ]
                    }
                ]
            }
        }

        result = await service.extract_entities_from_document(
            document=doc,
            parsed_payload=parsed_payload,
            tenant_id=uuid4(),
        )

        assert "bom_items" in result

    @pytest.mark.asyncio
    async def test_extract_stakeholders_no_emails(self):
        """Test stakeholder extraction returns 0 when no emails found."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_stakeholder_factory = MagicMock(return_value=MagicMock())
        mock_wbs_factory = MagicMock(return_value=MagicMock())
        mock_bom_factory = MagicMock(return_value=MagicMock())

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {"text_blocks": [{"text": "No emails here"}]}

        result = await service._extract_stakeholders(doc, parsed_payload, uuid4())

        assert result == 0

    @pytest.mark.asyncio
    async def test_extract_stakeholders_with_exception(self):
        """Test stakeholder extraction handles exceptions gracefully."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock(side_effect=Exception("Duplicate"))

        mock_stakeholder_factory = MagicMock(return_value=mock_use_case)
        mock_wbs_factory = MagicMock(return_value=MagicMock())
        mock_bom_factory = MagicMock(return_value=MagicMock())

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {"text_blocks": [{"text": "test@example.com"}]}

        result = await service._extract_stakeholders(doc, parsed_payload, uuid4())

        assert result == 0

    @pytest.mark.asyncio
    async def test_extract_stakeholders_passes_tenant_id_to_use_case(self):
        """Test stakeholder extraction forwards tenant context to the create use case."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock()

        mock_stakeholder_factory = MagicMock(return_value=mock_use_case)
        mock_wbs_factory = MagicMock(return_value=MagicMock())
        mock_bom_factory = MagicMock(return_value=MagicMock())
        user_id = uuid4()
        tenant_id = uuid4()

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=user_id,
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="contract.pdf",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {"text_blocks": [{"text": "tenant.user@example.com"}]}

        result = await service._extract_stakeholders(doc, parsed_payload, tenant_id)

        assert result == 1
        mock_use_case.execute.assert_awaited_once()
        assert mock_use_case.execute.await_args.kwargs["tenant_id"] == tenant_id
        assert mock_use_case.execute.await_args.kwargs["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_extract_wbs_items_no_schedule(self):
        """Test WBS extraction returns 0 when no schedule data."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_stakeholder_factory = MagicMock(return_value=MagicMock())
        mock_wbs_factory = MagicMock(return_value=MagicMock())
        mock_bom_factory = MagicMock(return_value=MagicMock())

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.SCHEDULE,
            filename="schedule.xlsx",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {}

        result = await service._extract_wbs_items(doc, parsed_payload, uuid4())

        assert result == 0

    @pytest.mark.asyncio
    async def test_extract_wbs_items_with_exception(self):
        """Test WBS extraction handles exceptions gracefully."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_use_case = MagicMock()
        mock_use_case.replace_for_source_document = AsyncMock(side_effect=Exception("DB error"))

        mock_stakeholder_factory = MagicMock(return_value=MagicMock())
        mock_wbs_factory = MagicMock(return_value=mock_use_case)
        mock_bom_factory = MagicMock(return_value=MagicMock())

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.SCHEDULE,
            filename="schedule.xlsx",
            upload_status=DocumentStatus.PARSED,
        )

        # Non-empty schedule so persistence runs and the raised error is handled.
        parsed_payload = {"schedule": [{"task": "Excavation"}]}

        result = await service._extract_wbs_items(doc, parsed_payload, uuid4())

        assert result == 0

    @pytest.mark.asyncio
    async def test_extract_wbs_items_preserves_explicit_predecessor_code(self):
        """TS-IA-COH-SCH-002: parsed schedule dependencies persist as WBS metadata."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_use_case = MagicMock()
        mock_use_case.replace_for_source_document = AsyncMock(
            side_effect=lambda **kwargs: kwargs["wbs_items"]
        )
        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=MagicMock(return_value=MagicMock()),
            wbs_use_case_factory=MagicMock(return_value=mock_use_case),
            bom_use_case_factory=MagicMock(return_value=MagicMock()),
            user_id=uuid4(),
        )
        document = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.SCHEDULE,
            filename="schedule.xlsx",
            upload_status=DocumentStatus.PARSED,
        )

        created = await service._extract_wbs_items(
            document,
            {
                "schedule": [
                    {
                        "task": "Structure",
                        "wbs": "SCH-002",
                        "start_date": "2026-04-01",
                        "end_date": "2026-08-01",
                        "predecessors": "SCH-001",
                        "status": "delayed",
                    }
                ]
            },
            document.tenant_id,
        )

        assert created == 1
        payload = mock_use_case.replace_for_source_document.await_args.kwargs["wbs_items"][0]
        assert payload.wbs_metadata["predecessor_id"] == "SCH-001"
        assert payload.wbs_metadata["status"] == "delayed"

    @pytest.mark.asyncio
    async def test_extract_bom_items_no_budget(self):
        """Test BOM extraction returns 0 when no budget data."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_stakeholder_factory = MagicMock(return_value=MagicMock())
        mock_wbs_factory = MagicMock(return_value=MagicMock())
        mock_bom_factory = MagicMock(return_value=MagicMock())

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.BUDGET,
            filename="budget.xlsx",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {}

        result = await service._extract_bom_items(doc, parsed_payload, uuid4())

        assert result == 0

    @pytest.mark.asyncio
    async def test_extract_bom_items_with_exception(self):
        """Test BOM extraction handles exceptions gracefully."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock(side_effect=Exception("DB error"))

        mock_stakeholder_factory = MagicMock(return_value=MagicMock())
        mock_wbs_factory = MagicMock(return_value=MagicMock())
        mock_bom_factory = MagicMock(return_value=mock_use_case)

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.BUDGET,
            filename="budget.xlsx",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {"budget": [{"item": "Test Item", "quantity": 1}]}

        result = await service._extract_bom_items(doc, parsed_payload, uuid4())

        assert result == 0

    @pytest.mark.asyncio
    async def test_extract_bom_items_skips_invalid_items(self):
        """Test BOM extraction skips items without name or quantity."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            DocumentsEntityExtractionService,
        )
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        mock_use_case = MagicMock()
        mock_use_case.execute = AsyncMock()

        mock_stakeholder_factory = MagicMock(return_value=MagicMock())
        mock_wbs_factory = MagicMock(return_value=MagicMock())
        mock_bom_factory = MagicMock(return_value=mock_use_case)

        service = DocumentsEntityExtractionService(
            stakeholder_use_case_factory=mock_stakeholder_factory,
            wbs_use_case_factory=mock_wbs_factory,
            bom_use_case_factory=mock_bom_factory,
            user_id=uuid4(),
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.BUDGET,
            filename="budget.xlsx",
            upload_status=DocumentStatus.PARSED,
        )

        parsed_payload = {
            "budget": [
                {"item": None, "quantity": None},
                {"item": "", "quantity": 0},
            ]
        }

        result = await service._extract_bom_items(doc, parsed_payload, uuid4())

        assert result == 0


class TestEmailExtraction:
    """Tests for email extraction helper function."""

    def test_extract_emails_single(self):
        """Test extracting single email."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _extract_emails,
        )

        text_blocks = [{"text": "Contact us at test@example.com for more info"}]
        result = _extract_emails(text_blocks)

        assert "test@example.com" in result

    def test_extract_emails_multiple(self):
        """Test extracting multiple emails."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _extract_emails,
        )

        text_blocks = [
            {"text": "Email: test1@example.com"},
            {"text": "Contact: test2@example.com"},
        ]
        result = _extract_emails(text_blocks)

        assert len(result) == 2

    def test_extract_emails_no_match(self):
        """Test extracting emails when none present."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _extract_emails,
        )

        text_blocks = [{"text": "No emails here"}]
        result = _extract_emails(text_blocks)

        assert len(result) == 0

    def test_extract_emails_empty_blocks(self):
        """Test extracting emails from empty blocks."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _extract_emails,
        )

        text_blocks = []
        result = _extract_emails(text_blocks)

        assert len(result) == 0


class TestParseDatetimeValue:
    """Tests for _parse_datetime_value helper."""

    def test_parse_datetime_from_datetime(self):
        """Test passing datetime returns same."""
        from datetime import datetime

        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _parse_datetime_value,
        )

        dt = datetime(2024, 1, 15, 10, 30)
        result = _parse_datetime_value(dt)

        assert result == dt

    def test_parse_datetime_from_string(self):
        """Test parsing ISO format string."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _parse_datetime_value,
        )

        result = _parse_datetime_value("2024-01-15T10:30:00")

        assert result is not None
        assert result.year == 2024

    def test_parse_datetime_invalid_string(self):
        """Test parsing invalid string returns None."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _parse_datetime_value,
        )

        result = _parse_datetime_value("not-a-date")

        assert result is None

    def test_parse_datetime_none(self):
        """Test passing None returns None."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _parse_datetime_value,
        )

        result = _parse_datetime_value(None)

        assert result is None


class TestParseDecimal:
    """Tests for _parse_decimal helper."""

    def test_parse_decimal_from_decimal(self):
        """Test passing Decimal returns same."""
        from decimal import Decimal

        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _parse_decimal,
        )

        value = Decimal("100.50")
        result = _parse_decimal(value)

        assert result == value

    def test_parse_decimal_from_string(self):
        """Test parsing string returns Decimal."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _parse_decimal,
        )

        result = _parse_decimal("100.50")

        assert result is not None
        assert float(result) == pytest.approx(100.50)

    def test_parse_decimal_from_int(self):
        """Test parsing int returns Decimal."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _parse_decimal,
        )

        result = _parse_decimal(100)

        assert result is not None
        assert result == 100

    def test_parse_decimal_invalid(self):
        """Test parsing invalid value returns None."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _parse_decimal,
        )

        result = _parse_decimal("not-a-number")

        assert result is None

    def test_parse_decimal_none(self):
        """Test passing None returns None."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _parse_decimal,
        )

        result = _parse_decimal(None)

        assert result is None


class TestNormalizeNameFromEmail:
    """Tests for _normalize_name_from_email helper."""

    def test_normalize_simple_email(self):
        """Test normalizing simple email."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _normalize_name_from_email,
        )

        result = _normalize_name_from_email("john.doe@example.com")

        assert result == "John Doe"

    def test_normalize_email_with_underscore(self):
        """Test normalizing email with underscore."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _normalize_name_from_email,
        )

        result = _normalize_name_from_email("jane_doe@example.com")

        assert "Jane" in result

    def test_normalize_short_email(self):
        """Test normalizing short email."""
        from src.documents.adapters.extraction.documents_entity_extraction_service import (
            _normalize_name_from_email,
        )

        result = _normalize_name_from_email("ab@example.com")

        assert result == "Ab"


class TestDocumentDomainModel:
    """Tests for Document domain model methods."""

    def test_is_parsed_when_parsed(self):
        """Test is_parsed returns True when status is PARSED."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.PARSED,
        )

        assert doc.is_parsed() is True

    def test_is_parsed_when_not_parsed(self):
        """Test is_parsed returns False when status is not PARSED."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )

        assert doc.is_parsed() is False

    def test_has_error_when_error(self):
        """Test has_error returns True when status is ERROR."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.ERROR,
        )

        assert doc.has_error() is True

    def test_has_error_when_no_error(self):
        """Test has_error returns False when status is not ERROR."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.PARSED,
        )

        assert doc.has_error() is False

    def test_clause_count(self):
        """Test clause_count returns correct count."""
        from src.documents.domain.models import (
            Clause,
            ClauseType,
            Document,
            DocumentStatus,
            DocumentType,
        )

        doc_id = uuid4()
        clause = Clause(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_id=doc_id,
            clause_code="1.0",
            clause_type=ClauseType.SCOPE,
            title="Test",
            full_text="Test clause",
        )
        doc = Document(
            id=doc_id,
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.PARSED,
            clauses=[clause],
        )

        assert doc.clause_count() == 1

    def test_add_clause_success(self):
        """Test add_clause adds clause to document."""
        from src.documents.domain.models import (
            Clause,
            ClauseType,
            Document,
            DocumentStatus,
            DocumentType,
        )

        doc_id = uuid4()
        doc = Document(
            id=doc_id,
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.PARSED,
        )
        clause = Clause(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_id=doc_id,
            clause_code="1.0",
            clause_type=ClauseType.SCOPE,
            title="Test",
            full_text="Test clause",
        )

        doc.add_clause(clause)

        assert len(doc.clauses) == 1

    def test_add_clause_wrong_document_raises(self):
        """Test add_clause raises when clause belongs to different document."""
        from src.documents.domain.models import (
            Clause,
            ClauseType,
            Document,
            DocumentStatus,
            DocumentType,
        )

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.PARSED,
        )
        clause = Clause(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_id=uuid4(),  # Different ID
            clause_code="1.0",
            clause_type=ClauseType.SCOPE,
            title="Test",
            full_text="Test clause",
        )

        with pytest.raises(ValueError) as exc_info:
            doc.add_clause(clause)

        assert "does not belong" in str(exc_info.value)


class TestClauseDomainModel:
    """Tests for Clause domain model methods."""

    def test_is_verified_when_verified(self):
        """Test is_verified returns True when manually verified with timestamp."""
        from datetime import datetime

        from src.documents.domain.models import Clause, ClauseType

        clause = Clause(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_id=uuid4(),
            clause_code="1.0",
            clause_type=ClauseType.SCOPE,
            title="Test",
            full_text="Test clause",
            manually_verified=True,
            verified_at=datetime.now(),
        )

        assert clause.is_verified() is True

    def test_is_verified_when_not_verified(self):
        """Test is_verified returns False when not manually verified."""
        from src.documents.domain.models import Clause, ClauseType

        clause = Clause(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_id=uuid4(),
            clause_code="1.0",
            clause_type=ClauseType.SCOPE,
            title="Test",
            full_text="Test clause",
            manually_verified=False,
        )

        assert clause.is_verified() is False

    def test_needs_verification_critical_type(self):
        """Test needs_verification returns True for critical clause types."""
        from src.documents.domain.models import Clause, ClauseType

        clause = Clause(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_id=uuid4(),
            clause_code="1.0",
            clause_type=ClauseType.PENALTY,
            title="Penalty",
            full_text="Penalty clause",
        )

        assert clause.needs_verification() is True

    def test_needs_verification_non_critical_type(self):
        """Test needs_verification returns False for non-critical types."""
        from src.documents.domain.models import Clause, ClauseType

        clause = Clause(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_id=uuid4(),
            clause_code="1.0",
            clause_type=ClauseType.SCOPE,
            title="Scope",
            full_text="Scope clause",
        )

        assert clause.needs_verification() is False


class TestDocumentTransition:
    """Tests for Document.transition_to method."""

    def test_transition_uploaded_to_queued(self):
        """Test valid transition from UPLOADED to QUEUED."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )

        result = doc.transition_to(DocumentStatus.QUEUED)

        assert result.upload_status == DocumentStatus.QUEUED

    def test_transition_uploaded_to_error(self):
        """Test valid transition from UPLOADED to ERROR."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )

        result = doc.transition_to(DocumentStatus.ERROR)

        assert result.upload_status == DocumentStatus.ERROR

    def test_transition_queued_to_parsing(self):
        """Test valid transition from QUEUED to PARSING."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.QUEUED,
        )

        result = doc.transition_to(DocumentStatus.PARSING)

        assert result.upload_status == DocumentStatus.PARSING

    def test_transition_parsing_to_parsed(self):
        """Test valid transition from PARSING to PARSED."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.PARSING,
        )

        result = doc.transition_to(DocumentStatus.PARSED)

        assert result.upload_status == DocumentStatus.PARSED

    def test_transition_same_status(self):
        """Test transition to same status returns same object."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.PARSED,
        )

        result = doc.transition_to(DocumentStatus.PARSED)

        assert result.upload_status == DocumentStatus.PARSED

    def test_transition_invalid_raises(self):
        """Test invalid transition raises ValueError."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.UPLOADED,
        )

        with pytest.raises(ValueError) as exc_info:
            doc.transition_to(DocumentStatus.PARSED)

        assert "Invalid status transition" in str(exc_info.value)

    def test_transition_from_error_not_allowed(self):
        """Test transition from ERROR is not allowed."""
        from src.documents.domain.models import Document, DocumentStatus, DocumentType

        doc = Document(
            id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.ERROR,
        )

        with pytest.raises(ValueError):
            doc.transition_to(DocumentStatus.PARSED)
