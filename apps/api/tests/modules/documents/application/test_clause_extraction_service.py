"""
Clause Extraction Service (TDD - RED Phase)

Refers to Suite ID: TS-UA-SVC-EXT-001.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.documents.application.services.clause_extraction_service import (
    ClauseExtractionService,
)
from src.documents.domain.models import ClauseType


class TestClauseExtractionService:
    """Refers to Suite ID: TS-UA-SVC-EXT-001."""

    @pytest.mark.asyncio
    async def test_calls_llm_port_and_maps_results(self):
        llm_port = AsyncMock()
        llm_port.extract_clauses.return_value = [
            {
                "clause_code": "1.1",
                "clause_type": "scope",
                "title": "Alcance",
                "content": "El contratista entregara el alcance total.",
                "confidence_score": 0.92,
            }
        ]

        service = ClauseExtractionService(llm_port=llm_port)

        text = "Clausula 1.1: El contratista entregara el alcance total."
        document_id = uuid4()
        project_id = uuid4()
        tenant_id = uuid4()

        clauses = await service.extract_from_text(
            text=text,
            document_id=document_id,
            project_id=project_id,
            tenant_id=tenant_id,
        )

        llm_port.extract_clauses.assert_awaited_once_with(
            text=text,
            document_id=document_id,
            project_id=project_id,
            tenant_id=tenant_id,
        )
        assert clauses[0].clause_code == "1.1"
        assert clauses[0].clause_type == ClauseType.SCOPE
